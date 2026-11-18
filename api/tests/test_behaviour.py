"""Behavioural tests for ``api/app.py`` — the things a schema cannot check.

The contract tests prove every response is *shaped* like ``api/openapi.yaml``. These tests
prove the numbers are right: the pipeline is really ranked by expected value, the filters
really filter, a closed lead really cannot have a counterfactual, an action really writes
exactly one row, dormancy really follows the 180-day rule, and the portfolio really adds up.

They run against a small **planted world** rather than ``data/demo.db`` for the same reason
``ml/tests/test_train.py`` does: the demo database is regenerable and never committed, so a
test that read it would pass on the demo laptop and fail in CI. The world comes from the real
generator, goes through the real ``ml/features.py``, and is scored by the committed model
artifact — the service is tested end to end against the same pipeline shape it will serve.

Shared fixture: ``test_contract.py`` imports the ``api``/``demo_db`` fixtures from this module
because the lane's deliverables are exactly these two test files; the world-building helper
lives here so both suites use the *same* database shape.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.app import DORMANCY_DAYS, create_app  # noqa: E402
from data import generator  # noqa: E402
from ml import explain, train  # noqa: E402
from ml.features import build_features  # noqa: E402

MODEL_PATH = REPO_ROOT / "ml" / "artifacts" / "model.joblib"
REGIONS = ("nord-ovest", "nord-est", "centro", "sud", "isole")

# 120 companies x 3 initiatives is large enough for every stage, both win classes and dormant
# companies to appear, and small enough that the whole module builds in a few seconds.
API_COMPANIES = 120

# Companies planted at the dormancy boundary, relative to the world's snapshot date. The exact
# 179/180/181 split is the rule's edge; "today" and "never" cover the other two branches.
DORMANCY_PROBES: tuple[tuple[str, int | None], ...] = (
    ("C-ASOF-TODAY", 0),
    ("C-ASOF-179", 179),
    ("C-ASOF-180", 180),
    ("C-ASOF-181", 181),
    ("C-NO-INITIATIVES", None),
)


# --------------------------------------------------------------------------------------
# database helpers
# --------------------------------------------------------------------------------------


def _connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _rows(db_path: str | Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with closing(_connect(db_path)) as connection:
        return connection.execute(sql, params).fetchall()


def _scalar(db_path: str | Path, sql: str, params: tuple = ()) -> object:
    with closing(_connect(db_path)) as connection:
        return connection.execute(sql, params).fetchone()[0]


def as_of_date(db_path: str | Path) -> date:
    """The world's "today": the latest feature snapshot, exactly what the API uses."""
    snapshot = _scalar(db_path, "SELECT MAX(snapshot_date) FROM lead_features")
    assert snapshot is not None, "the fixture world must have feature rows"
    return date.fromisoformat(str(snapshot)[:10])


def open_lead_ids(db_path: str | Path) -> list[str]:
    placeholders = ", ".join("?" for _ in train.OPEN_STATUSES)
    return [
        str(row["id"])
        for row in _rows(
            db_path,
            "SELECT l.id FROM leads AS l JOIN lead_scores AS s ON s.lead_id = l.id "
            f"WHERE l.status IN ({placeholders}) ORDER BY l.id",
            train.OPEN_STATUSES,
        )
    ]


def closed_lead_ids(db_path: str | Path) -> list[str]:
    return [
        str(row["id"])
        for row in _rows(
            db_path,
            "SELECT id FROM leads WHERE status IN ('won', 'lost') ORDER BY id",
        )
    ]


def feature_row(db_path: str | Path, lead_id: str) -> dict:
    row = _rows(db_path, "SELECT * FROM lead_features WHERE lead_id = ?", (lead_id,))
    assert row, f"lead {lead_id} has no feature row"
    return dict(row[0])


def action_count(db_path: str | Path, lead_id: str, kind: str | None = None) -> int:
    if kind is None:
        return int(
            _scalar(db_path, "SELECT COUNT(*) FROM actions WHERE lead_id = ?", (lead_id,))
        )
    return int(
        _scalar(
            db_path,
            "SELECT COUNT(*) FROM actions WHERE lead_id = ? AND kind = ?",
            (lead_id, kind),
        )
    )


def expected_leverage(bundle: dict, row: dict) -> tuple[float, dict[str, float]]:
    """Independently reproduce the three single-lever deltas for one feature row.

    Deliberately not the service's helper: the test states the lever mapping from
    ``docs/LABEL.md`` itself (+1 meeting / +5 NPS, and discount to 0 as the best discount).
    """
    current = float(train.predict(bundle, row)[0])

    sponsor = dict(row)
    sponsor["meetings_before_scoring"] = float(row["meetings_before_scoring"] or 0.0) + 1.0
    if row["nps_last"] is not None:
        sponsor["nps_last"] = min(float(row["nps_last"]) + 5.0, 100.0)

    discovery = dict(row)
    discovery["meetings_before_scoring"] = float(row["meetings_before_scoring"] or 0.0) + 1.0

    discount = dict(row)
    discount["discount_pct"] = 0.0

    return current, {
        "exec_sponsor_meeting": float(train.predict(bundle, sponsor)[0]) - current,
        "discovery_meeting": float(train.predict(bundle, discovery)[0]) - current,
        "discount_pct": float(train.predict(bundle, discount)[0]) - current,
    }


def expected_psi(expected: np.ndarray, actual: np.ndarray, edges: np.ndarray) -> float:
    """The PSI definition the stability panel is stated in, written out in the test."""
    expected_hist = np.histogram(
        np.clip(expected, edges[0], edges[-1]), bins=edges
    )[0].astype("float64")
    actual_hist = np.histogram(
        np.clip(actual, edges[0], edges[-1]), bins=edges
    )[0].astype("float64")
    expected_share = expected_hist / expected_hist.sum()
    actual_share = actual_hist / actual_hist.sum()
    epsilon = 1e-6
    expected_share = np.where(expected_share == 0.0, epsilon, expected_share)
    actual_share = np.where(actual_share == 0.0, epsilon, actual_share)
    return float(np.sum((actual_share - expected_share) * np.log(actual_share / expected_share)))


# --------------------------------------------------------------------------------------
# the planted world, built once per test module
# --------------------------------------------------------------------------------------


def _insert_dormancy_probes(connection: sqlite3.Connection) -> None:
    """Add companies whose latest initiative sits exactly on the 180-day boundary.

    The generated world contains dormant and active companies, but not deterministically at
    179/180/181 days; planting the edge is what turns "the flag is roughly right" into a
    boundary assertion. The probes are ``new`` leads with no score row, so they cannot leak
    into the pipeline or portfolio aggregates.
    """
    snapshot = connection.execute("SELECT MAX(snapshot_date) FROM lead_features").fetchone()[0]
    as_of = date.fromisoformat(str(snapshot)[:10])

    connection.execute(
        "INSERT INTO companies (id, name, vat_number, region, city, industry, employees, "
        "created_at, owner_rep) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "C-NO-INITIATIVES",
            "Never Proposed S.r.l.",
            "IT00000000001",
            "centro",
            "Roma",
            "Servizi",
            40,
            (as_of - timedelta(days=400)).isoformat(),
            "rep-boundary",
        ),
    )

    for company_id, offset in DORMANCY_PROBES:
        if offset is None:
            continue
        created = (as_of - timedelta(days=offset)).isoformat()
        connection.execute(
            "INSERT INTO companies (id, name, vat_number, region, city, industry, employees, "
            "created_at, owner_rep) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                company_id,
                f"Dormancy probe {offset}",
                f"IT0000000{offset:04d}",
                "centro",
                "Roma",
                "Servizi",
                55,
                created,
                "rep-boundary",
            ),
        )
        connection.execute(
            "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
            "first_response_hours, first_response_at, qualified_at, proposal_at, closed_at, "
            "lost_reason, amount_arr, discount_pct) "
            "VALUES (?, ?, ?, 'new', 'inbound', 'rep-boundary', NULL, NULL, NULL, NULL, NULL, "
            "NULL, 10000.0, 0.0)",
            (f"L-{company_id}", company_id, f"{created}T09:00:00"),
        )


def build_demo_database(db_path: Path) -> Path:
    """Generate, materialise features, and score the open pipeline with the committed model.

    The model is *loaded*, not retrained: the API only ever reads the artifact the demo ships,
    and training is already covered by ``ml/tests``. Scoring exercises the same
    ``score_open_leads``/``write_scores`` path that produced ``data/demo.db``.
    """
    generator.generate(db_path, seed=42, companies_count=API_COMPANIES, quiet=True)
    bundle = explain.load_bundle(MODEL_PATH)

    connection = sqlite3.connect(str(db_path))
    try:
        connection.row_factory = sqlite3.Row
        build_features(connection)
        frame = pd.read_sql_query("SELECT * FROM lead_features", connection)
        placeholders = ", ".join("?" for _ in train.OPEN_STATUSES)
        open_ids = [
            str(row[0])
            for row in connection.execute(
                f"SELECT id FROM leads WHERE status IN ({placeholders}) ORDER BY id",
                train.OPEN_STATUSES,
            )
        ]
        scores = train.score_open_leads(frame, open_ids, bundle)
        train.write_scores(
            connection,
            scores,
            datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        _insert_dormancy_probes(connection)
        connection.commit()
    finally:
        connection.close()
    return db_path


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("api-world")
    return build_demo_database(directory / "demo.db")


@pytest.fixture(scope="module")
def api(demo_db: Path):
    """A TestClient running the real lifespan (model loaded, not mocked)."""
    application = create_app(db_path=demo_db, model_path=MODEL_PATH)
    with TestClient(application) as client:
        yield client


@pytest.fixture(scope="module")
def bundle() -> dict:
    return explain.load_bundle(MODEL_PATH)


# --------------------------------------------------------------------------------------
# health
# --------------------------------------------------------------------------------------


def test_health_names_the_loaded_model_and_a_real_score_time(
    api: TestClient, demo_db: Path
) -> None:
    response = api.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_version"] == _scalar(
        demo_db, "SELECT DISTINCT model_version FROM lead_scores"
    )
    # date-time, and it is the batch's scored_at, not "now" invented by the service
    parsed = datetime.fromisoformat(body["scored_at"].replace("Z", "+00:00"))
    batch_scored_at = _scalar(demo_db, "SELECT MAX(scored_at) FROM lead_scores")
    assert parsed.date() == date.fromisoformat(str(batch_scored_at)[:10])


# --------------------------------------------------------------------------------------
# pipeline: ranking and filters
# --------------------------------------------------------------------------------------


def test_pipeline_is_ordered_by_expected_value(api: TestClient, demo_db: Path) -> None:
    body = api.get("/api/pipeline", params={"limit": 200}).json()
    items = body["items"]
    assert len(items) >= 2, "the fixture world must have a pipeline to rank"
    assert body["total"] <= 200, "the fixture is meant to fit inside the contract's row cap"
    assert body["total"] == len(items), (
        "the fixture has fewer open leads than the 200-row cap, so total must equal the page"
    )

    expected_values = [item["expected_value"] for item in items]
    assert expected_values == sorted(expected_values, reverse=True), (
        "pipeline is not ranked by expected value"
    )
    for item in items:
        assert 0.0 <= item["probability"] <= 1.0
        assert item["status"] in train.OPEN_STATUSES
        assert item["amount_arr"] > 0.0
        assert item["expected_value"] == pytest.approx(
            item["probability"] * item["amount_arr"], rel=1e-9, abs=1e-6
        )
        assert item["top_driver"]["direction"] in ("increases", "decreases")
        assert item["top_driver"]["label"] and item["top_driver"]["value"]

    # total_expected_value is the filtered population's EV, not a page-level number
    pipeline_ev = float(
        _scalar(demo_db, "SELECT COALESCE(SUM(expected_value), 0) FROM lead_scores")
    )
    assert body["total_expected_value"] == pytest.approx(pipeline_ev, rel=1e-9)
    assert body["total_expected_value"] == pytest.approx(
        sum(expected_values), rel=1e-9
    )


def test_pipeline_region_filter_narrows_to_that_region(api: TestClient, demo_db: Path) -> None:
    region = "centro"
    body = api.get("/api/pipeline", params={"region": region, "limit": 200}).json()
    assert body["items"], "centro must have an open pipeline in the fixture world"
    assert all(item["region"] == region for item in body["items"])

    expected_total = int(
        _scalar(
            demo_db,
            "SELECT COUNT(*) FROM lead_scores AS s "
            "JOIN leads AS l ON l.id = s.lead_id "
            "JOIN companies AS c ON c.id = l.company_id WHERE c.region = ?",
            (region,),
        )
    )
    expected_ev = float(
        _scalar(
            demo_db,
            "SELECT COALESCE(SUM(s.expected_value), 0) FROM lead_scores AS s "
            "JOIN leads AS l ON l.id = s.lead_id "
            "JOIN companies AS c ON c.id = l.company_id WHERE c.region = ?",
            (region,),
        )
    )
    assert body["total"] == expected_total
    assert body["total_expected_value"] == pytest.approx(expected_ev, rel=1e-9)


def test_pipeline_limit_caps_the_page_not_the_totals(api: TestClient) -> None:
    full = api.get("/api/pipeline", params={"limit": 200}).json()
    limited = api.get("/api/pipeline", params={"limit": 3}).json()

    assert len(limited["items"]) == 3
    assert limited["total"] == full["total"]
    assert limited["total_expected_value"] == pytest.approx(
        full["total_expected_value"], rel=1e-12
    )
    assert [item["lead_id"] for item in limited["items"]] == [
        item["lead_id"] for item in full["items"][:3]
    ]


def test_pipeline_min_probability_filter(api: TestClient, demo_db: Path) -> None:
    full = api.get("/api/pipeline", params={"limit": 200}).json()
    probabilities = sorted(item["probability"] for item in full["items"])
    threshold = probabilities[len(probabilities) // 2]
    assert 0.0 < threshold < 1.0, "the fixture needs a mid-range probability to filter on"

    body = api.get(
        "/api/pipeline", params={"min_probability": threshold, "limit": 200}
    ).json()
    assert body["items"], "the filter kept nothing; the fixture is too thin for this test"
    assert all(item["probability"] >= threshold for item in body["items"])

    expected_total = int(
        _scalar(
            demo_db,
            "SELECT COUNT(*) FROM lead_scores WHERE probability >= ?",
            (threshold,),
        )
    )
    assert body["total"] == expected_total
    assert expected_total < full["total"], "the filter did not remove anything"


def test_pipeline_at_risk_sort_flips_the_ranking_to_exposure(api: TestClient) -> None:
    body = api.get("/api/pipeline", params={"sort": "at_risk", "limit": 200}).json()
    exposure = [
        (1.0 - item["probability"]) * item["amount_arr"] for item in body["items"]
    ]
    assert exposure == sorted(exposure, reverse=True), (
        "sort=at_risk must rank by (1 - p) * ARR"
    )
    # expected_value stays the contract's p * ARR even when risk is the sort key
    for item in body["items"]:
        assert item["expected_value"] == pytest.approx(
            item["probability"] * item["amount_arr"], rel=1e-9, abs=1e-6
        )


# --------------------------------------------------------------------------------------
# 404s
# --------------------------------------------------------------------------------------


def test_unknown_lead_is_404_with_the_error_shape(api: TestClient) -> None:
    response = api.get("/api/leads/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "unknown_lead"
    assert response.json()["detail"]


def test_unknown_company_is_404_with_the_error_shape(api: TestClient) -> None:
    response = api.get("/api/companies/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "unknown_company"
    assert response.json()["detail"]


# --------------------------------------------------------------------------------------
# lead 360
# --------------------------------------------------------------------------------------


def test_lead_detail_serves_the_stored_score_and_drivers(api: TestClient, demo_db: Path) -> None:
    lead_id = open_lead_ids(demo_db)[0]
    detail = api.get(f"/api/leads/{lead_id}").json()
    assert detail["lead"]["id"] == lead_id

    score_row = _rows(
        demo_db, "SELECT * FROM lead_scores WHERE lead_id = ?", (lead_id,)
    )[0]
    assert detail["score"]["probability"] == pytest.approx(float(score_row["probability"]))
    assert detail["score"]["band"] == score_row["band"]
    assert detail["score"]["model_version"] == score_row["model_version"]
    assert detail["score"]["expected_value"] == pytest.approx(
        float(score_row["expected_value"])
    )
    # `drivers_json` parses to exactly the Driver shape the response serves.
    stored = json.loads(score_row["drivers_json"])
    assert detail["drivers"] == stored
    assert 0 < len(detail["drivers"]) <= 3

    assert detail["company"]["id"] == _scalar(
        demo_db, "SELECT company_id FROM leads WHERE id = ?", (lead_id,)
    )
    for prior in detail["prior_initiatives"]:
        assert prior["id"] != lead_id
        assert prior["created_at"] <= detail["lead"]["created_at"], (
            "prior_initiatives must be earlier than the lead being viewed"
        )

    # Dormancy on the lead 360 uses the same 180-day rule as the company 360.
    company_id = detail["company"]["id"]
    last_initiative = _scalar(
        demo_db, "SELECT MAX(created_at) FROM leads WHERE company_id = ?", (company_id,)
    )
    days = max(0, (as_of_date(demo_db) - date.fromisoformat(str(last_initiative)[:10])).days)
    assert detail["company"]["dormant"] is (days >= DORMANCY_DAYS)


def test_closed_lead_gets_a_consistent_score_on_its_360(
    api: TestClient, bundle: dict, demo_db: Path
) -> None:
    lead_id = closed_lead_ids(demo_db)[0]
    response = api.get(f"/api/leads/{lead_id}")
    assert response.status_code == 200, (
        "a closed initiative still has a 360; lead_scores only covers the open pipeline, so "
        "the service must score the stored feature row with the same artifact"
    )
    detail = response.json()
    assert detail["lead"]["status"] in ("won", "lost")
    assert 0.0 <= detail["score"]["probability"] <= 1.0
    assert detail["score"]["model_version"] == bundle["model_version"]
    assert detail["score"]["band"] in ("low", "medium", "high", "critical")
    assert detail["drivers"], "a closed lead still gets its SHAP drivers"
    assert detail["max_leverage"] is None, (
        "a closed lead is not actionable; its lead 360 must not promise a lever"
    )


def test_lead_detail_max_leverage_is_the_best_lever(
    api: TestClient, bundle: dict, demo_db: Path
) -> None:
    lead_id = open_lead_ids(demo_db)[0]
    _, deltas = expected_leverage(bundle, feature_row(demo_db, lead_id))
    best = max(max(deltas.values()), 0.0)

    detail = api.get(f"/api/leads/{lead_id}").json()
    assert detail["max_leverage"] is not None
    assert detail["max_leverage"] == pytest.approx(best, abs=1e-9)
    assert detail["max_leverage"] >= 0.0

    # The summary field must agree with the counterfactual endpoint it is computed from.
    endpoint_deltas = []
    for body in (
        {"exec_sponsor_meeting": True},
        {"discovery_meeting": True},
        {"discount_pct": 0},
    ):
        response = api.post(f"/api/leads/{lead_id}/counterfactual", json=body)
        assert response.status_code == 200
        endpoint_deltas.append(response.json()["delta"])
    assert max(endpoint_deltas) == pytest.approx(detail["max_leverage"], abs=1e-9)


def test_pipeline_items_carry_the_same_max_leverage_as_the_lead_360(
    api: TestClient, demo_db: Path
) -> None:
    items = api.get("/api/pipeline", params={"limit": 3}).json()["items"]
    assert items
    for item in items:
        assert item["max_leverage"] is not None
        assert item["max_leverage"] >= 0.0
        detail = api.get(f"/api/leads/{item['lead_id']}").json()
        assert item["max_leverage"] == pytest.approx(detail["max_leverage"], abs=1e-12)


def test_company_360_lists_initiatives_most_recent_first(api: TestClient, demo_db: Path) -> None:
    company_id = _scalar(
        demo_db,
        "SELECT company_id FROM leads GROUP BY company_id HAVING COUNT(*) >= 2 "
        "ORDER BY company_id LIMIT 1",
    )
    assert company_id is not None, "the fixture must contain a company with history"
    detail = api.get(f"/api/companies/{company_id}").json()

    created = [initiative["created_at"] for initiative in detail["initiatives"]]
    assert created == sorted(created, reverse=True)
    assert {initiative["id"] for initiative in detail["initiatives"]} == {
        str(row["id"])
        for row in _rows(
            demo_db, "SELECT id FROM leads WHERE company_id = ?", (company_id,)
        )
    }

    won = int(
        _scalar(
            demo_db,
            "SELECT COUNT(*) FROM leads WHERE company_id = ? AND status = 'won'",
            (company_id,),
        )
    )
    lost = int(
        _scalar(
            demo_db,
            "SELECT COUNT(*) FROM leads WHERE company_id = ? AND status = 'lost'",
            (company_id,),
        )
    )
    lifetime = float(
        _scalar(
            demo_db,
            "SELECT COALESCE(SUM(amount_arr), 0) FROM leads WHERE company_id = ? "
            "AND status = 'won'",
            (company_id,),
        )
    )
    assert detail["signals"]["won"] == won
    assert detail["signals"]["lost"] == lost
    assert detail["signals"]["lifetime_won_arr"] == pytest.approx(lifetime)


# --------------------------------------------------------------------------------------
# dormancy: the 180-day rule, including its exact boundary
# --------------------------------------------------------------------------------------


def test_company_dormancy_matches_the_180_day_rule(api: TestClient, demo_db: Path) -> None:
    as_of = as_of_date(demo_db)
    rows = _rows(
        demo_db,
        "SELECT c.id, MAX(l.created_at) AS last_initiative FROM companies AS c "
        "LEFT JOIN leads AS l ON l.company_id = c.id GROUP BY c.id ORDER BY c.id",
    )
    assert len(rows) > API_COMPANIES, "the planted probe companies must be present"

    dormant_count = 0
    for row in rows:
        company_id = str(row["id"])
        last = row["last_initiative"]
        if last is None:
            expected_dormant, expected_days = False, 0
        else:
            days = (as_of - date.fromisoformat(str(last)[:10])).days
            expected_dormant, expected_days = days >= DORMANCY_DAYS, max(days, 0)

        signals = api.get(f"/api/companies/{company_id}").json()["signals"]
        assert signals["dormant"] is expected_dormant, (
            f"{company_id}: last initiative {last} from as-of {as_of}, "
            f"expected dormant={expected_dormant}"
        )
        assert signals["days_since_last_initiative"] == expected_days
        dormant_count += int(expected_dormant)

    assert 0 < dormant_count < len(rows), (
        "the generated world must contain both dormant and active companies, otherwise this "
        "test proves nothing about the flag"
    )


@pytest.mark.parametrize(
    ("company_id", "offset", "expected_dormant", "expected_days"),
    [
        ("C-ASOF-TODAY", 0, False, 0),
        ("C-ASOF-179", 179, False, 179),
        ("C-ASOF-180", 180, True, 180),
        ("C-ASOF-181", 181, True, 181),
        ("C-NO-INITIATIVES", None, False, 0),
    ],
)
def test_dormancy_boundary_is_180_days(
    api: TestClient,
    company_id: str,
    offset: int | None,
    expected_dormant: bool,
    expected_days: int,
) -> None:
    signals = api.get(f"/api/companies/{company_id}").json()["signals"]
    assert signals["dormant"] is expected_dormant
    assert signals["days_since_last_initiative"] == expected_days


# --------------------------------------------------------------------------------------
# counterfactual
# --------------------------------------------------------------------------------------


def test_counterfactual_for_closed_lead_is_422(api: TestClient, demo_db: Path) -> None:
    lead_id = closed_lead_ids(demo_db)[0]
    response = api.post(
        f"/api/leads/{lead_id}/counterfactual", json={"exec_sponsor_meeting": True}
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "closed_lead"
    assert "open" in body["detail"]


def test_counterfactual_unsupported_lever_is_422(api: TestClient, demo_db: Path) -> None:
    lead_id = open_lead_ids(demo_db)[0]
    # `accelerate_to_proposal` was removed from the contract: stage is unlearnable (DECISIONS).
    response = api.post(
        f"/api/leads/{lead_id}/counterfactual", json={"accelerate_to_proposal": True}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"

    empty = api.post(f"/api/leads/{lead_id}/counterfactual", json={})
    assert empty.status_code == 422
    assert empty.json()["error"] == "no_lever"


def test_counterfactual_is_the_same_model_on_a_levered_feature_row(
    api: TestClient, bundle: dict, demo_db: Path
) -> None:
    lead_id = open_lead_ids(demo_db)[0]
    row = feature_row(demo_db, lead_id)

    response = api.post(
        f"/api/leads/{lead_id}/counterfactual", json={"exec_sponsor_meeting": True}
    )
    assert response.status_code == 200
    body = response.json()

    # Independently reproduce the lever with the same bundle: +1 meeting, +5 NPS (capped),
    # and NULL NPS stays NULL because "never surveyed" is not zero.
    levered = dict(row)
    levered["meetings_before_scoring"] = float(row["meetings_before_scoring"] or 0.0) + 1.0
    if row["nps_last"] is not None:
        levered["nps_last"] = min(float(row["nps_last"]) + 5.0, 100.0)

    current_expected = float(train.predict(bundle, row)[0])
    levered_expected = float(train.predict(bundle, levered)[0])

    assert body["current_probability"] == pytest.approx(current_expected, abs=1e-9)
    assert body["hypothetical_probability"] == pytest.approx(levered_expected, abs=1e-9)
    assert body["delta"] == pytest.approx(levered_expected - current_expected, abs=1e-12)
    # Monotone constraints from docs/LABEL.md: more meetings cannot lower the probability.
    assert levered_expected >= current_expected - 1e-9
    assert body["explanation"]


def test_counterfactual_discount_lever_sets_the_discount_feature(
    api: TestClient, bundle: dict, demo_db: Path
) -> None:
    lead_id = open_lead_ids(demo_db)[0]
    row = feature_row(demo_db, lead_id)
    current_discount = float(row["discount_pct"] or 0.0)
    # Move away from the current value so the lever is observable in either direction.
    target = 60.0 if current_discount <= 0.0 else 0.0
    levered = dict(row)
    levered["discount_pct"] = target

    response = api.post(
        f"/api/leads/{lead_id}/counterfactual", json={"discount_pct": target}
    )
    assert response.status_code == 200
    body = response.json()
    current = float(train.predict(bundle, row)[0])
    expected = float(train.predict(bundle, levered)[0])
    assert body["hypothetical_probability"] == pytest.approx(expected, abs=1e-9)
    assert body["delta"] == pytest.approx(expected - current, abs=1e-12)
    # discount is monotone-decreasing in the hazard (docs/LABEL.md)
    if target < current_discount:
        assert expected >= current - 1e-9
    else:
        assert expected <= current + 1e-9


def test_counterfactual_does_not_write_a_score(api: TestClient, demo_db: Path) -> None:
    lead_id = open_lead_ids(demo_db)[1]
    before = int(
        _scalar(
            demo_db, "SELECT COUNT(*) FROM lead_scores WHERE lead_id = ?", (lead_id,)
        )
    )
    assert api.post(
        f"/api/leads/{lead_id}/counterfactual", json={"discovery_meeting": True}
    ).status_code == 200
    after = int(
        _scalar(
            demo_db, "SELECT COUNT(*) FROM lead_scores WHERE lead_id = ?", (lead_id,)
        )
    )
    assert after == before, "a counterfactual is a what-if; it must not rewrite the score"


# --------------------------------------------------------------------------------------
# actions: exactly one row, and the retention guard
# --------------------------------------------------------------------------------------


def _assert_no_more_than_one_open_action(db_path: Path, lead_id: str, kind: str) -> None:
    open_rows = _rows(
        db_path,
        "SELECT id FROM actions WHERE lead_id = ? AND kind = ? AND status = 'open'",
        (lead_id, kind),
    )
    assert len(open_rows) <= 1


def test_action_creates_exactly_one_row(api: TestClient, bundle: dict, demo_db: Path) -> None:
    lead_id = open_lead_ids(demo_db)[-1]
    kind = "discovery_meeting"
    before = action_count(demo_db, lead_id, kind)

    row = feature_row(demo_db, lead_id)
    levered = dict(row)
    levered["meetings_before_scoring"] = float(row["meetings_before_scoring"] or 0.0) + 1.0
    current = float(train.predict(bundle, row)[0])
    expected_after = float(train.predict(bundle, levered)[0])

    response = api.post(
        f"/api/leads/{lead_id}/actions", json={"kind": kind, "note": "Booked by the demo"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["action"]["kind"] == kind
    assert body["action"]["status"] == "open"
    assert body["action"]["created_by"]
    assert body["action"]["note"] == "Booked by the demo"
    assert body["probability_after"] == pytest.approx(expected_after, abs=1e-9)
    assert body["delta"] == pytest.approx(expected_after - current, abs=1e-12)
    assert body["delta"] >= -1e-12

    assert action_count(demo_db, lead_id, kind) == before + 1
    stored = _rows(
        demo_db,
        "SELECT id, kind, status, created_at, created_by, note FROM actions "
        "WHERE lead_id = ? ORDER BY created_at DESC",
        (lead_id,),
    )
    assert len(stored) == before + 1
    inserted = [row for row in stored if row["id"] == body["action"]["id"]]
    assert len(inserted) == 1
    assert inserted[0]["kind"] == kind
    assert inserted[0]["status"] == "open"
    assert inserted[0]["note"] == "Booked by the demo"
    _assert_no_more_than_one_open_action(demo_db, lead_id, kind)


def test_second_open_action_of_the_same_kind_is_rejected(
    api: TestClient, demo_db: Path
) -> None:
    lead_id = open_lead_ids(demo_db)[-1]
    kind = "exec_sponsor_meeting"
    first = api.post(f"/api/leads/{lead_id}/actions", json={"kind": kind})
    assert first.status_code == 201, first.text
    count_after_first = action_count(demo_db, lead_id, kind)

    duplicate = api.post(f"/api/leads/{lead_id}/actions", json={"kind": kind})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"] == "duplicate_action"
    assert duplicate.json()["detail"]
    assert action_count(demo_db, lead_id, kind) == count_after_first
    _assert_no_more_than_one_open_action(demo_db, lead_id, kind)

    # A *different* kind on the same lead is allowed: the guard is per-kind.
    other = api.post(f"/api/leads/{lead_id}/actions", json={"kind": "call"})
    assert other.status_code == 201
    assert action_count(demo_db, lead_id, "call") >= 1


def test_action_without_a_modelled_lever_keeps_the_probability(
    api: TestClient, bundle: dict, demo_db: Path
) -> None:
    lead_id = open_lead_ids(demo_db)[-2]
    current = float(train.predict(bundle, feature_row(demo_db, lead_id))[0])

    response = api.post(f"/api/leads/{lead_id}/actions", json={"kind": "call"})
    assert response.status_code == 201
    body = response.json()
    assert body["probability_after"] == pytest.approx(current, abs=1e-9)
    assert body["delta"] == pytest.approx(0.0, abs=1e-12)


def test_action_on_closed_lead_is_rejected(api: TestClient, demo_db: Path) -> None:
    lead_id = closed_lead_ids(demo_db)[0]
    before = action_count(demo_db, lead_id)
    response = api.post(f"/api/leads/{lead_id}/actions", json={"kind": "call"})
    assert response.status_code == 422
    assert response.json()["error"] == "closed_lead"
    assert action_count(demo_db, lead_id) == before


# --------------------------------------------------------------------------------------
# portfolio
# --------------------------------------------------------------------------------------


def test_portfolio_totals_equal_the_sum_over_regions(api: TestClient, demo_db: Path) -> None:
    portfolio = api.get("/api/portfolio").json()
    by_region = portfolio["by_region"]

    assert [entry["region"] for entry in by_region] == list(REGIONS), (
        "the executive view must cover all five macro-regions, even an empty one"
    )
    assert portfolio["total_expected_value"] == pytest.approx(
        sum(entry["expected_value"] for entry in by_region), rel=1e-9
    )

    scored_leads = int(_scalar(demo_db, "SELECT COUNT(*) FROM lead_scores"))
    assert sum(entry["open_leads"] for entry in by_region) == scored_leads

    pipeline = api.get("/api/pipeline", params={"limit": 200}).json()
    assert portfolio["total_expected_value"] == pytest.approx(
        pipeline["total_expected_value"], rel=1e-9
    )

    # Per-region totals must agree across the two endpoints.
    for entry in by_region:
        region_pipeline = api.get(
            "/api/pipeline", params={"region": entry["region"], "limit": 200}
        ).json()
        assert entry["open_leads"] == region_pipeline["total"]
        assert entry["expected_value"] == pytest.approx(
            region_pipeline["total_expected_value"], rel=1e-9
        )
        assert 0.0 <= entry["win_rate"] <= 1.0

        won, closed = _rows(
            demo_db,
            "SELECT "
            "COALESCE(SUM(CASE WHEN l.status = 'won' THEN 1 ELSE 0 END), 0), "
            "COALESCE(SUM(CASE WHEN l.status IN ('won', 'lost') THEN 1 ELSE 0 END), 0) "
            "FROM leads AS l JOIN companies AS c ON c.id = l.company_id "
            "WHERE c.region = ?",
            (entry["region"],),
        )[0]
        expected_win_rate = (float(won) / int(closed)) if closed else 0.0
        assert entry["win_rate"] == pytest.approx(expected_win_rate, abs=1e-12)


def test_portfolio_calibration_and_drift_are_populated(api: TestClient) -> None:
    portfolio = api.get("/api/portfolio").json()

    calibration = portfolio["calibration"]
    assert calibration, "the fixture has labelled leads, so the calibration curve cannot be empty"
    for point in calibration:
        assert 0.0 <= point["predicted"] <= 1.0
        assert 0.0 <= point["actual"] <= 1.0
    # The curve is a curve, not ten copies of one number.
    assert len({point["predicted"] for point in calibration}) == len(calibration)

    drift = portfolio["drift"]
    assert math.isfinite(drift["psi"]) and drift["psi"] >= 0.0
    assert drift["status"] in ("stable", "watch", "alert")


def test_portfolio_drift_is_train_vs_holdout_stability(
    api: TestClient, bundle: dict, demo_db: Path
) -> None:
    """Drift is model stability on unseen labelled leads, not the open queue.

    Computing it against the open pipeline would conflate survivor selection (leads still
    open are the ones not yet lost) with drift and always read "alert"; this pins the
    intended definition: PSI between the temporal train and holdout score distributions,
    binned with the calibration deciles.
    """
    with closing(_connect(demo_db)) as connection:
        labelled = train.load_labeled_leads(connection)
    split = train.temporal_split(labelled)

    all_scores = train.predict(bundle, labelled)
    edges = np.unique(np.quantile(all_scores, np.linspace(0.0, 1.0, 11)))
    train_scores = train.predict(bundle, split.train)
    holdout_scores = train.predict(bundle, split.validation)

    expected = expected_psi(train_scores, holdout_scores, edges)
    drift = api.get("/api/portfolio").json()["drift"]
    assert drift["psi"] == pytest.approx(expected, abs=1e-6)
    expected_status = (
        "stable" if expected < 0.1 else ("watch" if expected < 0.25 else "alert")
    )
    assert drift["status"] == expected_status


def test_portfolio_drift_statistics_match_the_split(
    api: TestClient, bundle: dict, demo_db: Path
) -> None:
    """The four stability numbers are the temporal split's own summary, not hardcoded."""
    with closing(_connect(demo_db)) as connection:
        labelled = train.load_labeled_leads(connection)
    split = train.temporal_split(labelled)

    train_scores = train.predict(bundle, split.train)
    holdout_scores = train.predict(bundle, split.validation)
    observed_holdout_win_rate = float(split.validation["won"].sum()) / len(split.validation)

    drift = api.get("/api/portfolio").json()["drift"]
    assert drift["train_mean"] == pytest.approx(float(train_scores.mean()), abs=1e-6)
    assert drift["holdout_mean"] == pytest.approx(float(holdout_scores.mean()), abs=1e-6)
    assert drift["train_win_rate"] == pytest.approx(
        float(split.train["won"].mean()), abs=1e-6
    )
    assert drift["holdout_win_rate"] == pytest.approx(observed_holdout_win_rate, abs=1e-6)
    # A higher-scoring holdout should show a higher win rate here; if it did not, the four
    # numbers would be internally inconsistent even if each matched its own column.
    assert drift["holdout_mean"] > drift["train_mean"]
    assert drift["holdout_win_rate"] > drift["train_win_rate"]
