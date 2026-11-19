#!/usr/bin/env python3
"""Validate a deployment URL before a bypass secret is attached.

Accepts only HTTPS URLs for this project's own Vercel hosts, with no credentials,
query string or fragment (any of which could redirect the request elsewhere while
still matching a naive hostname check). Prints the parsed hostname on success.
"""

from __future__ import annotations

import sys
import urllib.parse

PROJECT_HOST = "crm-churn-demo.vercel.app"
PREVIEW_SUFFIX = "-promos6.vercel.app"
PREVIEW_PREFIX = "crm-churn-demo-"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_deployment_url.py <url>", file=sys.stderr)
        return 2
    parsed = urllib.parse.urlsplit(argv[1])
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return 1
    if parsed.query or parsed.fragment:
        return 1
    allowed = host == PROJECT_HOST or (
        host.startswith(PREVIEW_PREFIX) and host.endswith(PREVIEW_SUFFIX)
    )
    if not allowed:
        return 1
    print(host)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
