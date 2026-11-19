"""Vercel serverless entry point.

Adds the repository root to ``sys.path`` so that ``serverless.app`` can be imported
without the full package install path, then re-exports the FastAPI ``app`` object that
Vercel's Python runtime expects at the module level.

The function configuration in ``vercel.json`` points Vercel at this file:
  ``"functions": {"api/index.py": {"includeFiles": [...], ...}}``
"""

from __future__ import annotations

import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from serverless.app import app  # noqa: E402  re-exported for Vercel

__all__ = ["app"]
