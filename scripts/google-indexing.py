#!/usr/bin/env python3
"""
Submit all URLs from a sitemap to Google's Indexing API.

Prerequisites:
  1. Google Cloud project with Indexing API enabled
  2. Service account JSON key file
  3. Service account email added as Owner in Google Search Console
  4. pip install google-auth requests

Usage:
  python3 scripts/google-indexing.py                                          # submit all from default sitemap
  python3 scripts/google-indexing.py --sitemap https://example.com/sitemap.xml
  python3 scripts/google-indexing.py --urls https://example.com/page1 https://example.com/page2
  python3 scripts/google-indexing.py --status https://example.com/page1       # check indexing status
  GOOGLE_SERVICE_ACCOUNT_KEY=/path/to/key.json python3 scripts/google-indexing.py
"""

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/indexing"]
PUBLISH_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
METADATA_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications/metadata"

DEFAULT_SITEMAP = "https://terminalskills.io/sitemap.xml"
DEFAULT_KEY_PATH = os.path.expanduser("~/Documents/google-key-1.json")


def get_credentials_path():
    return os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY", DEFAULT_KEY_PATH)


def get_auth_session(credentials_file):
    credentials = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=SCOPES
    )
    credentials.refresh(GoogleAuthRequest())
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {credentials.token}"})
    return session


def submit_url(session, url, action="URL_UPDATED"):
    body = {"url": url, "type": action}
    response = session.post(PUBLISH_ENDPOINT, json=body)
    return response.status_code, response.json()


def check_status(session, url):
    response = session.get(METADATA_ENDPOINT, params={"url": url})
    return response.status_code, response.json()


def parse_sitemap(sitemap_url):
    response = requests.get(sitemap_url, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    sitemap_tags = root.findall("ns:sitemap/ns:loc", ns)
    if sitemap_tags:
        urls = []
        for sitemap_loc in sitemap_tags:
            print(f"  Parsing child sitemap: {sitemap_loc.text}")
            urls.extend(parse_sitemap(sitemap_loc.text))
        return urls

    return [loc.text for loc in root.findall("ns:url/ns:loc", ns)]


def cmd_submit(args):
    key_path = get_credentials_path()
    if not os.path.exists(key_path):
        print(f"Error: Service account key not found at {key_path}")
        print("Set GOOGLE_SERVICE_ACCOUNT_KEY env var or place key at default path.")
        sys.exit(1)

    if args.urls:
        urls = args.urls
        print(f"Submitting {len(urls)} URL(s)\n")
    else:
        sitemap = args.sitemap or DEFAULT_SITEMAP
        print(f"Parsing sitemap: {sitemap}")
        urls = parse_sitemap(sitemap)
        print(f"Found {len(urls)} URLs\n")

    session = get_auth_session(key_path)
    success = 0
    failed = 0
    errors = []

    for i, url in enumerate(urls, 1):
        status, response = submit_url(session, url)
        if status == 200:
            success += 1
            print(f"[{i:3d}/{len(urls)}] OK    {url}")
        else:
            failed += 1
            error_msg = response.get("error", {}).get("message", "Unknown error")
            errors.append({"url": url, "status": status, "error": error_msg})
            print(f"[{i:3d}/{len(urls)}] FAIL  {url} — {error_msg}")
        if i < len(urls):
            time.sleep(args.delay)

    print(f"\nDone: {success} submitted, {failed} failed out of {len(urls)} total")
    if errors:
        print("\nFailed URLs:")
        for err in errors:
            print(f"  {err['url']} — {err['status']} {err['error']}")

    return 0 if failed == 0 else 1


def cmd_status(args):
    key_path = get_credentials_path()
    if not os.path.exists(key_path):
        print(f"Error: Service account key not found at {key_path}")
        sys.exit(1)

    session = get_auth_session(key_path)
    for url in args.status:
        status_code, data = check_status(session, url)
        if status_code == 200:
            notify = data.get("latestUpdate", {})
            print(f"URL:           {data.get('url')}")
            print(f"Last notified: {notify.get('notifyTime', 'never')}")
            print(f"Type:          {notify.get('type', 'n/a')}")
        elif status_code == 404:
            print(f"URL not in notification history: {url}")
        else:
            err = data.get("error", {}).get("message", "Unknown error")
            print(f"Error ({status_code}): {err}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Submit URLs to Google Indexing API"
    )
    parser.add_argument(
        "--sitemap", help=f"Sitemap URL to parse (default: {DEFAULT_SITEMAP})"
    )
    parser.add_argument(
        "--urls", nargs="+", help="Specific URLs to submit"
    )
    parser.add_argument(
        "--status", nargs="+", help="Check indexing status for URLs"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )

    args = parser.parse_args()

    if args.status:
        cmd_status(args)
    else:
        sys.exit(cmd_submit(args))


if __name__ == "__main__":
    main()
