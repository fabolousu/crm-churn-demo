"""CRM schema migration — invariants (T12 / WS-B B1).

The gates live here:

* 1. the migration adds the seven ``crm_`` tables;
* 2. it does not touch any ML (non-crm) table or column — byte-for-byte snapshot
     before/after;
* 3. the 14 lead-status seeds exist with the exact categories, one manual
     default, one auto default, four legacy;
* 4. applying the migration twice is a no-op (no duplicate seeds);
* 5. ``UNIQUE(contact_id, initiative_id)`` rejects a duplicate lead but accepts
     a second initiative for the same contact;
* 6. a foreign-key violation is enforced under ``PRAGMA foreign_keys = ON``;
* 7. the ``INI-NNNNNN`` CHECK accepts a valid code and rejects a malformed one.

Tests use ``tmp_path``; they never touch ``data/demo.db``.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from api.migrations.apply import apply_migrations, CRM_SCHEMA_VERSION


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ML_SCHEMA_SQL = _REPO_ROOT / "data" / "schema.sql"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

_CRM_TABLES = {
    "crm_companies",
    "crm_contacts",
    "crm_company_contacts",
    "crm_initiatives",
    "crm_lead_statuses",
    "crm_leads",
    "crm_activities",
}


def _snapshot_tables(connection: sqlite3.Connection) -> dict[str, list[tuple]]:
    """Return {table_name: [(cid, name, type, notnull, dflt_value, pk), ...]} for
    every user table in the DB.  Snapshotting the PRAGMA table_info row verbatim
    catches any change in column order, type, nullability, default or PK flag.
    """
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]
    return {t: list(connection.execute(f"PRAGMA table_info({t})").fetchall()) for t in tables}


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _seed_fixture_rows(connection: sqlite3.Connection) -> dict[str, str]:
    """Insert one company, one contact, and one initiative; return their ids.
    Shared by the lead-constraint tests.
    """
    ids = {
        "company": "C-001",
        "contact": "P-001",
        "initiative": "I-001",
    }
    ts = "2026-11-19T00:00:00Z"
    connection.execute(
        "INSERT INTO crm_companies "
        "(id, denominazione, codice_fiscale, created_on, modified_on) "
        "VALUES (?, 'Acme Srl', '12345678901', ?, ?)",
        (ids["company"], ts, ts),
    )
    connection.execute(
        "INSERT INTO crm_contacts "
        "(id, nome, cognome, nome_completo, email, telefono, created_on, modified_on) "
        "VALUES (?, 'Mario', 'Rossi', 'Mario Rossi', 'm@x.it', '0000', ?, ?)",
        (ids["contact"], ts, ts),
    )
    connection.execute(
        "INSERT INTO crm_initiatives "
        "(id, codice, iniziativa, created_on, modified_on) "
        "VALUES (?, 'INI-052096', 'Missione in Svezia', ?, ?)",
        (ids["initiative"], ts, ts),
    )
    connection.commit()
    return ids


def _make_db_from_ml_schema(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(_ML_SCHEMA_SQL.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 1. the seven crm_ tables exist after the migration
# --------------------------------------------------------------------------- #

def test_migration_adds_the_seven_crm_tables(tmp_path):
    db = tmp_path / "demo.db"
    _make_db_from_ml_schema(db)

    applied, _msg = apply_migrations(db)
    assert applied is True

    with closing(_connect(db)) as connection:
        found = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'crm\\_%' ESCAPE '\\'"
            ).fetchall()
        }
    assert _CRM_TABLES.issubset(found), f"missing: {_CRM_TABLES - found}"


# --------------------------------------------------------------------------- #
# 2. ML tables are byte-for-byte unchanged
# --------------------------------------------------------------------------- #

def test_ml_tables_untouched_by_migration(tmp_path):
    db = tmp_path / "demo.db"
    _make_db_from_ml_schema(db)

    with closing(sqlite3.connect(db)) as connection:
        before = _snapshot_tables(connection)

    apply_migrations(db)

    with closing(sqlite3.connect(db)) as connection:
        after = _snapshot_tables(connection)

    # Every pre-existing (non-crm) table must survive identical.
    non_crm_before = {t: cols for t, cols in before.items() if not t.startswith("crm_")}
    for table, columns in non_crm_before.items():
        assert table in after, f"ML table {table!r} disappeared after migration"
        assert after[table] == columns, (
            f"ML table {table!r} schema changed after migration.\n"
            f"before: {columns}\nafter:  {after[table]}"
        )

    # And the new tables are purely additive.
    new_tables = set(after) - set(before)
    assert new_tables.issubset(_CRM_TABLES | {"crm_schema_migrations"}), (
        f"unexpected new tables: {new_tables - (_CRM_TABLES | {'crm_schema_migrations'})}"
    )


# --------------------------------------------------------------------------- #
# 3. status catalogue is seeded exactly
# --------------------------------------------------------------------------- #

def test_lead_statuses_are_seeded_per_spec(tmp_path):
    db = tmp_path / "demo.db"
    _make_db_from_ml_schema(db)
    apply_migrations(db)

    with closing(_connect(db)) as connection:
        rows = connection.execute(
            "SELECT code, category, is_default_manual, is_default_auto, is_legacy "
            "FROM crm_lead_statuses"
        ).fetchall()

    by_code = {r[0]: r for r in rows}
    assert len(rows) == 14, f"expected 14 statuses, got {len(rows)}"

    # Open statuses (10 current + 2 legacy among the open ones).
    expected_open = {
        "nuovo", "interessato", "da_contattare", "in_attesa_di_riscontro",
        "interessato_inbuyer", "da_richiamare",
    }
    expected_closed = {
        "prefattibilita_negativa", "nessuna_risposta", "non_interessato",
        "iscritto_all_evento", "servizio_concluso", "contratto_concluso",
        "concluso", "perso",
    }
    assert {c for c, r in by_code.items() if r[1] == "open"} == expected_open
    assert {c for c, r in by_code.items() if r[1] == "closed"} == expected_closed

    # Exactly one manual default, one auto default, four legacy.
    manual_defaults = [c for c, r in by_code.items() if r[2] == 1]
    auto_defaults = [c for c, r in by_code.items() if r[3] == 1]
    legacy = [c for c, r in by_code.items() if r[4] == 1]
    assert manual_defaults == ["nuovo"], manual_defaults
    assert auto_defaults == ["interessato"], auto_defaults
    assert set(legacy) == {"interessato_inbuyer", "concluso", "da_richiamare", "perso"}, legacy


# --------------------------------------------------------------------------- #
# 4. idempotency
# --------------------------------------------------------------------------- #

def test_migration_is_idempotent(tmp_path):
    db = tmp_path / "demo.db"
    _make_db_from_ml_schema(db)

    applied_1, _ = apply_migrations(db)
    applied_2, _ = apply_migrations(db)
    assert applied_1 is True
    assert applied_2 is False  # second call is a no-op

    with closing(_connect(db)) as connection:
        count = connection.execute("SELECT COUNT(*) FROM crm_lead_statuses").fetchone()[0]
        versions = connection.execute(
            "SELECT version FROM crm_schema_migrations"
        ).fetchall()
    assert count == 14, f"status seeds duplicated: got {count}"
    assert versions == [(CRM_SCHEMA_VERSION,)], versions


def test_migration_works_on_empty_database(tmp_path):
    """The runner must not require the ML schema to exist first."""
    db = tmp_path / "empty.db"
    applied, _ = apply_migrations(db)
    assert applied is True

    with closing(_connect(db)) as connection:
        found = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert _CRM_TABLES.issubset(found)


# --------------------------------------------------------------------------- #
# 5. UNIQUE(contact_id, initiative_id)
# --------------------------------------------------------------------------- #

def test_duplicate_lead_for_same_contact_and_initiative_is_rejected(tmp_path):
    db = tmp_path / "demo.db"
    _make_db_from_ml_schema(db)
    apply_migrations(db)

    with closing(_connect(db)) as connection:
        ids = _seed_fixture_rows(connection)
        ts = "2026-11-19T00:00:00Z"
        connection.execute(
            "INSERT INTO crm_leads (id, company_id, contact_id, initiative_id, "
            "status_code, created_on, modified_on) VALUES (?, ?, ?, ?, 'nuovo', ?, ?)",
            ("L-001", ids["company"], ids["contact"], ids["initiative"], ts, ts),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO crm_leads (id, company_id, contact_id, initiative_id, "
                "status_code, created_on, modified_on) VALUES (?, ?, ?, ?, 'nuovo', ?, ?)",
                ("L-002", ids["company"], ids["contact"], ids["initiative"], ts, ts),
            )
            connection.commit()


def test_same_contact_can_have_lead_for_a_different_initiative(tmp_path):
    db = tmp_path / "demo.db"
    _make_db_from_ml_schema(db)
    apply_migrations(db)

    with closing(_connect(db)) as connection:
        ids = _seed_fixture_rows(connection)
        ts = "2026-11-19T00:00:00Z"
        # second initiative
        connection.execute(
            "INSERT INTO crm_initiatives (id, codice, iniziativa, created_on, modified_on) "
            "VALUES ('I-002', 'INI-052097', 'Altra iniziativa', ?, ?)",
            (ts, ts),
        )
        connection.execute(
            "INSERT INTO crm_leads (id, company_id, contact_id, initiative_id, "
            "status_code, created_on, modified_on) VALUES ('L-001', ?, ?, 'I-001', 'nuovo', ?, ?)",
            (ids["company"], ids["contact"], ts, ts),
        )
        connection.execute(
            "INSERT INTO crm_leads (id, company_id, contact_id, initiative_id, "
            "status_code, created_on, modified_on) VALUES ('L-002', ?, ?, 'I-002', 'nuovo', ?, ?)",
            (ids["company"], ids["contact"], ts, ts),
        )
        connection.commit()

        count = connection.execute(
            "SELECT COUNT(*) FROM crm_leads WHERE contact_id = ?",
            (ids["contact"],),
        ).fetchone()[0]
    assert count == 2


# --------------------------------------------------------------------------- #
# 6. foreign-key enforcement
# --------------------------------------------------------------------------- #

def test_foreign_key_violation_is_enforced(tmp_path):
    db = tmp_path / "demo.db"
    _make_db_from_ml_schema(db)
    apply_migrations(db)

    with closing(_connect(db)) as connection:
        _seed_fixture_rows(connection)
        ts = "2026-11-19T00:00:00Z"
        # unknown company_id -> FK violation
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO crm_leads (id, company_id, contact_id, initiative_id, "
                "status_code, created_on, modified_on) "
                "VALUES ('L-BAD', 'GHOST', 'P-001', 'I-001', 'nuovo', ?, ?)",
                (ts, ts),
            )
            connection.commit()


# --------------------------------------------------------------------------- #
# 7. initiative code format
# --------------------------------------------------------------------------- #

def test_initiative_code_check_accepts_valid_format(tmp_path):
    db = tmp_path / "demo.db"
    apply_migrations(db)
    with closing(_connect(db)) as connection:
        ts = "2026-11-19T00:00:00Z"
        connection.execute(
            "INSERT INTO crm_initiatives (id, codice, iniziativa, created_on, modified_on) "
            "VALUES ('I-OK', 'INI-052096', 'Valida', ?, ?)",
            (ts, ts),
        )
        connection.commit()
        # Sanity: row is there.
        got = connection.execute(
            "SELECT codice FROM crm_initiatives WHERE id = 'I-OK'"
        ).fetchone()
    assert got == ("INI-052096",)


@pytest.mark.parametrize(
    "bad_code",
    [
        "INI-12345",       # 5 digits
        "INI-1234567",     # 7 digits
        "ini-052096",      # lowercase prefix
        "INI_052096",      # underscore separator
        "INI-05209A",      # non-digit
        "052096",          # missing prefix
        "",                # empty
    ],
)
def test_initiative_code_check_rejects_malformed(tmp_path, bad_code):
    db = tmp_path / "demo.db"
    apply_migrations(db)
    with closing(_connect(db)) as connection:
        ts = "2026-11-19T00:00:00Z"
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO crm_initiatives (id, codice, iniziativa, created_on, modified_on) "
                "VALUES ('I-BAD', ?, 'Invalida', ?, ?)",
                (bad_code, ts, ts),
            )
            connection.commit()
