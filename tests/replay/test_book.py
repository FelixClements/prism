from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from price_forecast.data.candles import Candle
from price_forecast.replay.benchmarks import constant_exposure
from price_forecast.replay.book import (
    book_metrics,
    book_weekly_returns,
    circular_shift_test,
    combine,
    constant_decisions,
    replay_targets,
    run_sleeves,
    sharpe_diff,
    slice_book,
    spell_shuffle_test,
)
from price_forecast.replay.engine import replay
from price_forecast.replay.sizing import SizingRule, ewma_vol, sizing_decisions, sizing_neighbours, tsmom_score
from price_forecast.search.runner import SpecSignal

from tests.replay.test_replay import ALWAYS, SMA_8_16, _candles, _weeks


def _spec_decisions(weeks, signal):
    position = 0
    out = []
    for index in range(signal.first, len(weeks) - 1):
        side = signal.decide(index, position)
        if side == "buy":
            position = 1
        elif side == "sell":
            position = 0
        out.append((weeks[index][0], float(position)))
    return out


@pytest.mark.parametrize("fill", ["same_close", "next_day"])
def test_binary_targets_reproduce_the_all_in_engine(fill):
    candles = _candles()
    bars, weeks = _weeks(candles)
    signal = SpecSignal(weeks, SMA_8_16, ALWAYS, bars=bars)
    path = replay(candles, weeks, signal, fill=fill, cost=0.0015, slippage=0.001)
    book = replay_targets(candles, _spec_decisions(weeks, signal), fill=fill, cost=0.0015, slippage=0.001)
    assert book.days == path.days
    assert book.equity == pytest.approx(path.equity, rel=1e-12)
    assert book.trades == len(path.fills)
    assert book.costs_paid == pytest.approx(path.costs_paid)


def test_constant_targets_match_the_constant_exposure_benchmark():
    candles = _candles()
    _bars, weeks = _weeks(candles)
    first = 10
    expected = constant_exposure(candles, weeks, first, 0.4, cost=0.0, slippage=0.0)
    decisions = [(day, 0.4) for day, _close in weeks[first:-1]]
    book = replay_targets(candles, decisions, fill="same_close", cost=0.0)
    assert book.equity == pytest.approx(expected.equity, rel=1e-12)
    decided = {day for day, _value in decisions}
    assert all(value == pytest.approx(0.4) for day, value in zip(book.days, book.exposure) if day in decided)


def test_fees_are_charged_on_traded_notional():
    candles = _candles(days=60)
    start = candles[0].day
    book = replay_targets(candles, [(start, 0.5)], fill="same_close", cost=0.01)
    assert book.trades == 1
    assert book.traded[0] == pytest.approx(5000.0 / 0.99)
    assert book.costs_paid == pytest.approx(book.traded[0] * 0.01)
    assert book.exposure[0] == pytest.approx(5000.0 / (10_000.0 - book.costs_paid))


def test_buys_never_borrow():
    candles = _candles(days=60)
    book = replay_targets(candles, [(candles[0].day, 1.0)], fill="same_close", cost=0.01)
    assert book.exposure[0] == pytest.approx(1.0)
    assert book.equity[0] == pytest.approx(9_900.0)


def test_targets_outside_unit_interval_are_rejected():
    candles = _candles(days=30)
    with pytest.raises(ValueError):
        replay_targets(candles, [(candles[0].day, 1.2)])
    with pytest.raises(ValueError):
        replay_targets(candles, [(candles[0].day, 0.5)], fill="next_week")


def test_two_half_sleeves_equal_one_whole_sleeve():
    candles = _candles()
    bars, weeks = _weeks(candles)
    signal = SpecSignal(weeks, SMA_8_16, ALWAYS, bars=bars)
    decisions = _spec_decisions(weeks, signal)
    start = decisions[0][0]
    whole = replay_targets(candles, decisions, start_day=start)
    halves = run_sleeves(candles, [decisions, decisions], start_day=start)
    assert halves.equity == pytest.approx(whole.equity)
    assert halves.exposure == pytest.approx(whole.exposure)
    assert book_metrics(halves).turnover == pytest.approx(book_metrics(whole).turnover)


def test_combined_exposure_is_the_wealth_weighted_mean():
    candles = _candles(days=120)
    start = candles[0].day
    a = replay_targets(candles, [(start, 1.0)], fill="same_close", cost=0.0)
    b = replay_targets(candles, [(start, 0.0)], fill="same_close", cost=0.0)
    both = combine([a, b])
    for i in range(len(both.days)):
        assert both.exposure[i] == pytest.approx(a.equity[i] / (a.equity[i] + b.equity[i]))


def test_slice_book_rebases_to_the_new_start():
    candles = _candles(days=200)
    start = candles[0].day
    book = replay_targets(candles, [(start, 1.0)], fill="same_close", cost=0.0)
    later = slice_book(book, start + timedelta(days=50))
    assert later.start_dollars == book.equity[50]
    assert book_metrics(later).total_return == pytest.approx(book.equity[-1] / book.equity[50] - 1.0)


def test_weekly_returns_use_sunday_marks():
    candles = _candles(days=70)
    book = replay_targets(candles, [(candles[0].day, 1.0)], fill="same_close", cost=0.0)
    sundays = [c.close for c in candles if c.day.weekday() == 6]
    expected = [sundays[i] / sundays[i - 1] - 1.0 for i in range(1, len(sundays))]
    assert book_weekly_returns(book) == pytest.approx(expected)


def test_constant_decisions_start_on_the_start_day():
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(30)]
    decisions = constant_decisions(days, days[2], 0.3)
    assert decisions[0] == (days[2], 0.3)
    assert all(day.weekday() == 6 for day, _value in decisions[1:])


def test_timing_tests_return_probabilities():
    candles = _candles()
    bars, weeks = _weeks(candles)
    signal = SpecSignal(weeks, SMA_8_16, ALWAYS, bars=bars)
    sleeves = [_spec_decisions(weeks, signal)]
    start = sleeves[0][0][0]

    def run(items):
        return run_sleeves(candles, items, start_day=start)

    observed = book_metrics(run(sleeves))
    shift = circular_shift_test(candles, sleeves, observed, min_shift=10, run=run)
    assert 0.0 < shift.sharpe_p <= 1.0
    assert shift.runs == len(sleeves[0]) - 20 + 1
    shuffle = spell_shuffle_test(sleeves, observed, runs=20, seed=1, run=run)
    assert 0.0 < shuffle.sharpe_p <= 1.0
    with pytest.raises(ValueError):
        spell_shuffle_test([[(start, 0.5)] * 3], observed, runs=2, seed=1, run=run)


def test_sharpe_diff_of_a_series_with_itself_is_zero():
    rng = np.random.default_rng(0)
    x = rng.normal(0.01, 0.05, 300)
    same = sharpe_diff(x, x, runs=200)
    assert same.diff == 0.0
    assert same.p_not_better == 1.0
    better = sharpe_diff(x + 0.02, x, runs=200)
    assert better.diff > 0.0
    assert better.p_not_better < 0.05


def test_ewma_vol_tracks_a_known_daily_vol():
    start = date(2020, 1, 1)
    price = 100.0
    candles = []
    for i in range(400):
        price *= 1.02 if i % 2 else 0.98
        candles.append(Candle(start + timedelta(days=i), price, price, price, price, 1.0))
    vols = ewma_vol(candles, 60)
    assert min(vols) == candles[60].day
    assert vols[candles[-1].day] == pytest.approx(0.02 * math.sqrt(365.0), rel=0.01)


def test_tsmom_score_uses_only_available_lookbacks():
    closes = [1.0, 2.0, 3.0, 2.5]
    assert tsmom_score(closes, 3, (1, 2, 52)) == 0.5
    assert tsmom_score(closes, 0, (1, 2)) == 0.0


def test_sizing_decisions_stay_in_unit_interval_and_follow_trend():
    start = date(2020, 1, 6)
    rising = [Candle(start + timedelta(days=i), 1, 1, 1, 100.0 * 1.002**i, 1.0) for i in range(500)]
    falling = [Candle(c.day, 1, 1, 1, 100.0 * 0.998**i, 1.0) for i, c in enumerate(rising)]
    for kind in ("voltarget", "tsmom", "voltarget_tsmom"):
        rule = SizingRule(kind)
        for candles in (rising, falling, _candles()):
            decisions = sizing_decisions(candles, rule, start_day=candles[100].day)
            assert decisions and all(0.0 <= value <= 1.0 for _day, value in decisions)
    up = sizing_decisions(rising, SizingRule("tsmom"), start_day=rising[100].day)
    down = sizing_decisions(falling, SizingRule("tsmom"), start_day=falling[100].day)
    assert all(value == 1.0 for _day, value in up)
    assert all(value == 0.0 for _day, value in down)


def test_sizing_neighbours_include_the_frozen_rule_once():
    for kind in ("voltarget", "tsmom", "voltarget_tsmom"):
        rule = SizingRule(kind)
        labels = [label for label, candidate in sizing_neighbours(rule) if candidate == rule]
        assert len(labels) == (1 if kind != "tsmom" else 0)
