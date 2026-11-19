"""Slim, read-only serving app for the Vercel function.

Kept outside ``api/`` so Vercel's Python runtime does not compile it as a second
function; only ``api/index.py`` is a function entry point.
"""

from serverless.app import app  # noqa: F401

__all__ = ["app"]
