"""Tests for ``serverless/app.py`` — the slim Vercel serverless entry point.

Uses a temporary SQLite database with the real schema, a small set of planted rows,
and a precomputed ``lead_leverage`` table so the full ML stack is never imported here.

Covers
------
* GET /api/health  → 200, schema-valid, correct status
* GET /api/pipeline → 200, schema-valid, expected_value ordering
* GET /api/pipeline?sort=at_risk → at_risk ordering
* GET /api/pipeline?region=... → region filter
* GET /api/pipeline?min_probability=... → probability filter
* GET /api/pipeline?limit=... → limit vs totals (total counts full population)
* Response bodies validated against ``api/openapi.yaml`` with jsonschema
  (same pattern as ``api/tests/test_contract.py``)
* No network access
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA_SQL = REPO_ROOT / "data" / "schema.sql"
CONTRACT_PATH = REPO_ROOT / "api" / "openapi.yaml"
CONTRACT = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
REGISTRY = Registry().with_resource(
    "urn:contract", Resource(contents=CONTRACT, specification=DRAFT202012)
)
FORMAT_CHECKER = FormatChecker()

# ---------------------------------------------------------------------------
# Contract validation helpers (same pattern as test_contract.py)
# ---------------------------------------------------------------------------


def _json_pointer(path: str) -> str:
    return path.replace("~", "~0").replace("/", "~1")


def _response_schema(path: str, method: str = "get", status: str = "200") -> str:
    return (
        f"/paths/{_json_pointer(path)}/{method}/responses/{status}"
        "/content/application~1json/schema"
    )


def _validate(instance: object, fragment: str) -> None:
    validator = Draft202012Validator(
        {"$ref": f"urn:contract#{fragment}"},
        registry=REGISTRY,
        format_checker=FORMAT_CHECKER,
    )
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        rendered = "\n".join(
            f"  at {'/'.join(str(p) for p in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise AssertionError(
            f"response does not match api/openapi.yaml at {fragment}:\n{rendered}\n"
            f"instance: {json.dumps(instance, ensure_ascii=False)[:2000]}"
        )


# ---------------------------------------------------------------------------
# Minimal test-world builder
# ---------------------------------------------------------------------------

SNAPSHOT_DATE = "2024-06-01"
SCORED_AT = "2024-06-01T12:00:00+00:00"
MODEL_VERSION = "lead-win-lgbm-v1"

# A tiny driver list that satisfies the Driver schema
_DRIVER = json.dumps([
    {
        "feature": "amount_arr",
        "label": "Proposed ARR",
        "contribution": 0.15,
        "value": "€100,000",
        "direction": "increases",
    }
])


def _make_db(tmp_path: Path) -> Path:
    """Create a minimal slim DB in ``tmp_path`` with the real schema.

    Uses ``isolation_level=None`` (autocommit) so every statement commits
    immediately — the same approach as ``scripts/build_slim_db.py``.  This
    avoids the ``executescript`` / implicit-transaction interaction in the
    default sqlite3 isolation mode.
    """
    db_path = tmp_path / "test.slim.db"
    schema_sql = SCHEMA_SQL.read_text(encoding="utf-8")

    # isolation_level=None → autocommit; every statement is its own transaction
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        # executescript() commits any pending tx and runs the DDL atomically
        conn.executescript(schema_sql)
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS lead_leverage ("
            "    lead_id TEXT PRIMARY KEY,"
            "    max_leverage REAL NOT NULL,"
            "    discount_upside REAL NOT NULL"
            ");"
        )

        # Bulk-insert all data in one explicit transaction
        conn.execute("BEGIN")

        # Two companies in different regions
        conn.execute("""
            INSERT INTO companies
              (id, name, vat_number, region, city, industry, employees, created_at, owner_rep)
            VALUES
              ('C-NW', 'Azienda Nord-Ovest', 'IT01234567890',
               'nord-ovest', 'Milano', 'Technology', 100, '2020-01-01', 'rep-a'),
              ('C-NE', 'Azienda Nord-Est', 'IT09876543210',
               'nord-est', 'Verona', 'Manufacturing', 200, '2020-01-01', 'rep-b')
        """)

        # Five open leads: 3 in nord-ovest, 2 in nord-est
        leads = [
            # (id, company_id, source, amount_arr, discount_pct)
            ("L-NW-1", "C-NW", "inbound",  150_000.0, 0.0),
            ("L-NW-2", "C-NW", "outbound",  80_000.0, 5.0),
            ("L-NW-3", "C-NW", "referral",  60_000.0, 0.0),
            ("L-NE-1", "C-NE", "partner",  120_000.0, 10.0),
            ("L-NE-2", "C-NE", "event",     40_000.0, 0.0),
        ]
        for lead_id, company_id, source, amount_arr, discount_pct in leads:
            conn.execute("""
                INSERT INTO leads
                  (id, company_id, created_at, status, source, owner_rep, amount_arr, discount_pct)
                VALUES (?, ?, '2024-01-15', 'qualified', ?, 'rep-a', ?, ?)
            """, (lead_id, company_id, source, amount_arr, discount_pct))

        # lead_features (snapshot_date must be consistent)
        for lead_id, company_id, source, amount_arr, discount_pct in leads:
            region = "nord-ovest" if company_id == "C-NW" else "nord-est"
            conn.execute("""
                INSERT INTO lead_features (
                  lead_id, snapshot_date, source, stage_at_scoring, age_days_at_scoring,
                  amount_arr, discount_pct, region, industry, employees,
                  company_age_days, prior_won_initiatives, prior_lost_initiatives,
                  days_since_last_initiative, lifetime_won_arr, open_initiatives_count,
                  tickets_90d, meetings_before_scoring
                ) VALUES (?, ?, ?, 'qualified', 90, ?, ?, ?, 'Technology', 100,
                          1500, 1, 0, 30, 50000.0, 1, 0, 2)
            """, (lead_id, SNAPSHOT_DATE, source, amount_arr, discount_pct, region))

        # lead_scores: different probabilities → different expected_values
        # L-NW-1: 0.70 * 150000 = 105000  ← highest EV
        # L-NE-1: 0.60 * 120000 =  72000
        # L-NW-2: 0.50 *  80000 =  40000
        # L-NW-3: 0.40 *  60000 =  24000
        # L-NE-2: 0.30 *  40000 =  12000  ← lowest EV
        scores = [
            ("L-NW-1", 0.70, "critical", 150_000.0, 105_000.0),
            ("L-NE-1", 0.60, "high",     120_000.0,  72_000.0),
            ("L-NW-2", 0.50, "high",      80_000.0,  40_000.0),
            ("L-NW-3", 0.40, "medium",    60_000.0,  24_000.0),
            ("L-NE-2", 0.30, "medium",    40_000.0,  12_000.0),
        ]
        for lead_id, prob, band, amount, ev in scores:
            conn.execute("""
                INSERT INTO lead_scores
                  (lead_id, scored_at, model_version, probability, band,
                   drivers_json, amount_arr, expected_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (lead_id, SCORED_AT, MODEL_VERSION, prob, band, _DRIVER, amount, ev))

        # lead_leverage (precomputed — no ML stack needed in tests)
        leverages = [
            ("L-NW-1", 0.05, 0.00),
            ("L-NE-1", 0.08, 0.10),
            ("L-NW-2", 0.06, 0.07),
            ("L-NW-3", 0.03, 0.00),
            ("L-NE-2", 0.04, 0.00),
        ]
        conn.executemany(
            "INSERT INTO lead_leverage (lead_id, max_leverage, discount_upside) VALUES (?, ?, ?)",
            leverages,
        )

        # model_runs
        conn.execute("""
            INSERT INTO model_runs (model_version, trained_at, metrics_json, artifact_path)
            VALUES (?, '2024-05-01T00:00:00', '{"auc": 0.773}', 'ml/artifacts/model.joblib')
        """, (MODEL_VERSION,))

        conn.execute("COMMIT")
        conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()

    return db_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def slim_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Module-scoped temp DB; built once, shared across all tests in this file."""
    return _make_db(tmp_path_factory.mktemp("slim_db"))


@pytest.fixture(scope="module")
def api(slim_db: Path) -> TestClient:
    """TestClient with CRM_DB_PATH pointing at the temp DB.

    Sets ``CRM_DB_PATH`` in ``os.environ`` directly (module scope; no monkeypatch).
    ``serverless.app._db_path()`` reads the env var at call time, so there is no
    need to reload the module.
    """
    os.environ["CRM_DB_PATH"] = str(slim_db)
    from serverless.app import app as serverless_app
    return TestClient(serverless_app)


# ---------------------------------------------------------------------------
# Health tests
# ---------------------------------------------------------------------------


def test_health_200(api: TestClient) -> None:
    response = api.get("/api/health")
    assert response.status_code == 200


def test_health_schema(api: TestClient) -> None:
    body = api.get("/api/health").json()
    _validate(body, _response_schema("/api/health"))


def test_health_ok_when_scores_exist(api: TestClient) -> None:
    body = api.get("/api/health").json()
    assert body["status"] == "ok"


def test_health_has_model_version_and_scored_at(api: TestClient) -> None:
    body = api.get("/api/health").json()
    assert body["model_version"] == MODEL_VERSION
    assert "scored_at" in body
    # scored_at must be a parseable datetime string
    dt = datetime.fromisoformat(body["scored_at"].replace("Z", "+00:00"))
    assert dt.year >= 2024


def test_health_degraded_on_missing_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the DB does not exist, /api/health returns 200 with status=degraded."""
    monkeypatch.setenv("CRM_DB_PATH", str(tmp_path / "nonexistent.db"))
    # _db_path() reads the env var at call time, so we just create a fresh TestClient.
    from serverless.app import app as serverless_app
    client = TestClient(serverless_app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    # monkeypatch automatically restores the original value at test teardown


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


def test_pipeline_200(api: TestClient) -> None:
    response = api.get("/api/pipeline")
    assert response.status_code == 200


def test_pipeline_schema(api: TestClient) -> None:
    body = api.get("/api/pipeline").json()
    _validate(body, _response_schema("/api/pipeline"))


def test_pipeline_items_schema(api: TestClient) -> None:
    body = api.get("/api/pipeline").json()
    for item in body["items"]:
        _validate(item, "/components/schemas/PipelineItem")


def test_pipeline_default_sort_by_expected_value(api: TestClient) -> None:
    """Items must be ordered by expected_value DESC by default."""
    body = api.get("/api/pipeline").json()
    items = body["items"]
    assert len(items) >= 2
    evs = [item["expected_value"] for item in items]
    assert evs == sorted(evs, reverse=True), f"expected_value not descending: {evs}"


def test_pipeline_sort_at_risk(api: TestClient) -> None:
    """sort=at_risk orders by (1-probability)*amount_arr DESC."""
    body = api.get("/api/pipeline", params={"sort": "at_risk"}).json()
    items = body["items"]
    assert len(items) >= 2
    # Compute at_risk values
    at_risk = [(1.0 - item["probability"]) * item["amount_arr"] for item in items]
    assert at_risk == sorted(at_risk, reverse=True), f"at_risk not descending: {at_risk}"


def test_pipeline_total_before_limit(api: TestClient) -> None:
    """total counts the whole filtered population; items is the page."""
    body_full = api.get("/api/pipeline").json()
    total_full = body_full["total"]

    body_limited = api.get("/api/pipeline", params={"limit": 2}).json()
    # total must reflect ALL matching leads, not just the returned items
    assert body_limited["total"] == total_full, (
        f"total={body_limited['total']} should equal full population {total_full} "
        f"regardless of limit=2"
    )
    assert len(body_limited["items"]) == 2


def test_pipeline_total_expected_value_before_limit(api: TestClient) -> None:
    """total_expected_value sums the full filtered population, not just the page."""
    body_full = api.get("/api/pipeline").json()
    tev_full = body_full["total_expected_value"]

    body_limited = api.get("/api/pipeline", params={"limit": 1}).json()
    assert body_limited["total_expected_value"] == pytest.approx(tev_full, rel=1e-6)


def test_pipeline_region_filter(api: TestClient) -> None:
    """?region=nord-ovest returns only nord-ovest items."""
    body = api.get("/api/pipeline", params={"region": "nord-ovest"}).json()
    for item in body["items"]:
        assert item["region"] == "nord-ovest"
    # We planted 3 nord-ovest leads
    assert body["total"] == 3


def test_pipeline_region_filter_nord_est(api: TestClient) -> None:
    body = api.get("/api/pipeline", params={"region": "nord-est"}).json()
    for item in body["items"]:
        assert item["region"] == "nord-est"
    assert body["total"] == 2


def test_pipeline_min_probability_filter(api: TestClient) -> None:
    """?min_probability=0.5 returns only items with probability >= 0.5."""
    body = api.get("/api/pipeline", params={"min_probability": 0.5}).json()
    for item in body["items"]:
        assert item["probability"] >= 0.5
    # L-NW-1 (0.70), L-NE-1 (0.60), L-NW-2 (0.50) → total=3
    assert body["total"] == 3


def test_pipeline_min_probability_zero(api: TestClient) -> None:
    """?min_probability=0 returns all open leads."""
    body = api.get("/api/pipeline", params={"min_probability": 0.0}).json()
    assert body["total"] == 5


def test_pipeline_items_have_top_driver(api: TestClient) -> None:
    body = api.get("/api/pipeline").json()
    for item in body["items"]:
        assert "top_driver" in item
        _validate(item["top_driver"], "/components/schemas/Driver")


def test_pipeline_items_have_leverage_fields(api: TestClient) -> None:
    """max_leverage and discount_upside are present (non-null) for open leads."""
    body = api.get("/api/pipeline").json()
    for item in body["items"]:
        assert item["max_leverage"] is not None, f"{item['lead_id']} missing max_leverage"
        assert 0.0 <= item["max_leverage"] <= 1.0
        assert item["discount_upside"] is not None, f"{item['lead_id']} missing discount_upside"
        assert item["discount_upside"] >= 0.0


def test_pipeline_days_open_uses_snapshot_not_wall_clock(api: TestClient) -> None:
    """days_open is computed from snapshot_date, not today, so it stays deterministic."""
    body = api.get("/api/pipeline").json()
    snapshot = date.fromisoformat(SNAPSHOT_DATE)
    created = date.fromisoformat("2024-01-15")
    expected_days = (snapshot - created).days
    for item in body["items"]:
        assert item["days_open"] == expected_days, (
            f"{item['lead_id']}: days_open={item['days_open']}, expected={expected_days}"
        )


def test_pipeline_combined_region_and_min_probability(api: TestClient) -> None:
    """Combining region and min_probability filters the intersection."""
    # nord-ovest leads with prob >= 0.5: L-NW-1 (0.70), L-NW-2 (0.50)
    body = api.get(
        "/api/pipeline",
        params={"region": "nord-ovest", "min_probability": 0.5},
    ).json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["region"] == "nord-ovest"
        assert item["probability"] >= 0.5


def test_pipeline_limit_max_200(api: TestClient) -> None:
    """limit=200 is the maximum allowed value and must not error."""
    response = api.get("/api/pipeline", params={"limit": 200})
    assert response.status_code == 200


def test_pipeline_limit_above_max_is_422(api: TestClient) -> None:
    response = api.get("/api/pipeline", params={"limit": 201})
    assert response.status_code == 422


def test_pipeline_empty_region_returns_zero(api: TestClient) -> None:
    """A region with no open leads returns total=0 and items=[]."""
    body = api.get("/api/pipeline", params={"region": "isole"}).json()
    assert body["total"] == 0
    assert body["items"] == []


# ---------------------------------------------------------------------------
# D7 guardrails: validation, surface reductions, headers
# ---------------------------------------------------------------------------


def test_pipeline_limit_below_min_is_422(api: TestClient) -> None:
    assert api.get("/api/pipeline", params={"limit": 0}).status_code == 422


def test_pipeline_min_probability_out_of_range_is_422(api: TestClient) -> None:
    assert api.get("/api/pipeline", params={"min_probability": 1.5}).status_code == 422


def test_pipeline_unknown_region_is_422(api: TestClient) -> None:
    assert api.get("/api/pipeline", params={"region": "atlantide"}).status_code == 422


def test_generated_docs_are_not_exposed(api: TestClient) -> None:
    assert api.get("/docs").status_code == 404
    assert api.get("/openapi.json").status_code == 404


def test_security_headers_present(api: TestClient) -> None:
    response = api.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_cors_allows_the_deployed_origin(api: TestClient) -> None:
    response = api.get(
        "/api/health", headers={"Origin": "https://crm-churn-demo.vercel.app"}
    )
    assert response.headers.get("access-control-allow-origin") == (
        "https://crm-churn-demo.vercel.app"
    )


def test_cors_rejects_an_unknown_origin(api: TestClient) -> None:
    response = api.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
