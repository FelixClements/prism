"""CrashGateV1 rule checks. The Coinbase regression needs the local candle file."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from price_forecast.data.candles import BTC_USD_DAILY_CSV
from price_forecast.strategies.crashgate_v1 import (
    BUY_WEEKS,
    FILL_COST,
    FIRST_BAR,
    SELL_WEEKS,
    STARTING_DOLLARS,
    WEEK_DROP,
    simulate_crashgate,
    weekly_sessions,
)
from price_forecast.data.candles import read_candles


def test_defaults_match_the_locked_rule():
    assert BUY_WEEKS == 8
    assert SELL_WEEKS == 16
    assert WEEK_DROP == pytest.approx(0.10)
    assert FILL_COST == pytest.approx(0.0015)
    assert STARTING_DOLLARS == 10_000.0
    assert FIRST_BAR == 16


def test_ten_percent_week_above_the_fast_average_does_not_sell():
    closes = [100.0] * 21 + [200.0, 200.0, 180.0]
    weeks = [(date(2018, 1, 1) + timedelta(days=7 * i), close) for i, close in enumerate(closes)]
    path = simulate_crashgate(weeks, lambda _day: True, cost=0.0)
    sell_fills = [fill for fill in path.fills if fill.side == "SELL"]
    assert sell_fills == []
    assert path.long[-1] is True


def test_ten_percent_week_under_the_fast_average_sells_next_week():
    closes = [100.0] * 21 + [200.0, 200.0, 180.0, 100.0, 100.0]
    weeks = [(date(2018, 1, 1) + timedelta(days=7 * i), close) for i, close in enumerate(closes)]
    path = simulate_crashgate(weeks, lambda _day: True, cost=0.0)
    sells = [fill for fill in path.fills if fill.side == "SELL"]
    assert len(sells) == 1
    assert sells[0].date == weeks[-1][0]
    assert sells[0].price == 100.0


def test_buy_stays_flat_when_the_base_gate_says_no():
    closes = [100.0] * 21 + [200.0, 200.0]
    weeks = [(date(2018, 1, 1) + timedelta(days=7 * i), close) for i, close in enumerate(closes)]
    path = simulate_crashgate(weeks, lambda _day: False, cost=0.0)
    assert path.fills == []
    assert path.end_dollars == STARTING_DOLLARS


def test_source_does_not_import_backtest_at_module_level():
    text = (
        Path(__file__).resolve().parents[2] / "price_forecast/strategies/crashgate_v1.py"
    ).read_text(encoding="utf-8")
    header, _, _rest = text.partition("def weekly_sessions")
    assert "price_forecast.backtest" not in header
    assert "backtest.t1" not in text


@pytest.mark.skipif(not BTC_USD_DAILY_CSV.is_file(), reason="local Coinbase candles are absent")
def test_locked_coinbase_result():
    candles = read_candles(BTC_USD_DAILY_CSV)
    from price_forecast.strategies.crashgate_entry import BaseBreakoutGate

    path = simulate_crashgate(weekly_sessions(candles), BaseBreakoutGate(candles))
    assert path.end_dollars == pytest.approx(266_891.67, abs=0.02)
    assert path.completed_round_trips == 14
