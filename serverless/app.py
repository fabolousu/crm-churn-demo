"""Slim FastAPI application for Vercel serverless deployment.

Serves ``/api/health`` and ``/api/pipeline`` from ``data/demo.slim.db`` using only
``fastapi``, ``pydantic``, and ``sqlite3`` (stdlib).  No numpy, no pandas, no
lightgbm — the ML stack is entirely absent from this module; precomputed scores
and leverage deltas come from the committed slim database.

DB path resolution (in order):
  1. ``CRM_DB_PATH`` environment variable
  2. ``data/demo.slim.db`` resolved from the repository root (two levels above this file)

Endpoints
---------
GET /api/health
    Returns ``{status, model_version, scored_at}``.
    ``status`` is ``"ok"`` when ``lead_scores`` has rows, else ``"degraded"``.

GET /api/pipeline
    Returns ``{total, total_expected_value, items}`` with ``PipelineItem`` objects
    matching ``api/openapi.yaml``.

    Query parameters
    ~~~~~~~~~~~~~~~~
    region          one of nord-ovest|nord-est|centro|sud|isole  (optional)
    limit           1–200, default 25
    min_probability 0.0–1.0, default 0.0
    sort            expected_value (default) | at_risk
                    at_risk orders by ``(1-probability)*amount_arr``
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from typing import Any, Literal, Mapping

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent


def _db_path() -> pathlib.Path:
    env = os.environ.get("CRM_DB_PATH")
    if env:
        p = pathlib.Path(env)
        return p if p.is_absolute() else (_REPO_ROOT / p)
    return _REPO_ROOT / "data" / "demo.slim.db"


# ---------------------------------------------------------------------------
# Contract types (verbatim from api/openapi.yaml, no ML imports)
# ---------------------------------------------------------------------------

Region = Literal["nord-ovest", "nord-est", "centro", "sud", "isole"]
Band = Literal["low", "medium", "high", "critical"]
Source = Literal["inbound", "outbound", "referral", "partner", "event"]


class Driver(BaseModel):
    feature: str
    label: str
    contribution: float
    value: str
    direction: Literal["increases", "decreases"]


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
    max_leverage: float | None = None
    discount_upside: float | None = None


class PipelineResponse(BaseModel):
    total: int
    total_expected_value: float
    items: list[PipelineItem]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    model_version: str
    scored_at: datetime


# ---------------------------------------------------------------------------
# DB helpers (stdlib sqlite3 only)
# ---------------------------------------------------------------------------

OPEN_STATUSES: tuple[str, ...] = ("new", "contacted", "qualified", "proposal")
DORMANCY_DAYS = 180


def _connect(db_path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _as_date(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


def _as_datetime(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _as_of(conn: sqlite3.Connection) -> date:
    """Return the world's frozen 'today': max(lead_features.snapshot_date)."""
    row = conn.execute("SELECT MAX(snapshot_date) FROM lead_features").fetchone()
    if row and row[0]:
        return _as_date(row[0])
    return datetime.now(timezone.utc).date()


def _drivers_from_json(raw: str | None) -> list[Driver]:
    """Parse ``lead_scores.drivers_json`` into Driver objects."""
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
            continue
    return drivers


def _fallback_driver(amount_arr: float) -> Driver:
    """Placeholder top driver when drivers_json is empty or unreadable."""
    return Driver(
        feature="amount_arr",
        label="Proposed ARR",
        contribution=0.0,
        value=f"€{amount_arr:,.0f}",
        direction="increases",
    )


def _pipeline_item(
    row: Mapping[str, Any],
    as_of: date,
    max_leverage: float | None = None,
    discount_upside: float | None = None,
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
        discount_upside=discount_upside,
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="crm-churn-demo serverless API",
    version="0.3.0",
    description=(
        "Slim serverless API reading from data/demo.slim.db. "
        "No ML stack at runtime — scores and leverage are precomputed."
    ),
    # The generated docs and schema are not part of the public demo surface.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Read-only demo: only the origins that actually host the UI may call it. The UI is
# same-origin in production, so this mainly protects local development and the Pages
# showcase. ``CRM_ALLOWED_ORIGINS`` (comma-separated) overrides the list.
_DEFAULT_ALLOWED_ORIGINS = [
    "https://crm-churn-demo.vercel.app",
    "https://fabolousu.github.io",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CRM_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
] or _DEFAULT_ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    """Baseline response hardening for a public, read-only demo endpoint."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe: ``ok`` when scores exist, ``degraded`` otherwise."""
    db = _db_path()
    try:
        with closing(_connect(db)) as conn:
            scored_row = conn.execute(
                "SELECT MAX(scored_at), COUNT(*) FROM lead_scores"
            ).fetchone()
            model_row = conn.execute(
                "SELECT model_version, trained_at FROM model_runs "
                "ORDER BY trained_at DESC LIMIT 1"
            ).fetchone()
    except Exception:
        # DB not found or unreadable → degraded but still answer
        return HealthResponse(
            status="degraded",
            model_version="unknown",
            scored_at=datetime.now(timezone.utc).replace(microsecond=0),
        )

    scored_at_raw = scored_row[0] if scored_row else None
    scored_count = int(scored_row[1]) if scored_row else 0
    model_version = str(model_row["model_version"]) if model_row else "unknown"

    if scored_at_raw is None and model_row is not None:
        scored_at_raw = model_row["trained_at"]

    parsed_at = (
        _as_datetime(scored_at_raw)
        if scored_at_raw is not None
        else datetime.now(timezone.utc).replace(microsecond=0)
    )

    return HealthResponse(
        status="ok" if scored_count > 0 else "degraded",
        model_version=model_version,
        scored_at=parsed_at,
    )


@app.get("/api/pipeline", response_model=PipelineResponse)
def get_pipeline(
    region: Region | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    min_probability: float = Query(default=0.0, ge=0.0, le=1.0),
    sort: Literal["expected_value", "at_risk"] = Query(default="expected_value"),
) -> PipelineResponse:
    """Open leads ranked by ``expected_value`` or ``at_risk`` = ``(1-p)*ARR``.

    ``total`` and ``total_expected_value`` describe the filtered population BEFORE ``limit``.
    ``days_open`` uses the frozen snapshot date, not wall-clock time.
    Leverage fields come from the precomputed ``lead_leverage`` table in the slim DB.
    """
    db = _db_path()

    open_placeholders = ", ".join("?" * len(OPEN_STATUSES))
    clauses = [f"l.status IN ({open_placeholders})"]
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

    with closing(_connect(db)) as conn:
        as_of = _as_of(conn)

        total_row = conn.execute(
            f"SELECT COUNT(*), COALESCE(SUM(s.expected_value), 0.0) {base}", params
        ).fetchone()
        total = int(total_row[0])
        total_expected = float(total_row[1])

        rows = conn.execute(
            "SELECT s.lead_id, s.amount_arr, s.probability, s.band, s.expected_value, "
            "s.drivers_json, l.status, l.source, l.created_at, c.name AS company_name, "
            f"c.region {base} ORDER BY {order} DESC, s.lead_id ASC LIMIT ?",
            (*params, int(limit)),
        ).fetchall()

        # Leverage from precomputed table (no ML at runtime)
        max_leverage_by_lead: dict[str, float] = {}
        discount_upside_by_lead: dict[str, float] = {}
        if rows:
            lead_ids = [str(row["lead_id"]) for row in rows]
            id_placeholders = ", ".join("?" * len(lead_ids))
            leverage_rows = conn.execute(
                f"SELECT lead_id, max_leverage, discount_upside FROM lead_leverage "
                f"WHERE lead_id IN ({id_placeholders})",
                lead_ids,
            ).fetchall()
            for lr in leverage_rows:
                max_leverage_by_lead[str(lr["lead_id"])] = float(lr["max_leverage"])
                discount_upside_by_lead[str(lr["lead_id"])] = float(lr["discount_upside"])

    items = [
        _pipeline_item(
            row,
            as_of,
            max_leverage_by_lead.get(str(row["lead_id"])),
            discount_upside_by_lead.get(str(row["lead_id"])),
        )
        for row in rows
    ]

    return PipelineResponse(
        total=total,
        total_expected_value=total_expected,
        items=items,
    )
