from __future__ import annotations

import math

import pytest

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.fit import (
    RealDay,
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
        nxt = order[(pos + 1) % len(order)]
        regimes[name] = RegimeModel(source.regimes[name].chapters, (nxt,))
    runs = tuple((name, 40) for name in order)
    return TapeModel(runs, regimes)


def _one_regime(days: list[RealDay], rows: int = 20) -> tuple[tuple[Candle, ...], TapeModel]:
    """Flat source tape, so the drift shift is the mean of `days`."""
    candles = candles_from_closes([100.0] * rows)
    chapter = tuple(days)
    tape = TapeModel(
        (("bull_quiet", len(chapter)),),
        {"bull_quiet": RegimeModel((chapter,), ("bull_quiet",))},
    )
    return candles, tape


def _returns(path) -> list[float]:
    return [
        math.log(path.candles[index].close / path.candles[index - 1].close)
        for index in range(1, len(path.candles))
    ]


def _day(log_return: float, volume: float = 1.0) -> RealDay:
    return RealDay(log_return, 1.01, 0.99, volume)


def test_invented_day_opens_where_the_previous_day_closed():
    candles, tape = _one_regime([_day(0.01), _day(-0.02), _day(0.03)])
    path = synthetic_paths(candles, tape, n_paths=1, seed=0)[0]
    for index in range(1, len(path.candles)):
        prev = path.candles[index - 1]
        candle = path.candles[index]
        assert candle.open == pytest.approx(prev.close)


def test_a_strong_bull_regime_is_pulled_toward_the_source_climb():
    candles = candles_from_closes([100.0 + index for index in range(20)])
    chapter = (_day(0.05),) * 30
    tape = TapeModel(
        (("bull_quiet", 30),),
        {"bull_quiet": RegimeModel((chapter,), ("bull_quiet",))},
    )
    path = synthetic_paths(candles, tape, n_paths=1, seed=0)[0]
    returns = _returns(path)
    target = math.log(candles[-1].close / candles[0].close) / (len(candles) - 1)
    assert sum(returns) / len(returns) == pytest.approx(target)


def test_a_real_crash_day_stays_one_day():
    crash = math.log(0.5)
    days = [_day(0.0)] * 9 + [_day(crash)]
    candles, tape = _one_regime(days, rows=200)
    path = synthetic_paths(candles, tape, n_paths=1, seed=0)[0]
    shift = sum(day.log_return for day in days) / len(days)
    returns = _returns(path)
    crashes = [ret for ret in returns if ret < -0.5]
    assert crashes
    assert all(ret == pytest.approx(crash - shift) for ret in crashes)
    assert len(path.candles) == len(candles)


def test_a_chapter_copies_consecutive_real_days():
    days = [_day(0.001 * (index + 1)) for index in range(50)]
    candles, tape = _one_regime(days, rows=40)
    path = synthetic_paths(candles, tape, n_paths=1, seed=0)[0]
    shift = sum(day.log_return for day in days) / len(days)
    positions = [round((ret + shift) / 0.001) - 1 for ret in _returns(path)]
    for left, right in zip(positions, positions[1:]):
        assert right == left + 1 or right == 0


def test_wicks_and_volume_travel_with_their_day():
    days = [
        RealDay(0.01, 1.01, 0.995, 10.0),
        RealDay(-0.08, 1.02, 0.90, 500.0),
        RealDay(0.03, 1.04, 0.99, 50.0),
    ]
    candles, tape = _one_regime(days, rows=60)
    path = synthetic_paths(candles, tape, n_paths=1, seed=0)[0]
    by_volume = {day.volume: day for day in days}
    shift = sum(day.log_return for day in days) / len(days)
    for index in range(1, len(path.candles)):
        candle = path.candles[index]
        day = by_volume[candle.volume]
        prev = path.candles[index - 1].close
        assert math.log(candle.close / prev) == pytest.approx(day.log_return - shift)
        assert candle.low == pytest.approx(min(candle.close * day.low_ratio, prev, candle.close))


def test_row_zero_is_the_source_and_a_long_chapter_is_cut_to_the_file():
    candles, tape = _one_regime([_day(0.01)] * 10_000)
    path = synthetic_paths(candles, tape, n_paths=1, seed=0)[0]
    assert path.candles[0] == candles[0]
    assert len(path.candles) == len(candles)
    assert path.regimes == ("bull_quiet",) * len(candles)


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
    returns = _returns(path)
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


def test_non_finite_return_raises():
    candles, tape = _one_regime([_day(0.01), _day(float("nan"))])
    with pytest.raises(ValueError, match="non-finite"):
        synthetic_paths(candles, tape, n_paths=2, seed=0)


def test_n_paths_below_one_raises():
    candles, tape = _one_regime([_day(0.01)])
    with pytest.raises(ValueError, match="n_paths"):
        synthetic_paths(candles, tape, n_paths=0, seed=0)


def test_control_uses_the_other_stream_and_keeps_row_zero():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    control = control_paths(candles, labeling, n_paths=1, seed=0)[0]
    path = synthetic_paths(candles, fit_tape(candles, labeling), n_paths=1, seed=0)[0]
    assert control[0] == candles[0]
    assert len(control) == len(candles)
    assert [row.close for row in control] != [row.close for row in path.candles]
    for index in range(1, len(control)):
        assert control[index].open == pytest.approx(control[index - 1].close)


def _std(values: list[float]) -> float:
    mean = sum(values) / len(values)
    var = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(var)
