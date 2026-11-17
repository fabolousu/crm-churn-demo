"""Leakage and point-in-time tests for ``ml/features.py``.

The fixture is a tiny synthetic world built straight from ``data/schema.sql`` in an
in-memory SQLite database.  It deliberately contains rows that sit either side of every
scoring point, so a feature that reaches one day too far produces a different number.

Properties enforced:

1. Source level -- the module text never mentions the label table (this mirrors the CI
   ``grep`` guard, which runs without importing anything).
2. Behavioural -- altering or deleting the ground-truth label rows does not move a single
   feature value, and the module still builds when the table is dropped outright.
3. Point-in-time -- activity dated after the scoring point (ticket, invoice, meeting, a
   sibling initiative) does not move the feature it would otherwise inflate; the same rows
   dated before the snapshot *do* move it, so the assertions can fail.
4. "Open at the snapshot" is a timestamp test, not a status test (contract v0.3.1).
5. ``first_response_hours`` is gated on ``first_response_at <= snapshot_date``, so a
   ``contacted`` lead scored at creation carries no response duration; a recorded
   ``leads.first_response_at`` wins over the ``created_at + hours`` derivation, and one test
   builds from a schema without that column so the derivation is not dead code.
6. A record's own outcome never enters its own features: ``owner_win_rate_180d`` excludes
   the scored lead's own closure, tested by flipping that outcome.
7. The rebuild is atomic: a forced insert failure leaves the previous table intact on both
   default and autocommit connections.
8. "Not measured" is NULL, never a sentinel zero: one test per signal column, plus a
   measured-zero test so the two states cannot be conflated.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.features import build_features  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "data" / "schema.sql"
FEATURES_PATH = REPO_ROOT / "ml" / "features.py"

_COMPANIES = [
    # id, name, vat, region, city, industry, employees, created_at, owner_rep
    (
        "C-1",
        "Alfa Meccanica Srl",
        "IT01234567890",
        "nord-ovest",
        "Milano",
        "manifattura",
        120,
        "2023-01-01T00:00:00",
        "rep-anna",
    ),
    (
        "C-2",
        "Beta Servizi Spa",
        "IT09876543210",
        "sud",
        "Napoli",
        "servizi",
        40,
        "2022-06-01T00:00:00",
        "rep-anna",
    ),
]

_LEADS = [
    # id, company, created_at, status, source, owner, first_response_hours, qualified_at,
    # proposal_at, closed_at, lost_reason, amount_arr, discount_pct
    ("L-0", "C-1", "2023-10-01T00:00:00", "won", "inbound", "rep-anna", 1.0,
     "2023-10-10T00:00:00", "2023-11-01T00:00:00", "2023-12-15T00:00:00", None, 30000.0, 0.0),
    ("L-1", "C-1", "2024-01-01T00:00:00", "won", "referral", "rep-anna", 4.0,
     "2024-02-10T00:00:00", "2024-03-01T00:00:00", "2024-04-01T00:00:00", None, 50000.0, 5.0),
    ("L-2", "C-1", "2024-06-01T00:00:00", "proposal", "outbound", "rep-marco", 2.5,
     "2024-06-20T00:00:00", "2024-07-05T00:00:00", None, None, 80000.0, 10.0),
    # contacted: no stage timestamp, so it is scored at creation and cannot be answered yet
    ("L-3", "C-1", "2024-01-15T00:00:00", "contacted", "event", "rep-marco", 2.5,
     None, None, None, None, 15000.0, 0.0),
    # closes exactly at its own qualification instant: its own outcome sits inside its own
    # 180-day owner window unless excluded
    ("L-4", "C-1", "2023-09-01T00:00:00", "won", "event", "rep-anna", 3.0,
     "2023-09-20T00:00:00", None, "2023-09-20T00:00:00", None, 12000.0, 0.0),
    ("L-5", "C-1", "2024-01-20T00:00:00", "qualified", "partner", "rep-marco", 6.0,
     "2024-01-25T00:00:00", None, None, None, 20000.0, 0.0),
    ("L-6", "C-2", "2023-12-01T00:00:00", "lost", "outbound", "rep-anna", None,
     "2024-01-05T00:00:00", None, "2024-01-20T00:00:00", "price", 10000.0, 15.0),
    ("L-7", "C-1", "2024-01-10T00:00:00", "new", "event", "rep-marco", None,
     None, None, None, None, 5000.0, 0.0),
    # won, but created long before L-1's snapshot and closed long after: open *at* that
    # snapshot, which the timestamp rule must see even though its status says otherwise
    ("L-8", "C-1", "2023-12-01T00:00:00", "won", "inbound", "rep-marco", 5.0,
     "2024-01-15T00:00:00", "2024-02-01T00:00:00", "2024-03-01T00:00:00", None, 18000.0, 0.0),
]

_TICKETS = [
    # id, company, opened_at, closed_at, severity, resolution_hours
    ("T-1", "C-1", "2024-01-15T00:00:00", "2024-01-20T00:00:00", "low", 5.0),
    ("T-2", "C-1", "2024-02-01T00:00:00", None, "high", None),
    ("T-3", "C-1", "2023-10-01T00:00:00", "2023-10-03T00:00:00", "low", 48.0),
    ("T-4", "C-1", "2024-06-10T00:00:00", None, "medium", None),
]

_INVOICES = [
    # id, company, issued_at, due_at, paid_at, amount
    ("I-1", "C-1", "2023-12-01T00:00:00", "2023-12-31T00:00:00", "2024-01-10T00:00:00", 1000.0),
    ("I-2", "C-1", "2024-01-05T00:00:00", "2024-02-04T00:00:00", None, 2000.0),
    ("I-3", "C-1", "2024-01-20T00:00:00", "2024-03-20T00:00:00", None, 3000.0),
    ("I-4", "C-1", "2022-01-01T00:00:00", "2022-02-01T00:00:00", "2022-02-10T00:00:00", 4000.0),
    ("I-5", "C-1", "2024-06-01T00:00:00", "2024-06-30T00:00:00", "2024-07-02T00:00:00", 5000.0),
]

_NPS = [
    # company, surveyed_at, score
    ("C-1", "2023-12-01T00:00:00", 20),
    ("C-1", "2024-01-10T00:00:00", 30),
    ("C-1", "2024-05-01T00:00:00", 60),
    ("C-1", "2024-08-01T00:00:00", -20),
]

_INTERACTIONS = [
    # id, company, lead, kind, direction, occurred_at, answered
    ("X-1", "C-1", "L-1", "meeting", "inbound", "2024-01-15T00:00:00", 1),
    ("X-2", "C-1", "L-1", "meeting", "outbound", "2024-01-25T00:00:00", 1),
    ("X-3", "C-1", "L-1", "email", "outbound", "2024-01-20T00:00:00", 1),
    # after L-1's scoring point, so it must never be counted for L-1
    ("X-4", "C-1", "L-1", "meeting", "outbound", "2024-03-05T00:00:00", 1),
    # company-level meeting: "meetings on this lead" excludes it
    ("X-5", "C-1", None, "meeting", "inbound", "2024-01-18T00:00:00", 1),
    ("X-6", "C-1", "L-5", "meeting", "outbound", "2024-01-22T00:00:00", 1),
]

# Week of usage: one stale week far outside every window, then thirteen rising weeks.
_USAGE = [("C-1", "2023-10-02T00:00:00", 5000)] + [
    (
        "C-1",
        f"{(date(2023, 11, 13) + timedelta(days=7 * index)).isoformat()}T00:00:00",
        10 * (index + 1),
    )
    for index in range(13)
]

_OUTCOMES = [
    # lead_id, snapshot_date, won, closed_at, latent_p
    ("L-0", "2023-10-10T00:00:00", 1, "2023-12-15T00:00:00", 0.81),
    ("L-1", "2024-02-10T00:00:00", 1, "2024-04-01T00:00:00", 0.62),
    ("L-4", "2023-09-20T00:00:00", 1, "2023-09-20T00:00:00", 0.55),
    ("L-6", "2024-01-05T00:00:00", 0, "2024-01-20T00:00:00", 0.19),
    ("L-8", "2024-01-15T00:00:00", 1, "2024-03-01T00:00:00", 0.47),
]


# Recorded response instants for the leads that were answered before their snapshot
# (created_at + first_response_hours, which is what a consistent generator writes).
# L-0 and L-3 are deliberately absent: their column is NULL while a duration is recorded,
# so the fixture also exercises the fallback branch when the column exists but is NULL --
# L-0's derived instant falls before its snapshot and is kept, L-3's falls after it and is
# gated away (a contacted lead scored at creation has not been answered yet).
_LEAD_RESPONSE_AT = {
    "L-1": "2024-01-01T04:00:00",
    "L-2": "2024-06-01T02:30:00",
    "L-4": "2023-09-01T03:00:00",
    "L-5": "2024-01-20T06:00:00",
    "L-8": "2023-12-01T05:00:00",
}


def _seed_leads(conn: sqlite3.Connection) -> None:
    """Insert the leads and, when the schema carries it, their recorded response instants.

    ``data/schema.sql`` declares ``leads.first_response_at``; populating it here means the
    normal fixture exercises the precedence path (recorded column wins over the derivation).
    """
    conn.executemany(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _LEADS,
    )
    lead_columns = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
    if "first_response_at" in lead_columns:
        conn.executemany(
            "UPDATE leads SET first_response_at = ? WHERE id = ?",
            [(recorded, lead_id) for lead_id, recorded in _LEAD_RESPONSE_AT.items()],
        )


def _schema_without_lead_response_column() -> str:
    """``data/schema.sql`` with ``leads.first_response_at`` removed, for the fallback test."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    start = schema.index("CREATE TABLE leads (")
    end = schema.index(");", start)
    block = schema[start:end]
    stripped = "\n".join(
        line for line in block.splitlines() if "first_response_at" not in line
    )
    return schema[:start] + stripped + schema[end:]


def _seeded_connection(
    isolation_level: str | None = "",
    schema_text: str | None = None,
) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=isolation_level)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        SCHEMA_PATH.read_text(encoding="utf-8") if schema_text is None else schema_text
    )

    conn.executemany(
        "INSERT INTO companies (id, name, vat_number, region, city, industry, employees, "
        "created_at, owner_rep) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _COMPANIES,
    )
    _seed_leads(conn)
    conn.executemany(
        "INSERT INTO tickets (id, company_id, opened_at, closed_at, severity, "
        "resolution_hours) VALUES (?, ?, ?, ?, ?, ?)",
        _TICKETS,
    )
    conn.executemany(
        "INSERT INTO invoices (id, company_id, issued_at, due_at, paid_at, amount) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        _INVOICES,
    )
    conn.executemany(
        "INSERT INTO nps_surveys (company_id, surveyed_at, score) VALUES (?, ?, ?)",
        _NPS,
    )
    conn.executemany(
        "INSERT INTO company_usage_weekly (company_id, week_start, events) "
        "VALUES (?, ?, ?)",
        _USAGE,
    )
    conn.executemany(
        "INSERT INTO interactions (id, company_id, lead_id, kind, direction, occurred_at, "
        "answered) VALUES (?, ?, ?, ?, ?, ?, ?)",
        _INTERACTIONS,
    )
    conn.executemany(
        "INSERT INTO lead_outcomes (lead_id, snapshot_date, won, closed_at, latent_p) "
        "VALUES (?, ?, ?, ?, ?)",
        _OUTCOMES,
    )
    conn.commit()
    return conn


def _feature_rows(conn: sqlite3.Connection) -> dict[str, dict[str, object]]:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(lead_features)")]
    rows: dict[str, dict[str, object]] = {}
    for row in conn.execute("SELECT * FROM lead_features"):
        record = dict(zip(columns, row))
        rows[str(record["lead_id"])] = record
    return rows


def _build(conn: sqlite3.Connection) -> dict[str, dict[str, object]]:
    build_features(conn)
    return _feature_rows(conn)


# --------------------------------------------------------------------------------------
# 1. source-level guard: feature code may not even name the label table
# --------------------------------------------------------------------------------------


def test_features_module_never_mentions_the_label_table() -> None:
    source = FEATURES_PATH.read_text(encoding="utf-8")
    # sanity: we are reading the module we think we are
    assert "def build_features" in source
    assert "_outcomes" not in source, (
        "ml/features.py mentions the label table; this is the same defect the CI "
        "leakage guard fails on"
    )


# --------------------------------------------------------------------------------------
# 2. behavioural guard: labels are not an input
# --------------------------------------------------------------------------------------


def test_features_are_unchanged_when_label_rows_are_altered_or_deleted() -> None:
    conn = _seeded_connection()
    before = _build(conn)
    assert before  # the build produced rows, so an unchanged comparison means something

    flipped = conn.execute(
        "UPDATE lead_outcomes SET won = 1 - won, latent_p = 0.99, "
        "closed_at = '2030-01-01T00:00:00'"
    ).rowcount
    assert flipped > 0, "fixture labels were not altered -- test would be vacuous"
    conn.commit()
    assert _build(conn) == before, "flipping the labels changed a feature value"

    deleted = conn.execute("DELETE FROM lead_outcomes").rowcount
    assert deleted > 0, "fixture labels were not deleted -- test would be vacuous"
    conn.commit()
    assert _build(conn) == before, "deleting every label row changed a feature value"

    # Strongest form: the feature pipeline must not need the table to exist at all.
    conn.execute("DROP TABLE lead_outcomes")
    conn.commit()
    assert _build(conn) == before, "the build stopped working without the label table"


# --------------------------------------------------------------------------------------
# 3. point-in-time: activity after the snapshot is invisible
# --------------------------------------------------------------------------------------


def test_activity_after_the_snapshot_does_not_change_features() -> None:
    conn = _seeded_connection()
    before = _build(conn)

    # L-1 is scored at 2024-02-10.  All of these sit inside a naive 90/180-day window but
    # after the scoring point, so each one is a trap for a "look back from now" query.
    conn.execute(
        "INSERT INTO tickets (id, company_id, opened_at, closed_at, severity, "
        "resolution_hours) VALUES ('T-FUTURE', 'C-1', '2024-02-20T00:00:00', NULL, "
        "'critical', NULL)"
    )
    conn.execute(
        "INSERT INTO invoices (id, company_id, issued_at, due_at, paid_at, amount) VALUES "
        "('I-FUTURE', 'C-1', '2024-02-15T00:00:00', '2024-02-20T00:00:00', "
        "'2024-02-25T00:00:00', 9999.0)"
    )
    conn.execute(
        "INSERT INTO interactions (id, company_id, lead_id, kind, direction, occurred_at, "
        "answered) VALUES ('X-FUTURE', 'C-1', 'L-1', 'meeting', 'outbound', "
        "'2024-02-12T00:00:00', 1)"
    )
    conn.commit()

    after = _build(conn)
    assert after["L-1"]["tickets_90d"] == before["L-1"]["tickets_90d"]
    assert (
        after["L-1"]["payment_delay_days_avg_180d"]
        == before["L-1"]["payment_delay_days_avg_180d"]
    )
    assert (
        after["L-1"]["meetings_before_scoring"]
        == before["L-1"]["meetings_before_scoring"]
    )

    # Baseline values are non-zero, so each assertion above is a real guard.
    assert before["L-1"]["tickets_90d"] == 2
    assert before["L-1"]["payment_delay_days_avg_180d"] == pytest.approx(16.0 / 3.0)
    assert before["L-1"]["meetings_before_scoring"] == 2


def test_activity_before_the_snapshot_does_change_features() -> None:
    """Positive control for the leakage test above: same rows, earlier dates."""
    conn = _seeded_connection()
    before = _build(conn)

    conn.execute(
        "INSERT INTO tickets (id, company_id, opened_at, closed_at, severity, "
        "resolution_hours) VALUES ('T-PAST', 'C-1', '2024-02-05T00:00:00', NULL, 'low', NULL)"
    )
    conn.execute(
        "INSERT INTO invoices (id, company_id, issued_at, due_at, paid_at, amount) VALUES "
        "('I-PAST', 'C-1', '2024-02-01T00:00:00', '2024-02-01T00:00:00', "
        "'2024-02-02T00:00:00', 100.0)"
    )
    conn.execute(
        "INSERT INTO interactions (id, company_id, lead_id, kind, direction, occurred_at, "
        "answered) VALUES ('X-PAST', 'C-1', 'L-1', 'meeting', 'inbound', "
        "'2024-02-05T00:00:00', 1)"
    )
    conn.commit()

    after = _build(conn)
    assert after["L-1"]["tickets_90d"] == before["L-1"]["tickets_90d"] + 1
    assert after["L-1"]["meetings_before_scoring"] == before["L-1"]["meetings_before_scoring"] + 1
    # invoice delay 1.0 joins delays of 10, 6 and 0 (see the fixture comment)
    assert after["L-1"]["payment_delay_days_avg_180d"] == pytest.approx(17.0 / 4.0)


def test_initiatives_after_the_snapshot_do_not_change_company_history() -> None:
    conn = _seeded_connection()
    before = _build(conn)

    # A won initiative and a fresh open one on C-1, both created after L-1's snapshot
    # (2024-02-10) and after L-2's (2024-07-05).
    conn.execute(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES ('L-FUTURE-WON', 'C-1', '2024-08-01T00:00:00', "
        "'won', 'referral', 'rep-anna', 1.0, '2024-08-05T00:00:00', "
        "'2024-08-10T00:00:00', '2024-08-30T00:00:00', NULL, 99999.0, 0.0)"
    )
    conn.execute(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES ('L-FUTURE-OPEN', 'C-1', '2024-08-02T00:00:00', "
        "'proposal', 'inbound', 'rep-marco', 1.0, '2024-08-03T00:00:00', "
        "'2024-08-04T00:00:00', NULL, NULL, 1234.0, 0.0)"
    )
    conn.commit()

    after = _build(conn)
    history_columns = (
        "prior_won_initiatives",
        "prior_lost_initiatives",
        "days_since_last_initiative",
        "lifetime_won_arr",
        "open_initiatives_count",
        "owner_win_rate_180d",
    )
    for lead_id in ("L-1", "L-2"):
        for column in history_columns:
            assert after[lead_id][column] == before[lead_id][column], (
                f"{column} for {lead_id} moved because of a later initiative"
            )

    assert before["L-1"]["prior_won_initiatives"] == 2
    assert before["L-1"]["lifetime_won_arr"] == 42000.0
    assert before["L-2"]["prior_won_initiatives"] == 4
    assert before["L-2"]["lifetime_won_arr"] == 110000.0


# --------------------------------------------------------------------------------------
# 4. "open at the snapshot" is a timestamp test, not a status test
# --------------------------------------------------------------------------------------


def test_open_initiatives_count_is_a_timestamp_test_not_a_status_test() -> None:
    conn = _seeded_connection()
    before = _build(conn)

    # L-8 is *won* today, but at L-1's snapshot (2024-02-10) it was still open: it was
    # created 2023-12-01 and closed 2024-03-01.  It must therefore count at that snapshot.
    assert conn.execute("SELECT status FROM leads WHERE id = 'L-8'").fetchone()[0] == "won"
    # L-8, L-7, L-3 and L-5 were open at L-1's snapshot.  L-1 itself was open at its own
    # snapshot too (it closes 2024-04-01) and must never count as its own sibling.
    assert before["L-1"]["open_initiatives_count"] == 4

    # A sibling created before the snapshot and already closed before it does not count,
    # even though it is a real initiative: the test is created/closed, not status.
    conn.execute(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES ('L-PAST-CLOSED', 'C-1', '2023-11-01T00:00:00', "
        "'lost', 'outbound', 'rep-anna', 1.0, '2023-11-05T00:00:00', NULL, "
        "'2024-01-01T00:00:00', 'price', 4000.0, 0.0)"
    )
    conn.commit()
    assert _build(conn)["L-1"]["open_initiatives_count"] == 4

    # A sibling opened before the snapshot and never closed was open then, so it counts.
    conn.execute(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES ('L-PAST-OPEN', 'C-1', '2023-01-05T00:00:00', "
        "'proposal', 'partner', 'rep-marco', 1.0, '2023-01-10T00:00:00', "
        "'2023-02-01T00:00:00', NULL, NULL, 6000.0, 0.0)"
    )
    conn.commit()
    assert _build(conn)["L-1"]["open_initiatives_count"] == 5


# --------------------------------------------------------------------------------------
# 5. first_response_hours is gated on first_response_at <= snapshot
# --------------------------------------------------------------------------------------


def test_first_response_is_gated_on_the_snapshot() -> None:
    conn = _seeded_connection()
    rows = _build(conn)

    # A contacted lead is scored at creation, and its 2.5h response has not happened yet.
    assert rows["L-3"]["snapshot_date"] == "2024-01-15T00:00:00"
    assert rows["L-3"]["stage_at_scoring"] == "contacted"
    assert rows["L-3"]["first_response_hours"] is None
    assert rows["L-3"]["first_response_at"] is None
    # ... even though the source row carries the duration, so this is the gate at work
    source_hours = conn.execute(
        "SELECT first_response_hours FROM leads WHERE id = 'L-3'"
    ).fetchone()[0]
    assert source_hours == 2.5

    # Answered before the snapshot: both columns carry the duration and its instant.
    assert rows["L-1"]["first_response_hours"] == 4.0
    assert rows["L-1"]["first_response_at"] == "2024-01-01T04:00:00"
    assert rows["L-0"]["first_response_at"] == "2023-10-01T01:00:00"

    # Never answered: both NULL.
    assert rows["L-6"]["first_response_hours"] is None
    assert rows["L-6"]["first_response_at"] is None


# --------------------------------------------------------------------------------------
# 6. a lead's own outcome never enters its own features
# --------------------------------------------------------------------------------------


def test_owner_win_rate_excludes_the_scored_leads_own_closure() -> None:
    conn = _seeded_connection()
    before = _build(conn)

    # L-4 closes exactly at its own qualification instant, so its own won/lost result sits
    # inside the 180-day window the feature measures.  Excluded, the rep has no closure at
    # all there; included, the value would be 1.0 and the model would be reading the label.
    assert before["L-4"]["snapshot_date"] == "2023-09-20T00:00:00"
    assert before["L-4"]["owner_win_rate_180d"] is None  # no closure left in the window
    # the company aggregates exclude the lead itself on the same instant
    assert before["L-4"]["prior_won_initiatives"] == 0
    assert before["L-4"]["lifetime_won_arr"] == 0.0

    # Flip the scored lead's own outcome: the feature may not move.
    conn.execute("UPDATE leads SET status = 'lost' WHERE id = 'L-4'")
    conn.commit()
    after = _build(conn)
    assert after["L-4"]["owner_win_rate_180d"] == before["L-4"]["owner_win_rate_180d"]

    # The flip did land and flow through the rebuild, so the equality above is meaningful.
    assert after["L-1"]["prior_won_initiatives"] == before["L-1"]["prior_won_initiatives"] - 1


# --------------------------------------------------------------------------------------
# 7. days_since_last_initiative is snapshot-relative
# --------------------------------------------------------------------------------------


def test_days_since_last_initiative_is_snapshot_relative() -> None:
    conn = _seeded_connection()
    before = _build(conn)
    # L-1 is scored 2024-02-10; the previous initiative (L-8) was created 2023-12-01.
    assert before["L-1"]["days_since_last_initiative"] == 71

    # Move the scoring point without touching any creation date: the gap must grow.
    conn.execute("UPDATE leads SET qualified_at = '2024-02-20T00:00:00' WHERE id = 'L-1'")
    conn.commit()
    after = _build(conn)
    assert after["L-1"]["days_since_last_initiative"] == 81
    assert after["L-1"]["age_days_at_scoring"] == 50


# --------------------------------------------------------------------------------------
# 8. the scoring point: stage and snapshot must agree
# --------------------------------------------------------------------------------------


def test_scoring_point_is_qualification_for_closed_and_current_stage_for_open() -> None:
    rows = _build(_seeded_connection())

    # closed: scored at qualified_at even though proposal_at and closed_at are later
    assert rows["L-0"]["snapshot_date"] == "2023-10-10T00:00:00"
    assert rows["L-0"]["stage_at_scoring"] == "qualified"
    assert rows["L-1"]["snapshot_date"] == "2024-02-10T00:00:00"
    assert rows["L-1"]["stage_at_scoring"] == "qualified"
    assert rows["L-6"]["snapshot_date"] == "2024-01-05T00:00:00"
    assert rows["L-8"]["snapshot_date"] == "2024-01-15T00:00:00"

    # open at proposal: scored when it reached proposal, not at qualification
    assert rows["L-2"]["snapshot_date"] == "2024-07-05T00:00:00"
    assert rows["L-2"]["stage_at_scoring"] == "proposal"

    # open at qualification: scored at qualified_at
    assert rows["L-5"]["snapshot_date"] == "2024-01-25T00:00:00"
    assert rows["L-5"]["stage_at_scoring"] == "qualified"

    # never qualified: scored at creation, at the stage it holds
    assert rows["L-7"]["snapshot_date"] == "2024-01-10T00:00:00"
    assert rows["L-7"]["stage_at_scoring"] == "new"
    assert rows["L-3"]["snapshot_date"] == "2024-01-15T00:00:00"
    assert rows["L-3"]["stage_at_scoring"] == "contacted"

    # closed at its own qualification instant
    assert rows["L-4"]["snapshot_date"] == "2023-09-20T00:00:00"
    assert rows["L-4"]["stage_at_scoring"] == "qualified"


def test_stage_and_snapshot_agree_when_a_stage_timestamp_is_missing() -> None:
    conn = _seeded_connection()
    # A proposal whose proposal_at was never recorded: the latest instant it can prove is
    # qualification, so it must not claim 'proposal' at the earlier qualified_at.
    conn.execute(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES ('L-BAD-1', 'C-1', '2023-11-01T00:00:00', "
        "'proposal', 'inbound', 'rep-anna', 1.0, '2023-11-10T00:00:00', NULL, NULL, NULL, "
        "7000.0, 0.0)"
    )
    # A lost lead that was never qualified: proposal_at is the furthest instant it proves.
    conn.execute(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES ('L-BAD-2', 'C-1', '2024-01-02T00:00:00', "
        "'lost', 'event', 'rep-anna', 1.0, NULL, '2024-01-05T00:00:00', "
        "'2024-01-10T00:00:00', 'price', 9000.0, 0.0)"
    )
    conn.commit()

    rows = _build(conn)
    assert rows["L-BAD-1"]["snapshot_date"] == "2023-11-10T00:00:00"
    assert rows["L-BAD-1"]["stage_at_scoring"] == "qualified"
    assert rows["L-BAD-2"]["snapshot_date"] == "2024-01-05T00:00:00"
    assert rows["L-BAD-2"]["stage_at_scoring"] == "proposal"


# --------------------------------------------------------------------------------------
# 9. the derived columns are query results, not placeholders
# --------------------------------------------------------------------------------------


def test_derived_features_for_a_closed_lead() -> None:
    rows = _build(_seeded_connection())
    row = rows["L-1"]  # scored 2024-02-10, company C-1

    assert row["source"] == "referral"
    assert row["age_days_at_scoring"] == 40
    assert row["amount_arr"] == 50000.0
    assert row["discount_pct"] == 5.0
    assert row["first_response_hours"] == 4.0

    assert row["region"] == "nord-ovest"
    assert row["industry"] == "manifattura"
    assert row["employees"] == 120
    assert row["company_age_days"] == 405

    assert row["prior_won_initiatives"] == 2  # L-4 and L-0
    assert row["prior_lost_initiatives"] == 0
    assert row["days_since_last_initiative"] == 71  # previous initiative 2023-12-01
    assert row["lifetime_won_arr"] == 42000.0
    assert row["open_initiatives_count"] == 4  # L-8, L-7, L-3, L-5

    assert row["usage_trend_slope"] == pytest.approx(10.0)  # +10 events per week
    assert row["tickets_90d"] == 2
    assert row["nps_last"] == 30  # latest survey at or before the snapshot
    assert row["payment_delay_days_avg_180d"] == pytest.approx(16.0 / 3.0)
    assert row["meetings_before_scoring"] == 2
    assert row["owner_win_rate_180d"] == pytest.approx(2.0 / 3.0)  # L-4 won, L-0 won, L-6 lost


def test_derived_features_for_an_open_lead() -> None:
    rows = _build(_seeded_connection())
    row = rows["L-2"]  # open at proposal, scored 2024-07-05

    assert row["age_days_at_scoring"] == 34
    assert row["company_age_days"] == 551
    assert row["prior_won_initiatives"] == 4  # L-4, L-0, L-8, L-1
    assert row["lifetime_won_arr"] == 110000.0
    assert row["days_since_last_initiative"] == 167  # L-5, 2024-01-20
    assert row["open_initiatives_count"] == 3  # L-7, L-3, L-5

    assert row["tickets_90d"] == 1  # T-4 only
    assert row["nps_last"] == 60  # 2024-05-01 survey; 2024-08-01 is later
    assert row["payment_delay_days_avg_180d"] == pytest.approx(54.5)  # (107 + 2) / 2
    assert row["meetings_before_scoring"] == 0  # nothing booked on L-2 yet
    assert row["usage_trend_slope"] is None  # no usage week in the 90-day window
    assert row["owner_win_rate_180d"] == pytest.approx(1.0)  # L-8 won, self is open


def test_missing_history_is_null_for_signals_and_zero_for_counters() -> None:
    rows = _build(_seeded_connection())

    never_answered = rows["L-6"]  # lost without ever being answered
    assert never_answered["first_response_hours"] is None
    assert never_answered["first_response_at"] is None
    assert never_answered["tickets_90d"] == 0
    # C-2 was never surveyed and has no invoices or usage weeks: not measured, so NULL
    assert never_answered["nps_last"] is None
    assert never_answered["payment_delay_days_avg_180d"] is None
    assert never_answered["usage_trend_slope"] is None
    assert never_answered["open_initiatives_count"] == 0
    assert never_answered["lifetime_won_arr"] == 0.0
    assert never_answered["prior_won_initiatives"] == 0
    assert never_answered["company_age_days"] == 583
    # no earlier initiative at C-2, so the gap is measured from company creation
    assert never_answered["days_since_last_initiative"] == 583
    # rep-anna's closed initiatives in the window are L-4 and L-0, both won
    assert never_answered["owner_win_rate_180d"] == pytest.approx(1.0)

    brand_new = rows["L-7"]  # status new, scored at creation
    assert brand_new["first_response_hours"] is None
    assert brand_new["age_days_at_scoring"] == 0
    assert brand_new["tickets_90d"] == 0
    assert brand_new["nps_last"] == 30  # a survey on the snapshot date still counts
    assert brand_new["payment_delay_days_avg_180d"] == pytest.approx(5.0)  # (10 + 0) / 2
    assert brand_new["meetings_before_scoring"] == 0
    assert brand_new["days_since_last_initiative"] == 9  # L-1, 2024-01-01
    assert brand_new["prior_won_initiatives"] == 2
    assert brand_new["open_initiatives_count"] == 2  # L-8 and L-1
    # rep-marco has no closure in L-7's window: not measured, so NULL rather than 0.0
    assert brand_new["owner_win_rate_180d"] is None


# --------------------------------------------------------------------------------------
# 10. NULL means "not measured"; 0.0 means "measured zero"
# --------------------------------------------------------------------------------------


def test_not_measured_signals_are_null() -> None:
    rows = _build(_seeded_connection())

    # owner_win_rate_180d: rep has no closure in the window (L-4's own close is excluded)
    assert rows["L-4"]["owner_win_rate_180d"] is None
    assert rows["L-3"]["owner_win_rate_180d"] is None  # rep-marco, nothing closed yet

    # nps_last: the company was never surveyed at or before this snapshot
    assert rows["L-0"]["nps_last"] is None  # first C-1 survey is 2023-12-01
    assert rows["L-4"]["nps_last"] is None
    assert rows["L-6"]["nps_last"] is None  # C-2 has no surveys at all

    # payment_delay_days_avg_180d: no invoice issued inside the window
    assert rows["L-0"]["payment_delay_days_avg_180d"] is None
    assert rows["L-4"]["payment_delay_days_avg_180d"] is None
    assert rows["L-6"]["payment_delay_days_avg_180d"] is None

    # usage_trend_slope: fewer than two weekly points, so no slope is estimable
    assert rows["L-0"]["usage_trend_slope"] is None  # one week in the window
    assert rows["L-4"]["usage_trend_slope"] is None  # none in the window
    assert rows["L-6"]["usage_trend_slope"] is None  # no usage rows at all

    # signals that do exist stay measured, so the NULLs above are not a column-wide failure
    assert rows["L-1"]["owner_win_rate_180d"] == pytest.approx(2.0 / 3.0)
    assert rows["L-1"]["nps_last"] == 30
    assert rows["L-1"]["payment_delay_days_avg_180d"] == pytest.approx(16.0 / 3.0)
    assert rows["L-1"]["usage_trend_slope"] == pytest.approx(10.0)


def test_measured_zero_is_not_null() -> None:
    conn = _seeded_connection()

    # An NPS score of 0 is a measurement, not an absence of one.
    conn.execute(
        "INSERT INTO nps_surveys (company_id, surveyed_at, score) "
        "VALUES ('C-1', '2023-09-01T00:00:00', 0)"
    )
    # Paid exactly on the due date: zero days late, not "no invoices".
    conn.execute(
        "INSERT INTO invoices (id, company_id, issued_at, due_at, paid_at, amount) VALUES "
        "('I-ON-TIME', 'C-1', '2023-08-01T00:00:00', '2023-08-20T00:00:00', "
        "'2023-08-20T00:00:00', 500.0)"
    )
    # Flat usage across two weeks: an estimable slope of zero, not a missing slope.
    conn.execute(
        "INSERT INTO company_usage_weekly (company_id, week_start, events) VALUES "
        "('C-1', '2023-07-03T00:00:00', 40), ('C-1', '2023-07-10T00:00:00', 40)"
    )
    # A rep at 0-for-1 in the window: a real zero win rate.
    conn.execute(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES ('L-9', 'C-2', '2023-07-15T00:00:00', 'lost', "
        "'event', 'rep-marco', 1.0, '2023-07-20T00:00:00', NULL, "
        "'2023-08-01T00:00:00', 'timing', 2000.0, 0.0)"
    )
    conn.commit()

    rows = _build(conn)
    l4 = rows["L-4"]  # snapshot 2023-09-20, C-1
    assert l4["nps_last"] == 0  # a survey score of zero, measured
    assert l4["payment_delay_days_avg_180d"] == 0.0  # paid on the due date
    assert l4["usage_trend_slope"] == 0.0  # flat weekly usage
    # L-3's rep window (2023-07-19 .. 2024-01-15) holds one loss and no win
    assert rows["L-3"]["owner_win_rate_180d"] == 0.0


# --------------------------------------------------------------------------------------
# 11. the recorded response timestamp beats the derived one
# --------------------------------------------------------------------------------------


def test_recorded_first_response_timestamp_wins_over_the_derived_instant() -> None:
    conn = _seeded_connection()

    # The normal fixture carries leads.first_response_at; the feature row reports it and
    # measures the duration to it.
    rows = _build(conn)
    assert rows["L-1"]["first_response_at"] == "2024-01-01T04:00:00"
    assert rows["L-1"]["first_response_hours"] == 4.0

    # Change only the recorded instant (the duration column still says 6.0): the column wins,
    # because it is the source of truth for when the response happened.
    conn.execute(
        "UPDATE leads SET first_response_at = '2024-01-20T18:00:00' WHERE id = 'L-5'"
    )
    conn.commit()
    rows = _build(conn)
    assert rows["L-5"]["first_response_at"] == "2024-01-20T18:00:00"
    assert rows["L-5"]["first_response_hours"] == 18.0

    # A recorded instant after the snapshot is not knowable there.
    conn.execute(
        "UPDATE leads SET first_response_at = '2024-02-01T00:00:00' WHERE id = 'L-6'"
    )
    conn.commit()
    rows = _build(conn)
    assert rows["L-6"]["first_response_at"] is None
    assert rows["L-6"]["first_response_hours"] is None


def test_derived_response_instant_when_the_source_column_is_absent() -> None:
    """The PRAGMA fallback is a real path, not dead code: build from a schema without it."""
    schema_without = _schema_without_lead_response_column()
    assert schema_without != SCHEMA_PATH.read_text(encoding="utf-8")
    conn = _seeded_connection(schema_text=schema_without)
    assert "first_response_at" not in {
        row[1] for row in conn.execute("PRAGMA table_info(leads)")
    }
    # the materialised table still records the instant the row actually used
    assert "first_response_at" in {
        row[1] for row in conn.execute("PRAGMA table_info(lead_features)")
    }

    rows = _build(conn)
    # derived as created_at + first_response_hours
    assert rows["L-1"]["first_response_at"] == "2024-01-01T04:00:00"
    assert rows["L-1"]["first_response_hours"] == 4.0
    assert rows["L-5"]["first_response_at"] == "2024-01-20T06:00:00"
    assert rows["L-5"]["first_response_hours"] == 6.0
    # and the snapshot gate still nulls a response that has not happened yet
    assert rows["L-3"]["first_response_at"] is None
    assert rows["L-3"]["first_response_hours"] is None
    assert rows["L-6"]["first_response_at"] is None
    assert rows["L-6"]["first_response_hours"] is None


# --------------------------------------------------------------------------------------
# 10. rebuild behaviour and atomicity
# --------------------------------------------------------------------------------------


def test_build_replaces_rows_and_returns_the_row_count() -> None:
    conn = _seeded_connection()

    assert build_features(conn) == len(_LEADS)
    first = _feature_rows(conn)
    assert set(first) == {lead[0] for lead in _LEADS}
    assert conn.in_transaction is False, "a successful build left a transaction open"

    assert build_features(conn) == len(_LEADS)
    assert _feature_rows(conn) == first, "a rebuild changed values without new activity"
    count = conn.execute("SELECT COUNT(*) FROM lead_features").fetchone()[0]
    assert count == len(_LEADS), "the rebuild duplicated rows instead of replacing them"


@pytest.mark.parametrize(
    "isolation_level",
    ["", None],
    ids=["default-connection", "autocommit"],
)
def test_failed_build_leaves_previous_rows_intact(isolation_level: str | None) -> None:
    conn = _seeded_connection(isolation_level=isolation_level)
    before = _build(conn)
    assert before

    # Forced insert failure part-way through the load: L-2 aborts, after L-0 and L-1 have
    # already been written by the same executemany.
    conn.execute(
        "CREATE TRIGGER fail_lead_insert BEFORE INSERT ON lead_features "
        "WHEN NEW.lead_id = 'L-2' BEGIN SELECT RAISE(ABORT, 'forced insert failure'); END"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        build_features(conn)

    assert _feature_rows(conn) == before, (
        "a failed build destroyed the previous materialisation"
    )
    assert conn.in_transaction is False, "the failed build left a transaction open"

    # The connection is still usable and a clean rebuild still works.
    conn.execute("DROP TRIGGER fail_lead_insert")
    conn.commit()
    assert _build(conn) == before


def test_build_inside_a_caller_transaction_uses_a_savepoint() -> None:
    conn = _seeded_connection()
    before = _build(conn)

    conn.execute(
        "INSERT INTO companies (id, name, vat_number, region, city, industry, employees, "
        "created_at, owner_rep) VALUES ('C-3', 'Gamma Srl', 'IT11111111111', 'centro', "
        "'Roma', 'servizi', 10, '2024-01-01T00:00:00', 'rep-anna')"
    )
    assert conn.in_transaction is True  # the caller owns an open unit of work

    conn.execute(
        "CREATE TRIGGER fail_lead_insert BEFORE INSERT ON lead_features "
        "WHEN NEW.lead_id = 'L-2' BEGIN SELECT RAISE(ABORT, 'forced insert failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        build_features(conn)

    # The previous materialisation and the caller's uncommitted row both survive, and the
    # caller still owns its transaction instead of having it committed or discarded.
    assert _feature_rows(conn) == before
    assert conn.execute(
        "SELECT COUNT(*) FROM companies WHERE id = 'C-3'"
    ).fetchone()[0] == 1
    assert conn.in_transaction is True
    conn.rollback()
