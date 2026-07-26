"""Deterministic scheduler-ready next-run calculations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from vip_api.dashboard_delivery.schemas import ScheduleCreate


def next_run(payload: ScheduleCreate, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    if payload.schedule_type == "one_time":
        assert payload.run_at is not None
        return payload.run_at.astimezone(UTC)
    local = current.astimezone(ZoneInfo(payload.timezone))
    if payload.schedule_type == "daily":
        candidate = local + timedelta(days=1)
    elif payload.schedule_type == "weekly":
        candidate = local + timedelta(days=7)
    elif payload.schedule_type == "monthly":
        candidate = local + timedelta(days=30)
    else:
        candidate = local + timedelta(minutes=1)
    return candidate.astimezone(UTC)
