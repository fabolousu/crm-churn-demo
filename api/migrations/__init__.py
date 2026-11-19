"""CRM schema migrations.

Stdlib-only, idempotent SQLite migration runner.  Import `apply_migrations` from
`api.migrations.apply` to run the CRM DDL against a SQLite database without
touching the ML tables already in `data/schema.sql`.
"""

from api.migrations.apply import apply_migrations  # noqa: F401
