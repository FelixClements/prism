"""Asymmetric SMA $10k grid: frozen combos, 40-week warmup, same calendar windows."""

from __future__ import annotations

from datetime import date, timedelta

from price_forecast.sma8_10k import STARTING_DOLLARS
from price_forecast.sma_asymmetric_10k import (
    BUY_WEEKS,
    LONGEST_SMA,
    SELL_WEEKS,
    combo_beats_sma8_and_keeps_both_crashes,
    dollar_window_specs,
    format_report,
    frozen_combos,
    score_grid,
)
from price_forecast.weekly_bakeoff import LONG_RUN_WINDOW, WINDOWS
from price_forecast.weekly_regime import DD_IMPROVEMENT, sma_first_fill_date


def test_starting_capital_is_ten_thousand_dollars():
    assert STARTING_DOLLARS == 10_000.0


def test_frozen_grid_skips_sell_weeks_not_longer_than_buy_weeks():
    assert BUY_WEEKS == (4, 6, 8, 10, 12)
    assert SELL_WEEKS == (12, 16, 20, 26, 40)
    combos = frozen_combos()
    assert len(combos) == 24
    assert (12, 12) not in combos
    assert all(sell > buy for buy, sell in combos)
    assert combos[0] == (4, 12)
    assert combos[-1] == (12, 40)


def test_dollar_windows_are_longest_sma_warmup_plus_the_three_calendar_spans():
    weeks = [(date(2018, 1, 7) + timedelta(weeks=i), 100.0) for i in range(50)]

    specs = dollar_window_specs(weeks)

    assert list(specs) == [
        "full-after-sma40-warmup",
        "2022",
        "2025-10-06..2026-06-30",
        LONG_RUN_WINDOW,
    ]
    assert LONGEST_SMA == 40
    assert specs["full-after-sma40-warmup"][0] == sma_first_fill_date(weeks, 40)
    assert specs["full-after-sma40-warmup"][0] == weeks[40][0]
    assert specs["full-after-sma40-warmup"][1] == weeks[-1][0]
    assert specs["2022"] == (WINDOWS["2022"][0], WINDOWS["2022"][1])
    assert specs["2025-10-06..2026-06-30"][0] == WINDOWS["2025-10-06..2026-06-30"][0]
    assert specs[LONG_RUN_WINDOW][0] == date(2024, 1, 1)


def test_callout_requires_beating_sma8_end_and_both_crash_drawdowns():
    both_crashes = [(-0.40, -0.55), (-0.30, -0.45)]
    assert combo_beats_sma8_and_keeps_both_crashes(
        full_end=12_000.0,
        sma8_end=11_000.0,
        crash_dds=both_crashes,
    )
    assert not combo_beats_sma8_and_keeps_both_crashes(
        full_end=11_000.0,
        sma8_end=11_000.0,
        crash_dds=both_crashes,
    )
    assert not combo_beats_sma8_and_keeps_both_crashes(
        full_end=12_000.0,
        sma8_end=11_000.0,
        crash_dds=[(-0.40, -0.55), (-0.50, -0.45)],
    )
    assert DD_IMPROVEMENT == 0.10


def _weeks_covering_all_windows() -> list[tuple[date, float]]:
    start = date(2018, 1, 7)
    return [(start + timedelta(weeks=i), 100.0 + i) for i in range(460)]


def test_report_is_a_map_not_a_product_rule():
    weeks = _weeks_covering_all_windows()
    grids = score_grid(weeks)
    report = format_report(
        weeks,
        grids,
        daily_first=weeks[0][0],
        daily_last=weeks[-1][0],
        n_daily=len(weeks) * 7,
    )

    assert "overfitting" in report.lower()
    assert "do not quietly replace sma-8" in report.lower()
    assert "not comparable" in report.lower()
    assert "buy4/sell12" in report
    assert "buy12/sell12" not in report
    assert "SMA-8" in report
    assert "SMA-12" in report
    assert "buy-and-hold" in report
    assert grids[0].window == "full-after-sma40-warmup"
    assert len(grids[0].combos) == 24
