"""Idempotent CRM-schema migration runner.

Policy (T12 brief):

* Stdlib only (``sqlite3``, ``pathlib``, ``argparse``) — no FastAPI import.
* ``apply_migrations(db_path)`` applies ``data/crm_schema.sql`` exactly once per
  database, tracked in ``crm_schema_migrations(version, applied_at)``.
* A second call is a no-op.  The DDL itself uses ``CREATE TABLE IF NOT EXISTS``
  as a defensive belt, but the ``crm_schema_migrations`` row is the authority.
* The CLI accepts ``--db <path>`` (default ``data/demo.db``), exits ``0`` on
  success and ``1`` on failure, printing exactly what it did.  It must work on
  a database created from ``data/schema.sql`` and on an empty database.
* The CLI is deliberately NOT run against ``data/demo.db`` during development;
  tests use ``tmp_path``.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

# Version string of the migration this module knows about.  Bump only when the
# DDL shipping alongside this file changes shape.
CRM_SCHEMA_VERSION = "2026-11-19_crm_b1"

# Resolve the DDL path relative to this file so the runner works regardless of
# the caller's current working directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
CRM_SCHEMA_SQL_PATH = _REPO_ROOT / "data" / "crm_schema.sql"


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp, matching the convention in data/schema.sql rows."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _already_applied(connection: sqlite3.Connection, version: str) -> bool:
    """Return True when the given version is recorded in crm_schema_migrations.

    The tracking table may not exist yet on a first run; its absence counts as
    'not applied'.
    """
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='crm_schema_migrations'"
    ).fetchone()
    if row is None:
        return False
    hit = connection.execute(
        "SELECT 1 FROM crm_schema_migrations WHERE version = ?", (version,)
    ).fetchone()
    return hit is not None


def apply_migrations(
    db_path: Path | str,
    *,
    schema_sql_path: Path | str | None = None,
    version: str = CRM_SCHEMA_VERSION,
) -> Tuple[bool, str]:
    """Apply the CRM DDL to ``db_path`` exactly once.

    Returns ``(applied, message)``:

    * ``applied=True`` means the DDL ran during this call and a tracking row
      was written.
    * ``applied=False`` means the version was already present; nothing was
      changed.

    ``message`` is a one-line description suitable for CLI output.
    """
    db_path = Path(db_path)
    sql_path = Path(schema_sql_path) if schema_sql_path else CRM_SCHEMA_SQL_PATH
    if not sql_path.is_file():
        raise FileNotFoundError(f"CRM schema SQL not found: {sql_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    ddl = sql_path.read_text(encoding="utf-8")

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")

        if _already_applied(connection, version):
            return False, f"CRM migration {version} already applied; no-op."

        # executescript() commits any pending transaction before it runs, so the
        # DDL and the tracking row are NOT one atomic transaction.  They do not
        # need to be: the DDL is idempotent (IF NOT EXISTS / INSERT OR IGNORE)
        # and the tracking row is written only after the DDL succeeds, so a run
        # that fails halfway can simply be re-applied.
        connection.executescript(ddl)
        connection.execute(
            "INSERT INTO crm_schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, _utc_now_iso()),
        )
        connection.commit()
    finally:
        connection.close()

    return True, f"CRM migration {version} applied to {db_path}."


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apply_migrations",
        description="Apply the CRM schema migration to a SQLite database (idempotent).",
    )
    parser.add_argument(
        "--db",
        default=str(_REPO_ROOT / "data" / "demo.db"),
        help="Path to the SQLite database (default: data/demo.db).",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Optional override for the CRM schema SQL path (default: data/crm_schema.sql).",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        applied, message = apply_migrations(args.db, schema_sql_path=args.schema)
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
