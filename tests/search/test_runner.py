from datetime import date, timedelta

import pytest

from price_forecast.search.runner import FILL_COST, simulate_spec
from price_forecast.search.spec import Spec, spec_from_mapping, spec_to_mapping
from price_forecast.strategies.indicators import WeekBar


def _weeks(closes: list[float]):
    start = date(2018, 1, 7)
    return [(start + timedelta(days=7 * i), close) for i, close in enumerate(closes)]


def test_spec_cannot_name_fill_or_fee():
    spec = Spec(mode="threshold", close_above_sma_weeks=4, close_below_sma_weeks=12)
    assert spec_to_mapping(spec).keys().isdisjoint({"cost", "fill", "starting_dollars"})
    assert FILL_COST == pytest.approx(0.0015)


def test_buy_fills_next_week_and_charges_fifteen_bps():
    closes = [100.0] * 20 + [200.0] * 8
    calls = {"n": 0}

    def gate(_day):
        calls["n"] += 1
        return True, True

    spec = Spec(mode="threshold", close_above_sma_weeks=4, close_below_sma_weeks=12)
    path = simulate_spec(_weeks(closes), spec, gate)
    buys = [fill for fill in path.fills if fill.side == "BUY"]
    assert buys
    assert buys[0].price == pytest.approx(200.0)
    assert buys[0].fee == pytest.approx(10_000.0 * 0.0015)
    assert calls["n"] == 0


def _bars(closes: list[float]) -> list[WeekBar]:
    start = date(2018, 1, 7)
    return [
        WeekBar(start + timedelta(days=7 * index), close, close, close, close, 1.0)
        for index, close in enumerate(closes)
    ]


def test_indicator_buys_on_the_next_week():
    bars = _bars([1.0, 1.0, 1.0, 10.0, 10.0])
    weeks = [(bar.day, bar.close) for bar in bars]
    spec = spec_from_mapping(
        {
            "mode": "indicator",
            "conditions": [
                {"left": "close", "args": [], "op": ">", "right": {"series": "sma", "args": [2]}},
            ],
            "base_or_breakout": False,
            "above_long_averages": False,
        }
    )
    path = simulate_spec(weeks, spec, lambda _day: (True, True), bars=bars)
    buys = [fill for fill in path.fills if fill.side == "BUY"]
    assert buys
    assert buys[0].price == pytest.approx(10.0)
    assert buys[0].fee == pytest.approx(10_000.0 * 0.0015)
    both = spec_from_mapping(
        {
            "mode": "indicator",
            "conditions": [
                {"left": "close", "args": [], "op": ">", "right": {"series": "sma", "args": [2]}},
                {"left": "close", "args": [], "op": "<", "right": {"value": 0}},
            ],
            "base_or_breakout": False,
            "above_long_averages": False,
        }
    )
    assert simulate_spec(weeks, both, lambda _day: (True, True), bars=bars).fills == []


def test_undefined_indicator_raises_and_a_flat_one_does_not_trade():
    one = _bars([10.0])
    spec = spec_from_mapping(
        {
            "mode": "indicator",
            "conditions": [
                {"left": "rsi", "args": [21], "op": "<", "right": {"value": 25}},
            ],
            "base_or_breakout": False,
            "above_long_averages": False,
        }
    )
    with pytest.raises(ValueError, match="undefined"):
        simulate_spec([(one[0].day, one[0].close)], spec, lambda _day: (True, True), bars=one)
    flat = _bars([5.0] * 8)
    weeks = [(bar.day, bar.close) for bar in flat]
    quiet = spec_from_mapping(
        {
            "mode": "indicator",
            "conditions": [
                {"left": "close", "args": [], "op": ">", "right": {"series": "sma", "args": [2]}},
            ],
            "base_or_breakout": False,
            "above_long_averages": False,
        }
    )
    path = simulate_spec(weeks, quiet, lambda _day: (True, True), bars=flat)
    assert path.fills == []
    long = _bars([100.0 + index for index in range(40)])
    long_weeks = [(bar.day, bar.close) for bar in long]
    simulated = simulate_spec(long_weeks, spec, lambda _day: (True, True), bars=long)
    assert simulated.end_dollars == pytest.approx(10_000.0)


def test_gate_false_blocks_the_buy():
    closes = [100.0] * 20 + [200.0] * 8
    spec = Spec(
        mode="threshold",
        close_above_sma_weeks=4,
        base_or_breakout=True,
        close_below_sma_weeks=12,
    )
    path = simulate_spec(_weeks(closes), spec, lambda _day: (False, True))
    assert path.fills == []
    assert path.end_dollars == pytest.approx(10_000.0)
