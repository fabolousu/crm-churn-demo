"""Leakage and point-in-time tests for ``ml/features.py``.

The fixture is a tiny synthetic world built straight from ``data/schema.sql`` in an
in-memory SQLite database.  It deliberately contains rows that sit either side of every
scoring point, so a feature that reaches one day too far produces a different number.

Three properties are enforced:

1. Source level -- the module text never mentions the label table (this mirrors the CI
   ``grep`` guard, which runs without importing anything).
2. Behavioural -- altering or deleting the ground-truth label rows does not move a single
   feature value, and the module still builds when the table is dropped outright.
3. Point-in-time -- a ticket, invoice, meeting or initiative dated after the scoring point
   does not change the feature it would otherwise inflate.  A positive control proves the
   same rows *do* move the feature when dated before the snapshot, so these assertions can
   fail rather than being vacuously true.
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
    ("L-5", "C-1", "2024-01-20T00:00:00", "qualified", "partner", "rep-marco", 6.0,
     "2024-01-25T00:00:00", None, None, None, 20000.0, 0.0),
    ("L-6", "C-2", "2023-12-01T00:00:00", "lost", "outbound", "rep-anna", None,
     "2024-01-05T00:00:00", None, "2024-01-20T00:00:00", "price", 10000.0, 15.0),
    ("L-7", "C-1", "2024-01-10T00:00:00", "new", "event", "rep-marco", None,
     None, None, None, None, 5000.0, 0.0),
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
    ("L-6", "2024-01-05T00:00:00", 0, "2024-01-20T00:00:00", 0.19),
]


def _seeded_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    conn.executemany(
        "INSERT INTO companies (id, name, vat_number, region, city, industry, employees, "
        "created_at, owner_rep) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _COMPANIES,
    )
    conn.executemany(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _LEADS,
    )
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
        "amount_arr, discount_pct) VALUES ('L-8', 'C-1', '2024-08-01T00:00:00', 'won', "
        "'referral', 'rep-anna', 1.0, '2024-08-05T00:00:00', '2024-08-10T00:00:00', "
        "'2024-08-30T00:00:00', NULL, 99999.0, 0.0)"
    )
    conn.execute(
        "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
        "first_response_hours, qualified_at, proposal_at, closed_at, lost_reason, "
        "amount_arr, discount_pct) VALUES ('L-9', 'C-1', '2024-08-02T00:00:00', "
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

    assert before["L-1"]["prior_won_initiatives"] == 1
    assert before["L-1"]["lifetime_won_arr"] == 30000.0
    assert before["L-1"]["open_initiatives_count"] == 2
    assert before["L-2"]["prior_won_initiatives"] == 2
    assert before["L-2"]["lifetime_won_arr"] == 80000.0


# --------------------------------------------------------------------------------------
# 4. the scoring point itself
# --------------------------------------------------------------------------------------


def test_scoring_point_is_qualification_for_closed_and_current_stage_for_open() -> None:
    rows = _build(_seeded_connection())

    # closed: scored at qualified_at even though proposal_at and closed_at are later
    assert rows["L-0"]["snapshot_date"] == "2023-10-10T00:00:00"
    assert rows["L-0"]["stage_at_scoring"] == "qualified"
    assert rows["L-1"]["snapshot_date"] == "2024-02-10T00:00:00"
    assert rows["L-1"]["stage_at_scoring"] == "qualified"
    assert rows["L-6"]["snapshot_date"] == "2024-01-05T00:00:00"

    # open at proposal: scored when it reached proposal, not at qualification
    assert rows["L-2"]["snapshot_date"] == "2024-07-05T00:00:00"
    assert rows["L-2"]["stage_at_scoring"] == "proposal"

    # open at qualification: scored at qualified_at
    assert rows["L-5"]["snapshot_date"] == "2024-01-25T00:00:00"
    assert rows["L-5"]["stage_at_scoring"] == "qualified"

    # never qualified: scored at creation, at the stage it holds
    assert rows["L-7"]["snapshot_date"] == "2024-01-10T00:00:00"
    assert rows["L-7"]["stage_at_scoring"] == "new"


# --------------------------------------------------------------------------------------
# 5. the derived columns are query results, not placeholders
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

    assert row["prior_won_initiatives"] == 1  # L-0, closed 2023-12-15
    assert row["prior_lost_initiatives"] == 0
    assert row["days_since_last_initiative"] == 92  # previous initiative 2023-10-01
    assert row["lifetime_won_arr"] == 30000.0
    assert row["open_initiatives_count"] == 2  # L-5 and L-7, both still open

    assert row["usage_trend_slope"] == pytest.approx(10.0)  # +10 events per week
    assert row["tickets_90d"] == 2
    assert row["nps_last"] == 30  # latest survey at or before the snapshot
    assert row["payment_delay_days_avg_180d"] == pytest.approx(16.0 / 3.0)
    assert row["meetings_before_scoring"] == 2
    assert row["owner_win_rate_180d"] == pytest.approx(0.5)  # L-0 won, L-6 lost


def test_derived_features_for_an_open_lead() -> None:
    rows = _build(_seeded_connection())
    row = rows["L-2"]  # open at proposal, scored 2024-07-05

    assert row["age_days_at_scoring"] == 34
    assert row["company_age_days"] == 551
    assert row["prior_won_initiatives"] == 2  # L-0 and L-1 both closed by then
    assert row["lifetime_won_arr"] == 80000.0
    assert row["days_since_last_initiative"] == 133  # L-5, 2024-01-20
    assert row["open_initiatives_count"] == 2  # L-5, L-7

    assert row["tickets_90d"] == 1  # T-4 only
    assert row["nps_last"] == 60  # 2024-05-01 survey; 2024-08-01 is later
    assert row["payment_delay_days_avg_180d"] == pytest.approx(54.5)  # (107 + 2) / 2
    assert row["meetings_before_scoring"] == 0  # nothing booked on L-2 yet
    assert row["usage_trend_slope"] == 0.0  # no usage week in the 90-day window
    assert row["owner_win_rate_180d"] == 0.0  # rep-marco has no closed initiative yet


def test_missing_history_yields_the_documented_defaults() -> None:
    rows = _build(_seeded_connection())

    never_answered = rows["L-6"]  # lost without ever being answered
    assert never_answered["first_response_hours"] is None
    assert never_answered["tickets_90d"] == 0
    assert never_answered["nps_last"] == 0
    assert never_answered["payment_delay_days_avg_180d"] == 0.0
    assert never_answered["usage_trend_slope"] == 0.0
    assert never_answered["open_initiatives_count"] == 0
    assert never_answered["lifetime_won_arr"] == 0.0
    assert never_answered["prior_won_initiatives"] == 0
    assert never_answered["company_age_days"] == 583
    # no earlier initiative at C-2, so the gap is measured from company creation to this
    # lead's creation (2023-12-01), not to the snapshot
    assert never_answered["days_since_last_initiative"] == 548
    # rep-anna's only closed initiative in the window is L-0 (won)
    assert never_answered["owner_win_rate_180d"] == pytest.approx(1.0)

    brand_new = rows["L-7"]  # status new, scored at creation
    assert brand_new["first_response_hours"] is None
    assert brand_new["age_days_at_scoring"] == 0
    assert brand_new["tickets_90d"] == 0
    assert brand_new["nps_last"] == 30  # a survey on the snapshot date still counts
    assert brand_new["payment_delay_days_avg_180d"] == pytest.approx(5.0)  # (10 + 0) / 2
    assert brand_new["meetings_before_scoring"] == 0
    assert brand_new["days_since_last_initiative"] == 9  # L-1, 2024-01-01


def test_build_replaces_rows_and_returns_the_row_count() -> None:
    conn = _seeded_connection()

    assert build_features(conn) == len(_LEADS)
    first = _feature_rows(conn)
    assert set(first) == {lead[0] for lead in _LEADS}

    assert build_features(conn) == len(_LEADS)
    assert _feature_rows(conn) == first, "a rebuild changed values without new activity"
    count = conn.execute("SELECT COUNT(*) FROM lead_features").fetchone()[0]
    assert count == len(_LEADS), "the rebuild duplicated rows instead of replacing them"
