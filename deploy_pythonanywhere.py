#!/usr/bin/env python3
"""Deploy the Flask app to PythonAnywhere via the REST API."""

import os
import sys
import requests
import zipfile
import io

API_BASE = "https://www.pythonanywhere.com/api/v0/user"

FILES = [
    "app.py",
    "wsgi.py",
    "requirements.txt",
    "templates/index.html",
    "templates/admin.html",
    "templates/admin_login.html",
    "static/css/style.css",
    "static/js/main.js",
    "static/img/project-api-auth.svg",
    "static/img/project-cicd.svg",
    "static/img/project-iac.svg",
    "static/img/project-microservices.svg",
    "static/img/project-monitoring.svg",
    "static/img/project-security.svg",
]


def main():
    token = os.environ.get("PA_API_TOKEN")
    username = os.environ.get("PA_USERNAME")
    domain = os.environ.get("PA_DOMAIN")
    remote_dir = os.environ.get("PA_REMOTE_DIR", "/home/{}/portfolio".format(username))

    missing = [k for k, v in [("PA_API_TOKEN", token), ("PA_USERNAME", username), ("PA_DOMAIN", domain)] if not v]
    if missing:
        sys.exit("Missing required secrets: " + ", ".join(missing))

    headers = {"Authorization": "Token {}".format(token)}

    # 1. Upload code files
    for rel in FILES:
        with open(rel, "rb") as fh:
            data = fh.read()
        url = "{}/{}/files/path{}".format(API_BASE, username, remote_dir + "/" + rel)
        r = requests.post(url, headers=headers, files={"content": data})
        print("Upload {} -> {}".format(rel, r.status_code))
        if r.status_code not in (200, 201):
            print(r.text)
            sys.exit(1)

    # 2. Reload the web app
    reload_url = "{}/{}/webapps/{}/reload/".format(API_BASE, username, domain)
    r = requests.post(reload_url, headers=headers)
    print("Reload {} -> {}".format(domain, r.status_code))
    if r.status_code != 200:
        print(r.text)
        sys.exit(1)

    print("Deployment complete.")


if __name__ == "__main__":
    main()
