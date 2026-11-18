"""FastAPI service for the crm-churn-demo pitch, written against ``api/openapi.yaml``.

The contract is the file, not this module: every path and every response shape below is a
literal transcription of the OpenAPI components, and ``api/tests/test_contract.py`` validates
the real responses against the YAML with ``jsonschema`` rather than against a second,
hand-maintained field list.

The one rule that shapes the read path
    **Scores are read from ``lead_scores``; the pipeline never re-scores.** ``ml/train.py`` is
    the only writer of that table and the only thing that has seen the model's training
    population. Recomputing a pipeline score here would let the service and the batch diverge,
    and the demo would show a number no artifact backs.

Where the model does run
    ``/counterfactual`` and ``/actions`` re-score *one* lead through ``ml.train.predict`` with
    the committed bundle: that is the whole point of the lever, and a stored score cannot answer
    "what if". The counterfactual compares two predictions from the *same* bundle -- current
    features versus levered features -- so the delta is like-for-like even if the database's
    stored score were stale.

Interpretations where the contract is silent (reported in the PR, contract untouched)
    * ``/api/pipeline``'s ``total`` and ``total_expected_value`` describe the filtered
      population *before* ``limit``; ``items`` is the page. A total that duplicated
      ``len(items)`` would say nothing the list does not.
    * ``days_open``, ``days_since_last_initiative`` and the 180-day dormancy flag are measured
      against the world's snapshot (``MAX(lead_features.snapshot_date)``, i.e. ``t0``), not the
      wall clock. The frozen world has one "today"; using the wall clock would make a
      deterministic demo drift as the laptop's clock moves.
    * A company with **no initiative ever** is not dormant: dormancy flags a lapsed
      relationship, and ``days_since_last_initiative`` is ``0`` because there is no last
      initiative to measure from.
    * An action of kind ``call`` or ``discount_review`` has no lever in ``docs/LABEL.md``
      (``discount_review`` carries no discount value), so it records the action and returns
      the unchanged probability with ``delta == 0``. Only ``exec_sponsor_meeting`` and
      ``discovery_meeting`` map to a modelled feature change.
    * A duplicate open action of the same kind is a ``409 Conflict`` with the ``Error`` body:
      the contract lists only ``201`` for the happy path and is silent on the retention guard.
    * An unknown lead or company is a ``404`` with the ``Error`` body, including on
      ``/counterfactual`` and ``/actions`` where the contract does not list ``404``.
    * ``/api/portfolio``'s calibration curve comes from the *labelled* population (closed
      leads with a ``lead_outcomes`` row), re-scored with the loaded bundle: a calibration
      curve needs outcomes, and ``lead_scores`` holds only the open pipeline. **Drift is
      model stability**: the PSI between the temporal *train* and *holdout (validation)*
      score distributions, both on labelled leads, binned with the same decile edges as the
      calibration chart. It answers "did the model's output move on unseen data?", not "is
      the open queue shaped like history?" -- the latter is survivor selection, not drift.
      Thresholds are the conventional 0.10 / 0.25.
    * ``max_leverage`` is the largest single-action delta reachable with the three contract
      levers (exec sponsor meeting, discovery meeting, discount to 0%). It is an **additive
      extension**: ``api/openapi.yaml`` is deliberately untouched, so the schema still
      validates these responses (additional properties are allowed) while lane D is told to
      read the field. See the PR for why the contract owner may want to adopt it formally.
    * ``/api/health`` reports ``degraded`` when the artifact cannot be loaded or
      ``lead_scores`` is empty; it still answers, so the demo's liveness probe is honest
      about a half-built environment instead of returning a 500.

Run it with ``uvicorn api.app:app --port 8000`` from the repository root.
"""

from __future__ import annotations

import json
import math
import os
import pathlib
import sqlite3
import sys
import uuid
from contextlib import asynccontextmanager, closing
from datetime import date, datetime, timezone
from typing import Any, Literal, Mapping

import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_serializer

APP_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
if str(REPO_ROOT) not in sys.path:  # so ``uvicorn api.app:app`` finds ``ml.*``
    sys.path.insert(0, str(REPO_ROOT))

from ml.explain import Explainer, describe_value, load_bundle  # noqa: E402
from ml.train import (  # noqa: E402
    OPEN_STATUSES,
    band_for,
    load_labeled_leads,
    predict,
    temporal_split,
)

DEFAULT_DB_PATH = REPO_ROOT / "data" / "demo.db"
DEFAULT_MODEL_PATH = REPO_ROOT / "ml" / "artifacts" / "model.joblib"

# ``docs/LABEL.md``: dormancy is shown, not modelled. 180+ days without a new initiative.
DORMANCY_DAYS = 180

# The demo has no auth (docs/DECISIONS.md non-goals), but ``actions.created_by`` is NOT NULL.
# One constant is honest about that: this is the signed-in rep the demo pretends to be.
DEMO_CREATED_BY = "demo-rep"

REGIONS: tuple[str, ...] = ("nord-ovest", "nord-est", "centro", "sud", "isole")

# Drift thresholds for the population stability index, stated here because the contract only
# names the three statuses: psi < 0.10 stable, < 0.25 watch, else alert.
PSI_STABLE_BELOW = 0.10
PSI_WATCH_BELOW = 0.25

REQUEST_ID = uuid.uuid4().hex  # cosmetic; makes action ids recognisable in a demo session


# --------------------------------------------------------------------------------------
# contract types -- one Pydantic model per OpenAPI component, same fields, same optionality
# --------------------------------------------------------------------------------------

Region = Literal["nord-ovest", "nord-est", "centro", "sud", "isole"]
Band = Literal["low", "medium", "high", "critical"]
Source = Literal["inbound", "outbound", "referral", "partner", "event"]
LeadStatus = Literal["new", "contacted", "qualified", "proposal", "won", "lost"]
ActionKind = Literal["call", "exec_sponsor_meeting", "discovery_meeting", "discount_review"]
ActionStatus = Literal["open", "done", "cancelled"]
LostReason = Literal["price", "no_budget", "competitor", "no_fit", "timing", "silent"]


class Driver(BaseModel):
    feature: str
    label: str
    contribution: float
    value: str
    direction: Literal["increases", "decreases"]


class Lead(BaseModel):
    id: str
    status: LeadStatus
    source: Source
    created_at: date
    closed_at: date | None = None
    amount_arr: float | None = None
    discount_pct: float = 0.0
    lost_reason: LostReason | None = None


class PipelineItem(BaseModel):
    lead_id: str
    company_name: str
    region: Region
    source: Source
    status: str
    amount_arr: float
    probability: float
    band: Band
    expected_value: float
    days_open: int
    top_driver: Driver
    # Additive extension to the contract: the biggest single-lever gain for this lead. See
    # the module docstring -- api/openapi.yaml is intentionally untouched.
    max_leverage: float | None = None


class PipelineResponse(BaseModel):
    total: int
    total_expected_value: float
    items: list[PipelineItem]


class Action(BaseModel):
    id: str
    kind: str
    status: ActionStatus
    created_at: datetime
    created_by: str
    note: str | None = None

    @model_serializer(mode="wrap")
    def _omit_none_note(self, handler: Any) -> dict[str, Any]:
        """``Action.note`` is a plain string in the contract, not nullable: omit it when unset."""
        data = handler(self)
        if data.get("note") is None:
            data.pop("note", None)
        return data


class LeadCompany(BaseModel):
    id: str
    name: str
    region: Region
    industry: str
    employees: int
    lifetime_won_arr: float
    dormant: bool


class LeadScore(BaseModel):
    probability: float
    band: Band
    model_version: str
    scored_at: datetime
    expected_value: float


class LeadDetail(BaseModel):
    lead: Lead
    company: LeadCompany
    score: LeadScore
    drivers: list[Driver]
    prior_initiatives: list[Lead]
    open_actions: list[Action]
    # Additive extension: the biggest single-lever delta available on this lead. See the
    # module docstring -- api/openapi.yaml is intentionally untouched.
    max_leverage: float | None = None


class CompanySummary(BaseModel):
    id: str
    name: str
    region: Region
    industry: str
    employees: int
    created_at: date


class CompanySignals(BaseModel):
    dormant: bool
    days_since_last_initiative: int
    won: int
    lost: int
    lifetime_won_arr: float


class CompanyDetail(BaseModel):
    company: CompanySummary
    initiatives: list[Lead]
    signals: CompanySignals


class CounterfactualRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exec_sponsor_meeting: bool | None = None
    discovery_meeting: bool | None = None
    discount_pct: float | None = Field(default=None, ge=0.0, le=60.0)


class CounterfactualResponse(BaseModel):
    current_probability: float
    hypothetical_probability: float
    delta: float
    explanation: str


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ActionKind
    note: str | None = Field(default=None, max_length=500)


class ActionResponse(BaseModel):
    action: Action
    probability_after: float
    delta: float


class RegionPortfolio(BaseModel):
    region: Region
    open_leads: int
    win_rate: float
    expected_value: float


class CalibrationBin(BaseModel):
    predicted: float
    actual: float


class Drift(BaseModel):
    psi: float
    status: Literal["stable", "watch", "alert"]


class Portfolio(BaseModel):
    total_expected_value: float
    by_region: list[RegionPortfolio]
    calibration: list[CalibrationBin]
    drift: Drift


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    model_version: str
    scored_at: datetime


class Error(BaseModel):
    error: str
    detail: str


# --------------------------------------------------------------------------------------
# errors
# --------------------------------------------------------------------------------------


class ApiError(Exception):
    """An error the contract models as ``Error``; raised instead of ``HTTPException``."""

    def __init__(self, status_code: int, error: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.error = error
        self.detail = detail


# --------------------------------------------------------------------------------------
# small data helpers
# --------------------------------------------------------------------------------------


def _connect(db_path: str | pathlib.Path, *, autocommit: bool = False) -> sqlite3.Connection:
    """A short-lived connection. SQLite is opened per request: no shared mutable state."""
    connection = sqlite3.connect(
        str(db_path),
        timeout=15.0,
        isolation_level=None if autocommit else "",
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _as_date(value: Any) -> date:
    """The date half of a stored ISO timestamp (``YYYY-MM-DD`` or ``YYYY-MM-DDTHH:MM:SS``)."""
    return date.fromisoformat(str(value)[:10])


def _as_datetime(value: Any) -> datetime:
    """Parse a stored ISO timestamp, accepting both ``Z`` and ``+00:00`` offsets."""
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _as_of(connection: sqlite3.Connection) -> date:
    """The world's "today": ``t0``, recorded as the latest feature snapshot.

    The generator builds one frozen world up to ``T0``; measuring "days open" or dormancy
    against the laptop clock would make the same database tell a different story next week.
    """
    row = connection.execute("SELECT MAX(snapshot_date) FROM lead_features").fetchone()
    if row is not None and row[0]:
        return _as_date(row[0])
    return datetime.now(timezone.utc).date()


def dormancy_for(last_initiative_at: Any, as_of: date) -> tuple[bool, int]:
    """The 180-day rule: ``(dormant, days_since_last_initiative)``.

    No initiative ever means no relationship to lapse: not dormant, and zero days because
    there is no last initiative to count from (the contract requires an integer).
    """
    if last_initiative_at is None:
        return False, 0
    days = (as_of - _as_date(last_initiative_at)).days
    return days >= DORMANCY_DAYS, max(days, 0)


def _drivers_from_json(raw: str | None) -> list[Driver]:
    """Parse ``lead_scores.drivers_json`` into the contract's ``Driver`` shape."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    drivers: list[Driver] = []
    for item in parsed if isinstance(parsed, list) else []:
        try:
            drivers.append(Driver(**item))
        except (TypeError, ValueError):
            continue  # a malformed row must not take the whole 360 down
    return drivers


def _fallback_driver(amount_arr: float) -> Driver:
    """A placeholder top driver for a score row whose ``drivers_json`` is unreadable.

    Public data from ``ml/train.py`` always carries three drivers; this exists so a partially
    built database degrades to an honest "no explanation" rather than a 500. The contribution
    is zero because nothing was computed -- a fabricated direction would be worse.
    """
    return Driver(
        feature="amount_arr",
        label="Proposed ARR",
        contribution=0.0,
        value=describe_value("amount_arr", amount_arr),
        direction="increases",
    )


def _lead_from_row(row: Mapping[str, Any]) -> Lead:
    return Lead(
        id=str(row["id"]),
        status=str(row["status"]),
        source=str(row["source"]),
        created_at=_as_date(row["created_at"]),
        closed_at=_as_date(row["closed_at"]) if row["closed_at"] else None,
        amount_arr=None if row["amount_arr"] is None else float(row["amount_arr"]),
        discount_pct=float(row["discount_pct"] or 0.0),
        lost_reason=row["lost_reason"],
    )


def _score_from_row(row: Mapping[str, Any]) -> LeadScore:
    return LeadScore(
        probability=float(row["probability"]),
        band=str(row["band"]),
        model_version=str(row["model_version"]),
        scored_at=_as_datetime(row["scored_at"]),
        expected_value=float(row["expected_value"]),
    )


def _score_from_features(
    request: Request, feature_row: Mapping[str, Any]
) -> tuple[LeadScore, list[Driver]]:
    """Score one lead with the loaded bundle. Used only when ``lead_scores`` has no row.

    Open leads always have a stored score; this path is the Lead 360 for a *closed* lead,
    which the trainer deliberately does not score (it has no open pipeline to rank). The
    comparison stays honest: the number is produced by the same artifact the batch used.
    """
    bundle = request.app.state.bundle
    explainer = request.app.state.explainer
    if bundle is None or explainer is None:
        raise ApiError(503, "model_unavailable", "the model artifact could not be loaded")

    probability = float(predict(bundle, dict(feature_row))[0])
    amount = float(feature_row["amount_arr"])
    score = LeadScore(
        probability=probability,
        band=band_for(probability),
        model_version=str(bundle["model_version"]),
        scored_at=datetime.now(timezone.utc).replace(microsecond=0),
        expected_value=probability * amount,
    )
    return score, [Driver(**driver) for driver in explainer.explain_one(dict(feature_row))]


def _company_row(connection: sqlite3.Connection, company_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    if row is None:
        raise ApiError(404, "unknown_company", f"company {company_id} does not exist")
    return row


def _company_signals(connection: sqlite3.Connection, company_id: str, as_of: date) -> tuple[
    bool, int, int, int, float
]:
    """``(dormant, days_since_last_initiative, won, lost, lifetime_won_arr)`` for one company."""
    last = connection.execute(
        "SELECT MAX(created_at) FROM leads WHERE company_id = ?", (company_id,)
    ).fetchone()[0]
    dormant, days = dormancy_for(last, as_of)
    won, lost, lifetime = connection.execute(
        "SELECT "
        "COALESCE(SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN status = 'won' THEN amount_arr ELSE 0 END), 0) "
        "FROM leads WHERE company_id = ?",
        (company_id,),
    ).fetchone()
    return dormant, days, int(won), int(lost), float(lifetime)


def _apply_levers(
    feature_row: Mapping[str, Any],
    *,
    exec_sponsor_meeting: bool | None,
    discovery_meeting: bool | None,
    discount_pct: float | None,
) -> tuple[dict[str, Any], list[str]]:
    """Apply the ``docs/LABEL.md`` lever mapping to one feature row.

    ``exec_sponsor_meeting`` is the only lever that touches NPS, and it does so only when NPS
    was measured: ``NULL`` means "never surveyed", and adding five to an unmeasured signal would
    fabricate a survey. ``meetings_before_scoring`` is NOT NULL, so it rises from its value
    (or zero) for each meeting lever that fires.
    """
    modified = dict(feature_row)
    changes: list[str] = []

    meetings = float(modified.get("meetings_before_scoring") or 0.0)
    nps = modified.get("nps_last")
    nps_measured = nps is not None and not (
        isinstance(nps, float) and math.isnan(nps)
    )

    if exec_sponsor_meeting:
        meetings += 1.0
        if nps_measured:
            modified["nps_last"] = min(float(nps) + 5.0, 100.0)
            changes.append("an executive sponsor meeting (+1 meeting, +5 NPS)")
        else:
            changes.append("an executive sponsor meeting (+1 meeting)")

    if discovery_meeting:
        meetings += 1.0
        changes.append("a discovery meeting (+1 meeting)")

    if exec_sponsor_meeting or discovery_meeting:
        modified["meetings_before_scoring"] = meetings

    if discount_pct is not None:
        modified["discount_pct"] = float(discount_pct)
        changes.append(f"a {float(discount_pct):g}% discount")

    return modified, changes


def _lever_from_action(kind: str) -> dict[str, Any]:
    """The lever an action kind applies, if the contract has one for it.

    ``call`` and ``discount_review`` have no entry in the ``docs/LABEL.md`` lever table, so
    they leave every feature untouched and return a zero delta. ``discount_review`` cannot
    carry a discount value, so it cannot be the ``discount_pct`` lever in disguise.
    """
    if kind == "exec_sponsor_meeting":
        return {"exec_sponsor_meeting": True}
    if kind == "discovery_meeting":
        return {"discovery_meeting": True}
    return {}


def _leverage_variants(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The three contract levers, each at its most favourable value.

    Every lever is one-directional in the hazard (``docs/LABEL.md``): a meeting and an NPS
    lift can only raise the win probability, and a discount can only lower it -- so the
    strongest discount lever is 0%. ``max_leverage`` is therefore the ceiling one simulated
    action can reach, not a tuned number. ``nps_last`` stays ``NaN`` when it was never
    measured, for the same reason the counterfactual leaves it unset.
    """
    variants: dict[str, pd.DataFrame] = {}

    sponsor = frame.copy()
    sponsor["meetings_before_scoring"] = (
        pd.to_numeric(sponsor["meetings_before_scoring"], errors="coerce").fillna(0.0)
        + 1.0
    )
    nps = pd.to_numeric(sponsor["nps_last"], errors="coerce")
    sponsor["nps_last"] = np.minimum(nps + 5.0, 100.0)
    variants["exec_sponsor_meeting"] = sponsor

    discovery = frame.copy()
    discovery["meetings_before_scoring"] = (
        pd.to_numeric(discovery["meetings_before_scoring"], errors="coerce").fillna(0.0)
        + 1.0
    )
    variants["discovery_meeting"] = discovery

    discount = frame.copy()
    discount["discount_pct"] = 0.0
    variants["discount_pct"] = discount

    return variants


def _max_leverage_deltas(bundle: Mapping[str, Any], frame: pd.DataFrame) -> np.ndarray:
    """Largest single-lever probability gain per row, in probability (not log-odds) units."""
    current = predict(bundle, frame)
    best = np.zeros(len(frame), dtype="float64")
    for variant in _leverage_variants(frame).values():
        best = np.maximum(best, predict(bundle, variant) - current)
    return np.clip(best, 0.0, 1.0)


def _max_leverage_delta(bundle: Mapping[str, Any], feature_row: Mapping[str, Any]) -> float:
    frame = pd.DataFrame([dict(feature_row)])
    return float(_max_leverage_deltas(bundle, frame)[0])


def _pipeline_item(
    row: Mapping[str, Any], as_of: date, max_leverage: float | None = None
) -> PipelineItem:
    drivers = _drivers_from_json(row["drivers_json"])
    top = drivers[0] if drivers else _fallback_driver(float(row["amount_arr"]))
    return PipelineItem(
        lead_id=str(row["lead_id"]),
        company_name=str(row["company_name"]),
        region=str(row["region"]),
        source=str(row["source"]),
        status=str(row["status"]),
        amount_arr=float(row["amount_arr"]),
        probability=float(row["probability"]),
        band=str(row["band"]),
        expected_value=float(row["expected_value"]),
        days_open=max(0, (as_of - _as_date(row["created_at"])).days),
        top_driver=top,
        max_leverage=max_leverage,
    )


# --------------------------------------------------------------------------------------
# the application
# --------------------------------------------------------------------------------------


def create_app(
    db_path: str | pathlib.Path | None = None,
    model_path: str | pathlib.Path | None = None,
) -> FastAPI:
    """Build the app against a specific database and artifact (tests pass temporary ones)."""
    resolved_db = pathlib.Path(
        db_path or os.environ.get("CRM_DB_PATH") or DEFAULT_DB_PATH
    )
    resolved_model = pathlib.Path(
        model_path or os.environ.get("CRM_MODEL_PATH") or DEFAULT_MODEL_PATH
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.db_path = str(resolved_db)
        application.state.model_path = str(resolved_model)
        application.state.bundle = None
        application.state.explainer = None
        application.state.load_error = None
        # A missing artifact must not stop the service from answering /api/health; it makes
        # health say "degraded" and the model-backed endpoints fail loudly.
        try:
            bundle = load_bundle(application.state.model_path)
            application.state.bundle = bundle
            application.state.explainer = Explainer(bundle)
        except Exception as exc:  # noqa: BLE001 - surfaced through /api/health
            application.state.load_error = f"{type(exc).__name__}: {exc}"
        yield

    application = FastAPI(
        title="crm-churn-demo API",
        version="0.3.0",
        description=(
            "Implementation of api/openapi.yaml. Scores are read from lead_scores; "
            "counterfactuals re-score one lead with the committed model bundle."
        ),
        lifespan=lifespan,
    )

    # The UI runs on :5173 during development (docs/DECISIONS.md ports). Without this the
    # demo page cannot call the API at all.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @application.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error, "detail": exc.detail},
        )

    @application.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # The contract models 422 as ``Error``; keeping that shape for request validation
        # means one error contract for the whole service, not two.
        details = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ()))
            details.append(f"{location}: {error.get('msg', 'invalid value')}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": "; ".join(details) or "request validation failed",
            },
        )

    # ---------------------------------------------------------------- health

    @application.get("/api/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        bundle = request.app.state.bundle
        with closing(_connect(request.app.state.db_path)) as connection:
            scored_row = connection.execute(
                "SELECT MAX(scored_at), COUNT(*) FROM lead_scores"
            ).fetchone()
            model_row = connection.execute(
                "SELECT model_version, trained_at FROM model_runs "
                "ORDER BY trained_at DESC LIMIT 1"
            ).fetchone()

        scored_at = scored_row[0] if scored_row else None
        scored_count = int(scored_row[1]) if scored_row else 0
        model_version = (
            str(bundle["model_version"])
            if bundle is not None
            else (str(model_row["model_version"]) if model_row else "unknown")
        )
        if scored_at is None and model_row is not None:
            scored_at = model_row["trained_at"]
        parsed_at = (
            _as_datetime(scored_at)
            if scored_at is not None
            else datetime.now(timezone.utc).replace(microsecond=0)
        )
        healthy = bundle is not None and scored_count > 0
        return HealthResponse(
            status="ok" if healthy else "degraded",
            model_version=model_version,
            scored_at=parsed_at,
        )

    # ---------------------------------------------------------------- pipeline

    @application.get("/api/pipeline", response_model=PipelineResponse)
    def get_pipeline(
        request: Request,
        region: Region | None = Query(default=None),
        limit: int = Query(default=25, ge=1, le=200),
        min_probability: float = Query(default=0.0, ge=0.0, le=1.0),
        sort: Literal["expected_value", "at_risk"] = Query(default="expected_value"),
    ) -> PipelineResponse:
        """Open leads ranked by ``expected_value``, or by risk when ``sort=at_risk``.

        ``at_risk`` flips the ranking to ``(1 - p) * ARR`` -- the biggest *exposed* money --
        while ``expected_value`` in each item stays the contract's ``probability * ARR``.
        """
        placeholders = ", ".join("?" for _ in OPEN_STATUSES)
        clauses = [f"l.status IN ({placeholders})"]
        params: list[Any] = list(OPEN_STATUSES)
        if region is not None:
            clauses.append("c.region = ?")
            params.append(region)
        clauses.append("s.probability >= ?")
        params.append(float(min_probability))
        where = " AND ".join(clauses)

        base = (
            "FROM lead_scores AS s "
            "JOIN leads AS l ON l.id = s.lead_id "
            "JOIN companies AS c ON c.id = l.company_id "
            f"WHERE {where}"
        )
        order = (
            "(1.0 - s.probability) * s.amount_arr"
            if sort == "at_risk"
            else "s.expected_value"
        )

        bundle = request.app.state.bundle

        with closing(_connect(request.app.state.db_path)) as connection:
            as_of = _as_of(connection)
            total, total_expected = connection.execute(
                f"SELECT COUNT(*), COALESCE(SUM(s.expected_value), 0.0) {base}", params
            ).fetchone()
            rows = connection.execute(
                "SELECT s.lead_id, s.amount_arr, s.probability, s.band, s.expected_value, "
                "s.drivers_json, l.status, l.source, l.created_at, c.name AS company_name, "
                f"c.region {base} ORDER BY {order} DESC, s.lead_id ASC LIMIT ?",
                (*params, int(limit)),
            ).fetchall()

            # ``max_leverage`` is an additive extension, computed only for the page (<= 200
            # leads), never for the whole queue, so opening the pipeline stays cheap.
            max_leverage_by_lead: dict[str, float] = {}
            if bundle is not None and rows:
                lead_ids = [str(row["lead_id"]) for row in rows]
                feature_placeholders = ", ".join("?" for _ in lead_ids)
                feature_rows = connection.execute(
                    "SELECT * FROM lead_features "
                    f"WHERE lead_id IN ({feature_placeholders})",
                    lead_ids,
                ).fetchall()
                by_lead = {str(row["lead_id"]): dict(row) for row in feature_rows}
                ordered_ids = [lead_id for lead_id in lead_ids if lead_id in by_lead]
                if ordered_ids:
                    frame = pd.DataFrame([by_lead[lead_id] for lead_id in ordered_ids])
                    for lead_id, delta in zip(
                        ordered_ids, _max_leverage_deltas(bundle, frame)
                    ):
                        max_leverage_by_lead[lead_id] = float(delta)

        items = [
            _pipeline_item(row, as_of, max_leverage_by_lead.get(str(row["lead_id"])))
            for row in rows
        ]
        return PipelineResponse(
            total=int(total),
            total_expected_value=float(total_expected),
            items=items,
        )

    # ---------------------------------------------------------------- lead 360

    @application.get("/api/leads/{lead_id}", response_model=LeadDetail)
    def get_lead(request: Request, lead_id: str) -> LeadDetail:
        with closing(_connect(request.app.state.db_path)) as connection:
            lead_row = connection.execute(
                "SELECT * FROM leads WHERE id = ?", (lead_id,)
            ).fetchone()
            if lead_row is None:
                raise ApiError(404, "unknown_lead", f"lead {lead_id} does not exist")

            company_row = _company_row(connection, str(lead_row["company_id"]))
            as_of = _as_of(connection)
            dormant, _, _, _, lifetime_won = _company_signals(
                connection, str(company_row["id"]), as_of
            )

            score_row = connection.execute(
                "SELECT * FROM lead_scores WHERE lead_id = ? "
                "ORDER BY scored_at DESC LIMIT 1",
                (lead_id,),
            ).fetchone()
            feature_row = connection.execute(
                "SELECT * FROM lead_features WHERE lead_id = ?", (lead_id,)
            ).fetchone()

            if score_row is not None:
                score = _score_from_row(score_row)
                drivers = _drivers_from_json(score_row["drivers_json"])
                if not drivers and feature_row is not None:
                    explainer = request.app.state.explainer
                    if explainer is not None:
                        drivers = [
                            Driver(**driver)
                            for driver in explainer.explain_one(dict(feature_row))
                        ]
                if not drivers:
                    drivers = [_fallback_driver(float(score_row["amount_arr"]))]
            elif feature_row is not None:
                # A closed initiative: the batch scorer only scores the open pipeline.
                score, drivers = _score_from_features(request, feature_row)
            else:
                raise ApiError(
                    500,
                    "score_unavailable",
                    f"lead {lead_id} has neither a stored score nor a feature row",
                )

            # An open lead's ceiling: the biggest delta any single contract lever could reach.
            # A closed lead is not actionable, so it reports null rather than a hypothetical
            # gain nobody can book.
            bundle = request.app.state.bundle
            max_leverage = (
                _max_leverage_delta(bundle, feature_row)
                if bundle is not None
                and feature_row is not None
                and str(lead_row["status"]) not in ("won", "lost")
                else None
            )

            prior_rows = connection.execute(
                "SELECT * FROM leads WHERE company_id = ? AND created_at < ? AND id != ? "
                "ORDER BY created_at DESC",
                (company_row["id"], lead_row["created_at"], lead_id),
            ).fetchall()
            action_rows = connection.execute(
                "SELECT * FROM actions WHERE lead_id = ? AND status = 'open' "
                "ORDER BY created_at DESC, id ASC",
                (lead_id,),
            ).fetchall()

        return LeadDetail(
            lead=_lead_from_row(lead_row),
            company=LeadCompany(
                id=str(company_row["id"]),
                name=str(company_row["name"]),
                region=str(company_row["region"]),
                industry=str(company_row["industry"]),
                employees=int(company_row["employees"]),
                lifetime_won_arr=float(lifetime_won),
                dormant=dormant,
            ),
            score=score,
            drivers=drivers,
            prior_initiatives=[_lead_from_row(row) for row in prior_rows],
            open_actions=[
                Action(
                    id=str(row["id"]),
                    kind=str(row["kind"]),
                    status=str(row["status"]),
                    created_at=_as_datetime(row["created_at"]),
                    created_by=str(row["created_by"]),
                    note=row["note"],
                )
                for row in action_rows
            ],
            max_leverage=max_leverage,
        )

    # ---------------------------------------------------------------- counterfactual

    @application.post(
        "/api/leads/{lead_id}/counterfactual", response_model=CounterfactualResponse
    )
    def post_counterfactual(
        request: Request, lead_id: str, body: CounterfactualRequest
    ) -> CounterfactualResponse:
        """Re-score the same bundle with one hypothetical forward-looking lever applied.

        Both sides are predictions from the loaded artifact, so ``delta`` is like-for-like.
        A closed lead is a 422: no forward-looking lever rewrites an outcome that happened,
        and ``accelerate_to_proposal`` is deliberately absent for the reason in
        ``docs/DECISIONS.md`` (stage is constant in training, so the effect is unlearnable).
        """
        if all(
            value is None
            for value in (
                body.exec_sponsor_meeting,
                body.discovery_meeting,
                body.discount_pct,
            )
        ):
            raise ApiError(
                422,
                "no_lever",
                "provide at least one of exec_sponsor_meeting, discovery_meeting, discount_pct",
            )

        bundle = request.app.state.bundle
        if bundle is None:
            raise ApiError(503, "model_unavailable", "the model artifact could not be loaded")

        with closing(_connect(request.app.state.db_path)) as connection:
            lead_row = connection.execute(
                "SELECT id, status FROM leads WHERE id = ?", (lead_id,)
            ).fetchone()
            if lead_row is None:
                raise ApiError(404, "unknown_lead", f"lead {lead_id} does not exist")
            if str(lead_row["status"]) in ("won", "lost"):
                raise ApiError(
                    422,
                    "closed_lead",
                    f"lead {lead_id} is {lead_row['status']}; counterfactuals apply to open leads",
                )
            feature_row = connection.execute(
                "SELECT * FROM lead_features WHERE lead_id = ?", (lead_id,)
            ).fetchone()

        if feature_row is None:
            raise ApiError(
                422,
                "lead_not_scorable",
                f"lead {lead_id} has no feature row; the model cannot score it",
            )

        current_features = dict(feature_row)
        hypothetical_features, changes = _apply_levers(
            current_features,
            exec_sponsor_meeting=body.exec_sponsor_meeting,
            discovery_meeting=body.discovery_meeting,
            discount_pct=body.discount_pct,
        )
        current = float(predict(bundle, current_features)[0])
        hypothetical = float(predict(bundle, hypothetical_features)[0])
        delta = hypothetical - current

        if changes:
            explanation = (
                f"Applying {', '.join(changes)} moves this initiative from "
                f"{current:.1%} to {hypothetical:.1%} "
                f"({delta * 100.0:+.1f} points), re-scored by the same model."
            )
        else:
            explanation = (
                f"No lever changed a modelled feature, so the probability stays at "
                f"{current:.1%}."
            )
        return CounterfactualResponse(
            current_probability=current,
            hypothetical_probability=hypothetical,
            delta=delta,
            explanation=explanation,
        )

    # ---------------------------------------------------------------- actions

    @application.post(
        "/api/leads/{lead_id}/actions", response_model=ActionResponse, status_code=201
    )
    def post_action(
        request: Request, lead_id: str, body: ActionRequest
    ) -> ActionResponse:
        """Record a simulated retention action and return the re-scored probability.

        The retention guard is the duplicate check: one *open* action of a kind per lead.
        Two open "exec sponsor meeting" rows would be two promises to the same person, and
        the demo's "action ledger" would double-count work that was never done twice.
        """
        bundle = request.app.state.bundle
        if bundle is None:
            raise ApiError(503, "model_unavailable", "the model artifact could not be loaded")

        lever = _lever_from_action(body.kind)

        with closing(
            _connect(request.app.state.db_path, autocommit=True)
        ) as connection:
            lead_row = connection.execute(
                "SELECT id, status FROM leads WHERE id = ?", (lead_id,)
            ).fetchone()
            if lead_row is None:
                raise ApiError(404, "unknown_lead", f"lead {lead_id} does not exist")
            if str(lead_row["status"]) in ("won", "lost"):
                raise ApiError(
                    422,
                    "closed_lead",
                    f"lead {lead_id} is {lead_row['status']}; a closed lead cannot be actioned",
                )
            feature_row = connection.execute(
                "SELECT * FROM lead_features WHERE lead_id = ?", (lead_id,)
            ).fetchone()
            if feature_row is None:
                raise ApiError(
                    422,
                    "lead_not_scorable",
                    f"lead {lead_id} has no feature row; the model cannot score it",
                )

            # Score before writing: a model failure must not leave an action row behind.
            current_features = dict(feature_row)
            levered_features, _ = _apply_levers(
                current_features,
                exec_sponsor_meeting=lever.get("exec_sponsor_meeting"),
                discovery_meeting=lever.get("discovery_meeting"),
                discount_pct=lever.get("discount_pct"),
            )
            probability_before = float(predict(bundle, current_features)[0])
            probability_after = float(predict(bundle, levered_features)[0])

            action_id = f"A-{REQUEST_ID[:4]}-{uuid.uuid4().hex[:10]}"
            created_at = datetime.now(timezone.utc).replace(microsecond=0)
            created_at_text = created_at.isoformat()

            connection.execute("BEGIN IMMEDIATE")
            try:
                duplicate = connection.execute(
                    "SELECT id FROM actions WHERE lead_id = ? AND kind = ? "
                    "AND status = 'open'",
                    (lead_id, body.kind),
                ).fetchone()
                if duplicate is not None:
                    raise ApiError(
                        409,
                        "duplicate_action",
                        f"lead {lead_id} already has an open {body.kind} action "
                        f"({duplicate['id']})",
                    )
                connection.execute(
                    "INSERT INTO actions "
                    "(id, lead_id, kind, note, created_at, created_by, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'open')",
                    (
                        action_id,
                        lead_id,
                        body.kind,
                        body.note,
                        created_at_text,
                        DEMO_CREATED_BY,
                    ),
                )
                connection.execute("COMMIT")
            except BaseException:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.Error:  # the transaction may already be gone
                    pass
                raise

        return ActionResponse(
            action=Action(
                id=action_id,
                kind=body.kind,
                status="open",
                created_at=created_at,
                created_by=DEMO_CREATED_BY,
                note=body.note,
            ),
            probability_after=probability_after,
            delta=probability_after - probability_before,
        )

    # ---------------------------------------------------------------- company 360

    @application.get("/api/companies/{company_id}", response_model=CompanyDetail)
    def get_company(request: Request, company_id: str) -> CompanyDetail:
        with closing(_connect(request.app.state.db_path)) as connection:
            company_row = _company_row(connection, company_id)
            as_of = _as_of(connection)
            dormant, days, won, lost, lifetime = _company_signals(
                connection, company_id, as_of
            )
            initiative_rows = connection.execute(
                "SELECT * FROM leads WHERE company_id = ? ORDER BY created_at DESC",
                (company_id,),
            ).fetchall()

        return CompanyDetail(
            company=CompanySummary(
                id=str(company_row["id"]),
                name=str(company_row["name"]),
                region=str(company_row["region"]),
                industry=str(company_row["industry"]),
                employees=int(company_row["employees"]),
                created_at=_as_date(company_row["created_at"]),
            ),
            initiatives=[_lead_from_row(row) for row in initiative_rows],
            signals=CompanySignals(
                dormant=dormant,
                days_since_last_initiative=days,
                won=won,
                lost=lost,
                lifetime_won_arr=lifetime,
            ),
        )

    # ---------------------------------------------------------------- portfolio

    @application.get("/api/portfolio", response_model=Portfolio)
    def get_portfolio(request: Request) -> Portfolio:
        """Executive view: EV by region, a calibration curve, and model stability.

        Calibration and drift are computed on the labelled population (closed leads with a
        ``lead_outcomes`` row), because ``lead_scores`` only covers the open pipeline and a
        calibration curve needs outcomes. Drift is **model stability**: the score
        distribution on the temporal holdout versus the temporal train side. Comparing the
        open queue against history would measure survivor selection, not drift.
        """
        bundle = request.app.state.bundle
        if bundle is None:
            raise ApiError(503, "model_unavailable", "the model artifact could not be loaded")

        with closing(_connect(request.app.state.db_path)) as connection:
            total_expected = float(
                connection.execute(
                    "SELECT COALESCE(SUM(expected_value), 0.0) FROM lead_scores"
                ).fetchone()[0]
            )

            by_region: list[RegionPortfolio] = []
            for region in REGIONS:
                open_leads, expected = connection.execute(
                    "SELECT COUNT(*), COALESCE(SUM(s.expected_value), 0.0) "
                    "FROM lead_scores AS s "
                    "JOIN leads AS l ON l.id = s.lead_id "
                    "JOIN companies AS c ON c.id = l.company_id "
                    "WHERE c.region = ?",
                    (region,),
                ).fetchone()
                won, lost = connection.execute(
                    "SELECT "
                    "COALESCE(SUM(CASE WHEN l.status = 'won' THEN 1 ELSE 0 END), 0), "
                    "COALESCE(SUM(CASE WHEN l.status = 'lost' THEN 1 ELSE 0 END), 0) "
                    "FROM leads AS l JOIN companies AS c ON c.id = l.company_id "
                    "WHERE c.region = ?",
                    (region,),
                ).fetchone()
                closed = int(won) + int(lost)
                by_region.append(
                    RegionPortfolio(
                        region=region,
                        open_leads=int(open_leads),
                        win_rate=(float(won) / closed) if closed else 0.0,
                        expected_value=float(expected),
                    )
                )

            try:
                labelled = load_labeled_leads(connection)
            except RuntimeError:  # no labels yet: nothing to calibrate or compare
                labelled = pd.DataFrame()

        predictions = predict(bundle, labelled) if not labelled.empty else np.empty(0)
        edges = _calibration_edges(predictions)
        calibration = _calibration_bins(labelled, predictions, edges)
        drift = _stability_drift(bundle, labelled, edges)

        return Portfolio(
            total_expected_value=total_expected,
            by_region=by_region,
            calibration=calibration,
            drift=drift,
        )

    return application


def _calibration_edges(predictions: np.ndarray) -> np.ndarray:
    """Decile edges over all labelled predictions; the calibration chart and drift share them."""
    if predictions.size == 0:
        return np.empty(0)
    return np.unique(np.quantile(predictions, np.linspace(0.0, 1.0, 11)))


def _calibration_bins(
    labelled: pd.DataFrame, predictions: np.ndarray, edges: np.ndarray
) -> list[CalibrationBin]:
    """Ten equal-frequency predicted-probability bins: mean prediction vs observed win rate."""
    if labelled.empty or predictions.size == 0:
        return []
    labels = labelled["won"].to_numpy(dtype="float64")
    if edges.size < 2:
        return [
            CalibrationBin(
                predicted=float(predictions.mean()), actual=float(labels.mean())
            )
        ]
    indices = np.clip(np.digitize(predictions, edges[1:-1]), 0, edges.size - 2)
    bins: list[CalibrationBin] = []
    for index in range(edges.size - 1):
        mask = indices == index
        if not mask.any():
            continue
        bins.append(
            CalibrationBin(
                predicted=round(float(predictions[mask].mean()), 6),
                actual=round(float(labels[mask].mean()), 6),
            )
        )
    return bins


def _stability_drift(
    bundle: Mapping[str, Any], labelled: pd.DataFrame, edges: np.ndarray
) -> Drift:
    """PSI between the temporal train and holdout score distributions.

    Both sides are labelled leads, so the comparison is model stability on unseen data rather
    than a comparison against the open queue (which is positively selected by censoring).
    The temporal split is the trainer's own, so the holdout is the population the model was
    validated on. Degenerate worlds (no labels, one class on a side) report stable at 0.0
    because stability is undefined without two comparable score samples.
    """
    if labelled.empty or edges.size < 2:
        return Drift(psi=0.0, status="stable")
    try:
        split = temporal_split(labelled)
    except (RuntimeError, AssertionError):
        return Drift(psi=0.0, status="stable")
    train_scores = predict(bundle, split.train)
    holdout_scores = predict(bundle, split.validation)
    return _psi(train_scores, holdout_scores, edges)


def _psi(expected: np.ndarray, actual: np.ndarray, edges: np.ndarray) -> Drift:
    """Population stability index of ``actual`` against ``expected`` over fixed edges."""
    expected_share = np.histogram(
        np.clip(expected, edges[0], edges[-1]), bins=edges
    )[0].astype("float64")
    actual_share = np.histogram(
        np.clip(actual, edges[0], edges[-1]), bins=edges
    )[0].astype("float64")
    expected_share /= expected_share.sum()
    actual_share /= actual_share.sum()

    # A zero share makes ln(share) undefined; a small epsilon is the standard PSI convention
    # and leaves the verdict unchanged at these thresholds.
    epsilon = 1e-6
    expected_share = np.where(expected_share == 0.0, epsilon, expected_share)
    actual_share = np.where(actual_share == 0.0, epsilon, actual_share)
    psi = float(np.sum((actual_share - expected_share) * np.log(actual_share / expected_share)))

    if psi < PSI_STABLE_BELOW:
        status: Literal["stable", "watch", "alert"] = "stable"
    elif psi < PSI_WATCH_BELOW:
        status = "watch"
    else:
        status = "alert"
    return Drift(psi=round(psi, 6), status=status)


app = create_app()
