"""Dollar SMA-8 vs buy-and-hold: $10k fresh BTC start per window."""

from __future__ import annotations

from datetime import date, timedelta

from price_forecast.sma8_10k import STARTING_DOLLARS, dollar_window_specs
from price_forecast.weekly_bakeoff import LONG_RUN_WINDOW, WINDOWS
from price_forecast.weekly_regime import SMA8_LOOKBACK


def test_starting_capital_is_ten_thousand_dollars():
    assert STARTING_DOLLARS == 10_000.0


def test_dollar_windows_are_sma8_warmup_plus_the_three_calendar_spans():
    weeks = [(date(2018, 1, 7) + timedelta(weeks=i), 100.0) for i in range(40)]

    specs = dollar_window_specs(weeks)

    assert list(specs) == [
        "full-after-sma8-warmup",
        "2022",
        "2025-10-06..2026-06-30",
        LONG_RUN_WINDOW,
    ]
    assert specs["full-after-sma8-warmup"][0] == weeks[SMA8_LOOKBACK][0]
    assert specs["full-after-sma8-warmup"][1] == weeks[-1][0]
    assert specs["2022"] == (WINDOWS["2022"][0], WINDOWS["2022"][1])
    assert specs["2025-10-06..2026-06-30"][0] == WINDOWS["2025-10-06..2026-06-30"][0]
    assert specs[LONG_RUN_WINDOW][0] == date(2024, 1, 1)
