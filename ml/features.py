"""Materialise ``lead_features`` at each lead's scoring point.

The column contract is ``data/schema.sql``; the semantics are ``docs/LABEL.md`` and
``docs/DECISIONS.md`` (contract v0.3).  Two rules shape everything in this module:

Scoring point
    A *closed* lead (``won``/``lost``) is scored at ``qualified_at`` — the point the model
    is meant to predict from, so nothing that happened after qualification may inform it.
    A *still-open* lead is scored at the stage it currently holds: ``proposal_at`` for a
    proposal, ``qualified_at`` for qualification, ``created_at`` before contact.  That is
    the "current stage at the snapshot" rule, and it is what the pipeline screen acts on.
    ``snapshot_date`` is the verbatim timestamp text of that stage entry, so it joins back
    to the source table and to the label rows written by the generator.

Point-in-time discipline
    Every aggregate is filtered to rows at or before ``snapshot_date``.  A ticket opened,
    an invoice issued, a meeting held or an initiative closed after the snapshot is
    invisible to that lead's features.  The ground-truth label table is never queried;
    labels live somewhere else and feature code has no business reading them.

Every lead gets a row, including leads that never reached qualification: the pipeline
screen scores whatever is open.  Deciding which rows carry a usable label is the trainer's
job (``docs/LABEL.md`` excludes censored and never-qualified leads), not this module's.

Degenerate cases are explicit rather than invented: ``amount_arr`` falls back to ``0.0``
when the source column is NULL (the materialised column is NOT NULL); no survey yields
``nps_last = 0``; no invoices yields ``0.0`` average delay; fewer than two usage weeks (or
no variance in time) yields ``usage_trend_slope = 0.0``; and a rep with no closed initiative
in the window yields ``owner_win_rate_180d = 0.0``.  ``prior_won_initiatives`` and
``prior_lost_initiatives`` count initiatives of the same company closed at or before the
scoring point, never the lead itself.  ``days_since_last_initiative`` measures the gap from
the company's previous initiative ``created_at`` to this lead's ``created_at``, falling back
to the company's ``created_at`` when this is the company's first initiative.  The schema keeps
no stage history, so ``open_initiatives_count`` can only see leads that are *still* open at
build time and were created at or before the snapshot; a lead that was open at the snapshot
and closed afterwards is invisible.  That limitation is upstream of this module.

All arithmetic is standard library only.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, NamedTuple

__all__ = ["build_features"]

_OPEN_STATUSES = frozenset({"new", "contacted", "qualified", "proposal"})
_SECONDS_PER_DAY = 86400.0

_INSERT_SQL = """
INSERT INTO lead_features (
    lead_id, snapshot_date, source, stage_at_scoring, age_days_at_scoring,
    amount_arr, discount_pct, first_response_hours,
    region, industry, employees, company_age_days,
    prior_won_initiatives, prior_lost_initiatives, days_since_last_initiative,
    lifetime_won_arr, open_initiatives_count,
    usage_trend_slope, tickets_90d, nps_last, payment_delay_days_avg_180d,
    meetings_before_scoring, owner_win_rate_180d
) VALUES (
    ?, ?, ?, ?, ?,
    ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?,
    ?, ?,
    ?, ?, ?, ?,
    ?, ?
)
"""


class _Lead(NamedTuple):
    lead_id: str
    company_id: str
    status: str
    source: str
    owner_rep: str
    created_at: str
    created_days: float
    qualified_at: str | None
    proposal_at: str | None
    closed_at: str | None
    closed_days: float | None
    amount_arr: float
    discount_pct: float
    first_response_hours: float | None


@dataclass
class _World:
    """Every source row needed by the features, indexed for point-in-time lookups."""

    companies: dict[str, tuple[str, str, int]] = field(default_factory=dict)
    company_created: dict[str, float] = field(default_factory=dict)
    leads: list[_Lead] = field(default_factory=list)

    # company-scoped buckets
    tickets: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    invoices: dict[str, list[tuple[float, float, float | None]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    nps: dict[str, list[tuple[float, int]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    usage: dict[str, list[tuple[float, int]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    won: dict[str, list[tuple[float, float]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    lost: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    lead_created: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    open_created: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # lead- and rep-scoped buckets
    meetings: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    rep_closed: dict[str, list[tuple[float, int]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # derived after loading
    won_prefix: dict[str, list[float]] = field(default_factory=dict)
    rep_wins_prefix: dict[str, list[int]] = field(default_factory=dict)


def build_features(conn: sqlite3.Connection) -> int:
    """Replace ``lead_features`` with one row per lead and return the row count.

    The build is a full refresh: existing rows are deleted and re-inserted, so calling it
    twice produces the identical table and a rebuild after new activity changes only the
    leads whose inputs changed.  The caller's connection is committed on success.
    """
    world = _load_world(conn)
    rows = [_feature_row(lead, world) for lead in world.leads]
    rows.sort(key=lambda row: row[0])

    conn.execute("DELETE FROM lead_features")
    if rows:
        conn.executemany(_INSERT_SQL, rows)
    conn.commit()
    return len(rows)


# --------------------------------------------------------------------------------------
# timestamps
# --------------------------------------------------------------------------------------


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, normalising any offset to naive UTC."""
    text = value.strip()
    parsed: datetime | None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError(f"unsupported timestamp in source data: {value!r}")
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _day_number(value: str) -> float:
    """Timestamp text -> absolute (fractional) day number, the unit used for comparisons."""
    moment = _parse_timestamp(value)
    seconds = moment.hour * 3600 + moment.minute * 60 + moment.second + moment.microsecond / 1e6
    return moment.toordinal() + seconds / _SECONDS_PER_DAY


def _whole_days(delta: float) -> int:
    """Whole days elapsed, never negative."""
    return max(0, int(delta))


# --------------------------------------------------------------------------------------
# point-in-time helpers
# --------------------------------------------------------------------------------------


def _upper_bound(values: list, target: float, key: Callable[[object], float]) -> int:
    """Index of the first item whose ``key`` is greater than ``target``.

    Equivalent to ``bisect_right`` with a key accessor: the count of rows at or before the
    target.  Binary search keeps the build linear in rows rather than quadratic.
    """
    low, high = 0, len(values)
    while low < high:
        middle = (low + high) // 2
        if key(values[middle]) <= target:
            low = middle + 1
        else:
            high = middle
    return low


def _lower_bound(values: list, target: float, key: Callable[[object], float]) -> int:
    """Index of the first item whose ``key`` is at or after ``target``."""
    low, high = 0, len(values)
    while low < high:
        middle = (low + high) // 2
        if key(values[middle]) < target:
            low = middle + 1
        else:
            high = middle
    return low


def _window(
    values: list,
    snapshot: float,
    horizon_days: float,
    key: Callable[[object], float],
) -> tuple[int, int]:
    """Closed slice ``[snapshot - horizon_days, snapshot]`` of a day-sorted bucket."""
    return (
        _lower_bound(values, snapshot - horizon_days, key),
        _upper_bound(values, snapshot, key),
    )


def _scoring_point(lead: _Lead) -> tuple[str, float, str]:
    """Return ``(snapshot_date_text, snapshot_day_number, stage_at_scoring)``."""
    status = lead.status

    if status in _OPEN_STATUSES:
        if status == "proposal" and lead.proposal_at is not None:
            return lead.proposal_at, _day_number(lead.proposal_at), "proposal"
        if status == "qualified" and lead.qualified_at is not None:
            return lead.qualified_at, _day_number(lead.qualified_at), "qualified"
        if status in ("new", "contacted"):
            return lead.created_at, lead.created_days, status
        # status says qualified/proposal but the stage timestamp is missing: fall back to
        # the earliest timestamp we do have rather than invent a later one.
        raw = lead.qualified_at or lead.proposal_at or lead.created_at
        return raw, _day_number(raw), status

    # Closed lead: the model is trained on the state at qualification.
    if lead.qualified_at is not None:
        return lead.qualified_at, _day_number(lead.qualified_at), "qualified"
    if lead.proposal_at is not None:
        return lead.proposal_at, _day_number(lead.proposal_at), "proposal"
    return lead.created_at, lead.created_days, "new"


def _usage_trend_slope(world: _World, company_id: str, snapshot: float) -> float:
    """OLS slope of weekly usage events per week over the 90 days before the snapshot."""
    entries = world.usage.get(company_id, [])
    start, end = _window(entries, snapshot, 90.0, key=lambda row: row[0])
    points = entries[start:end]
    if len(points) < 2:
        return 0.0
    origin = points[0][0]
    xs = [(point[0] - origin) / 7.0 for point in points]  # weeks since the first week
    ys = [float(point[1]) for point in points]
    count = float(len(points))
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0.0:
        return 0.0
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return sxy / sxx


def _payment_delay_days(world: _World, company_id: str, snapshot: float) -> float:
    """Mean days late on invoices issued in the 180 days before the snapshot.

    An invoice paid after the snapshot is treated as unpaid at the snapshot, so its delay
    is the run-out from ``due_at`` to the snapshot rather than a future payment date.
    """
    invoices = world.invoices.get(company_id, [])
    start, end = _window(invoices, snapshot, 180.0, key=lambda row: row[0])
    delays: list[float] = []
    for _issued, due, paid in invoices[start:end]:
        paid_at_snapshot = paid if paid is not None and paid <= snapshot else None
        elapsed = (paid_at_snapshot if paid_at_snapshot is not None else snapshot) - due
        delays.append(max(0.0, elapsed))
    if not delays:
        return 0.0
    return sum(delays) / len(delays)


# --------------------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------------------


def _load_world(conn: sqlite3.Connection) -> _World:
    world = _World()

    for company_id, region, industry, employees, created_at in conn.execute(
        "SELECT id, region, industry, employees, created_at FROM companies"
    ):
        world.companies[company_id] = (region, industry, int(employees))
        world.company_created[company_id] = _day_number(created_at)

    for row in conn.execute(
        "SELECT id, company_id, created_at, status, source, owner_rep, qualified_at, "
        "proposal_at, closed_at, amount_arr, discount_pct, first_response_hours "
        "FROM leads"
    ):
        (
            lead_id,
            company_id,
            created_at,
            status,
            source,
            owner_rep,
            qualified_at,
            proposal_at,
            closed_at,
            amount_arr,
            discount_pct,
            first_response_hours,
        ) = row
        created_days = _day_number(created_at)
        lead = _Lead(
            lead_id=lead_id,
            company_id=company_id,
            status=status,
            source=source,
            owner_rep=owner_rep,
            created_at=created_at,
            created_days=created_days,
            qualified_at=qualified_at,
            proposal_at=proposal_at,
            closed_at=closed_at,
            closed_days=_day_number(closed_at) if closed_at is not None else None,
            amount_arr=float(amount_arr) if amount_arr is not None else 0.0,
            discount_pct=float(discount_pct) if discount_pct is not None else 0.0,
            first_response_hours=(
                float(first_response_hours) if first_response_hours is not None else None
            ),
        )
        world.leads.append(lead)
        world.lead_created[company_id].append(created_days)
        if status in _OPEN_STATUSES:
            world.open_created[company_id].append(created_days)
        if status == "won" and lead.closed_days is not None:
            world.won[company_id].append((lead.closed_days, lead.amount_arr))
        elif status == "lost" and lead.closed_days is not None:
            world.lost[company_id].append(lead.closed_days)

    for company_id, opened_at in conn.execute(
        "SELECT company_id, opened_at FROM tickets"
    ):
        world.tickets[company_id].append(_day_number(opened_at))

    for company_id, issued_at, due_at, paid_at in conn.execute(
        "SELECT company_id, issued_at, due_at, paid_at FROM invoices"
    ):
        world.invoices[company_id].append(
            (
                _day_number(issued_at),
                _day_number(due_at),
                _day_number(paid_at) if paid_at is not None else None,
            )
        )

    for company_id, surveyed_at, score in conn.execute(
        "SELECT company_id, surveyed_at, score FROM nps_surveys"
    ):
        world.nps[company_id].append((_day_number(surveyed_at), int(score)))

    for company_id, week_start, events in conn.execute(
        "SELECT company_id, week_start, events FROM company_usage_weekly"
    ):
        world.usage[company_id].append((_day_number(week_start), int(events)))

    for lead_id, occurred_at in conn.execute(
        "SELECT lead_id, occurred_at FROM interactions WHERE kind = 'meeting'"
    ):
        if lead_id is not None:
            world.meetings[lead_id].append(_day_number(occurred_at))

    for owner_rep, closed_at, status in conn.execute(
        "SELECT owner_rep, closed_at, status FROM leads "
        "WHERE status IN ('won', 'lost') AND closed_at IS NOT NULL"
    ):
        world.rep_closed[owner_rep].append(
            (_day_number(closed_at), 1 if status == "won" else 0)
        )

    _finalise(world)
    return world


def _finalise(world: _World) -> None:
    for bucket in (
        world.tickets,
        world.lost,
        world.lead_created,
        world.open_created,
        world.meetings,
    ):
        for values in bucket.values():
            values.sort()

    for entries in world.won.values():
        entries.sort(key=lambda row: row[0])
    for entries in world.invoices.values():
        entries.sort(key=lambda row: row[0])
    for entries in world.nps.values():
        entries.sort(key=lambda row: row[0])
    for entries in world.usage.values():
        entries.sort(key=lambda row: row[0])
    for entries in world.rep_closed.values():
        entries.sort(key=lambda row: row[0])

    for company_id, entries in world.won.items():
        prefix = [0.0]
        for _closed, amount in entries:
            prefix.append(prefix[-1] + amount)
        world.won_prefix[company_id] = prefix

    for owner_rep, entries in world.rep_closed.items():
        prefix = [0]
        for _closed, won in entries:
            prefix.append(prefix[-1] + won)
        world.rep_wins_prefix[owner_rep] = prefix


# --------------------------------------------------------------------------------------
# the feature row
# --------------------------------------------------------------------------------------


def _feature_row(lead: _Lead, world: _World) -> tuple:
    snapshot_text, snapshot, stage = _scoring_point(lead)

    company_id = lead.company_id
    region, industry, employees = world.companies[company_id]
    company_created = world.company_created[company_id]

    # --- company initiative history, strictly up to the snapshot -----------------------
    won_entries = world.won.get(company_id, [])
    won_until = _upper_bound(won_entries, snapshot, key=lambda row: row[0])
    prior_won = won_until
    lifetime_won_arr = world.won_prefix.get(company_id, [0.0])[won_until]
    if (
        lead.status == "won"
        and lead.closed_days is not None
        and lead.closed_days <= snapshot
    ):
        # A closed lead normally closes after its snapshot; guard the degenerate case so a
        # lead never counts as its own prior initiative.
        prior_won -= 1
        lifetime_won_arr -= lead.amount_arr

    lost_entries = world.lost.get(company_id, [])
    prior_lost = _upper_bound(lost_entries, snapshot, key=lambda d: d)
    if (
        lead.status == "lost"
        and lead.closed_days is not None
        and lead.closed_days <= snapshot
    ):
        prior_lost -= 1

    created_entries = world.lead_created.get(company_id, [])
    previous_index = _lower_bound(created_entries, lead.created_days, key=lambda d: d) - 1
    previous_created = (
        created_entries[previous_index]
        if previous_index >= 0
        else company_created
    )
    days_since_last_initiative = _whole_days(lead.created_days - previous_created)

    open_entries = world.open_created.get(company_id, [])
    open_initiatives_count = _upper_bound(open_entries, snapshot, key=lambda d: d)
    if lead.status in _OPEN_STATUSES and lead.created_days <= snapshot:
        open_initiatives_count -= 1

    # --- relationship signals ----------------------------------------------------------
    ticket_days = world.tickets.get(company_id, [])
    tickets_90d = _upper_bound(ticket_days, snapshot, key=lambda d: d) - _lower_bound(
        ticket_days, snapshot - 90.0, key=lambda d: d
    )

    survey_entries = world.nps.get(company_id, [])
    survey_until = _upper_bound(survey_entries, snapshot, key=lambda row: row[0])
    nps_last = survey_entries[survey_until - 1][1] if survey_until else 0

    rep_entries = world.rep_closed.get(lead.owner_rep, [])
    rep_start, rep_end = _window(rep_entries, snapshot, 180.0, key=lambda row: row[0])
    rep_total = rep_end - rep_start
    if rep_total == 0:
        owner_win_rate_180d = 0.0
    else:
        rep_prefix = world.rep_wins_prefix[lead.owner_rep]
        owner_win_rate_180d = (rep_prefix[rep_end] - rep_prefix[rep_start]) / rep_total

    meeting_days = world.meetings.get(lead.lead_id, [])
    meetings_before_scoring = _upper_bound(meeting_days, snapshot, key=lambda d: d)

    return (
        lead.lead_id,
        snapshot_text,
        lead.source,
        stage,
        _whole_days(snapshot - lead.created_days),
        lead.amount_arr,
        lead.discount_pct,
        lead.first_response_hours,
        region,
        industry,
        employees,
        _whole_days(snapshot - company_created),
        prior_won,
        prior_lost,
        days_since_last_initiative,
        lifetime_won_arr,
        open_initiatives_count,
        _usage_trend_slope(world, company_id, snapshot),
        tickets_90d,
        nps_last,
        _payment_delay_days(world, company_id, snapshot),
        meetings_before_scoring,
        owner_win_rate_180d,
    )
