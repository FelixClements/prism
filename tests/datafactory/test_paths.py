from __future__ import annotations

import math

import pytest

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.fit import (
    BarShape,
    RegimeModel,
    TapeModel,
    fit_tape,
)
from price_forecast.datafactory.synthetic.label import label_candles
from price_forecast.datafactory.synthetic.paths import control_paths, synthetic_paths
from tests.datafactory.fixture import balanced_tape, candles_from_closes


def _cycle_model(source: TapeModel) -> TapeModel:
    order = (
        "bull_quiet",
        "bear_quiet",
        "bull_volatile",
        "bear_volatile",
        "sideways_quiet",
        "sideways_volatile",
    )
    regimes = {}
    for pos, name in enumerate(order):
        current = source.regimes[name]
        nxt = order[(pos + 1) % len(order)]
        regimes[name] = RegimeModel(
            current.df,
            current.loc,
            current.scale,
            (40,),
            (nxt,),
            current.shapes,
        )
    runs = tuple((name, 40) for name in order)
    return TapeModel(runs, regimes)


def _long_chapter() -> tuple[tuple[Candle, ...], TapeModel]:
    candles = candles_from_closes([100.0 + index for index in range(20)])
    shape = BarShape(0.995, 1.01, 0.99, 1.0)
    model = RegimeModel(8.0, 0.0, 0.01, (10_000,), ("bull_quiet",), (shape,))
    tape = TapeModel((("bull_quiet", 10_000),), {"bull_quiet": model})
    return candles, tape


def test_row_zero_is_the_source_and_a_long_chapter_is_cut_to_the_file():
    candles, tape = _long_chapter()
    path = synthetic_paths(candles, tape, n_paths=1, seed=0)[0]
    assert path.candles[0] == candles[0]
    assert len(path.candles) == len(candles)
    assert path.regimes == ("bull_quiet",) * len(candles)
    assert path.regimes[0] == "bull_quiet"


def test_same_seed_repeats_and_extra_paths_do_not_change_path_zero():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    model = _cycle_model(fit_tape(candles, labeling))
    first = synthetic_paths(candles, model, n_paths=1, seed=0)[0]
    second = synthetic_paths(candles, model, n_paths=2, seed=0)[0]
    assert first.candles == second.candles
    assert first.regimes == second.regimes


def test_bull_chapters_drift_up_more_than_bear_and_volatile_jumps_more():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    model = _cycle_model(fit_tape(candles, labeling))
    path = synthetic_paths(candles, model, n_paths=1, seed=0)[0]
    returns = [
        math.log(path.candles[index].close / path.candles[index - 1].close)
        for index in range(1, len(path.candles))
    ]
    bull = [ret for ret, name in zip(returns, path.regimes[1:]) if name.startswith("bull")]
    bear = [ret for ret, name in zip(returns, path.regimes[1:]) if name.startswith("bear")]
    volatile = [ret for ret, name in zip(returns, path.regimes[1:]) if name.endswith("volatile")]
    quiet = [ret for ret, name in zip(returns, path.regimes[1:]) if name.endswith("quiet")]
    assert sum(bull) / len(bull) > sum(bear) / len(bear)
    assert _std(volatile) > _std(quiet)


def test_every_invented_candle_is_a_valid_bar():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    path = synthetic_paths(candles, fit_tape(candles, labeling), n_paths=1, seed=0)[0]
    for candle in path.candles:
        assert math.isfinite(candle.close) and candle.close > 0
        assert candle.low <= min(candle.open, candle.close)
        assert candle.high >= max(candle.open, candle.close)
        assert candle.volume is not None and candle.volume >= 0


def test_non_finite_return_raises(monkeypatch):
    candles, tape = _long_chapter()
    monkeypatch.setattr(
        "price_forecast.datafactory.synthetic.paths.t.rvs",
        lambda *args, **kwargs: float("nan"),
    )
    with pytest.raises(ValueError, match="non-finite"):
        synthetic_paths(candles, tape, n_paths=2, seed=0)


def test_n_paths_below_one_raises():
    candles, tape = _long_chapter()
    with pytest.raises(ValueError, match="n_paths"):
        synthetic_paths(candles, tape, n_paths=0, seed=0)


def test_control_uses_the_other_stream_and_keeps_row_zero():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    control = control_paths(candles, labeling, n_paths=1, seed=0)[0]
    assert control[0] == candles[0]
    assert len(control) == len(candles)
    assert control[1].close != candles[1].close


def _std(values: list[float]) -> float:
    mean = sum(values) / len(values)
    var = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(var)
