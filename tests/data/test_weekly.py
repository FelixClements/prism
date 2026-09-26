"""Sunday weekly bars from daily UTC closes."""

from __future__ import annotations

from datetime import date, timedelta

from price_forecast.data.series import PriceSeries
from price_forecast.data.weekly import weekly_closes


def test_weekly_close_is_last_utc_daily_in_sunday_ending_week():
    daily = []
    price = 100.0
    day = date(2022, 1, 3)
    while day <= date(2022, 1, 9):
        daily.append((day, price))
        price += 1.0
        day += timedelta(days=1)
    series = PriceSeries(daily)

    weeks = weekly_closes(series)

    assert weeks == [(date(2022, 1, 9), 106.0)]


def test_incomplete_trailing_week_is_dropped():
    daily = []
    day = date(2022, 1, 3)
    price = 100.0
    while day <= date(2022, 1, 12):
        daily.append((day, price))
        price += 1.0
        day += timedelta(days=1)
    series = PriceSeries(daily)

    weeks = weekly_closes(series)

    assert [week_end for week_end, _close in weeks] == [date(2022, 1, 9)]
