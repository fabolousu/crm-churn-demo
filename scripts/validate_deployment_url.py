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


def _project_owns(host: str) -> bool | None:
    """True/False for ownership, None when the check itself could not run."""
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        return None
    request = urllib.request.Request(
        VERCEL_API + urllib.parse.quote(host, safe=""),
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except Exception:
        return None
    return payload.get("projectId") == PROJECT_ID


def validate(raw: str) -> tuple[int, str | None]:
    """Return (exit_code, host). 0 allowed, 1 unrelated/unapproved, 2 verification failed."""
    parsed = urllib.parse.urlsplit(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return 1, None
    if parsed.query or parsed.fragment:
        return 1, None
    if host == PROJECT_HOST:
        return 0, host
    if not (host.startswith(PREVIEW_PREFIX) and host.endswith(PREVIEW_SUFFIX)):
        return 1, None
    owned = _project_owns(host)
    if owned is None:
        return 2, None
    return (0, host) if owned else (1, None)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_deployment_url.py <url>", file=sys.stderr)
        return 2
    code, host = validate(argv[1])
    if code == 0 and host is not None:
        print(host)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
