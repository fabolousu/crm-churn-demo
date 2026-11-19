#!/usr/bin/env python3
"""Validate a deployment URL before a bypass secret is attached.

Rules:
- HTTPS only; no credentials, query string or fragment.
- The canonical production host is accepted directly.
- A preview host must match this project's Vercel hostname shape *and* be confirmed
  against the Vercel API as belonging to this project (``projectId``), so a matching
  hostname pattern alone is not treated as proof of ownership.

Set ``VERCEL_TOKEN`` for preview validation. Prints the parsed hostname on success.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

PROJECT_ID = "prj_bIOTXnHFIIEMAyejsDV65oJldtrn"
PROJECT_HOST = "crm-churn-demo.vercel.app"
PREVIEW_PREFIX = "crm-churn-demo-"
PREVIEW_SUFFIX = "-promos6.vercel.app"
VERCEL_API = "https://api.vercel.com/v13/deployments/"


def _project_owns(host: str) -> bool:
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        return False
    request = urllib.request.Request(
        VERCEL_API + urllib.parse.quote(host, safe=""),
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except Exception:
        return False
    return payload.get("projectId") == PROJECT_ID


def validate(raw: str) -> str | None:
    parsed = urllib.parse.urlsplit(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    if parsed.query or parsed.fragment:
        return None
    if host == PROJECT_HOST:
        return host
    if not (host.startswith(PREVIEW_PREFIX) and host.endswith(PREVIEW_SUFFIX)):
        return None
    return host if _project_owns(host) else None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_deployment_url.py <url>", file=sys.stderr)
        return 2
    host = validate(argv[1])
    if host is None:
        return 1
    print(host)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
