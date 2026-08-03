"""Unit coverage for delivery next-run math: cron, timezones, intervals, catch-up."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vip_api.dashboard_delivery.scheduling import (
    advance_next_run,
    next_cron,
    next_interval,
    parse_cron,
)


def _utc(y: int, mo: int, d: int, h: int, mi: int) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


class TestCronParsing:
    def test_rejects_wrong_field_count(self) -> None:
        with pytest.raises(ValueError):
            parse_cron("0 9 * *")

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            parse_cron("99 9 * * *")

    def test_supports_lists_ranges_and_steps(self) -> None:
        spec = parse_cron("0,30 9-17/4 * * *")
        assert spec.minute == frozenset({0, 30})
        assert spec.hour == frozenset({9, 13, 17})

    def test_sunday_accepts_0_and_7(self) -> None:
        assert parse_cron("0 0 * * 7").day_of_week == parse_cron("0 0 * * 0").day_of_week


class TestNextCron:
    def test_daily_utc(self) -> None:
        # From 08:00 UTC, "0 9 * * *" fires the same day at 09:00.
        assert next_cron("0 9 * * *", "UTC", after=_utc(2026, 8, 3, 8, 0)) == _utc(2026, 8, 3, 9, 0)

    def test_daily_rolls_to_next_day(self) -> None:
        assert next_cron("0 9 * * *", "UTC", after=_utc(2026, 8, 3, 9, 0)) == _utc(2026, 8, 4, 9, 0)

    def test_timezone_offset_applied(self) -> None:
        # 09:00 Asia/Riyadh (UTC+3) == 06:00 UTC.
        result = next_cron("0 9 * * *", "Asia/Riyadh", after=_utc(2026, 8, 3, 0, 0))
        assert result == _utc(2026, 8, 3, 6, 0)

    def test_step_minutes(self) -> None:
        assert next_cron("*/15 * * * *", "UTC", after=_utc(2026, 8, 3, 8, 1)) == _utc(
            2026, 8, 3, 8, 15
        )

    def test_monthly_first_day(self) -> None:
        assert next_cron("0 0 1 * *", "UTC", after=_utc(2026, 8, 3, 0, 0)) == _utc(2026, 9, 1, 0, 0)

    def test_weekday_monday(self) -> None:
        # 2026-08-03 is a Monday; from Tuesday it advances to the next Monday.
        assert next_cron("0 9 * * 1", "UTC", after=_utc(2026, 8, 4, 0, 0)) == _utc(
            2026, 8, 10, 9, 0
        )

    def test_dom_or_dow_when_both_restricted(self) -> None:
        # "1st OR Monday": 2026-08-01 is a Saturday (day 1 matches).
        assert next_cron("0 0 1 * 1", "UTC", after=_utc(2026, 7, 31, 0, 0)) == _utc(
            2026, 8, 1, 0, 0
        )


class TestIntervals:
    def test_daily_interval_preserves_time_of_day(self) -> None:
        anchor = _utc(2026, 8, 3, 9, 0)
        assert next_interval("daily", "UTC", anchor=anchor, after=_utc(2026, 8, 3, 12, 0)) == _utc(
            2026, 8, 4, 9, 0
        )

    def test_weekly_interval(self) -> None:
        anchor = _utc(2026, 8, 3, 9, 0)
        assert next_interval("weekly", "UTC", anchor=anchor, after=_utc(2026, 8, 3, 9, 0)) == _utc(
            2026, 8, 10, 9, 0
        )

    def test_monthly_is_calendar_aware(self) -> None:
        anchor = _utc(2026, 1, 31, 9, 0)
        # January 31 -> February (clamped to 28 in 2026).
        assert next_interval(
            "monthly", "UTC", anchor=anchor, after=_utc(2026, 1, 31, 9, 0)
        ) == _utc(2026, 2, 28, 9, 0)

    def test_catch_up_collapses_missed_slots(self) -> None:
        # A daily anchor from a week ago, evaluated now, fires ONCE at the next
        # future slot — not seven times.
        anchor = _utc(2026, 8, 1, 9, 0)
        result = next_interval("daily", "UTC", anchor=anchor, after=_utc(2026, 8, 8, 10, 0))
        assert result == _utc(2026, 8, 9, 9, 0)


class TestAdvance:
    def test_one_time_does_not_recur(self) -> None:
        assert (
            advance_next_run(
                schedule_type="one_time",
                schedule_expression=None,
                timezone="UTC",
                previous_next_run=_utc(2026, 8, 3, 9, 0),
                now=_utc(2026, 8, 3, 9, 1),
            )
            is None
        )

    def test_cron_advances_from_now(self) -> None:
        result = advance_next_run(
            schedule_type="cron",
            schedule_expression="0 9 * * *",
            timezone="UTC",
            previous_next_run=_utc(2026, 8, 3, 9, 0),
            now=_utc(2026, 8, 3, 9, 0),
        )
        assert result == _utc(2026, 8, 4, 9, 0)

    def test_interval_advances_from_anchor(self) -> None:
        result = advance_next_run(
            schedule_type="daily",
            schedule_expression=None,
            timezone="UTC",
            previous_next_run=_utc(2026, 8, 3, 9, 0),
            now=_utc(2026, 8, 3, 9, 0),
        )
        assert result == _utc(2026, 8, 4, 9, 0)
