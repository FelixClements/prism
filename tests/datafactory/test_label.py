from __future__ import annotations

import pytest

from price_forecast.datafactory.synthetic.label import (
    TREND_BAND,
    MIN_RUN_BARS,
    TREND_BARS,
    VOL_BARS,
    label_candles,
)
from tests.datafactory.fixture import candles_from_closes


def test_defaults_are_the_spec_windows():
    assert TREND_BARS == 365
    assert VOL_BARS == 30
    assert TREND_BAND == 0.25
    assert MIN_RUN_BARS == 7


def test_prefix_is_unlabeled_and_cutoffs_name_the_trend():
    bull = label_candles(candles_from_closes([100, 100, 100, 100, 130]), trend_bars=4, vol_bars=2, min_run_bars=1)
    bear = label_candles(candles_from_closes([100, 100, 100, 100, 70]), trend_bars=4, vol_bars=2, min_run_bars=1)
    inside = label_candles(candles_from_closes([100, 100, 100, 100, 110]), trend_bars=4, vol_bars=2, min_run_bars=1)
    up_edge = label_candles(candles_from_closes([100, 100, 100, 100, 125]), trend_bars=4, vol_bars=2, min_run_bars=1)
    down_edge = label_candles(candles_from_closes([100, 100, 100, 100, 75]), trend_bars=4, vol_bars=2, min_run_bars=1)

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
        min_run_bars=1,
    )
    assert labeled.labels[4] == "bull_quiet"
    assert labeled.labels[5] == "sideways_volatile"
    assert labeled.vol_median == pytest.approx(0.35717248497513854)


def test_equal_volatility_is_quiet():
    closes = [100.0]
    for _ in range(5):
        closes.append(closes[-1] * 1.1)
    labeled = label_candles(candles_from_closes(closes), trend_bars=4, vol_bars=2, min_run_bars=1)
    assert labeled.labels[4] == "bull_quiet"
    assert labeled.labels[5] == "bull_quiet"


def test_no_labeled_row_raises():
    with pytest.raises(ValueError, match="no labeled rows"):
        label_candles(candles_from_closes([100, 101, 102]), trend_bars=4, vol_bars=2, min_run_bars=1)


def test_a_short_run_joins_the_run_before_it():
    closes = [100.0] * 5 + [130.0] * 3 + [100.0] * 5
    raw = label_candles(candles_from_closes(closes), trend_bars=4, vol_bars=2, min_run_bars=1)
    merged = label_candles(candles_from_closes(closes), trend_bars=4, vol_bars=2, min_run_bars=3)
    assert len({name for name in raw.labels if name}) > 1
    runs = _runs(merged.labels)
    assert all(length >= 3 for _name, length in runs)
    assert merged.labels[:4] == (None,) * 4
    assert merged.vol_median == raw.vol_median


def test_a_short_first_run_joins_the_run_after_it():
    labels = label_candles(
        candles_from_closes([100.0] * 4 + [130.0] + [130.0] * 6),
        trend_bars=4,
        vol_bars=2,
        min_run_bars=3,
    ).labels
    assert all(length >= 3 for _name, length in _runs(labels))


def _runs(labels):
    runs = []
    for name in labels:
        if name is None:
            continue
        if runs and runs[-1][0] == name:
            runs[-1][1] += 1
        else:
            runs.append([name, 1])
    return runs
