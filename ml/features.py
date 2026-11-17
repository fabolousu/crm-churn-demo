"""Materialise ``lead_features`` at each lead's scoring point.

The column contract is ``data/schema.sql``; the semantics are ``docs/LABEL.md`` and
``docs/DECISIONS.md`` (contract v0.3.1).  Four rules shape everything in this module:

Scoring point
    A *closed* lead (``won``/``lost``) is scored at ``qualified_at`` -- the point the model
    is meant to predict from, so nothing that happened after qualification may inform it.
    A *still-open* lead is scored at the stage it currently holds: ``proposal_at`` for a
    proposal, ``qualified_at`` for qualification, ``created_at`` before contact.  Stage and
    snapshot always agree: when the timestamp for the current stage is missing, the row
    falls back to a stage the available timestamp proves, never to a later stage at an
    earlier instant.  ``snapshot_date`` is the verbatim timestamp text of that stage entry.

Point-in-time discipline
    Every aggregate is filtered to rows at or before ``snapshot_date``, and "at the
    snapshot" is always a *timestamp* test, never a status test: a sibling initiative that
    is closed today but was open at the snapshot still counted then, and one that closed
    later must not change a historical row.  A ticket, invoice, meeting, response or close
    dated after the snapshot is invisible.  The ground-truth label table is never queried;
    labels live somewhere else and feature code has no business reading them.

Self-exclusion
    A record's own outcome never enters its own features.  ``owner_win_rate_180d`` drops
    the scored lead's own closure from the rep's window, and the company aggregates exclude
    the lead too.  This matters when ``closed_at == qualified_at``: the lead's own won/lost
    result would otherwise sit inside its own feature.

``first_response_at`` prefers the recorded source column ``leads.first_response_at`` when
the database exposes it (lane A's generator populates it), and otherwise derives the instant
from ``created_at + first_response_hours`` -- the only other representation ``data/schema.sql``
can express for a lead. Whichever instant is chosen, the duration is measured from
``created_at`` to it, so the two materialised columns cannot disagree. Both are NULL when the
instant is later than ``snapshot_date``: a ``contacted`` lead scored at creation carries no
response duration yet.

Every lead gets a row, including leads that never reached qualification: the pipeline
screen scores whatever is open.  Deciding which rows carry a usable label is the trainer's
job (``docs/LABEL.md`` excludes censored and never-qualified leads), not this module's.

"Not measured" is NULL, never a sentinel zero (convention 5 in ``docs/LABEL.md``; the four
signal columns are nullable in ``data/schema.sql`` for exactly that reason).  A slope is not
estimable from fewer than two usage weeks, so ``usage_trend_slope`` is NULL there; a company
that was never surveyed leaves ``nps_last`` NULL; no invoice in the window leaves
``payment_delay_days_avg_180d`` NULL; and a rep with no closure in the window -- after the
scored lead's own closure is excluded -- leaves ``owner_win_rate_180d`` NULL.  Measured zeros
(on-time invoices, a 0 NPS score, flat usage, a rep at 0-for-1) stay 0.0.
``amount_arr`` still falls back to 0.0 when the source column is NULL, because its own
column is NOT NULL.  ``prior_won_initiatives`` and ``prior_lost_initiatives`` count
initiatives of the same company closed at or before the scoring point, never the lead
itself.  ``days_since_last_initiative`` is snapshot-relative: the gap from the company's
previous initiative ``created_at`` back to the scoring point, and to the company's
``created_at`` when this is its first initiative.

The build runs read, compute, replace and commit inside one transaction, so an autocommit
connection cannot observe two different committed states part-way through a build, and both
a failed insert and a failed commit roll back to the previous materialisation.

All arithmetic is standard library only.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, NamedTuple

__all__ = ["build_features"]

_CLOSED_STATUSES = frozenset({"won", "lost"})
_SECONDS_PER_DAY = 86400.0

_INSERT_SQL = """
INSERT INTO lead_features (
    lead_id, snapshot_date, source, stage_at_scoring, age_days_at_scoring,
    amount_arr, discount_pct, first_response_hours, first_response_at,
    region, industry, employees, company_age_days,
    prior_won_initiatives, prior_lost_initiatives, days_since_last_initiative,
    lifetime_won_arr, open_initiatives_count,
    usage_trend_slope, tickets_90d, nps_last, payment_delay_days_avg_180d,
    meetings_before_scoring, owner_win_rate_180d
) VALUES (
    ?, ?, ?, ?, ?,
    ?, ?, ?, ?,
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
    closed_days: float | None
    amount_arr: float
    discount_pct: float
    first_response_hours: float | None
    first_response_at: str | None


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
    closed: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    lead_created: dict[str, list[float]] = field(
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

    The whole build runs in a single transaction: the transaction is opened *before* the
    source tables are read, so an autocommit connection cannot hand back two different
    committed states during one build, and a failure at any point -- loading, computing,
    deleting, inserting, or committing -- rolls back to the previous materialisation.
    Works on autocommit connections (``isolation_level=None``) as well as on default ones.
    If the caller already has a transaction open, a savepoint is used so the caller's own
    work is neither committed nor discarded.
    """
    # Ownership is decided before any work: a transaction the caller opened stays theirs.
    caller_owns_transaction = conn.in_transaction
    if caller_owns_transaction:
        conn.execute("SAVEPOINT lead_features_build")
    else:
        conn.execute("BEGIN IMMEDIATE")

    try:
        world = _load_world(conn)
        rows = [_feature_row(lead, world) for lead in world.leads]
        rows.sort(key=lambda row: row[0])

        conn.execute("DELETE FROM lead_features")
        if rows:
            conn.executemany(_INSERT_SQL, rows)

        if caller_owns_transaction:
            conn.execute("RELEASE lead_features_build")
        else:
            conn.commit()
    except BaseException:
        if caller_owns_transaction:
            conn.execute("ROLLBACK TO lead_features_build")
            conn.execute("RELEASE lead_features_build")
        else:
            # Covers a failed commit too: SQLite leaves the transaction active when COMMIT
            # fails, and a retry must not mistake that for a caller-owned transaction.
            conn.rollback()
        raise
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


def _moment_days(moment: datetime) -> float:
    """Datetime -> absolute (fractional) day number, the unit used for comparisons."""
    seconds = moment.hour * 3600 + moment.minute * 60 + moment.second + moment.microsecond / 1e6
    return moment.toordinal() + seconds / _SECONDS_PER_DAY


def _day_number(value: str) -> float:
    """Timestamp text -> absolute (fractional) day number."""
    return _moment_days(_parse_timestamp(value))


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
    """Return ``(snapshot_date_text, snapshot_day_number, stage_at_scoring)``.

    The stage always describes the instant: when the timestamp for the lead's current stage
    is missing, the row falls back to the latest stage an available timestamp proves rather
    than claiming a later stage at an earlier time.
    """
    status = lead.status

    if status in ("new", "contacted"):
        return lead.created_at, lead.created_days, status

    # Open or closed: a stage timestamp is only usable if it belongs to the stage claimed.
    if status == "proposal" and lead.proposal_at is not None:
        return lead.proposal_at, _day_number(lead.proposal_at), "proposal"
    if status == "qualified" and lead.qualified_at is not None:
        return lead.qualified_at, _day_number(lead.qualified_at), "qualified"

    if status in _CLOSED_STATUSES:
        # Closed leads are scored at qualification, the training population's instant.
        if lead.qualified_at is not None:
            return lead.qualified_at, _day_number(lead.qualified_at), "qualified"
        if lead.proposal_at is not None:
            return lead.proposal_at, _day_number(lead.proposal_at), "proposal"
        return lead.created_at, lead.created_days, "new"

    # Still open but the timestamp for its current stage is missing: claim only what a
    # timestamp proves.  A proposal with no proposal_at was at best qualified.
    if lead.qualified_at is not None:
        return lead.qualified_at, _day_number(lead.qualified_at), "qualified"
    return lead.created_at, lead.created_days, "new"


def _first_response(lead: _Lead, snapshot: float) -> tuple[str | None, float | None]:
    """Resolve the response instant and its duration, gated on the snapshot.

    The recorded ``leads.first_response_at`` wins when the database carries that column;
    otherwise the instant is derived from ``created_at + first_response_hours``.  A response
    later than the snapshot is not knowable there, so both materialised columns are NULL.
    The duration is always measured from ``created_at`` to the chosen instant, so the pair
    cannot disagree.  Returns ``(first_response_at, first_response_hours)``.
    """
    created = _parse_timestamp(lead.created_at)
    if lead.first_response_at is not None:
        moment = _parse_timestamp(lead.first_response_at)
        text = lead.first_response_at
    elif lead.first_response_hours is not None:
        moment = created + timedelta(hours=lead.first_response_hours)
        separator = "T" if "T" in lead.created_at else " "
        text = moment.isoformat(sep=separator, timespec="seconds")
    else:
        return None, None
    if _moment_days(moment) > snapshot:
        return None, None
    hours = (moment - created).total_seconds() / 3600.0
    return text, hours


def _usage_trend_slope(world: _World, company_id: str, snapshot: float) -> float | None:
    """OLS slope of weekly usage events per week over the 90 days before the snapshot.

    NULL when the window holds fewer than two weekly points: a slope is not estimable from
    one observation, and "not measured" must not be encoded as a flat zero.
    """
    entries = world.usage.get(company_id, [])
    start, end = _window(entries, snapshot, 90.0, key=lambda row: row[0])
    points = entries[start:end]
    if len(points) < 2:
        return None
    origin = points[0][0]
    xs = [(point[0] - origin) / 7.0 for point in points]  # weeks since the first week
    ys = [float(point[1]) for point in points]
    count = float(len(points))
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0.0:
        return None
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return sxy / sxx


def _payment_delay_days(world: _World, company_id: str, snapshot: float) -> float | None:
    """Mean days late on invoices issued in the 180 days before the snapshot.

    An invoice paid after the snapshot is treated as unpaid at the snapshot, so its delay
    is the run-out from ``due_at`` to the snapshot rather than a future payment date.  NULL
    when no invoice fell in the window, because that is "not measured", not "always on time".
    """
    invoices = world.invoices.get(company_id, [])
    start, end = _window(invoices, snapshot, 180.0, key=lambda row: row[0])
    delays: list[float] = []
    for _issued, due, paid in invoices[start:end]:
        paid_at_snapshot = paid if paid is not None and paid <= snapshot else None
        elapsed = (paid_at_snapshot if paid_at_snapshot is not None else snapshot) - due
        delays.append(max(0.0, elapsed))
    if not delays:
        return None
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

    # ``leads.first_response_at`` is the recorded response instant when the database carries
    # it; a database built from a schema without the column simply has nothing to prefer.
    lead_columns = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
    response_column = (
        "first_response_at" if "first_response_at" in lead_columns else "NULL"
    )

    for row in conn.execute(
        "SELECT id, company_id, created_at, status, source, owner_rep, qualified_at, "
        "proposal_at, closed_at, amount_arr, discount_pct, first_response_hours, "
        f"{response_column} FROM leads"
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
            first_response_at,
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
            closed_days=_day_number(closed_at) if closed_at is not None else None,
            amount_arr=float(amount_arr) if amount_arr is not None else 0.0,
            discount_pct=float(discount_pct) if discount_pct is not None else 0.0,
            first_response_hours=(
                float(first_response_hours) if first_response_hours is not None else None
            ),
            first_response_at=first_response_at,
        )
        world.leads.append(lead)
        world.lead_created[company_id].append(created_days)
        if lead.closed_days is not None:
            world.closed[company_id].append(lead.closed_days)
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
        world.closed,
        world.lead_created,
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
    # Snapshot-relative, per docs/LABEL.md: the gap from the scoring point back to the
    # previous initiative's creation, not creation-to-creation.
    days_since_last_initiative = _whole_days(snapshot - previous_created)

    # "Open at the snapshot" is a timestamp test, never a status test: an initiative that
    # closed today but was open at the snapshot still counted then.
    closed_entries = world.closed.get(company_id, [])
    open_initiatives_count = _upper_bound(created_entries, snapshot, key=lambda d: d) - (
        _upper_bound(closed_entries, snapshot, key=lambda d: d)
    )
    scored_lead_was_open = (
        lead.created_days <= snapshot
        and (lead.closed_days is None or lead.closed_days > snapshot)
    )
    if scored_lead_was_open:
        open_initiatives_count -= 1
    open_initiatives_count = max(0, open_initiatives_count)

    # --- relationship signals ----------------------------------------------------------
    ticket_days = world.tickets.get(company_id, [])
    tickets_90d = _upper_bound(ticket_days, snapshot, key=lambda d: d) - _lower_bound(
        ticket_days, snapshot - 90.0, key=lambda d: d
    )

    survey_entries = world.nps.get(company_id, [])
    survey_until = _upper_bound(survey_entries, snapshot, key=lambda row: row[0])
    nps_last = survey_entries[survey_until - 1][1] if survey_until else None

    rep_entries = world.rep_closed.get(lead.owner_rep, [])
    rep_start, rep_end = _window(rep_entries, snapshot, 180.0, key=lambda row: row[0])
    rep_prefix = world.rep_wins_prefix.get(lead.owner_rep, [0])
    rep_total = rep_end - rep_start
    rep_wins = rep_prefix[rep_end] - rep_prefix[rep_start]
    if (
        lead.status in _CLOSED_STATUSES
        and lead.closed_days is not None
        and snapshot - 180.0 <= lead.closed_days <= snapshot
    ):
        # Never let the scored lead's own result enter its own feature: when a lead closes
        # at its own qualification instant the closure would otherwise land in this window.
        rep_total -= 1
        rep_wins -= 1 if lead.status == "won" else 0
    owner_win_rate_180d = rep_wins / rep_total if rep_total > 0 else None

    meeting_days = world.meetings.get(lead.lead_id, [])
    meetings_before_scoring = _upper_bound(meeting_days, snapshot, key=lambda d: d)

    first_response_at, first_response_hours = _first_response(lead, snapshot)

    return (
        lead.lead_id,
        snapshot_text,
        lead.source,
        stage,
        _whole_days(snapshot - lead.created_days),
        lead.amount_arr,
        lead.discount_pct,
        first_response_hours,
        first_response_at,
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
