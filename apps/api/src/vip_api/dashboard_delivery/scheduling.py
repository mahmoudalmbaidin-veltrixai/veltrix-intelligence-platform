"""Deterministic, timezone-aware next-run calculations for delivery schedules.

Supports one-time, fixed-interval (daily/weekly/monthly, wall-clock anchored),
and standard five-field cron expressions. Cron and interval math step in local
wall-clock time within the schedule's timezone, then convert to UTC — so a
"09:00" schedule stays at 09:00 local across DST transitions, matching operator
expectations and typical cron semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from vip_api.dashboard_delivery.schemas import ScheduleCreate

# Guard against pathological cron expressions that never match (e.g. Feb 30).
_MAX_CRON_SCAN_DAYS = 1500


def _parse_field(token: str, low: int, high: int) -> frozenset[int]:
    values: set[int] = set()
    for part in token.split(","):
        step = 1
        base = part
        if "/" in part:
            base, step_raw = part.split("/", 1)
            step = int(step_raw)
            if step < 1:
                raise ValueError("Cron step must be positive")
        if base == "*":
            start, end = low, high
        elif "-" in base:
            start_raw, end_raw = base.split("-", 1)
            start, end = int(start_raw), int(end_raw)
        else:
            start = end = int(base)
        if start < low or end > high or start > end:
            raise ValueError("Cron field out of range")
        values.update(range(start, end + 1, step))
    if not values:
        raise ValueError("Cron field matched no values")
    return frozenset(values)


@dataclass(frozen=True, slots=True)
class CronSpec:
    minute: frozenset[int]
    hour: frozenset[int]
    day_of_month: frozenset[int]
    month: frozenset[int]
    day_of_week: frozenset[int]
    dom_restricted: bool
    dow_restricted: bool


def parse_cron(expression: str) -> CronSpec:
    """Parse a five-field cron expression (minute hour dom month dow).

    Supports ``*``, lists (``a,b``), ranges (``a-b``), and steps (``*/n``,
    ``a-b/n``). Day-of-week is 0-6 with Sunday=0 (7 also accepted as Sunday).
    """
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("Cron schedules require a five-field expression")
    minute = _parse_field(fields[0], 0, 59)
    hour = _parse_field(fields[1], 0, 23)
    day_of_month = _parse_field(fields[2], 1, 31)
    month = _parse_field(fields[3], 1, 12)
    dow_raw = _parse_field(fields[4], 0, 7)
    day_of_week = frozenset(0 if value == 7 else value for value in dow_raw)
    return CronSpec(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month=month,
        day_of_week=day_of_week,
        dom_restricted=fields[2] != "*",
        dow_restricted=fields[4] != "*",
    )


def _day_matches(spec: CronSpec, moment: datetime) -> bool:
    # cron weekday: Sunday=0..Saturday=6; Python weekday(): Monday=0..Sunday=6.
    cron_dow = (moment.weekday() + 1) % 7
    dom_ok = moment.day in spec.day_of_month
    dow_ok = cron_dow in spec.day_of_week
    # Standard cron: when both day fields are restricted, either may match; when
    # only one is restricted, that one governs; when neither, every day matches.
    if spec.dom_restricted and spec.dow_restricted:
        return dom_ok or dow_ok
    if spec.dom_restricted:
        return dom_ok
    if spec.dow_restricted:
        return dow_ok
    return True


def _localize(naive: datetime, tz: ZoneInfo) -> datetime:
    return naive.replace(tzinfo=tz)


def next_cron(expression: str, timezone: str, *, after: datetime) -> datetime:
    """Return the next UTC instant after ``after`` matching the cron expression."""
    spec = parse_cron(expression)
    tz = ZoneInfo(timezone)
    local = after.astimezone(tz)
    # Step in wall-clock local time so DST does not shift the scheduled hour.
    naive = local.replace(tzinfo=None, second=0, microsecond=0) + timedelta(minutes=1)
    horizon = naive + timedelta(days=_MAX_CRON_SCAN_DAYS)
    while naive <= horizon:
        if naive.month not in spec.month:
            # Jump to the first minute of the next month.
            year, month = (
                (naive.year + 1, 1) if naive.month == 12 else (naive.year, naive.month + 1)
            )
            naive = naive.replace(year=year, month=month, day=1, hour=0, minute=0)
            continue
        if not _day_matches(spec, naive):
            naive = (naive + timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if naive.hour not in spec.hour:
            naive = (naive + timedelta(hours=1)).replace(minute=0)
            continue
        if naive.minute not in spec.minute:
            naive += timedelta(minutes=1)
            continue
        return _localize(naive, tz).astimezone(UTC)
    raise ValueError("Cron expression has no occurrence within the supported horizon")


def _add_month(moment: datetime) -> datetime:
    year, month = (moment.year + 1, 1) if moment.month == 12 else (moment.year, moment.month + 1)
    # Clamp the day to the target month's length (e.g. Jan 31 -> Feb 28/29).
    if month == 2:
        last = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
    elif month in (4, 6, 9, 11):
        last = 30
    else:
        last = 31
    return moment.replace(year=year, month=month, day=min(moment.day, last))


def _step(unit: str, moment: datetime) -> datetime:
    if unit == "daily":
        return moment + timedelta(days=1)
    if unit == "weekly":
        return moment + timedelta(days=7)
    return _add_month(moment)


def next_interval(unit: str, timezone: str, *, anchor: datetime, after: datetime) -> datetime:
    """Advance a wall-clock ``anchor`` by ``unit`` until strictly after ``after``.

    Anchoring to the previous scheduled instant preserves the time-of-day and
    catches up past missed slots to the next future occurrence (fired once, not
    replayed) — important after downtime.
    """
    tz = ZoneInfo(timezone)
    naive = anchor.astimezone(tz).replace(tzinfo=None, second=0, microsecond=0)
    after_local = after.astimezone(tz).replace(tzinfo=None)
    guard = 0
    while naive <= after_local:
        naive = _step(unit, naive)
        guard += 1
        if guard > 100_000:  # unreachable defensive cap
            raise ValueError("Interval schedule failed to advance")
    return _localize(naive, tz).astimezone(UTC)


def next_run(payload: ScheduleCreate, *, now: datetime | None = None) -> datetime:
    """Initial next-run at schedule creation/update time."""
    current = now or datetime.now(UTC)
    if payload.schedule_type == "one_time":
        assert payload.run_at is not None
        return payload.run_at.astimezone(UTC)
    if payload.schedule_type == "cron":
        assert payload.schedule_expression is not None
        return next_cron(payload.schedule_expression, payload.timezone, after=current)
    # Fixed intervals anchor their first run one interval out from now.
    return next_interval(payload.schedule_type, payload.timezone, anchor=current, after=current)


def advance_next_run(
    *,
    schedule_type: str,
    schedule_expression: str | None,
    timezone: str,
    previous_next_run: datetime,
    now: datetime | None = None,
) -> datetime | None:
    """Compute the next run for an existing schedule after it has fired.

    Returns ``None`` for one-time schedules (which do not recur). Interval
    schedules step from ``previous_next_run`` (preserving time-of-day) to the
    next slot strictly after ``now`` — collapsing any missed slots into one.
    """
    current = now or datetime.now(UTC)
    if schedule_type == "one_time":
        return None
    if schedule_type == "cron":
        assert schedule_expression is not None
        return next_cron(schedule_expression, timezone, after=current)
    return next_interval(schedule_type, timezone, anchor=previous_next_run, after=current)
