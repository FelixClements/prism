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
    assert set(bull.successors) == {"sideways_quiet"}
    assert sum(len(item.successors) for item in model.regimes.values()) == len(model.runs) - 1
    assert model.regimes["bull_quiet"].loc > 0.05
    assert model.regimes["bear_quiet"].loc < -0.05


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


def test_student_t_df_at_or_below_two_names_the_regime(monkeypatch):
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)

    def _flat_df(_returns):
        return (2.0, 0.0, 0.01)

    monkeypatch.setattr("price_forecast.datafactory.synthetic.fit.t.fit", _flat_df)
    with pytest.raises(ValueError, match="bull_quiet"):
        fit_tape(candles, labeling)
