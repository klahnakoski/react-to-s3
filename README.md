# react-to-s3
Simple script that will build-and-copy React app to S3



### Example config file

```json
{
    "package": { 
        "homepage": "https://charts.mozilla.org/coverage"
    },
    "env": { 
        "ROUTING": "hashHistory"
    },
    "source": "C:/Users/kyle/code/firefox-code-coverage-frontend",
    "destination": {
        "bucket": "charts.mozilla.org",
        "directory": "/coverage",
        "$ref": "file://~/private.json#aws_credentials"
    },
    "debug": {
        "trace": true
    }
}

```

* **package** - replaces properties found in the `package.json` file
* **env** - additional environment variables added during `install` and `build` commands 
* **source** - path to (local) react application directory
* **destination** - Which S3 bucket to place data
* **debug** - [see documentation](https://github.com/klahnakoski/mo-logs#configuration)

