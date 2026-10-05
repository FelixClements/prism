"""Hand-computed weekly indicator values from the 2026-10-05 spec."""

from datetime import date, timedelta

import pytest

from price_forecast.data.candles import Candle
from price_forecast.strategies.crashgate_v1 import weekly_sessions
from price_forecast.strategies.indicators import WeekBar, series_values, weekly_bars


def _bars_from_closes(closes: list[float]) -> list[WeekBar]:
    start = date(2022, 1, 2)
    return [
        WeekBar(start + timedelta(weeks=index), close, close, close, close, 1.0)
        for index, close in enumerate(closes)
    ]


def _ohlc() -> list[WeekBar]:
    start = date(2022, 1, 2)
    rows = (
        (10.0, 8.0, 9.0, 100.0),
        (12.0, 9.0, 11.0, 50.0),
        (11.0, 7.0, 8.0, 80.0),
        (13.0, 10.0, 12.0, 40.0),
    )
    return [
        WeekBar(start + timedelta(weeks=index), row[2], row[0], row[1], row[2], row[3])
        for index, row in enumerate(rows)
    ]


def test_sma_ema_rsi_and_roc_on_the_sample_closes():
    bars = _bars_from_closes([10.0, 11.0, 12.0, 11.0, 13.0])

    assert series_values("sma", (3,), bars)[-1] == pytest.approx(12.0)
    assert series_values("ema", (3,), bars)[2] == pytest.approx(11.0)
    assert series_values("ema", (3,), bars)[3] == pytest.approx(11.0)
    assert series_values("ema", (3,), bars)[-1] == pytest.approx(12.0)
    assert series_values("rsi", (2,), bars)[-1] == pytest.approx(100.0 - 100.0 / 6.0)
    assert series_values("roc", (2,), bars)[-1] == pytest.approx((13.0 / 12.0 - 1.0) * 100.0)


def test_macd_and_bollinger_on_the_sample_closes():
    bars = _bars_from_closes([10.0, 11.0, 12.0, 11.0, 13.0])

    assert series_values("macd", (2, 3), bars)[-1] == pytest.approx(7.0 / 18.0)
    assert series_values("macd_signal", (2, 3, 2), bars)[-1] == pytest.approx(10.0 / 27.0)
    assert series_values("macd_hist", (2, 3, 2), bars)[-1] == pytest.approx(1.0 / 54.0)
    assert series_values("bb_mid", (2, 2), bars)[-1] == pytest.approx(12.0)
    assert series_values("bb_upper", (2, 2), bars)[-1] == pytest.approx(14.0)
    assert series_values("bb_lower", (2, 2), bars)[-1] == pytest.approx(10.0)


def test_ohlc_indicators_match_the_hand_values():
    bars = _ohlc()

    assert series_values("atr", (2,), bars)[2] == pytest.approx(3.5)
    assert series_values("donchian_high", (2,), bars)[2] == pytest.approx(12.0)
    assert series_values("obv", (), bars)[:3] == pytest.approx((100.0, 150.0, 70.0))
    assert series_values("rel_volume", (2,), bars)[2] == pytest.approx(80.0 / 65.0)
    assert series_values("stoch", (2,), bars)[1] == pytest.approx(75.0)
    assert series_values("stoch", (2,), bars)[2] == pytest.approx(20.0)
    assert series_values("stoch_d", (2, 2), bars)[2] == pytest.approx(47.5)
    assert series_values("adx", (2,), bars)[3] == pytest.approx(25.0)


def test_blank_volume_makes_obv_undefined():
    bars = _ohlc()
    blank = WeekBar(bars[0].day, bars[0].open, bars[0].high, bars[0].low, bars[0].close, None)

    assert series_values("obv", (), [blank, *bars[1:]])[0] is None
    assert series_values("rel_volume", (2,), [blank, *bars[1:]])[1] is None


def test_weekly_bars_use_the_same_close_as_the_locked_week_builder():
    start = date(2024, 1, 1)
    candles = []
    for offset in range(14):
        day = start + timedelta(days=offset)
        close = 100.0 + offset
        candles.append(Candle(day, close - 2, close + 2, close - 1, close, 10.0 + offset))

    bars = weekly_bars(candles)
    sessions = weekly_sessions(candles)

    assert [(bar.day, bar.close) for bar in bars] == sessions
    assert bars[0].high == pytest.approx(max(candle.high for candle in candles[:7]))
    assert bars[0].low == pytest.approx(min(candle.low for candle in candles[:7]))
    assert bars[0].volume == pytest.approx(sum(10.0 + offset for offset in range(7)))
