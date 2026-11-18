"""Contract tests: every endpoint's real response is validated against ``api/openapi.yaml``.

The schema is the file. These tests load ``api/openapi.yaml``, resolve its ``$ref``s with the
2020-12 dialect (OpenAPI 3.1's dialect), and validate the live HTTP responses with
``jsonschema``. There is deliberately no second, hand-written field list to drift: if the
contract and the service disagree, one of these tests fails and the diff is the disagreement.

Two fixture notes
    * The world is the tiny fixture from ``api/tests/test_behaviour.py`` (imported, not
      duplicated, because this lane's deliverables are exactly these two files). It is built
      from the real generator and scored by the committed artifact.
    * ``api/openapi.yaml`` is not modified by this lane. Where it is silent (``404`` on a
      company, the retention-guard ``409``), the service answers with the contract's own
      ``Error`` component and the test validates that shape under the documented reading.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import closing
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

# Importing the behaviour module also imports its module-scoped fixtures; pytest registers an
# imported fixture in this module's namespace, so both suites share one world-building helper.
from test_behaviour import (  # noqa: E402
    api,
    as_of_date,
    closed_lead_ids,
    demo_db,
    open_lead_ids,
)

CONTRACT_PATH = REPO_ROOT / "api" / "openapi.yaml"
CONTRACT = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
REGISTRY = Registry().with_resource(
    "urn:contract", Resource(contents=CONTRACT, specification=DRAFT202012)
)
FORMAT_CHECKER = FormatChecker()


# --------------------------------------------------------------------------------------
# contract machinery
# --------------------------------------------------------------------------------------


def _json_pointer(path: str) -> str:
    """Escape a literal string for a JSON pointer token (RFC 6901)."""
    return path.replace("~", "~0").replace("/", "~1")


def _response_schema(path: str, method: str = "get", status: str = "200") -> str:
    """The JSON-pointer fragment of a path response's ``application/json`` schema."""
    return (
        f"/paths/{_json_pointer(path)}/{method}/responses/{status}"
        "/content/application~1json/schema"
    )


def _validate(instance: object, fragment: str) -> None:
    """Validate one response against the schema at ``fragment`` in the contract."""
    validator = Draft202012Validator(
        {"$ref": f"urn:contract#{fragment}"},
        registry=REGISTRY,
        format_checker=FORMAT_CHECKER,
    )
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    if errors:
        rendered = "\n".join(
            f"  at {'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise AssertionError(
            f"response does not match api/openapi.yaml at {fragment}:\n{rendered}\n"
            f"instance: {json.dumps(instance, ensure_ascii=False)[:2000]}"
        )


def _query(db_path: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with closing(sqlite3.connect(str(db_path))) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(sql, params).fetchall()


# --------------------------------------------------------------------------------------
# coverage: the service implements the whole contract
# --------------------------------------------------------------------------------------


def test_app_implements_every_path_in_the_contract(api: TestClient) -> None:
    """No endpoint may be missing, and the service may not invent an ``/api`` one."""
    contract_paths = set(CONTRACT["paths"])
    assert contract_paths, "the contract has no paths"

    generated = set(api.app.openapi()["paths"])
    implemented = {path for path in generated if path.startswith("/api/")}
    assert implemented == contract_paths, (
        f"missing from the service: {sorted(contract_paths - implemented)}; "
        f"not in the contract: {sorted(implemented - contract_paths)}"
    )


def test_contract_is_openapi_3_1_with_the_components_this_lane_codes_against() -> None:
    assert str(CONTRACT["openapi"]).startswith("3.1")
    expected = {
        "Region",
        "Band",
        "Source",
        "Driver",
        "Lead",
        "PipelineItem",
        "LeadDetail",
        "CompanyDetail",
        "CounterfactualRequest",
        "CounterfactualResponse",
        "ActionRequest",
        "Action",
        "ActionResponse",
        "Portfolio",
        "Error",
    }
    assert expected <= set(CONTRACT["components"]["schemas"])


# --------------------------------------------------------------------------------------
# health
# --------------------------------------------------------------------------------------


def test_health_matches_contract(api: TestClient) -> None:
    response = api.get("/api/health")
    assert response.status_code == 200
    _validate(response.json(), _response_schema("/api/health"))


# --------------------------------------------------------------------------------------
# pipeline
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"limit": 5},
        {"region": "centro"},
        {"sort": "at_risk"},
        {"min_probability": 0.3},
        {"region": "nord-est", "limit": 2, "sort": "at_risk", "min_probability": 0.1},
    ],
)
def test_pipeline_matches_contract_for_every_query_shape(
    api: TestClient, params: dict
) -> None:
    response = api.get("/api/pipeline", params=params)
    assert response.status_code == 200
    body = response.json()
    _validate(body, _response_schema("/api/pipeline"))
    assert isinstance(body["items"], list)


def test_pipeline_item_drivers_match_the_driver_component(api: TestClient) -> None:
    body = api.get("/api/pipeline", params={"limit": 5}).json()
    assert body["items"]
    for item in body["items"]:
        _validate(item["top_driver"], "/components/schemas/Driver")


# --------------------------------------------------------------------------------------
# lead 360
# --------------------------------------------------------------------------------------


def test_open_lead_detail_matches_contract(api: TestClient, demo_db: Path) -> None:
    lead_id = open_lead_ids(demo_db)[0]
    response = api.get(f"/api/leads/{lead_id}")
    assert response.status_code == 200
    _validate(response.json(), _response_schema("/api/leads/{lead_id}"))


def test_closed_lead_detail_matches_contract(api: TestClient, demo_db: Path) -> None:
    lead_id = closed_lead_ids(demo_db)[0]
    response = api.get(f"/api/leads/{lead_id}")
    assert response.status_code == 200
    _validate(response.json(), _response_schema("/api/leads/{lead_id}"))


def test_stored_drivers_parse_to_the_driver_shape(api: TestClient, demo_db: Path) -> None:
    """``lead_scores.drivers_json`` is a JSON string in SQLite; it must surface as ``Driver``."""
    lead_id = open_lead_ids(demo_db)[0]
    stored = json.loads(
        _query(demo_db, "SELECT drivers_json FROM lead_scores WHERE lead_id = ?", (lead_id,))[0][
            "drivers_json"
        ]
    )
    assert stored
    for driver in stored:
        _validate(driver, "/components/schemas/Driver")

    detail = api.get(f"/api/leads/{lead_id}").json()
    assert detail["drivers"] == stored, (
        "the Lead 360 must serve the batch's drivers, not a re-worded copy"
    )


def test_unknown_lead_matches_the_error_component(api: TestClient) -> None:
    response = api.get("/api/leads/missing-lead")
    assert response.status_code == 404
    _validate(response.json(), "/components/schemas/Error")


# --------------------------------------------------------------------------------------
# counterfactual
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"exec_sponsor_meeting": True},
        {"discovery_meeting": True},
        {"discount_pct": 10},
        {"exec_sponsor_meeting": True, "discovery_meeting": True, "discount_pct": 5},
    ],
)
def test_counterfactual_matches_contract(api: TestClient, demo_db: Path, body: dict) -> None:
    lead_id = open_lead_ids(demo_db)[0]
    response = api.post(f"/api/leads/{lead_id}/counterfactual", json=body)
    assert response.status_code == 200
    _validate(
        response.json(),
        _response_schema("/api/leads/{lead_id}/counterfactual", method="post"),
    )


def test_counterfactual_closed_lead_matches_contract_error(api: TestClient, demo_db: Path) -> None:
    lead_id = closed_lead_ids(demo_db)[0]
    response = api.post(
        f"/api/leads/{lead_id}/counterfactual", json={"exec_sponsor_meeting": True}
    )
    assert response.status_code == 422
    _validate(response.json(), "/components/schemas/Error")


def test_counterfactual_unsupported_lever_matches_contract_error(
    api: TestClient, demo_db: Path
) -> None:
    lead_id = open_lead_ids(demo_db)[0]
    response = api.post(
        f"/api/leads/{lead_id}/counterfactual", json={"accelerate_to_proposal": True}
    )
    assert response.status_code == 422
    _validate(response.json(), "/components/schemas/Error")


# --------------------------------------------------------------------------------------
# actions
# --------------------------------------------------------------------------------------


def test_action_matches_contract(api: TestClient, demo_db: Path) -> None:
    # A lead the behaviour suite has not claimed, and a kind the counterfactual tests never
    # write, so the response is a fresh 201 rather than the retention guard's 409.
    lead_id = open_lead_ids(demo_db)[-1]
    response = api.post(
        f"/api/leads/{lead_id}/actions",
        json={"kind": "exec_sponsor_meeting", "note": "Written by the contract test"},
    )
    assert response.status_code == 201
    body = response.json()
    _validate(body, _response_schema("/api/leads/{lead_id}/actions", method="post", status="201"))
    _validate(body["action"], "/components/schemas/Action")

    duplicate = api.post(f"/api/leads/{lead_id}/actions", json={"kind": "exec_sponsor_meeting"})
    assert duplicate.status_code == 409
    _validate(duplicate.json(), "/components/schemas/Error")

    # `note` is a plain string in the contract, so an action without one must omit it rather
    # than serialise `null`.
    no_note = api.post(
        f"/api/leads/{open_lead_ids(demo_db)[-2]}/actions", json={"kind": "call"}
    )
    assert no_note.status_code == 201
    _validate(
        no_note.json(),
        _response_schema("/api/leads/{lead_id}/actions", method="post", status="201"),
    )
    assert "note" not in no_note.json()["action"]


def test_action_on_closed_lead_is_a_422_error(api: TestClient, demo_db: Path) -> None:
    lead_id = closed_lead_ids(demo_db)[0]
    response = api.post(f"/api/leads/{lead_id}/actions", json={"kind": "call"})
    assert response.status_code == 422
    _validate(response.json(), "/components/schemas/Error")


# --------------------------------------------------------------------------------------
# company 360
# --------------------------------------------------------------------------------------


def test_company_detail_matches_contract(api: TestClient, demo_db: Path) -> None:
    lead_id = open_lead_ids(demo_db)[0]
    company_id = _query(demo_db, "SELECT company_id FROM leads WHERE id = ?", (lead_id,))[0][0]
    response = api.get(f"/api/companies/{company_id}")
    assert response.status_code == 200
    body = response.json()
    _validate(body, _response_schema("/api/companies/{company_id}"))
    for initiative in body["initiatives"]:
        _validate(initiative, "/components/schemas/Lead")


def test_company_without_initiatives_matches_contract(api: TestClient) -> None:
    """A company with zero initiatives still owes the contract a complete ``CompanyDetail``."""
    response = api.get("/api/companies/C-NO-INITIATIVES")
    assert response.status_code == 200
    body = response.json()
    _validate(body, _response_schema("/api/companies/{company_id}"))
    assert body["initiatives"] == []
    assert body["signals"]["days_since_last_initiative"] == 0
    assert body["signals"]["dormant"] is False


def test_unknown_company_answers_with_the_error_component(api: TestClient) -> None:
    # The contract documents the 404 but no body schema for this path; the service answers
    # with ``Error`` anyway, and this pins the documented reading.
    response = api.get("/api/companies/missing-company")
    assert response.status_code == 404
    _validate(response.json(), "/components/schemas/Error")


# --------------------------------------------------------------------------------------
# portfolio
# --------------------------------------------------------------------------------------


def test_portfolio_matches_contract(api: TestClient) -> None:
    response = api.get("/api/portfolio")
    assert response.status_code == 200
    body = response.json()
    _validate(body, _response_schema("/api/portfolio"))
    region_enum = set(CONTRACT["components"]["schemas"]["Region"]["enum"])
    assert {entry["region"] for entry in body["by_region"]} == region_enum
    assert body["calibration"], "the fixture has labelled leads; the chart cannot be empty"
