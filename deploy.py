# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http:# mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import hashlib

from boto.s3 import connect_to_region
from jx_python import jx
from mo_dots import unwrap, Data, wrap, set_default
from mo_files import File, join_path
from mo_future import text_type
from mo_json import value2json, json2value
from mo_logs import startup, constants, Log
from mo_logs.strings import quote
from mo_threads import Process

DEBUG = True
CHUNK_SIZE = 8388608  # BE SURE THIS IS BOTO'S multipart_chunksize https://boto3.readthedocs.io/en/latest/reference/customizations/s3.html#boto3.s3.transfer.TransferConfig


def md5(source, chunk_size=CHUNK_SIZE):
    md5s = []
    for g, data in jx.groupby(source.read_bytes(), size=chunk_size):
        md5s.append(hashlib.md5(data).digest())

    if len(md5s) == 0:
        return '"d41d8cd98f00b204e9800998ecf8427e"'
    elif len(md5s) == 1:
        return quote(md5s[0].encode("hex"))
    else:
        Log.warning("not known to work")
        new_md5 = hashlib.md5(b"".join(md5s))
        return text_type(new_md5.hexdigest()+b"-"+str(text_type(len(md5s))))


def _synch(config):
    main_dir = File(config.source)
    build_directory = main_dir / "build"

    Log.note("update homepage")
    package_json = File(main_dir) / "package.json"
    old_package = package_json.read()
    new_package = set_default({}, config.package, json2value(old_package, leaves=False))
    package_json.write(value2json(new_package, pretty=True))

    try:
        p = Process(
            "install",
            ["yarn", "install"],
            env={str(k): str(v) for k, v in config.env.items()},
            cwd=main_dir,
            shell=True,
            debug=True
        )
        p.join()
        p = Process(
            "build",
            ["yarn", "build"],
            env={str(k): str(v) for k, v in config.env.items()},
            cwd=main_dir,
            shell=True,
            debug=True
        )
        p.join()
    finally:
        # RESTORE package.json
        Log.note("restore homepage")
        package_json.write(old_package)

    config.destination.directory = config.destination.directory.strip("/")
    try:
        connection = connect_to_region(
            region_name=config.destination.region,
            calling_format="boto.s3.connection.OrdinaryCallingFormat",
            aws_access_key_id=unwrap(config.destination.aws_access_key_id),
            aws_secret_access_key=unwrap(config.destination.aws_secret_access_key)
        )
        bucket = connection.get_bucket(config.destination.bucket)
    except Exception as e:
        Log.error("Problem connecting to {{bucket}}", bucket=config.destination.bucket, cause=e)

    remote_prefix = config.destination.directory.strip('/') + "/"
    listing = bucket.list(prefix=remote_prefix)
    metas = {m.key[len(remote_prefix):]: Data(key=m.key, etag=m.etag) for m in listing}
    net_new = []

    Log.note("Look for differences")
    for local_file in build_directory.leaves:
        local_rel_file = local_file.abspath[len(build_directory.abspath):].lstrip(b'/')
        if "/." in local_rel_file or local_rel_file.startswith("."):
            continue
        remote_file = wrap(metas.get(local_rel_file))
        Log.note("remote = {{etag}}, local={{md5}}", etag=remote_file.etag, md5=md5(local_file))
        if not config.force and remote_file:
            if remote_file.etag != md5(local_file):
                net_new.append(local_file)
        else:
            net_new.append(local_file)

    # SEND DIFFERENCES
    for n in net_new:
        remote_file = join_path(config.destination.directory, n.abspath[len(build_directory.abspath):])
        try:
            Log.note("upload {{file}} ({{type}})", file=remote_file, type=n.mime_type)
            storage = bucket.new_key(remote_file)
            storage.content_type = n.mime_type
            storage.set_contents_from_string(n.read_bytes())
            storage.set_acl('public-read')
        except Exception as e:
            Log.warning("can not upload {{file}} ({{type}})", file=remote_file, type=n.mime_type, cause=e)


def progress(num, total):
    Log.note("Upload {{num}} of {{total}}", num=num, total=total)


def main():
    settings = startup.read_settings()
    Log.start(settings.debug)
    constants.set(settings.constants)

    try:
        _synch(settings)
    except Exception as e:
        Log.error("Problem with synch", e)
    finally:
        Log.stop()


if __name__ == "__main__":
    main()

