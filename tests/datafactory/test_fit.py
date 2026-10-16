from __future__ import annotations

import math

import pytest

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.fit import fit_tape
from price_forecast.datafactory.synthetic.label import REGIME_NAMES, LabelResult, label_candles
from tests.datafactory.fixture import balanced_tape, candles_from_closes


def _labeled(shock: float) -> tuple[tuple[Candle, ...], LabelResult]:
    """Two runs of 15 rows for every regime. `shock` is the log-return, or 0 to alternate."""
    labels: list[str | None] = [None]
    plan: list[str] = []
    for _ in range(2):
        for name in REGIME_NAMES:
            plan.extend([name] * 15)
    labels.extend(plan)
    closes = [100.0]
    for index in range(len(plan)):
        step = shock if shock != 0.0 else (0.01 if index % 2 == 0 else 0.02)
        closes.append(closes[-1] * math.exp(step))
    return candles_from_closes(closes), LabelResult(tuple(labels), 0.01)


def test_balanced_tape_fits_all_six_and_keeps_a_single_successor():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    model = fit_tape(candles, labeling)

    assert set(model.regimes) == set(REGIME_NAMES)
    bull = model.regimes["bull_quiet"]
    assert set(bull.successors) == {"bear_quiet"}
    assert sum(len(item.successors) for item in model.regimes.values()) == len(model.runs) - 1
    assert _mean_return(model, "bull_quiet") > 0.05
    assert _mean_return(model, "bear_quiet") < -0.05
    for name, length in model.runs:
        assert length in [len(chapter) for chapter in model.regimes[name].chapters]


def _mean_return(model, name: str) -> float:
    days = [day for chapter in model.regimes[name].chapters for day in chapter]
    return sum(day.log_return for day in days) / len(days)


def test_each_real_day_keeps_its_own_wicks_and_volume():
    candles = list(balanced_tape())
    candles[200] = Candle(candles[200].day, candles[200].close * 0.8, candles[200].close * 1.3,
                          candles[200].open, candles[200].close, 77.0)
    labeling = label_candles(tuple(candles), trend_bars=4, vol_bars=2)
    model = fit_tape(tuple(candles), labeling)
    days = [day for regime in model.regimes.values() for chapter in regime.chapters for day in chapter]
    marked = [day for day in days if day.volume == 77.0]
    assert len(marked) == 1
    assert marked[0].high_ratio == pytest.approx(1.3)
    assert marked[0].low_ratio == pytest.approx(0.8)
    assert marked[0].log_return == pytest.approx(math.log(candles[200].close / candles[199].close))


def test_thin_regime_names_itself():
    candles, labeling = _labeled(0.0)
    labels = list(labeling.labels)
    seen = 0
    for index, name in enumerate(labels):
        if name == "bull_quiet":
            seen += 1
            if seen > 10:
                labels[index] = "bull_volatile"
    with pytest.raises(ValueError, match="bull_quiet"):
        fit_tape(candles, LabelResult(tuple(labels), labeling.vol_median))


def test_blank_volume_names_the_regime():
    candles, labeling = _labeled(0.0)
    broken = list(candles)
    broken[1] = Candle(
        broken[1].day,
        broken[1].low,
        broken[1].high,
        broken[1].open,
        broken[1].close,
        None,
    )
    with pytest.raises(ValueError, match="bull_quiet"):
        fit_tape(tuple(broken), labeling)


def test_zero_volatility_names_the_regime():
    candles, labeling = _labeled(0.01)
    with pytest.raises(ValueError, match="bull_quiet"):
        fit_tape(candles, labeling)
