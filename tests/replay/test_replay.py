from __future__ import annotations

import math
import random
from datetime import date, timedelta

import numpy as np
import pytest

from price_forecast.data.candles import Candle
from price_forecast.replay.benchmarks import constant_exposure, hodl, random_timing, shuffled_targets, spells
from price_forecast.replay.engine import FlagSignal, metrics, replay
from price_forecast.replay.robustness import anchor_sweep, neighbours
from price_forecast.replay.selection import cscv_pbo, deflated_sharpe, expected_max_sharpe, probabilistic_sharpe
from price_forecast.search.runner import SpecSignal, simulate_spec
from price_forecast.search.spec import Spec, locked_crashgate
from price_forecast.strategies.indicators import weekly_bars

ALWAYS = lambda _day: (True, True)  # noqa: E731
SMA_8_16 = Spec(mode="threshold", close_above_sma_weeks=8, close_below_sma_weeks=16, down_week=0.10)


def _candles(days: int = 900, seed: int = 3) -> list[Candle]:
    rng = random.Random(seed)
    start = date(2020, 1, 6)  # a Monday
    price = 100.0
    out = []
    for offset in range(days):
        drift = 0.004 * math.sin(offset / 90.0)
        price *= math.exp(drift + rng.gauss(0.0, 0.03))
        out.append(Candle(start + timedelta(days=offset), price * 0.98, price * 1.02, price, price, 1.0))
    return out


def _weeks(candles, anchor: int = 6):
    bars = weekly_bars(candles, week_end_weekday=anchor)
    return bars, [(bar.day, bar.close) for bar in bars]


def test_next_week_replay_matches_the_search_simulator_at_weekly_marks():
    candles = _candles()
    bars, weeks = _weeks(candles)
    expected = simulate_spec(weeks, SMA_8_16, ALWAYS, bars=bars)
    signal = SpecSignal(weeks, SMA_8_16, ALWAYS, bars=bars)
    path = replay(candles, weeks, signal, fill="next_week", cost=0.0015)
    assert path.week_days == expected.dates
    assert path.week_equity == pytest.approx(expected.equity)
    assert len(path.trip_returns) == expected.completed_round_trips
    assert len(path.fills) == len(expected.fills)


def test_locked_crashgate_spec_runs_through_the_signal():
    candles = _candles()
    bars, weeks = _weeks(candles)
    signal = SpecSignal(weeks, locked_crashgate(), ALWAYS, bars=bars)
    assert signal.first == 16
    path = replay(candles, weeks, signal, fill="next_day")
    assert path.fills


def test_next_day_fill_uses_the_next_daily_close():
    candles = _candles()
    _bars, weeks = _weeks(candles)
    signal = SpecSignal(weeks, SMA_8_16, ALWAYS, bars=_bars)
    path = replay(candles, weeks, signal, fill="next_day", cost=0.0)
    signal_days = {day for day, _close in weeks}
    by_day = {candle.day: candle.close for candle in candles}
    assert path.fills
    for fill in path.fills:
        assert fill.day - timedelta(days=1) in signal_days
        assert fill.price == by_day[fill.day]


def test_same_close_fill_uses_the_signal_close():
    candles = _candles()
    bars, weeks = _weeks(candles)
    signal = SpecSignal(weeks, SMA_8_16, ALWAYS, bars=bars)
    path = replay(candles, weeks, signal, fill="same_close", cost=0.0)
    closes = dict(weeks)
    for fill in path.fills:
        assert fill.price == closes[fill.day]


def test_slippage_only_lowers_the_result():
    candles = _candles()
    bars, weeks = _weeks(candles)
    signal = SpecSignal(weeks, SMA_8_16, ALWAYS, bars=bars)
    clean = replay(candles, weeks, signal, fill="next_day", slippage=0.0)
    slipped = replay(candles, weeks, signal, fill="next_day", slippage=0.003)
    assert [f.day for f in clean.fills] == [f.day for f in slipped.fills]
    assert slipped.end_dollars < clean.end_dollars


def test_hodl_and_full_constant_exposure_agree_without_costs():
    candles = _candles()
    _bars, weeks = _weeks(candles)
    held = hodl(candles, weeks, 16, cost=0.0)
    mixed = constant_exposure(candles, weeks, 16, 1.0, cost=0.0)
    assert mixed.end_dollars == pytest.approx(held.end_dollars)
    assert held.days[0] == weeks[16][0]
    assert held.end_dollars == pytest.approx(10_000.0 * candles[-1].close / weeks[16][1])


def test_zero_exposure_stays_in_cash():
    candles = _candles()
    _bars, weeks = _weeks(candles)
    path = constant_exposure(candles, weeks, 16, 0.0)
    assert path.end_dollars == pytest.approx(10_000.0)


def test_weekly_bars_anchor_on_the_requested_weekday():
    candles = _candles()
    sunday = weekly_bars(candles)
    assert sunday == weekly_bars(candles, week_end_weekday=6)
    for anchor in range(7):
        bars = weekly_bars(candles, week_end_weekday=anchor)
        assert all(bar.day.weekday() == anchor for bar in bars)
        assert bars[-1].day <= candles[-1].day
    with pytest.raises(ValueError):
        weekly_bars(candles, week_end_weekday=7)


def test_anchor_sweep_covers_every_weekday():
    candles = _candles()
    variants = anchor_sweep(candles, SMA_8_16, ALWAYS, fill="next_day")
    assert [variant.anchor for variant in variants] == list(range(7))


def test_shuffled_spells_keep_exposure_and_trade_count():
    targets = [0, 0, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 0]
    rng = random.Random(1)
    for _ in range(50):
        shuffled = shuffled_targets(targets, rng)
        assert len(shuffled) == len(targets)
        assert sum(shuffled) == sum(targets)
        assert [state for state, _ in spells(shuffled)] == [state for state, _ in spells(targets)]


def test_random_timing_p_values_are_probabilities():
    candles = _candles()
    bars, weeks = _weeks(candles)
    signal = SpecSignal(weeks, SMA_8_16, ALWAYS, bars=bars)
    path = replay(candles, weeks, signal, fill="next_day")
    result = random_timing(candles, weeks, path, signal.first, runs=40, seed=2, fill="next_day")
    for value in (result.total_return_p, result.sharpe_p, result.drawdown_p):
        assert 0.0 < value <= 1.0


def test_flag_signal_all_true_buys_once():
    candles = _candles()
    _bars, weeks = _weeks(candles)
    path = replay(candles, weeks, FlagSignal([True] * len(weeks), 16), fill="next_day")
    assert [fill.side for fill in path.fills] == ["BUY"]
    assert metrics(path).round_trips == 0


def test_neighbours_include_the_frozen_spec_once_and_stay_on_grid():
    found = neighbours(locked_crashgate())
    frozen = [spec for label, spec in found if label.endswith("(frozen)")]
    assert frozen == [locked_crashgate()]
    assert len({spec for _label, spec in found}) == len(found)
    assert len(found) == 27 + 3


def test_neighbours_reject_indicator_specs():
    with pytest.raises(ValueError):
        neighbours(Spec(mode="indicator"))


def test_expected_max_sharpe_grows_with_trials():
    assert expected_max_sharpe(1, 0.01) == 0.0
    assert expected_max_sharpe(10, 0.01) < expected_max_sharpe(1000, 0.01)


def test_deflated_sharpe_equals_psr_with_one_trial_and_falls_with_more():
    rng = np.random.default_rng(0)
    returns = rng.normal(0.01, 0.05, 400)
    _sr, psr = probabilistic_sharpe(returns, 0.0)
    one = deflated_sharpe(returns, n_trials=1, sharpe_variance=0.01)
    many = deflated_sharpe(returns, n_trials=10_000, sharpe_variance=0.01)
    assert one.dsr == pytest.approx(psr)
    assert many.dsr < one.dsr


def test_pbo_is_high_for_noise_and_low_for_a_dominant_strategy():
    rng = np.random.default_rng(0)
    noise = rng.normal(0.0, 0.02, (320, 40))
    assert cscv_pbo(noise, blocks=8).pbo > 0.3
    skilled = noise.copy()
    skilled[:, 0] += 0.02
    assert cscv_pbo(skilled, blocks=8).pbo < 0.05
