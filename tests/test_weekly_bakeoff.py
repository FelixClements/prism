"""Frozen weekly bakeoff scoreboard: no extra lookbacks, no F&G threshold search."""

from __future__ import annotations

from datetime import date, timedelta

from price_forecast.weekly_bakeoff import (
    CRASH_WINDOWS,
    LONG_RUN_WINDOW,
    STRATEGIES,
    WindowScore,
    strategy_signals,
    window_specs,
    winner_line,
)
from price_forecast.weekly_regime import BacktestResult


def test_frozen_strategies_are_the_three_families_plus_fng_overlay_and_fng_only():
    assert STRATEGIES == [
        "buy-hold",
        "sma-8",
        "sma-12",
        "dual-sma-12-26",
        "donchian-12",
        "sma-8+fng",
        "sma-12+fng",
        "dual-sma-12-26+fng",
        "donchian-12+fng",
        "fng-only",
    ]


def test_crash_windows_are_2022_and_the_53pct_path():
    assert CRASH_WINDOWS == ("2022", "2025-10-06..2026-06-30")
    assert LONG_RUN_WINDOW == "2024-01-01..latest"


def _score(name: str, *, c: bool, a: bool) -> WindowScore:
    dummy = BacktestResult(1.0, -0.2, 0.5, 1, date(2022, 1, 9), date(2022, 12, 25), 50)
    return WindowScore(strategy=name, window="2022", result=dummy, buy_hold=dummy, pass_c=c, pass_a=a)


def test_winner_requires_c_or_a_on_both_crash_windows():
    scores = [
        _score("sma-8", c=True, a=True),
        _score("sma-8", c=True, a=True),
    ]
    # one crash window missing
    by_window = {"2022": [scores[0]]}
    assert "none passed" in winner_line(by_window).lower()

    by_window = {
        "2022": [_score("sma-8", c=True, a=True)],
        "2025-10-06..2026-06-30": [_score("sma-8", c=True, a=True)],
    }
    line = winner_line(by_window)
    assert "sma-8" in line
    assert "C" in line


def test_a_only_winner_if_a_on_both_crashes_but_not_c():
    by_window = {
        "2022": [_score("donchian-12", c=False, a=True)],
        "2025-10-06..2026-06-30": [_score("donchian-12", c=False, a=True)],
    }
    line = winner_line(by_window)
    assert "donchian-12" in line
    assert "A" in line
    assert "none passed" not in line.lower()


def test_no_winner_when_a_passes_only_one_crash_window():
    by_window = {
        "2022": [_score("sma-8", c=False, a=True)],
        "2025-10-06..2026-06-30": [_score("sma-8", c=False, a=False)],
    }
    assert "none passed" in winner_line(by_window).lower()


def test_full_after_warmup_starts_at_the_26th_completed_week_close():
    weeks = [(date(2020, 1, 5) + timedelta(weeks=i), 100.0) for i in range(30)]

    specs = window_specs(weeks)

    assert specs["full-after-warmup"][0] == weeks[26][0]
    assert specs["full-after-warmup"][1] == weeks[-1][0]


def test_fng_overlay_strategy_forces_cash_and_does_not_force_a_buy():
    weeks = [(date(2022, 1, 9) + timedelta(weeks=i), 100.0) for i in range(8)]
    greedy = [80] * 8
    fearful = [10] * 8

    greedy_signals = strategy_signals("sma-8+fng", weeks, greedy)
    assert all(s == 0 for s in greedy_signals if s is not None)
    assert strategy_signals("sma-8", weeks, fearful)[-1] == 0
    assert strategy_signals("sma-8+fng", weeks, fearful)[-1] == 0
