"""Contract and integrity tests for ``data/generator.py``.

The generator writes raw CRM history plus ``lead_outcomes``.  It deliberately
does **not** write ``lead_features``: that table is materialised by
``ml/features.py`` (single writer), and an empty table after generation is what
keeps the two lanes honest.

The suite generates the world twice (once for the shared fixture, once for the
determinism test) and checks the contract from the left side of that seam:
volumes, the 25-30% prevalence, regional base rates, censoring, raw point-in-
time coherence, ``leads.first_response_at`` consistency, and reachability of the
measured / measured-zero / not-measured states that ``ml/features.py`` must
handle.
"""

from __future__ import annotations

import hashlib
import math
import re
import random
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from data import generator

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "data" / "generator.py"
T0 = "2026-01-01T00:00:00"
T0_DT = datetime(2026, 1, 1, 0, 0, 0)
HISTORY_START = "2024-01-01T00:00:00"

REGIONS = {"nord-ovest", "nord-est", "centro", "sud", "isole"}
SOURCES = {"inbound", "outbound", "referral", "partner", "event"}
OPEN_STATUSES = {"new", "contacted", "qualified", "proposal"}
CLOSED_STATUSES = {"won", "lost"}

TABLES = (
    "companies",
    "leads",
    "company_usage_weekly",
    "tickets",
    "invoices",
    "nps_surveys",
    "interactions",
    "lead_outcomes",
    "lead_scores",
    "actions",
    "model_runs",
    "lead_features",
)


# ---------------------------------------------------------------------------
# Fixtures / process helpers
# ---------------------------------------------------------------------------


def _generator_command(db_path: Path, extra_args: list[str]) -> list[str]:
    return [
        sys.executable,
        str(GENERATOR),
        "--db",
        str(db_path),
        "--seed",
        "42",
        *extra_args,
    ]


def run_generator(db_path: Path) -> None:
    result = subprocess.run(
        _generator_command(db_path, ["--quiet"]),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"generator failed with {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.fixture(scope="session")
def demo_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("generator")
    db_path = directory / "demo.db"
    run_generator(db_path)
    # Test-only indexes for the reachability queries; the demo schema indexes
    # the columns the product needs, not necessarily the ones tests probe.
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_test_rep "
            "ON leads(owner_rep, closed_at)"
        )
    return db_path


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def scalar(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> object:
    row = connection.execute(sql, params).fetchone()
    return None if row is None else row[0]


# ---------------------------------------------------------------------------
# Volume, window, and the single-writer rule
# ---------------------------------------------------------------------------


def test_row_counts_and_single_writer(demo_db: Path) -> None:
    with connect(demo_db) as connection:
        assert scalar(connection, "SELECT COUNT(*) FROM companies") == 20_000
        assert scalar(connection, "SELECT COUNT(*) FROM leads") == 60_000
        # The decisive integration assertion: B1's ml/features.py is the only
        # writer of lead_features.
        assert scalar(connection, "SELECT COUNT(*) FROM lead_features") == 0

        # 24 months of lead history ending at t0.
        minimum_lead = scalar(connection, "SELECT MIN(created_at) FROM leads")
        maximum_lead = scalar(connection, "SELECT MAX(created_at) FROM leads")
        assert isinstance(minimum_lead, str) and isinstance(maximum_lead, str)
        assert datetime.fromisoformat(minimum_lead) >= datetime.fromisoformat(
            HISTORY_START
        )
        assert datetime.fromisoformat(maximum_lead) <= T0_DT

        # No raw timestamp may point into the future.
        timestamp_checks = {
            "companies.created_at": "companies.created_at",
            "leads.created_at": "leads.created_at",
            "leads.first_response_at": "leads.first_response_at",
            "leads.qualified_at": "leads.qualified_at",
            "leads.proposal_at": "leads.proposal_at",
            "leads.closed_at": "leads.closed_at",
            "tickets.opened_at": "tickets.opened_at",
            "tickets.closed_at": "tickets.closed_at",
            "invoices.issued_at": "invoices.issued_at",
            "invoices.due_at": "invoices.due_at",
            "invoices.paid_at": "invoices.paid_at",
            "nps_surveys.surveyed_at": "nps_surveys.surveyed_at",
            "interactions.occurred_at": "interactions.occurred_at",
            "lead_outcomes.closed_at": "lead_outcomes.closed_at",
        }
        for label, column in timestamp_checks.items():
            future = scalar(
                connection,
                f"SELECT COUNT(*) FROM {column.split('.')[0]} WHERE {column} > ?",
                (T0,),
            )
            assert future == 0, f"{label} contains a value after t0"

        # Weekly usage is only materialised for weeks that ended by t0.
        last_week = scalar(connection, "SELECT MAX(week_start) FROM company_usage_weekly")
        assert isinstance(last_week, str)
        assert (
            datetime.fromisoformat(last_week + "T00:00:00")
            + timedelta(days=7)
            <= T0_DT
        )

        assert {
            row[0] for row in connection.execute("SELECT DISTINCT region FROM companies")
        } == REGIONS
        assert {
            row[0] for row in connection.execute("SELECT DISTINCT source FROM leads")
        } == SOURCES


def test_degenerate_cli_targets_terminate_and_fail_fast(tmp_path: Path) -> None:
    """Odd --companies/--leads combinations must not hang.

    A single company can hold 20 ordinary leads plus 90 rep-history seeds, so
    110 is the hard limit.  111 must fail fast with that limit in the message;
    zero must still be a valid, terminating world.
    """
    zero_db = tmp_path / "zero.db"
    zero = subprocess.run(
        _generator_command(zero_db, ["--companies", "1", "--leads", "0", "--quiet"]),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert zero.returncode == 0, zero.stderr
    with connect(zero_db) as connection:
        assert scalar(connection, "SELECT COUNT(*) FROM companies") == 1
        assert scalar(connection, "SELECT COUNT(*) FROM leads") == 0
        assert scalar(connection, "SELECT COUNT(*) FROM lead_features") == 0

    feasible_db = tmp_path / "feasible.db"
    feasible = subprocess.run(
        _generator_command(
            feasible_db, ["--companies", "1", "--leads", "110", "--quiet"]
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert feasible.returncode == 0, feasible.stderr
    with connect(feasible_db) as connection:
        assert scalar(connection, "SELECT COUNT(*) FROM companies") == 1
        assert scalar(connection, "SELECT COUNT(*) FROM leads") == 110
        assert scalar(connection, "SELECT COUNT(*) FROM lead_features") == 0
        assert scalar(
            connection,
            """
            SELECT COUNT(*) FROM leads l
            JOIN companies c ON c.id = l.company_id
            WHERE l.created_at < c.created_at
            """,
        ) == 0

    over_db = tmp_path / "over.db"
    over = subprocess.run(
        _generator_command(
            over_db, ["--companies", "1", "--leads", "111", "--quiet"]
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert over.returncode != 0, "111 leads must be rejected, not silently clipped"
    combined = over.stdout + over.stderr
    assert "limit is 110" in combined, combined


def test_refuses_to_overwrite_without_flag(tmp_path: Path) -> None:
    db_path = tmp_path / "guarded.db"
    first = subprocess.run(
        _generator_command(
            db_path, ["--companies", "1", "--leads", "10", "--quiet"]
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert first.returncode == 0, first.stderr

    guarded = subprocess.run(
        _generator_command(
            db_path, ["--companies", "1", "--leads", "10", "--quiet"]
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert guarded.returncode != 0, "existing --db must not be overwritten silently"
    assert "refusing to overwrite" in guarded.stdout + guarded.stderr

    allowed = subprocess.run(
        _generator_command(
            db_path,
            ["--companies", "1", "--leads", "10", "--quiet", "--overwrite"],
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert allowed.returncode == 0, allowed.stderr


def test_domain_invariants(demo_db: Path) -> None:
    with connect(demo_db) as connection:
        vat_pattern = re.compile(r"^\d{11}$")
        for (vat,) in connection.execute("SELECT vat_number FROM companies"):
            assert isinstance(vat, str) and vat_pattern.match(vat), vat
            assert _italian_vat_check(vat), vat

        assert scalar(connection, "SELECT COUNT(*) FROM companies WHERE employees <= 0") == 0
        assert scalar(connection, "SELECT COUNT(*) FROM leads WHERE amount_arr <= 0") == 0
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE discount_pct < 0 OR discount_pct > 100",
        ) == 0
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM nps_surveys WHERE score < -100 OR score > 100",
        ) == 0
        assert scalar(connection, "SELECT COUNT(*) FROM invoices WHERE amount <= 0") == 0

        # Lost leads carry a reason; won and open leads do not.
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE status = 'lost' AND lost_reason IS NULL",
        ) == 0
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE status = 'won' AND lost_reason IS NOT NULL",
        ) == 0
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE status IN ('new','contacted','qualified','proposal') "
            "AND lost_reason IS NOT NULL",
        ) == 0


# ---------------------------------------------------------------------------
# Label prevalence and regional ordering
# ---------------------------------------------------------------------------


def test_win_prevalence(demo_db: Path) -> None:
    with connect(demo_db) as connection:
        total = scalar(connection, "SELECT COUNT(*) FROM lead_outcomes")
        wins = scalar(connection, "SELECT SUM(won) FROM lead_outcomes")
        assert isinstance(total, int) and total > 0
        prevalence = wins / total
        assert 0.25 <= prevalence <= 0.30, (
            f"win prevalence {prevalence:.3%} outside the documented 25-30% band "
            f"({wins}/{total})"
        )

        closed_qualified = scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE qualified_at IS NOT NULL "
            "AND qualified_at <= ? AND status IN ('won','lost')",
            (T0,),
        )
        assert total == closed_qualified


def test_latent_signal_matches_seed42_reference(demo_db: Path) -> None:
    """The generating-process ceiling is a reference, not the model gate band.

    docs/LABEL.md pins the seed-42 latent ceiling at ~0.78.  This is a
    regression assertion on the generating process itself: if it moves
    materially, the world changed and every downstream metric is invalid.
    """
    with connect(demo_db) as connection:
        rows = connection.execute(
            "SELECT latent_p, won FROM lead_outcomes ORDER BY lead_id"
        ).fetchall()
    probabilities = [row["latent_p"] for row in rows]
    labels = [row["won"] for row in rows]
    auc = _rank_auc(probabilities, labels)
    reference = 0.78
    tolerance = 0.01
    assert abs(auc - reference) <= tolerance, (
        f"generating-process AUC {auc:.3f} is outside the seed-42 reference "
        f"{reference:.2f} +/- {tolerance:.2f}"
    )


def test_regional_base_rate_ordering(demo_db: Path) -> None:
    """Region effects in LABEL.md: NE +0.05 > NW 0 = Centro 0 > Sud -0.10 > Isole -0.15.

    The realised *observed* rate for one seed is a Bernoulli sample, so the
    strict assertion is on the mean generating probability (much less noisy) and
    observed rates are checked within sampling error.  The +0.05 steps get a
    wider tolerance than the +0.10 steps.
    """
    with connect(demo_db) as connection:
        rows = connection.execute(
            """
            SELECT c.region,
                   AVG(o.latent_p) AS mean_p,
                   AVG(o.won)     AS observed_rate,
                   COUNT(*)       AS n
            FROM lead_outcomes o
            JOIN leads l      ON l.id = o.lead_id
            JOIN companies c  ON c.id = l.company_id
            GROUP BY c.region
            """
        ).fetchall()
    by_region = {row["region"]: row for row in rows}
    assert set(by_region) == REGIONS
    assert all(row["n"] > 3_000 for row in rows), "not enough outcomes per region"

    mean_p = {region: by_region[region]["mean_p"] for region in REGIONS}
    observed = {region: by_region[region]["observed_rate"] for region in REGIONS}

    # Generating base rate: the +0.05 step is allowed a small finite-sample
    # tolerance; the +0.10 step must be strict.
    assert mean_p["nord-est"] >= mean_p["nord-ovest"] - 0.005, mean_p
    assert abs(mean_p["nord-ovest"] - mean_p["centro"]) < 0.010, mean_p
    assert mean_p["nord-ovest"] > mean_p["sud"] > mean_p["isole"], mean_p

    # Observed rates agree with that order within normal sampling error.
    assert observed["nord-est"] >= observed["nord-ovest"] - 0.015, observed
    assert abs(observed["nord-ovest"] - observed["centro"]) <= 0.020, observed
    assert observed["centro"] >= observed["sud"] - 0.015, observed
    assert observed["sud"] >= observed["isole"] - 0.015, observed


# ---------------------------------------------------------------------------
# Censoring and raw point-in-time coherence
# ---------------------------------------------------------------------------


def test_lead_outcomes_contains_no_censored_lead(demo_db: Path) -> None:
    with connect(demo_db) as connection:
        # No lead still open at t0, and no lead that never reached qualified
        # (including the early-stage rep-history seeds), may appear in labels.
        assert scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM lead_outcomes o
            JOIN leads l ON l.id = o.lead_id
            WHERE l.status IN ('new','contacted','qualified','proposal')
               OR l.qualified_at IS NULL
               OR l.closed_at IS NULL
               OR l.closed_at > ?
            """,
            (T0,),
        ) == 0

        # Every qualified lead closed by t0 has exactly one outcome row.
        assert scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM leads l
            LEFT JOIN lead_outcomes o ON o.lead_id = l.id
            WHERE l.qualified_at IS NOT NULL
              AND l.qualified_at <= ?
              AND l.status IN ('won','lost')
              AND o.lead_id IS NULL
            """,
            (T0,),
        ) == 0

        # The label is the close status, and the outcome dates match the lead.
        assert scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM lead_outcomes o
            JOIN leads l ON l.id = o.lead_id
            WHERE o.won <> CASE WHEN l.status = 'won' THEN 1 ELSE 0 END
               OR o.closed_at <> l.closed_at
               OR o.snapshot_date <> l.qualified_at
            """,
        ) == 0

        assert scalar(
            connection,
            "SELECT COUNT(*) FROM lead_outcomes WHERE won NOT IN (0, 1)",
        ) == 0
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM lead_outcomes WHERE latent_p <= 0 OR latent_p >= 1",
        ) == 0


def test_leads_first_response_at_consistency(demo_db: Path) -> None:
    with connect(demo_db) as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(leads)").fetchall()
        }
        assert "first_response_at" in columns

        assert scalar(
            connection,
            """
            SELECT COUNT(*) FROM leads
            WHERE (first_response_at IS NULL) <> (first_response_hours IS NULL)
            """,
        ) == 0
        assert scalar(
            connection,
            """
            SELECT COUNT(*) FROM leads
            WHERE first_response_at IS NOT NULL
              AND (
                first_response_at < created_at
                OR first_response_at > ?
                OR (closed_at IS NOT NULL AND first_response_at > closed_at)
                OR ABS((julianday(first_response_at) - julianday(created_at)) * 24
                       - first_response_hours) > 0.11
              )
            """,
            (T0,),
        ) == 0

        # Both answered and unanswered leads exist.
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE first_response_at IS NOT NULL",
        ) > 0
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE first_response_at IS NULL",
        ) > 0


def test_answered_email_matches_first_response(demo_db: Path) -> None:
    with connect(demo_db) as connection:
        assert scalar(connection, """
            SELECT COUNT(*) FROM interactions i JOIN leads l ON l.id = i.lead_id
            WHERE i.kind = 'email' AND i.direction = 'inbound' AND i.answered = 1
              AND (l.first_response_at IS NULL OR i.occurred_at < l.first_response_at)
        """) == 0
        assert scalar(connection, """
            SELECT COUNT(*) FROM leads l
            LEFT JOIN (
                SELECT lead_id, MIN(occurred_at) AS first_answer
                FROM interactions
                WHERE kind = 'email' AND direction = 'inbound' AND answered = 1
                GROUP BY lead_id
            ) i ON i.lead_id = l.id
            WHERE l.first_response_at IS NOT NULL
              AND (i.first_answer IS NULL OR i.first_answer <> l.first_response_at)
        """) == 0


def test_raw_point_in_time_temporal_coherence(demo_db: Path) -> None:
    with connect(demo_db) as connection:
        # A lead can never exist before its company.
        assert scalar(
            connection,
            """
            SELECT COUNT(*) FROM leads l
            JOIN companies c ON c.id = l.company_id
            WHERE l.created_at < c.created_at
            """,
        ) == 0

        # A usage week can never have ended before its company existed.
        assert scalar(
            connection,
            """
            SELECT COUNT(*) FROM company_usage_weekly u
            JOIN companies c ON c.id = u.company_id
            WHERE date(u.week_start, '+7 days') <= date(c.created_at)
            """,
        ) == 0

        # created <= qualified <= proposal <= closed, wherever present.
        coherence_checks = (
            "qualified_at IS NOT NULL AND qualified_at < created_at",
            "proposal_at IS NOT NULL AND qualified_at IS NULL",
            "proposal_at IS NOT NULL AND proposal_at < qualified_at",
            "closed_at IS NOT NULL AND closed_at < created_at",
            "closed_at IS NOT NULL AND qualified_at IS NOT NULL AND closed_at < qualified_at",
            "closed_at IS NOT NULL AND proposal_at IS NOT NULL AND closed_at < proposal_at",
        )
        for condition in coherence_checks:
            assert scalar(
                connection, f"SELECT COUNT(*) FROM leads WHERE {condition}"
            ) == 0, condition

        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE status = 'proposal' "
            "AND proposal_at IS NULL",
        ) == 0

        # Status/timestamp agreement.  Closed-without-qualified is allowed only
        # for the early-stage rep-history seeds, which never enter the label.
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE status IN ('new','contacted') "
            "AND qualified_at IS NOT NULL",
        ) == 0
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE status IN ('qualified','proposal') "
            "AND closed_at IS NOT NULL",
        ) == 0
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE status IN ('won','lost') "
            "AND closed_at IS NULL",
        ) == 0
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM leads WHERE qualified_at IS NOT NULL "
            "AND status NOT IN ('qualified','proposal','won','lost')",
        ) == 0


# ---------------------------------------------------------------------------
# Raw-data reachability of measured / zero / not-measured states
# ---------------------------------------------------------------------------


def test_reachability_of_null_and_zero_states(demo_db: Path) -> None:
    with connect(demo_db) as connection:
        snapshot = (
            "CASE WHEN l.status IN ('won','lost') THEN l.qualified_at "
            "ELSE '2026-01-01T00:00:00' END"
        )
        rep_window = (
            "p.owner_rep = l.owner_rep AND p.id <> l.id "
            "AND p.status IN ('won','lost') AND p.closed_at IS NOT NULL "
            f"AND p.closed_at < {snapshot} "
            f"AND julianday(p.closed_at) >= julianday({snapshot}) - 180"
        )

        # -- NOT MEASURED: company never surveyed, with a scored lead --------
        assert scalar(
            connection,
            """
            SELECT EXISTS (
              SELECT 1 FROM leads l
              WHERE l.qualified_at IS NOT NULL
                AND NOT EXISTS (
                  SELECT 1 FROM nps_surveys n WHERE n.company_id = l.company_id
                )
              LIMIT 1
            )
            """,
        ) == 1

        # -- NOT MEASURED: company never invoiced, with a scored lead --------
        assert scalar(
            connection,
            """
            SELECT EXISTS (
              SELECT 1 FROM leads l
              WHERE l.qualified_at IS NOT NULL
                AND NOT EXISTS (
                  SELECT 1 FROM invoices i WHERE i.company_id = l.company_id
                )
              LIMIT 1
            )
            """,
        ) == 1

        # -- NOT MEASURED: fewer than two completed usage weeks at snapshot --
        assert scalar(
            connection,
            f"""
            SELECT EXISTS (
              SELECT 1 FROM leads l
              WHERE l.qualified_at IS NOT NULL
                AND (
                  SELECT COUNT(*) FROM company_usage_weekly u
                  WHERE u.company_id = l.company_id
                    AND u.week_start <= date({snapshot}, '-7 days')
                    AND u.week_start >= date({snapshot}, '-90 days')
                ) < 2
              LIMIT 1
            )
            """,
        ) == 1

        # -- NOT MEASURED: rep with no prior closure in the 180d window ------
        assert scalar(
            connection,
            f"""
            SELECT EXISTS (
              SELECT 1 FROM leads l
              WHERE l.qualified_at IS NOT NULL
                AND NOT EXISTS (
                  SELECT 1 FROM leads p WHERE {rep_window}
                )
              LIMIT 1
            )
            """,
        ) == 1

        # -- MEASURED ZERO: a *scored* lead with flat, observed usage --------
        assert scalar(
            connection,
            f"""
            SELECT EXISTS (
              SELECT 1 FROM leads l
              WHERE l.qualified_at IS NOT NULL
                AND (
                  SELECT COUNT(*) FROM company_usage_weekly u
                  WHERE u.company_id = l.company_id
                    AND u.week_start <= date({snapshot}, '-7 days')
                    AND u.week_start >= date({snapshot}, '-90 days')
                ) >= 2
                AND (
                  SELECT COUNT(DISTINCT u.events) FROM company_usage_weekly u
                  WHERE u.company_id = l.company_id
                    AND u.week_start <= date({snapshot}, '-7 days')
                    AND u.week_start >= date({snapshot}, '-90 days')
                ) = 1
              LIMIT 1
            )
            """,
        ) == 1

        # -- MEASURED ZERO: latest survey at/before snapshot is exactly zero --
        assert scalar(
            connection,
            f"""
            SELECT EXISTS (
              SELECT 1 FROM leads l
              WHERE l.qualified_at IS NOT NULL
                AND (
                  SELECT n.score FROM nps_surveys n
                  WHERE n.company_id = l.company_id
                    AND n.surveyed_at <= {snapshot}
                  ORDER BY n.surveyed_at DESC LIMIT 1
                ) = 0
              LIMIT 1
            )
            """,
        ) == 1

        # -- MEASURED ZERO: average invoice delay is 0 with >=1 eligible invoice
        assert scalar(
            connection,
            f"""
            SELECT EXISTS (
              SELECT 1 FROM leads l
              WHERE l.qualified_at IS NOT NULL
                AND (
                  SELECT COUNT(*) FROM invoices i
                  WHERE i.company_id = l.company_id
                    AND i.due_at <= {snapshot}
                    AND julianday(i.due_at) >= julianday({snapshot}) - 180
                ) > 0
                AND (
                  SELECT AVG(
                    CASE
                      WHEN i.paid_at IS NOT NULL AND i.paid_at <= {snapshot}
                      THEN julianday(date(i.paid_at)) - julianday(date(i.due_at))
                      ELSE julianday(date({snapshot})) - julianday(date(i.due_at))
                    END
                  )
                  FROM invoices i
                  WHERE i.company_id = l.company_id
                    AND i.due_at <= {snapshot}
                    AND julianday(i.due_at) >= julianday({snapshot}) - 180
                ) = 0.0
              LIMIT 1
            )
            """,
        ) == 1

        # -- MEASURED ZERO: a rep with exactly one prior closure, lost ------
        assert scalar(
            connection,
            f"""
            SELECT EXISTS (
              SELECT 1 FROM leads l
              WHERE l.qualified_at IS NOT NULL
                AND (SELECT COUNT(*) FROM leads p WHERE {rep_window}) = 1
                AND (SELECT COUNT(*) FROM leads p
                     WHERE {rep_window} AND p.status = 'won') = 0
              LIMIT 1
            )
            """,
        ) == 1


# ---------------------------------------------------------------------------
# Numerical hygiene and determinism
# ---------------------------------------------------------------------------


def test_no_nan_in_numeric_columns(demo_db: Path) -> None:
    with connect(demo_db) as connection:
        for table in TABLES:
            columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
            for column in columns:
                column_name = column["name"]
                column_type = (column["type"] or "").upper()
                if (
                    "INT" not in column_type
                    and "REAL" not in column_type
                    and "NUM" not in column_type
                ):
                    continue
                nullable = not bool(column["notnull"])
                null_count = scalar(
                    connection,
                    f"SELECT COUNT(*) FROM {table} WHERE {column_name} IS NULL",
                )
                if not nullable:
                    assert null_count == 0, f"{table}.{column_name} is NULL"
                values = connection.execute(
                    f"SELECT {column_name} FROM {table} "
                    f"WHERE {column_name} IS NOT NULL"
                )
                for (value,) in values:
                    assert isinstance(value, (int, float)), (
                        f"{table}.{column_name} contains non-numeric {value!r}"
                    )
                    assert math.isfinite(float(value)), (
                        f"{table}.{column_name} contains non-finite {value!r}"
                    )


def test_determinism(demo_db: Path, tmp_path: Path) -> None:
    second_db = tmp_path / "demo-second.db"
    run_generator(second_db)

    with connect(demo_db) as first, connect(second_db) as second:
        for table in TABLES:
            first_count = scalar(first, f"SELECT COUNT(*) FROM {table}")
            second_count = scalar(second, f"SELECT COUNT(*) FROM {table}")
            assert first_count == second_count, (
                f"{table} row count differs: {first_count} != {second_count}"
            )

        first_outcomes = first.execute(
            "SELECT COUNT(*), COALESCE(SUM(won), 0) FROM lead_outcomes"
        ).fetchone()
        second_outcomes = second.execute(
            "SELECT COUNT(*), COALESCE(SUM(won), 0) FROM lead_outcomes"
        ).fetchone()
        assert tuple(first_outcomes) == tuple(second_outcomes), (
            f"outcome counts differ: {tuple(first_outcomes)} != {tuple(second_outcomes)}"
        )

        # Stronger than row counts: the raw world and the labels are identical.
        assert _table_hash(first, "companies", "id") == _table_hash(
            second, "companies", "id"
        )
        assert _table_hash(first, "leads", "id") == _table_hash(second, "leads", "id")
        assert _table_hash(first, "lead_outcomes", "lead_id") == _table_hash(
            second, "lead_outcomes", "lead_id"
        )
        for table, primary_key in (
            ("company_usage_weekly", "company_id, week_start"),
            ("tickets", "id"),
            ("invoices", "id"),
            ("nps_surveys", "company_id, surveyed_at"),
            ("interactions", "id"),
        ):
            assert _table_hash(first, table, primary_key) == _table_hash(
                second, table, primary_key
            ), table



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _italian_vat_check(vat: str) -> bool:
    if len(vat) != 11 or not vat.isdigit():
        return False
    total = 0
    for index, char in enumerate(vat[:10]):
        digit = int(char)
        if index % 2 == 0:
            total += digit
        else:
            doubled = digit * 2
            total += doubled - 9 if doubled > 9 else doubled
    return (10 - (total % 10)) % 10 == int(vat[10])


def _rank_auc(probabilities: list[float], labels: list[int]) -> float:
    pairs = sorted(zip(probabilities, labels), key=lambda item: item[0])
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return 0.5
    rank_sum = 0.0
    index = 0
    while index < len(pairs):
        end = index + 1
        while end < len(pairs) and pairs[end][0] == pairs[index][0]:
            end += 1
        average_rank = (index + 1 + end) / 2.0
        rank_sum += average_rank * sum(label for _, label in pairs[index:end])
        index = end
    return (rank_sum - positives * (positives + 1) / 2.0) / (
        positives * negatives
    )


def _table_hash(connection: sqlite3.Connection, table: str, key: str) -> str:
    digest = hashlib.sha256()
    for row in connection.execute(f"SELECT * FROM {table} ORDER BY {key}"):
        digest.update(repr(tuple(row)).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


@pytest.fixture
def small_world():
    company = generator.generate_companies(random.Random(42), 1)[0]
    world = generator.RawWorld(
        companies=[company], company_by_id={company.id: company},
        company_leads={company.id: []}, usage_by_company={company.id: {}},
        week_starts=[], tickets_by_company={}, invoices_by_company={},
        nps_by_company={}, meetings_by_lead={},
    )
    return company, world


@pytest.mark.parametrize("resolution", [float("nan"), float("inf"), -float("inf")])
def test_invalid_ticket_preserves_existing_database(tmp_path, small_world, resolution):
    company, world = small_world
    destination = tmp_path / "existing.db"
    # A failure after schema creation must preserve even a non-SQLite destination.
    destination.write_bytes(b"existing database")
    tickets = [
        (f"T{i}", company.id, T0, T0, "low", 0.0) for i in range(201)
    ]
    tickets.append(("invalid", company.id, T0, T0, "low", resolution))
    with pytest.raises(ValueError, match="resolution_hours must be finite"):
        generator.write_database(
            destination, [company], [], world, [], tickets, [], [], overwrite=True
        )
    assert destination.read_bytes() == b"existing database"
    assert list(tmp_path.iterdir()) == [destination]


def test_nullable_resolution_and_failed_publication(tmp_path, small_world, monkeypatch):
    company, world = small_world
    destination = tmp_path / "existing.db"
    tickets = [("T1", company.id, T0, None, "low", None)]
    generator.write_database(destination, [company], [], world, [], tickets, [], [])
    original = destination.read_bytes()

    def fail_replace(source, target):
        # The replacement is a committed database before publication.
        with sqlite3.connect(source) as connection:
            assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 1
        raise OSError("publication failed")

    monkeypatch.setattr(generator.os, "replace", fail_replace)
    with pytest.raises(OSError, match="publication failed"):
        generator.write_database(
            destination, [company], [], world, [], tickets, [], [], overwrite=True
        )
    assert destination.read_bytes() == original
    assert list(tmp_path.iterdir()) == [destination]


def test_signed_payment_delays(small_world):
    company, world = small_world
    lead = generator.Lead(
        id="L1", company_id=company.id, created_at=T0_DT - timedelta(days=200),
        source="inbound", owner_rep=company.owner_rep, first_response_hours=None,
        first_response_at=None, qualified_at=None, proposal_at=None, closed_at=None,
        amount_arr=1000.0, discount_pct=0.0,
    )
    due = T0_DT - timedelta(days=10)
    world.invoices_by_company[company.id] = [
        (due, due - timedelta(days=6)),  # early: -6
        (due, due),  # on time: 0
        (due, due + timedelta(days=2)),  # late: 2
        (due, None),  # unpaid: 10
        (due, T0_DT + timedelta(days=1)),  # future payment: 10
        (T0_DT - timedelta(days=181), None),  # outside window
        (T0_DT + timedelta(days=1), None),  # not due yet
    ]
    values = generator.compute_feature_values(
        lead, company, T0_DT, "qualified", world, {}, {}
    )
    assert values["payment_delay_days_avg_180d"] == 3.2
