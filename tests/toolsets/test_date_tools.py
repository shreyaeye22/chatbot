from __future__ import annotations

from datetime import date

from toolsets.date_tools import get_current_week_range, get_today


def test_get_today_returns_iso_format_of_the_real_date():
    assert get_today(ctx=None) == date.today().isoformat()


def test_get_current_week_range_spans_monday_to_sunday():
    week = get_current_week_range(ctx=None)

    start = date.fromisoformat(week["start"])
    end = date.fromisoformat(week["end"])

    assert start.weekday() == 0  # Monday
    assert end.weekday() == 6  # Sunday
    assert (end - start).days == 6
