#!/usr/bin/env python3
"""Synthetic world generator for the crm-churn-demo pitch.

The world is Italy-only: five macro-regions, EUR, synthetic Italian company names
and format-plausible Italian VAT numbers.  It writes ``data/demo.db`` (SQLite)
against ``data/schema.sql`` and is deterministic from a seed.

What makes this generator trustworthy
-------------------------------------
* The lead-win hazard is the one in ``docs/LABEL.md``, coefficient for
  coefficient.  The only extra definition is how ``z()`` is standardised:
  feature values are standardised against the reference lead population (the
  scored subset is selected by qualification and is narrower), with mean/SD
  fixed from a deterministic seed-42 calibration of this same process.  That
  keeps the process causal: no outcome is needed to standardise an input.
* Features are computed *internally* at the scoring point only, to draw the
  label.  Closed leads are scored at ``qualified_at``; still-open qualified
  leads are scored at ``t0`` at their current stage.  Every aggregate is
  filtered to rows at or before that snapshot (``closed_at < snapshot``,
  tickets opened by then, invoices due by then, surveys taken by then,
  interactions before then, and usage weeks that ended by then).
* **The generator does not write ``lead_features``.**  That table is
  materialised once by ``ml/features.py`` (single writer), so the raw CRM
  tables must be enough for the real feature pipeline.
* ``leads.first_response_at`` is the source of truth for the response.  The
  duration is derived from that timestamp; an unanswered lead has NULL in both.
* Censoring is explicit: a lead that is still open at ``t0`` gets no
  ``lead_outcomes`` row, ever.  The same is true of the early-stage rep-history
  seeds: they closed without reaching ``qualified``, so they seed
  ``owner_win_rate_180d`` but never enter the labelled population.
* The raw world exercises measured, measured-zero and not-measured states:
  some companies are never surveyed or never invoiced, some usage histories are
  flat (zero slope), some are too short for a slope, some reps have no prior
  closures, and some leads/rep windows genuinely have a zero rate.  NULL is
  produced by absence of the event, never by a sentinel zero.
* The z-score constants are fixed population parameters, so the outcome pass is
  causal and one-shot.  Two runs with the same seed therefore write identical
  row counts and identical win counts.

Run::

    python data/generator.py
    python data/generator.py --overwrite  # replace an existing demo.db
    python data/generator.py --db data/demo.db --seed 42 --companies 20000

Known limitation (deferred, recorded on purpose): the database is written in
place, so replacement is not atomic.  A crash leaves a partial ``demo.db`` and
costs one rerun of a deterministic generator; ``temp file + os.replace`` is the
eventual fix.
"""

from __future__ import annotations

import argparse
import math
import random
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Fixed points in time and target volumes
# ---------------------------------------------------------------------------

SEED = 42
T0 = datetime(2026, 1, 1, 0, 0, 0)
HISTORY_START = datetime(2024, 1, 1, 0, 0, 0)
HISTORY_END = datetime(2025, 12, 31, 23, 59, 59)
COMPANY_CREATED_START = datetime(2005, 1, 1, 0, 0, 0)
COMPANY_CREATED_END = datetime(2024, 12, 31, 23, 59, 59)

DEFAULT_COMPANIES = 20_000
LEADS_PER_COMPANY = 3  # ~60,000 when the default company count is used
# Hard cap on ordinary leads per company.  Rep-history seeds are additional and
# bounded separately, so a degenerate --companies 1 run has a known limit.
MAX_NORMAL_LEADS_PER_COMPANY = 20

# ---------------------------------------------------------------------------
# Geography, language, firmographics
# ---------------------------------------------------------------------------

REGIONS = ("nord-ovest", "nord-est", "centro", "sud", "isole")

REGION_EFFECT = {
    "nord-ovest": 0.00,
    "nord-est": 0.05,
    "centro": 0.00,
    "sud": -0.10,
    "isole": -0.15,
}

# Balanced-ish on purpose: the demo compares regional base rates, and groups of
# similar size make the comparison legible instead of dominated by sample noise.
REGION_WEIGHTS = {
    "nord-ovest": 0.12,
    "nord-est": 0.12,
    "centro": 0.20,
    "sud": 0.28,
    "isole": 0.28,
}

CITIES = {
    "nord-ovest": [
        "Milano", "Torino", "Genova", "Bergamo", "Brescia", "Novara",
        "Alessandria", "Vercelli", "Como", "Varese", "Monza", "Pavia",
        "Cremona", "Mantova", "Aosta", "Savona", "La Spezia", "Imperia",
    ],
    "nord-est": [
        "Venezia", "Verona", "Padova", "Trieste", "Bologna", "Trento",
        "Bolzano", "Parma", "Modena", "Reggio Emilia", "Udine", "Pordenone",
        "Ferrara", "Ravenna", "Rimini", "Vicenza", "Rovigo", "Belluno",
        "Treviso",
    ],
    "centro": [
        "Roma", "Firenze", "Perugia", "Ancona", "Terni", "Siena", "Pisa",
        "Livorno", "Arezzo", "Grosseto", "Pesaro", "Macerata", "Viterbo",
        "Rieti", "Latina", "Frosinone",
    ],
    "sud": [
        "Napoli", "Bari", "Taranto", "Reggio Calabria", "Catanzaro",
        "Potenza", "Matera", "Campobasso", "Salerno", "Caserta", "Benevento",
        "Avellino", "Lecce", "Brindisi", "Foggia", "Andria", "Trani",
        "Cosenza", "Crotone", "Isernia", "Teramo", "Chieti", "L'Aquila",
        "Pescara",
    ],
    "isole": [
        "Palermo", "Catania", "Messina", "Siracusa", "Ragusa", "Trapani",
        "Agrigento", "Caltanissetta", "Enna", "Cagliari", "Sassari", "Nuoro",
        "Oristano", "Olbia", "Iglesias",
    ],
}

SOURCES = ("inbound", "outbound", "referral", "partner", "event")
SOURCE_EFFECT = {
    "referral": 0.35,
    "partner": 0.15,
    "inbound": 0.10,
    "event": 0.00,
    "outbound": -0.25,
}
# This is a sales-led motion: outbound dominates the mix.  The source mix is a
# free design choice (LABEL.md fixes the effects, not the mix) and it holds the
# overall base rate in the documented 25-30% band without touching a coefficient.
SOURCE_WEIGHTS = (0.05, 0.78, 0.06, 0.04, 0.07)  # inbound, outbound, referral, partner, event

INDUSTRIES = (
    "Manifattura", "Software", "Logistica", "Retail", "Finanza", "Sanità",
    "Costruzioni", "Energia", "Agricoltura", "Turismo", "Automotive",
    "Chimica", "Tessile", "Alimentare", "Servizi professionali",
    "Telecomunicazioni", "Utility", "Farmaceutica", "Meccanica",
    "Elettronica",
)

SURNAMES = (
    "Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo",
    "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti", "De Luca",
    "Costa", "Giordano", "Mancini", "Rizzo", "Lombardi", "Moretti",
    "Barbieri", "Fontana", "Santoro", "Mariani", "Rinaldi", "Caruso",
    "Ferrara", "Galli", "Martini", "Leone", "Longo", "Gentile",
    "Martinelli", "Vitale", "Lombardo", "Serra", "Coppola", "De Santis",
    "D'Angelo", "Marchetti", "Parisi", "Villa", "Conte", "Ferraro", "Ferri",
    "Fabbri", "Bianco", "Marini", "Grasso", "Valentini", "Messina", "Sala",
    "De Angelis", "Gatti", "Pellegrini", "Palumbo", "Sanna", "Farina",
    "Rizzi", "Monti", "Cattaneo", "Morelli", "Amato", "Silvestri", "Mazza",
    "Testa", "Grassi", "Pellegrino", "Carbone", "Giuliani", "Benedetti",
    "Barone", "Rossetti", "Caputo", "Montanari", "Guerra", "Palmieri",
    "Bernardi", "Martino", "Fiore", "De Rosa", "Ferretti",
)

BUSINESS_NOUNS = (
    "Impianti", "Tecnologie", "Soluzioni", "Sistemi", "Costruzioni",
    "Meccanica", "Elettronica", "Logistica", "Energia", "Ambiente",
    "Servizi", "Industrie", "Forniture", "Automazione", "Digital",
    "Consulting", "Ingegneria", "Materiali", "Packaging", "Trasporti",
    "Gruppo", "Officine", "Laboratori", "Studio", "Partner", "Reti",
    "Infrastrutture", "Componenti", "Utensili", "Acciai", "Legno", "Chimica",
    "Farmaceutica", "Alimentare", "Tessile", "Moda", "Arredo", "Ceramiche",
    "Vetri", "Plastica", "Carta", "Grafica", "Comunicazione", "Formazione",
    "Ricerca", "Sviluppo", "Qualità", "Sicurezza", "Misure", "Controlli",
    "Analisi", "Progetti", "Cantieri", "Edilizia", "Casa", "Territorio",
    "Mobilità", "Acqua", "Aria", "Calore", "Luce",
)

LEGAL_FORMS = ("S.r.l.", "S.p.A.", "S.n.c.", "S.a.s.", "S.r.l.s.")

REPS = (
    "Marco Rossi", "Giulia Bianchi", "Luca Ferrari", "Sara Romano",
    "Andrea Colombo", "Elisa Ricci", "Matteo Marino", "Chiara Greco",
    "Davide Bruno", "Valentina Gallo", "Stefano Conti", "Federica Costa",
    "Alessandro Giordano", "Martina Mancini", "Francesco Rizzo",
    "Ilaria Lombardi", "Simone Moretti", "Alice Barbieri",
    "Pietro Fontana", "Beatrice Santoro",
)

LOST_REASONS = ("price", "no_budget", "competitor", "no_fit", "timing", "silent")
LOST_REASON_WEIGHTS = (0.25, 0.20, 0.20, 0.10, 0.15, 0.10)
TICKET_SEVERITIES = ("low", "medium", "high", "critical")
TICKET_SEVERITY_WEIGHTS = (0.45, 0.35, 0.15, 0.05)

# How many closed leads carry a proposal-stage scoring point.  A lead that goes
# straight from contacted to proposal is still "qualified" at that instant; this
# is what gives the labeled population a non-constant is_proposal_stage.
FAST_TRACK_PROPOSAL_P = 0.03
REACH_PROPOSAL_P = 0.65
ANSWERED_P = 0.90
QUALIFY_P = 0.82

# Every rep needs a measured 180-day win rate from the first scored lead.  These
# are early-stage initiatives that closed *without* reaching qualified, so they
# seed rep history without entering the labelled population.  They are spread
# less than 180 days apart, so at any snapshot each rep has a recent closure.
SEED_LEAD_DATES = (
    date(2024, 1, 1),
    date(2024, 5, 1),
    date(2024, 9, 1),
    date(2025, 1, 1),
    date(2025, 5, 1),
    date(2025, 9, 1),
)

# ---------------------------------------------------------------------------
# Hazard: exactly docs/LABEL.md
# ---------------------------------------------------------------------------

HAZARD_INTERCEPT = -0.95
BETA_LOG_RESPONSE = -0.45
BETA_MEETINGS = 0.25
BETA_PROPOSAL = 0.30
BETA_PRIOR_WON = 0.40
BETA_PRIOR_LOST = -0.30
BETA_OWNER_WIN_RATE = 0.35
BETA_DAYS_SINCE_LAST = 0.20
BETA_AMOUNT = -0.25
BETA_DISCOUNT = -0.20
BETA_TICKETS = -0.25
BETA_NPS = 0.20
NOISE_SD = 0.40

# z() uses a fixed global reference scale, never a per-region or per-snapshot
# refit.  CALIBRATED_Z stores the scored-population mean and SD from the
# deterministic seed-42 calibration.  Z_REFERENCE_SCALE converts those SDs to
# the reference scale used by the hazard: reference SD = scored SD / 1.25, so
# z = (x - mean) * 1.25 / scored_sd.  This is a scale conversion, not a second
# standardisation, and it is applied identically everywhere.  The constant is
# fixed so the world's true latent AUC is ~0.79, the documented signal ceiling
# (a model should land around 0.77-0.79; materially above means leakage).
Z_REFERENCE_SCALE = 1.25

# Population parameters for z().  They were measured from a deterministic
# seed-42 calibration of this same generating process, with a damped fixed-point
# iteration so the lagged outcomes (prior wins/losses, rep win rate) are
# self-consistent.  Fixing them here keeps the outcome pass causal and one-shot;
# no outcome is needed to standardise an input.  The NULL ("not measured")
# feature states contribute neutrally.
CALIBRATED_Z: dict[str, tuple[float, float]] = {
    "log_response": (2.23622196, 0.77309021),
    "meetings": (2.13690664, 1.25527411),
    "prior_won": (0.22160970, 0.54767257),
    "prior_lost": (0.64554761, 0.91573950),
    "owner_win_rate": (0.24866004, 0.10283417),
    "neg_days_since_last": (-1302.88484388, 2010.52319764),
    "amount_arr": (36246.04918124, 26851.75449610),
    "discount_pct": (8.82963269, 8.35726263),
    "tickets_90d": (0.34942098, 0.60309205),
    "nps_last": (14.75480686, 34.99411608),
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def random_dt(rng: random.Random, start: datetime, end: datetime) -> datetime:
    """Uniform datetime in [start, end]."""
    if end <= start:
        return start
    span = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randrange(span + 1))


def whole_second(value: datetime) -> datetime:
    """Drop sub-second precision at assignment, not only at persistence."""
    return value.replace(microsecond=0)


def poisson_draw(rng: random.Random, lam: float) -> int:
    """Knuth's Poisson sampler (lambda is small everywhere here)."""
    if lam <= 0:
        return 0
    limit = math.exp(-lam)
    k = 0
    product = 1.0
    while True:
        k += 1
        product *= rng.random()
        if product <= limit:
            return k - 1


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def italian_vat(number: int) -> str:
    """Format-plausible Italian VAT: 11 digits with a valid check digit."""
    progressive = number + 1
    office = (number % 100) + 1
    base = f"{progressive:07d}{office:03d}"
    total = 0
    for index, char in enumerate(base):
        digit = int(char)
        if index % 2 == 0:  # 1st, 3rd, ... 9th digit (1-based)
            total += digit
        else:
            doubled = digit * 2
            total += doubled - 9 if doubled > 9 else doubled
    check = (10 - (total % 10)) % 10
    return f"{base}{check}"


def ols_slope(values: list[int] | tuple[int, ...]) -> float:
    """OLS slope of values against 0..n-1."""
    n = len(values)
    if n < 2:
        return 0.0
    sum_x = n * (n - 1) / 2.0
    sum_y = float(sum(values))
    sum_xx = (n - 1) * n * (2 * n - 1) / 6.0
    sum_xy = float(sum(index * value for index, value in enumerate(values)))
    denominator = n * sum_xx - sum_x * sum_x
    if denominator == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denominator


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat(timespec="seconds")


def dt_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------------------
# In-memory entities and raw-world containers
# ---------------------------------------------------------------------------


@dataclass
class Company:
    id: str
    name: str
    vat: str
    region: str
    city: str
    industry: str
    employees: int
    created_at: datetime
    owner_rep: str


@dataclass
class Lead:
    id: str
    company_id: str
    created_at: datetime
    source: str
    owner_rep: str
    first_response_hours: float | None
    first_response_at: datetime | None
    qualified_at: datetime | None
    proposal_at: datetime | None
    closed_at: datetime | None
    amount_arr: float
    discount_pct: float
    is_closed: bool = False
    is_legacy: bool = False
    open_status: str = "new"
    stage_at_scoring: str = "qualified"
    status: str = "new"
    lost_reason: str | None = None
    prev_created_at: datetime | None = None


@dataclass
class RawWorld:
    companies: list[Company]
    company_by_id: dict[str, Company]
    company_leads: dict[str, list[Lead]]
    usage_by_company: dict[str, dict[date, int]]
    week_starts: list[date]
    tickets_by_company: dict[str, list[datetime]]
    invoices_by_company: dict[str, list[tuple[datetime, datetime | None]]]
    nps_by_company: dict[str, list[tuple[datetime, int]]]
    meetings_by_lead: dict[str, list[datetime]]
    interaction_rows: list[tuple[Any, ...]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Company and lead generation
# ---------------------------------------------------------------------------


def generate_companies(rng: random.Random, count: int) -> list[Company]:
    combinations = [
        (surname, noun, legal)
        for surname in SURNAMES
        for noun in BUSINESS_NOUNS
        for legal in LEGAL_FORMS
    ]
    rng.shuffle(combinations)

    companies: list[Company] = []
    for index in range(count):
        if index < len(combinations):
            surname, noun, legal = combinations[index]
            name = f"{surname} {noun} {legal}"
        else:  # pragma: no cover - the default 20k fits in the combination pool
            name = f"Impresa {index + 1} S.r.l."

        region = rng.choices(REGIONS, weights=[REGION_WEIGHTS[r] for r in REGIONS])[0]
        city = rng.choice(CITIES[region])
        industry = rng.choice(INDUSTRIES)
        employees = int(
            clamp(
                round(rng.lognormvariate(math.log(75.0), 0.95)),
                3,
                15_000,
            )
        )
        created_at = random_dt(rng, COMPANY_CREATED_START, COMPANY_CREATED_END)
        owner_rep = rng.choice(REPS)
        companies.append(
            Company(
                id=f"C{index + 1:06d}",
                name=name,
                vat=italian_vat(index),
                region=region,
                city=city,
                industry=industry,
                employees=employees,
                created_at=created_at,
                owner_rep=owner_rep,
            )
        )
    return companies


def adjust_counts_to_total(
    rng: random.Random,
    counts: list[int],
    target: int,
    cap: int = MAX_NORMAL_LEADS_PER_COMPANY,
) -> None:
    total = sum(counts)
    if total < target:
        order = list(range(len(counts)))
        rng.shuffle(order)
        cursor = 0
        while total < target:
            index = order[cursor % len(order)]
            if counts[index] < cap:
                counts[index] += 1
                total += 1
            cursor += 1
    elif total > target:
        order = [index for index, value in enumerate(counts) if value > 0]
        rng.shuffle(order)
        cursor = 0
        while total > target:
            index = order[cursor % len(order)]
            if counts[index] > 0:
                counts[index] -= 1
                total -= 1
            cursor += 1


def simulate_lead_stage(
    rng: random.Random,
    lead_id: str,
    company: Company,
    created_at: datetime,
    source: str,
    owner_rep: str,
    amount_arr: float,
    discount_pct: float,
) -> Lead:
    """Draw the lead lifecycle up to t0.  Future events are stored as NULL."""
    answered = rng.random() < ANSWERED_P
    first_response_hours: float | None = None
    first_response_at: datetime | None = None
    response_at: datetime | None = None
    if answered:
        hours = clamp(rng.lognormvariate(math.log(8.0), 0.90), 0.10, 240.0)
        candidate = whole_second(created_at + timedelta(hours=hours))
        if candidate <= T0:
            response_at = candidate
            first_response_at = candidate
            first_response_hours = round(
                (candidate - created_at).total_seconds() / 3600.0, 1
            )
        else:
            answered = False

    qualified_at: datetime | None = None
    proposal_at: datetime | None = None
    closed_at: datetime | None = None
    fast_track = False
    open_status = "new"

    if answered and response_at is not None:
        open_status = "contacted"
        if rng.random() < QUALIFY_P:
            qualification_days = clamp(
                rng.lognormvariate(math.log(12.0), 0.70), 1.0, 90.0
            )
            candidate_qualified = whole_second(
                response_at + timedelta(days=qualification_days)
            )
            if candidate_qualified <= T0:
                qualified_at = candidate_qualified
                open_status = "qualified"

                fast_track = rng.random() < FAST_TRACK_PROPOSAL_P
                proposal_after_t0 = False
                if fast_track:
                    proposal_at = qualified_at
                elif rng.random() < REACH_PROPOSAL_P:
                    proposal_days = clamp(
                        rng.lognormvariate(math.log(14.0), 0.70), 1.0, 120.0
                    )
                    candidate_proposal = whole_second(
                        qualified_at + timedelta(days=proposal_days)
                    )
                    if candidate_proposal <= T0:
                        proposal_at = candidate_proposal
                    else:
                        proposal_after_t0 = True

                if proposal_at is not None:
                    open_status = "proposal"
                    close_days = clamp(
                        rng.lognormvariate(math.log(30.0), 0.80), 2.0, 180.0
                    )
                    candidate_close = whole_second(
                        proposal_at + timedelta(days=close_days)
                    )
                elif proposal_after_t0:
                    # The proposal has not happened by t0, so the lead cannot
                    # close by t0 either; it stays at qualified.
                    candidate_close = None
                else:
                    close_days = clamp(
                        rng.lognormvariate(math.log(22.0), 0.80), 2.0, 150.0
                    )
                    candidate_close = whole_second(
                        qualified_at + timedelta(days=close_days)
                    )

                if candidate_close is not None and candidate_close <= T0:
                    closed_at = candidate_close

    is_closed = closed_at is not None
    if is_closed:
        open_status = "proposal" if proposal_at is not None else "qualified"
        stage_at_scoring = "proposal" if fast_track else "qualified"
    elif qualified_at is not None:
        open_status = "proposal" if proposal_at is not None else "qualified"
        stage_at_scoring = open_status
    else:
        stage_at_scoring = "qualified"  # unused: no feature row without qualification

    return Lead(
        id=lead_id,
        company_id=company.id,
        created_at=created_at,
        source=source,
        owner_rep=owner_rep,
        first_response_hours=first_response_hours,
        first_response_at=first_response_at,
        qualified_at=qualified_at,
        proposal_at=proposal_at,
        closed_at=closed_at,
        amount_arr=amount_arr,
        discount_pct=discount_pct,
        is_closed=is_closed,
        open_status=open_status,
        stage_at_scoring=stage_at_scoring,
        status="new" if not is_closed else "pending",
    )


def generate_leads(
    rng: random.Random, companies: list[Company], target_leads: int
) -> tuple[list[Lead], dict[str, list[Lead]]]:
    seeded_rep_count = sum(1 for index in range(len(REPS)) if index % 4 != 3)
    seed_total = min(target_leads, seeded_rep_count * len(SEED_LEAD_DATES))
    normal_target = max(0, target_leads - seed_total)

    normal_capacity = len(companies) * MAX_NORMAL_LEADS_PER_COMPANY
    if normal_target > normal_capacity:
        limit = normal_capacity + seed_total
        raise ValueError(
            f"cannot allocate {target_leads} leads: limit is {limit} "
            f"({len(companies)} companies x {MAX_NORMAL_LEADS_PER_COMPANY} "
            f"normal leads + {seed_total} rep-history seeds)"
        )

    counts = [
        min(15, poisson_draw(rng, float(LEADS_PER_COMPANY))) for _ in companies
    ]
    adjust_counts_to_total(rng, counts, normal_target)

    leads: list[Lead] = []
    company_leads: dict[str, list[Lead]] = {
        company.id: [] for company in companies
    }
    lead_number = 0

    for company, count in zip(companies, counts):
        raw_created: list[datetime] = []
        start = max(HISTORY_START, company.created_at + timedelta(days=1))
        end = T0 - timedelta(minutes=1)
        for _ in range(count):
            raw_created.append(random_dt(rng, start, end))
        raw_created.sort()

        for created_at in raw_created:
            lead_number += 1
            lead_id = f"L{lead_number:06d}"
            owner_rep = (
                company.owner_rep if rng.random() < 0.85 else rng.choice(REPS)
            )
            source = rng.choices(SOURCES, weights=SOURCE_WEIGHTS)[0]

            size_scale = 0.60 + 0.40 * math.log10(company.employees / 10.0 + 1.0)
            amount = clamp(
                rng.lognormvariate(math.log(30_000.0), 0.65) * size_scale,
                4_000.0,
                400_000.0,
            )
            amount_arr = round(amount / 100.0) * 100.0

            if rng.random() < 0.35:
                discount_pct = 0.0
            else:
                discount_pct = round(rng.uniform(2.0, 25.0), 1)

            lead = simulate_lead_stage(
                rng,
                lead_id,
                company,
                created_at,
                source,
                owner_rep,
                amount_arr,
                discount_pct,
            )
            company_leads[company.id].append(lead)
            leads.append(lead)

    # Rep-history seeds: closed, never qualified, and therefore outside the
    # labelled population.  They keep owner_win_rate_180d measured rather than
    # forcing a sentinel.  One rep in four is deliberately left unseeded, so the
    # rep with no prior closures (NULL) case is reachable too.  Prefer companies
    # that already existed by 2024-01-01; if a degenerate --companies count has
    # none, slide the seed to just after the chosen company's creation so the
    # count is preserved without inventing a row before its company existed.
    seed_company_cutoff = datetime(2024, 1, 1, 8, 0, 0)
    eligible_companies = [
        company for company in companies if company.created_at <= seed_company_cutoff
    ]
    seed_pool = eligible_companies if eligible_companies else companies
    for rep_index, rep in enumerate(REPS):
        if rep_index % 4 == 3:
            continue
        for seed_index, seed_date in enumerate(SEED_LEAD_DATES):
            if lead_number >= target_leads:
                break
            lead_number += 1
            company = seed_pool[
                (rep_index * 37 + seed_index * 101) % len(seed_pool)
            ]
            created_at = datetime(
                seed_date.year, seed_date.month, seed_date.day, 9, 0, 0
            )
            if created_at < company.created_at:
                created_at = company.created_at + timedelta(hours=1)
            amount_arr = (
                round(
                    clamp(
                        rng.lognormvariate(math.log(25_000.0), 0.70),
                        4_000.0,
                        200_000.0,
                    )
                    / 100.0
                )
                * 100.0
            )
            seed = Lead(
                id=f"L{lead_number:06d}",
                company_id=company.id,
                created_at=created_at,
                source=rng.choices(SOURCES, weights=SOURCE_WEIGHTS)[0],
                owner_rep=rep,
                first_response_hours=None,
                first_response_at=None,
                qualified_at=None,
                proposal_at=None,
                closed_at=created_at + timedelta(hours=6),
                amount_arr=amount_arr,
                discount_pct=round(rng.uniform(0.0, 15.0), 1),
                is_closed=True,
                is_legacy=True,
                open_status="contacted",
                stage_at_scoring="qualified",
                status="lost",
                lost_reason="silent",
            )
            company_leads[company.id].append(seed)
            leads.append(seed)

    for company in companies:
        ordered = company_leads[company.id]
        ordered.sort(key=lambda item: (item.created_at, item.id))
        for index, lead in enumerate(ordered):
            lead.prev_created_at = (
                ordered[index - 1].created_at if index > 0 else company.created_at
            )

    return leads, company_leads


# ---------------------------------------------------------------------------
# Raw history: usage, tickets, invoices, NPS, interactions
# ---------------------------------------------------------------------------


def build_week_starts() -> list[date]:
    weeks: list[date] = []
    cursor = HISTORY_START.date()
    while datetime.combine(cursor + timedelta(days=7), datetime.min.time()) <= T0:
        weeks.append(cursor)
        cursor += timedelta(days=7)
    return weeks


def generate_usage(
    rng: random.Random, company: Company, week_starts: list[date]
) -> dict[date, int]:
    company_number = int(company.id[1:])
    flat = company_number % 20 == 0
    base = max(
        1.0,
        (8.0 + 5.0 * math.log2(company.employees + 1)) * rng.uniform(0.55, 1.65),
    )
    trend = 0.0 if flat else rng.gauss(0.0, 0.12)
    phase = rng.uniform(0.0, 2.0 * math.pi)
    company_day = company.created_at.date()
    events: dict[date, int] = {}
    for index, week_start in enumerate(week_starts):
        # Do not materialise a row for a week that ended before the company
        # existed: pre-creation zeros are not observed usage.
        if week_start + timedelta(days=7) <= company_day:
            continue
        if flat:
            events[week_start] = max(0, int(round(base)))
            continue
        seasonal = 0.10 * base * math.sin(2.0 * math.pi * index / 52.0 + phase)
        noise = rng.gauss(0.0, 0.12 * base)
        value = base + trend * index + seasonal + noise
        events[week_start] = max(0, int(round(value)))
    return events


def generate_tickets(
    rng: random.Random, company: Company
) -> list[tuple[Any, ...]]:
    lam = min(8.0, 1.0 + 2.0 * math.log10(max(company.employees, 3) / 10.0 + 1.0))
    count = poisson_draw(rng, lam)
    start = max(HISTORY_START, company.created_at + timedelta(hours=1))
    end = T0 - timedelta(hours=1)
    rows: list[tuple[Any, ...]] = []
    if start >= end:
        return rows
    for _ in range(count):
        opened_at = random_dt(rng, start, end)
        severity = rng.choices(
            TICKET_SEVERITIES, weights=TICKET_SEVERITY_WEIGHTS
        )[0]
        resolution_hours = clamp(
            rng.lognormvariate(math.log(24.0), 0.90), 0.25, 1_500.0
        )
        candidate_close = opened_at + timedelta(hours=resolution_hours)
        if candidate_close <= T0:
            closed_at = candidate_close
            stored_resolution: float | None = round(resolution_hours, 2)
        else:
            closed_at = None
            stored_resolution = None
        rows.append(
            (
                company.id,
                opened_at,
                closed_at,
                severity,
                stored_resolution,
            )
        )
    return rows


def generate_invoices(
    rng: random.Random, company: Company
) -> list[tuple[datetime, datetime, datetime | None, float]]:
    """A baseline invoice plus quarterly billing.

    One company in five is never invoiced, so ``payment_delay_days_avg_180d``
    reaches NULL ("not measured").  A few companies are perfectly on-time, and
    a deterministic slice of individual invoices is on-time, so the measured
    zero case is real too.  Only rows whose due date has happened by t0 are
    written.
    """
    company_number = int(company.id[1:])
    if company_number % 5 == 1:
        return []

    start = max(HISTORY_START, company.created_at)
    pay_base = rng.gauss(2.0, 9.0)
    always_on_time = company_number % 41 == 0
    rows: list[tuple[datetime, datetime, datetime | None, float]] = []
    invoice_index = 0

    def add_invoice(issued_at: datetime, terms: int) -> None:
        nonlocal invoice_index
        due_at = issued_at + timedelta(days=terms)
        if issued_at > T0 or due_at > T0:
            return
        invoice_index += 1
        amount = round(
            clamp(
                rng.lognormvariate(math.log(20_000.0), 0.80),
                1_000.0,
                300_000.0,
            ),
            2,
        )
        if always_on_time or (company_number + invoice_index) % 17 == 0:
            delay_days = 0.0
        else:
            delay_days = clamp(pay_base + rng.gauss(0.0, 6.0), -20.0, 120.0)
        paid_at = max(due_at + timedelta(days=delay_days), issued_at)
        stored_paid: datetime | None = paid_at if paid_at <= T0 else None
        rows.append((issued_at, due_at, stored_paid, amount))

    add_invoice(start, 1)
    for quarter in range(1, 9):
        add_invoice(start + timedelta(days=90 * quarter), 30)
    return rows


def generate_nps(
    rng: random.Random, company: Company
) -> list[tuple[datetime, int]]:
    """Onboarding survey plus occasional follow-ups.

    One company in five is never surveyed: that is how ``nps_last`` reaches
    NULL ("not measured") rather than a sentinel zero.  For surveyed companies
    the onboarding survey happens at the start of observable history, before the
    first possible qualification, so ``nps_last`` is measured for every scored
    lead of that company.
    """
    company_number = int(company.id[1:])
    if company_number % 5 == 0:
        return []

    start = max(HISTORY_START, company.created_at)
    end = T0 - timedelta(days=1)
    disposition = clamp(rng.gauss(15.0, 30.0), -70.0, 85.0)
    used: set[datetime] = set()
    rows: list[tuple[datetime, int]] = []

    def add_survey(surveyed_at: datetime, force_zero: bool = False) -> None:
        while surveyed_at in used:
            surveyed_at += timedelta(seconds=1)
        if surveyed_at > T0:
            return
        used.add(surveyed_at)
        if force_zero:
            score = 0
        else:
            score = int(round(clamp(rng.gauss(disposition, 20.0), -100.0, 100.0)))
        rows.append((surveyed_at, score))

    # Guarantee a measured zero as well as a measured positive/negative score.
    force_zero = company_number % 37 == 0
    add_survey(start, force_zero=force_zero)
    if force_zero:
        # No later survey can turn the latest score into a non-zero value.
        return rows
    count = poisson_draw(rng, 1.8)
    follow_up_start = start + timedelta(days=1)
    if follow_up_start < end:
        for _ in range(count):
            add_survey(random_dt(rng, follow_up_start, end))
    return rows


def generate_interactions(
    rng: random.Random, leads: list[Lead]
) -> tuple[list[tuple[Any, ...]], dict[str, list[datetime]]]:
    rows: list[tuple[Any, ...]] = []
    meetings_by_lead: dict[str, list[datetime]] = {}
    interaction_number = 0

    def add(
        lead: Lead,
        kind: str,
        direction: str,
        occurred_at: datetime,
        answered: int,
    ) -> None:
        nonlocal interaction_number
        interaction_number += 1
        rows.append(
            (
                f"X{interaction_number:07d}",
                lead.company_id,
                lead.id,
                kind,
                direction,
                iso(occurred_at),
                answered,
            )
        )

    for lead in leads:
        life_end = lead.closed_at if lead.closed_at is not None else T0
        if life_end <= lead.created_at:
            life_end = min(lead.created_at + timedelta(hours=1), T0)
        if life_end <= lead.created_at:
            meetings_by_lead[lead.id] = []
            continue

        meeting_times: list[datetime] = []
        if lead.qualified_at is not None:
            pre_end = min(life_end, lead.qualified_at)
            pre_count = max(1, poisson_draw(rng, 2.0))
            for _ in range(min(pre_count, 8)):
                occurred_at = random_dt(rng, lead.created_at, pre_end)
                meeting_times.append(occurred_at)
                add(lead, "meeting", "outbound", occurred_at, 1)
            if lead.is_closed and lead.closed_at is not None:
                post_count = poisson_draw(rng, 0.8)
                for _ in range(min(post_count, 3)):
                    occurred_at = random_dt(rng, lead.qualified_at, lead.closed_at)
                    meeting_times.append(occurred_at)
                    add(lead, "meeting", "outbound", occurred_at, 1)
        else:
            count = poisson_draw(rng, 1.0)
            for _ in range(min(count, 4)):
                occurred_at = random_dt(rng, lead.created_at, life_end)
                meeting_times.append(occurred_at)
                add(lead, "meeting", "outbound", occurred_at, 1)

        meetings_by_lead[lead.id] = meeting_times

        call_count = poisson_draw(rng, 1.8)
        for _ in range(min(call_count, 6)):
            occurred_at = random_dt(rng, lead.created_at, life_end)
            direction = "outbound" if rng.random() < 0.80 else "inbound"
            answered = 1 if rng.random() < 0.55 else 0
            add(lead, "call", direction, occurred_at, answered)

        email_count = poisson_draw(rng, 2.2)
        for _ in range(min(email_count, 8)):
            occurred_at = random_dt(rng, lead.created_at, life_end)
            direction = "inbound" if rng.random() < 0.55 else "outbound"
            answered = 1 if rng.random() < 0.60 else 0
            add(lead, "email", direction, occurred_at, answered)

        if (
            lead.first_response_at is not None
            and lead.created_at <= lead.first_response_at <= life_end
        ):
            add(lead, "email", "inbound", lead.first_response_at, 1)

    return rows, meetings_by_lead


# ---------------------------------------------------------------------------
# Point-in-time features and the hazard
# ---------------------------------------------------------------------------


def window_usage(
    world: RawWorld, company_id: str, snapshot: datetime
) -> list[int]:
    """Observed weekly events in the 90 days before snapshot.

    Only completed weeks are included; weeks before the company existed were
    never materialised, so they cannot pad the two-week minimum.
    """
    low = snapshot.date() - timedelta(days=90)
    high = snapshot.date() - timedelta(days=7)
    return [
        events
        for week_start, events in sorted(
            world.usage_by_company[company_id].items()
        )
        if low <= week_start <= high
    ]


def compute_feature_values(
    lead: Lead,
    company: Company,
    snapshot: datetime,
    stage_at_scoring: str,
    world: RawWorld,
    company_history: dict[str, list[tuple[str, datetime, int, float]]],
    rep_history: dict[str, list[tuple[str, datetime, int]]],
) -> dict[str, Any]:
    """Every value is filtered to information available at ``snapshot``."""
    prior_won = 0
    prior_lost = 0
    lifetime_won_arr = 0.0
    for history_lead_id, closed_at, won, amount in company_history.get(
        company.id, []
    ):
        # Never let the scored record's own closure enter its features.
        if history_lead_id != lead.id and closed_at < snapshot:
            if won:
                prior_won += 1
                lifetime_won_arr += amount
            else:
                prior_lost += 1

    open_count = 0
    for other in world.company_leads[company.id]:
        if other.id == lead.id:
            continue
        if other.created_at <= snapshot and (
            other.closed_at is None or other.closed_at > snapshot
        ):
            open_count += 1

    # Snapshot-relative: the gap is measured from the scoring point, not from
    # the scored lead's own creation (LABEL.md convention 1).
    previous = lead.prev_created_at or company.created_at
    days_since_last = max(0, (snapshot.date() - previous.date()).days)

    usage_values = window_usage(world, company.id, snapshot)
    usage_trend: float | None = (
        round(ols_slope(usage_values), 6) if len(usage_values) >= 2 else None
    )

    low_90 = snapshot - timedelta(days=90)
    tickets_90d = sum(
        1
        for opened_at in world.tickets_by_company.get(company.id, [])
        if low_90 <= opened_at <= snapshot
    )

    nps_last: int | None = None
    latest_survey: datetime | None = None
    for surveyed_at, score in world.nps_by_company.get(company.id, []):
        if surveyed_at <= snapshot and (
            latest_survey is None or surveyed_at > latest_survey
        ):
            latest_survey = surveyed_at
            nps_last = score
    # NULL means "not measured".  The generator never turns it into a zero.
    nps_value = nps_last

    low_180 = snapshot - timedelta(days=180)
    delays: list[int] = []
    for due_at, paid_at in world.invoices_by_company.get(company.id, []):
        if low_180 <= due_at <= snapshot:
            if paid_at is not None and paid_at <= snapshot:
                delays.append((paid_at.date() - due_at.date()).days)
            else:
                delays.append((snapshot.date() - due_at.date()).days)
    payment_delay: float | None = (
        round(sum(delays) / len(delays), 2) if delays else None
    )

    meetings = sum(
        1
        for occurred_at in world.meetings_by_lead.get(lead.id, [])
        if occurred_at <= snapshot
    )

    recent_rep: list[int] = [
        won
        for history_lead_id, closed_at, won in rep_history.get(lead.owner_rep, [])
        if history_lead_id != lead.id and low_180 <= closed_at < snapshot
    ]
    owner_win_rate: float | None = (
        round(sum(recent_rep) / len(recent_rep), 6) if recent_rep else None
    )

    first_response_at_value: datetime | None = None
    first_response_hours_value: float | None = None
    if lead.first_response_at is not None and lead.first_response_at <= snapshot:
        first_response_at_value = lead.first_response_at
        first_response_hours_value = round(
            (lead.first_response_at - lead.created_at).total_seconds() / 3600.0,
            1,
        )

    return {
        "lead_id": lead.id,
        "snapshot_date": snapshot.isoformat(timespec="seconds"),
        "source": lead.source,
        "stage_at_scoring": stage_at_scoring,
        "age_days_at_scoring": max(
            0, (snapshot.date() - lead.created_at.date()).days
        ),
        "amount_arr": lead.amount_arr,
        "discount_pct": lead.discount_pct,
        "first_response_hours": first_response_hours_value,
        "first_response_at": (
            None
            if first_response_at_value is None
            else first_response_at_value.isoformat(timespec="seconds")
        ),
        "region": company.region,
        "industry": company.industry,
        "employees": company.employees,
        "company_age_days": max(
            0, (snapshot.date() - company.created_at.date()).days
        ),
        "prior_won_initiatives": prior_won,
        "prior_lost_initiatives": prior_lost,
        "days_since_last_initiative": days_since_last,
        "lifetime_won_arr": round(lifetime_won_arr, 2),
        "open_initiatives_count": open_count,
        "usage_trend_slope": usage_trend,
        "tickets_90d": tickets_90d,
        "nps_last": nps_value,
        "payment_delay_days_avg_180d": payment_delay,
        "meetings_before_scoring": meetings,
        "owner_win_rate_180d": owner_win_rate,
    }


def z_value(
    value: float | None, key: str, stats: dict[str, tuple[float, float]]
) -> float:
    """z-score, with NULL ("not measured") contributing neutrally."""
    if value is None:
        return 0.0
    mean, sd = stats.get(key, (0.0, 1.0))
    if sd <= 0:
        return 0.0
    return (value - mean) * Z_REFERENCE_SCALE / sd


def hazard_logit(
    row: dict[str, Any], stats: dict[str, tuple[float, float]]
) -> float:
    """The exact logit from docs/LABEL.md."""
    logit = HAZARD_INTERCEPT
    if row["first_response_hours"] is not None:
        logit += BETA_LOG_RESPONSE * z_value(
            math.log1p(float(row["first_response_hours"])), "log_response", stats
        )
    logit += BETA_MEETINGS * z_value(
        float(row["meetings_before_scoring"]), "meetings", stats
    )
    logit += BETA_PROPOSAL * (1.0 if row["stage_at_scoring"] == "proposal" else 0.0)
    logit += BETA_PRIOR_WON * z_value(
        float(row["prior_won_initiatives"]), "prior_won", stats
    )
    logit += BETA_PRIOR_LOST * z_value(
        float(row["prior_lost_initiatives"]), "prior_lost", stats
    )
    logit += BETA_OWNER_WIN_RATE * z_value(
        row["owner_win_rate_180d"], "owner_win_rate", stats
    )
    logit += BETA_DAYS_SINCE_LAST * z_value(
        -float(row["days_since_last_initiative"]), "neg_days_since_last", stats
    )
    logit += BETA_AMOUNT * z_value(
        float(row["amount_arr"]), "amount_arr", stats
    )
    logit += BETA_DISCOUNT * z_value(
        float(row["discount_pct"]), "discount_pct", stats
    )
    logit += BETA_TICKETS * z_value(
        float(row["tickets_90d"]), "tickets_90d", stats
    )
    logit += BETA_NPS * z_value(row["nps_last"], "nps_last", stats)
    logit += SOURCE_EFFECT[row["source"]]
    logit += REGION_EFFECT[row["region"]]
    return logit


def choose_lost_reason(rng: random.Random) -> str:
    return rng.choices(LOST_REASONS, weights=LOST_REASON_WEIGHTS)[0]


def simulate_outcomes(
    leads: list[Lead],
    world: RawWorld,
    z_stats: dict[str, tuple[float, float]],
    outcome_seed: int,
) -> list[dict[str, Any]]:
    """Causally walk closed qualified leads and draw win/loss."""
    outcome_rng = random.Random(outcome_seed)

    for lead in leads:
        if lead.is_legacy:
            lead.status = "lost"
            lead.lost_reason = "silent"
        elif lead.is_closed:
            lead.status = "pending"
            lead.lost_reason = None
        else:
            lead.status = lead.open_status
            lead.lost_reason = None

    company_history: dict[str, list[tuple[str, datetime, int, float]]] = defaultdict(
        list
    )
    rep_history: dict[str, list[tuple[str, datetime, int]]] = defaultdict(list)

    # Seed rep/company history with the early-stage losses that never reached
    # qualified.  They are not labels, but they are real closures a rep or
    # account did have, so the 180-day win-rate feature is measured.
    for lead in leads:
        if lead.is_legacy and lead.closed_at is not None:
            company_history[lead.company_id].append(
                (lead.id, lead.closed_at, 0, lead.amount_arr)
            )
            rep_history[lead.owner_rep].append((lead.id, lead.closed_at, 0))

    closed_leads = sorted(
        (
            lead
            for lead in leads
            if lead.is_closed and not lead.is_legacy and lead.qualified_at is not None
        ),
        key=lambda item: (item.qualified_at, item.id),  # type: ignore[arg-type,return-value]
    )

    outcomes: list[dict[str, Any]] = []

    for lead in closed_leads:
        assert lead.qualified_at is not None
        company = world.company_by_id[lead.company_id]
        row = compute_feature_values(
            lead,
            company,
            lead.qualified_at,
            lead.stage_at_scoring,
            world,
            company_history,
            rep_history,
        )
        logit = hazard_logit(row, z_stats)
        noise = outcome_rng.gauss(0.0, NOISE_SD)
        probability = sigmoid(logit + noise)
        won = 1 if outcome_rng.random() < probability else 0

        lead.status = "won" if won else "lost"
        lead.lost_reason = None if won else choose_lost_reason(outcome_rng)

        company_history[lead.company_id].append(
            (lead.id, lead.closed_at, won, lead.amount_arr)  # type: ignore[arg-type]
        )
        rep_history[lead.owner_rep].append(
            (lead.id, lead.closed_at, won)  # type: ignore[arg-type]
        )

        outcomes.append(
            {
                "lead_id": lead.id,
                "snapshot_date": row["snapshot_date"],
                "won": won,
                "closed_at": iso(lead.closed_at),
                "latent_p": probability,
            }
        )

    return outcomes


# ---------------------------------------------------------------------------
# Database writing
# ---------------------------------------------------------------------------


def insert_rows(
    connection: sqlite3.Connection, sql: str, rows: list[tuple[Any, ...]]
) -> None:
    if rows:
        connection.executemany(sql, rows)


def write_database(
    db_path: Path,
    companies: list[Company],
    leads: list[Lead],
    world: RawWorld,
    outcomes: list[dict[str, Any]],
    ticket_rows: list[tuple[Any, ...]],
    invoice_rows: list[tuple[Any, ...]],
    nps_rows: list[tuple[Any, ...]],
    overwrite: bool = False,
) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")

    if db_path.exists() and not overwrite:
        raise FileExistsError(
            f"refusing to overwrite existing database {db_path}; "
            "pass --overwrite to replace it"
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-journal", "-wal", "-shm"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute("PRAGMA journal_mode = MEMORY")
        connection.executescript(schema_sql)
        connection.execute("BEGIN")

        insert_rows(
            connection,
            "INSERT INTO companies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    company.id,
                    company.name,
                    company.vat,
                    company.region,
                    company.city,
                    company.industry,
                    company.employees,
                    iso(company.created_at),
                    company.owner_rep,
                )
                for company in companies
            ],
        )

        insert_rows(
            connection,
            "INSERT INTO leads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    lead.id,
                    lead.company_id,
                    iso(lead.created_at),
                    lead.status,
                    lead.source,
                    lead.owner_rep,
                    lead.first_response_hours,
                    iso(lead.first_response_at),
                    iso(lead.qualified_at),
                    iso(lead.proposal_at),
                    iso(lead.closed_at),
                    lead.lost_reason,
                    lead.amount_arr,
                    lead.discount_pct,
                )
                for lead in leads
            ],
        )

        usage_batch: list[tuple[Any, ...]] = []
        for company in companies:
            for week_start, value in sorted(
                world.usage_by_company[company.id].items()
            ):
                usage_batch.append(
                    (company.id, week_start.isoformat(), int(value))
                )
            if len(usage_batch) >= 20_000:
                insert_rows(
                    connection,
                    "INSERT INTO company_usage_weekly VALUES (?, ?, ?)",
                    usage_batch,
                )
                usage_batch.clear()
        insert_rows(
            connection,
            "INSERT INTO company_usage_weekly VALUES (?, ?, ?)",
            usage_batch,
        )

        insert_rows(
            connection,
            "INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)",
            ticket_rows,
        )
        insert_rows(
            connection,
            "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?)",
            invoice_rows,
        )
        insert_rows(
            connection,
            "INSERT INTO nps_surveys VALUES (?, ?, ?)",
            nps_rows,
        )
        insert_rows(
            connection,
            "INSERT INTO interactions VALUES (?, ?, ?, ?, ?, ?, ?)",
            world.interaction_rows,
        )

        insert_rows(
            connection,
            "INSERT INTO lead_outcomes VALUES (?, ?, ?, ?, ?)",
            [
                (
                    outcome["lead_id"],
                    outcome["snapshot_date"],
                    outcome["won"],
                    outcome["closed_at"],
                    outcome["latent_p"],
                )
                for outcome in outcomes
            ],
        )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# Summary / audit helpers
# ---------------------------------------------------------------------------


def rank_auc(probabilities: list[float], labels: list[int]) -> float:
    """Mann-Whitney AUC, used only for the generator's stdout summary."""
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


def print_summary(
    companies: list[Company],
    leads: list[Lead],
    outcomes: list[dict[str, Any]],
) -> None:
    wins = sum(outcome["won"] for outcome in outcomes)
    prevalence = wins / len(outcomes) if outcomes else 0.0
    open_qualified = sum(
        1
        for lead in leads
        if (not lead.is_closed) and lead.qualified_at is not None
    )
    region_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    lead_by_id = {lead.id: lead for lead in leads}
    company_by_id = {company.id: company for company in companies}
    for outcome in outcomes:
        lead = lead_by_id[outcome["lead_id"]]
        region = company_by_id[lead.company_id].region
        region_totals[region][0] += 1
        region_totals[region][1] += outcome["won"]

    auc = rank_auc(
        [outcome["latent_p"] for outcome in outcomes],
        [outcome["won"] for outcome in outcomes],
    )

    print(f"companies            : {len(companies):,}")
    print(f"leads                : {len(leads):,}")
    print(f"rep-history seeds    : {sum(1 for lead in leads if lead.is_legacy):,}")
    print(f"closed qualified     : {len(outcomes):,}")
    print(f"open qualified       : {open_qualified:,}")
    print("lead_features rows   : 0 (left to ml/features.py)")
    print(f"win prevalence       : {prevalence:.3%} ({wins:,}/{len(outcomes):,})")
    print(f"latent-p AUC         : {auc:.3f}")
    print("regional win rates   :")
    for region in REGIONS:
        total, won = region_totals[region]
        rate = won / total if total else 0.0
        print(f"  {region:<11} {rate:.3%} ({won:,}/{total:,})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def generate(
    db_path: Path,
    seed: int = SEED,
    companies_count: int = DEFAULT_COMPANIES,
    leads_count: int | None = None,
    quiet: bool = False,
    overwrite: bool = False,
) -> tuple[list[Company], list[Lead], list[dict[str, Any]]]:
    if leads_count is None:
        leads_count = companies_count * LEADS_PER_COMPANY
    if companies_count <= 0:
        raise ValueError("companies must be positive")
    if leads_count < 0:
        raise ValueError("leads must be non-negative")
    if db_path.exists() and not overwrite:
        raise FileExistsError(
            f"refusing to overwrite existing database {db_path}; "
            "pass --overwrite to replace it"
        )

    rng = random.Random(seed)

    companies = generate_companies(rng, companies_count)
    leads, company_leads = generate_leads(rng, companies, leads_count)
    week_starts = build_week_starts()

    world = RawWorld(
        companies=companies,
        company_by_id={company.id: company for company in companies},
        company_leads=company_leads,
        usage_by_company={},
        week_starts=week_starts,
        tickets_by_company={},
        invoices_by_company={},
        nps_by_company={},
        meetings_by_lead={},
    )

    ticket_rows: list[tuple[Any, ...]] = []
    invoice_rows: list[tuple[Any, ...]] = []
    nps_rows: list[tuple[Any, ...]] = []
    ticket_number = 0
    invoice_number = 0

    for company in companies:
        events = generate_usage(rng, company, week_starts)
        world.usage_by_company[company.id] = events

        company_ticket_rows = generate_tickets(rng, company)
        opened_times: list[datetime] = []
        for company_id, opened_at, closed_at, severity, resolution in company_ticket_rows:
            ticket_number += 1
            ticket_id = f"T{ticket_number:07d}"
            opened_times.append(opened_at)
            ticket_rows.append(
                (
                    ticket_id,
                    company_id,
                    iso(opened_at),
                    iso(closed_at),
                    severity,
                    resolution,
                )
            )
        world.tickets_by_company[company.id] = opened_times

        invoice_company_rows = generate_invoices(rng, company)
        invoice_times: list[tuple[datetime, datetime | None]] = []
        for issued_at, due_at, paid_at, amount in invoice_company_rows:
            invoice_number += 1
            invoice_id = f"I{invoice_number:07d}"
            invoice_rows.append(
                (
                    invoice_id,
                    company.id,
                    iso(issued_at),
                    iso(due_at),
                    iso(paid_at),
                    amount,
                )
            )
            invoice_times.append((due_at, paid_at))
        world.invoices_by_company[company.id] = invoice_times

        nps_company_rows = generate_nps(rng, company)
        for surveyed_at, score in nps_company_rows:
            nps_rows.append((company.id, iso(surveyed_at), score))
        world.nps_by_company[company.id] = nps_company_rows

    interaction_rows, meetings_by_lead = generate_interactions(rng, leads)
    world.interaction_rows = interaction_rows
    world.meetings_by_lead = meetings_by_lead

    # Final pass: labels only.  The z constants are the calibrated population
    # parameters above, so the pass is causal, deterministic and single-shot.
    outcomes = simulate_outcomes(
        leads, world, CALIBRATED_Z, seed * 10 + 2
    )

    write_database(
        db_path,
        companies,
        leads,
        world,
        outcomes,
        ticket_rows,
        invoice_rows,
        nps_rows,
        overwrite=overwrite,
    )

    if not quiet:
        print_summary(companies, leads, outcomes)

    return companies, leads, outcomes


def default_db_path() -> Path:
    return Path(__file__).resolve().with_name("demo.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the synthetic Italy-only CRM world."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=default_db_path(),
        help="SQLite output path (default: data/demo.db)",
    )
    parser.add_argument(
        "--seed", type=int, default=SEED, help="deterministic seed (default: 42)"
    )
    parser.add_argument(
        "--companies",
        type=int,
        default=DEFAULT_COMPANIES,
        help="company count (default: 20000)",
    )
    parser.add_argument(
        "--leads",
        type=int,
        default=None,
        help="lead count (default: companies * 3)",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress the summary")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing --db file (refused by default)",
    )
    args = parser.parse_args(argv)

    generate(
        args.db,
        seed=args.seed,
        companies_count=args.companies,
        leads_count=args.leads,
        quiet=args.quiet,
        overwrite=args.overwrite,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
