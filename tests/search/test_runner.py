from datetime import date, timedelta

import pytest

from price_forecast.search.runner import FILL_COST, simulate_spec
from price_forecast.search.spec import Spec, spec_to_mapping


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
