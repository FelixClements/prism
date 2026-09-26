"""Sunday-ending weekly closes from a daily PriceSeries."""

from __future__ import annotations

from datetime import date, timedelta

from price_forecast.data.series import PriceSeries


def _sunday_week_end(day: date) -> date:
    return day + timedelta(days=(6 - day.weekday()))


def weekly_closes(series: PriceSeries) -> list[tuple[date, float]]:
    """Last UTC daily close in each complete Sunday-ending week."""
    last_day = series.dates()[-1]
    buckets: dict[date, tuple[date, float]] = {}
    for day in series.dates():
        week_end = _sunday_week_end(day)
        buckets[week_end] = (day, series.close_at(day))
    weeks = []
    for week_end in sorted(buckets):
        if week_end > last_day:
            continue
        weeks.append((week_end, buckets[week_end][1]))
    return weeks
