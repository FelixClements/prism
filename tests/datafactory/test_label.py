from __future__ import annotations

import pytest

from price_forecast.datafactory.synthetic.label import (
    TREND_BAND,
    TREND_BARS,
    VOL_BARS,
    label_candles,
)
from tests.datafactory.fixture import candles_from_closes


def test_defaults_are_the_spec_windows():
    assert TREND_BARS == 365
    assert VOL_BARS == 30
    assert TREND_BAND == 0.25


def test_prefix_is_unlabeled_and_cutoffs_name_the_trend():
    bull = label_candles(candles_from_closes([100, 100, 100, 100, 130]), trend_bars=4, vol_bars=2)
    bear = label_candles(candles_from_closes([100, 100, 100, 100, 70]), trend_bars=4, vol_bars=2)
    inside = label_candles(candles_from_closes([100, 100, 100, 100, 110]), trend_bars=4, vol_bars=2)
    up_edge = label_candles(candles_from_closes([100, 100, 100, 100, 125]), trend_bars=4, vol_bars=2)
    down_edge = label_candles(candles_from_closes([100, 100, 100, 100, 75]), trend_bars=4, vol_bars=2)

    assert bull.labels == (None, None, None, None, "bull_quiet")
    assert bear.labels == (None, None, None, None, "bear_quiet")
    assert inside.labels[-1] == "sideways_quiet"
    assert up_edge.labels[-1] == "sideways_quiet"
    assert down_edge.labels[-1] == "sideways_quiet"


def test_row_at_the_vol_median_is_quiet_and_a_wilder_row_is_volatile():
    labeled = label_candles(
        candles_from_closes([100, 100, 100, 100, 130, 80]),
        trend_bars=4,
        vol_bars=2,
    )
    assert labeled.labels[4] == "bull_quiet"
    assert labeled.labels[5] == "sideways_volatile"
    assert labeled.vol_median == pytest.approx(0.35717248497513854)


def test_equal_volatility_is_quiet():
    closes = [100.0]
    for _ in range(5):
        closes.append(closes[-1] * 1.1)
    labeled = label_candles(candles_from_closes(closes), trend_bars=4, vol_bars=2)
    assert labeled.labels[4] == "bull_quiet"
    assert labeled.labels[5] == "bull_quiet"


def test_no_labeled_row_raises():
    with pytest.raises(ValueError, match="no labeled rows"):
        label_candles(candles_from_closes([100, 101, 102]), trend_bars=4, vol_bars=2)
