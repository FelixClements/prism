"""Draw synthetic candle paths and the one-regime control."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Sequence

import numpy as np
from scipy.stats import t

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.fit import BarShape, TapeModel
from price_forecast.datafactory.synthetic.label import LabelResult

MAX_DAILY_MOVE = 0.20


@dataclass(frozen=True)
class PathResult:
    candles: tuple[Candle, ...]
    regimes: tuple[str, ...]


def synthetic_paths(
    candles: Sequence[Candle],
    model: TapeModel,
    *,
    n_paths: int,
    seed: int,
) -> tuple[PathResult, ...]:
    if n_paths < 1:
        raise ValueError("n_paths must be at least 1")
    return tuple(
        _regime_path(candles, model, _rng(seed, index, 0)) for index in range(n_paths)
    )


def control_paths(
    candles: Sequence[Candle],
    labeling: LabelResult,
    *,
    n_paths: int,
    seed: int,
) -> tuple[tuple[Candle, ...], ...]:
    if n_paths < 1:
        raise ValueError("n_paths must be at least 1")
    pooled = _pooled(candles, labeling)
    return tuple(
        _flat_path(candles, pooled, _rng(seed, index, 1)) for index in range(n_paths)
    )


def _rng(seed: int, path_index: int, stream: int) -> np.random.Generator:
    sequence = np.random.SeedSequence([seed, path_index, stream])
    return np.random.Generator(np.random.PCG64(sequence))


def _regime_path(
    candles: Sequence[Candle],
    model: TapeModel,
    rng: np.random.Generator,
) -> PathResult:
    start = int(rng.integers(0, len(model.runs)))
    regime = model.runs[start][0]
    rows = [candles[0]]
    regimes = [regime]
    remaining = len(candles) - 1
    shift = _drift_shift(candles, model)
    while remaining > 0:
        params = model.regimes[regime]
        length = int(params.run_lengths[int(rng.integers(0, len(params.run_lengths)))])
        take = min(length, remaining)
        for _ in range(take):
            shock = float(
                t.rvs(
                    params.df,
                    loc=params.loc - shift,
                    scale=params.scale,
                    random_state=rng,
                )
            )
            if not math.isfinite(shock):
                raise ValueError(f"non-finite return in {regime}")
            for piece in _split_log_return(shock):
                close = rows[-1].close * math.exp(piece)
                if not math.isfinite(close) or close <= 0.0:
                    raise ValueError(f"non-finite return in {regime}")
                shape = params.shapes[int(rng.integers(0, len(params.shapes)))]
                day = rows[-1].day + timedelta(days=1)
                open_price = rows[-1].close
                rows.append(_scaled(day, close, shape, open_price))
                regimes.append(regime)
        remaining -= take
        if remaining > 0:
            regime = params.successors[int(rng.integers(0, len(params.successors)))]
    return PathResult(tuple(rows), tuple(regimes))


def _flat_path(
    candles: Sequence[Candle],
    pooled: tuple[float, float, float, tuple[BarShape, ...]],
    rng: np.random.Generator,
) -> tuple[Candle, ...]:
    df, loc, scale, shapes = pooled
    rows = [candles[0]]
    anchored = loc - _source_daily_drift(candles)
    for _ in range(1, len(candles)):
        shock = float(t.rvs(df, loc=loc - anchored, scale=scale, random_state=rng))
        if not math.isfinite(shock):
            raise ValueError("non-finite return in control")
        for piece in _split_log_return(shock):
            close = rows[-1].close * math.exp(piece)
            if not math.isfinite(close) or close <= 0.0:
                raise ValueError("non-finite return in control")
            shape = shapes[int(rng.integers(0, len(shapes)))]
            day = rows[-1].day + timedelta(days=1)
            open_price = rows[-1].close
            rows.append(_scaled(day, close, shape, open_price))
    return tuple(rows)


def _pooled(
    candles: Sequence[Candle],
    labeling: LabelResult,
) -> tuple[float, float, float, tuple[BarShape, ...]]:
    indexes = [index for index, name in enumerate(labeling.labels) if name is not None]
    if len(indexes) < 30:
        raise ValueError("pooled regime has fewer than 30 labeled rows")
    returns = [
        math.log(candles[index].close / candles[index - 1].close) for index in indexes
    ]
    vol = float(np.std(returns, ddof=1))
    if vol == 0.0:
        raise ValueError("pooled regime has zero volatility")
    for index in indexes:
        if candles[index].volume is None:
            raise ValueError("pooled regime has a blank volume")
    df, loc, scale = t.fit(returns)
    df, loc, scale = float(df), float(loc), float(scale)
    if df <= 2.0 or not all(math.isfinite(value) for value in (df, loc, scale)):
        raise ValueError(f"pooled student-t df={df}")
    shapes = tuple(
        BarShape(
            candles[index].open / candles[index].close,
            candles[index].high / candles[index].close,
            candles[index].low / candles[index].close,
            float(candles[index].volume),
        )
        for index in indexes
    )
    return df, loc, scale, shapes


def _source_daily_drift(candles: Sequence[Candle]) -> float:
    steps = len(candles) - 1
    return math.log(candles[-1].close / candles[0].close) / steps


def _drift_shift(candles: Sequence[Candle], model: TapeModel) -> float:
    total = 0
    weighted = 0.0
    for params in model.regimes.values():
        weight = sum(params.run_lengths)
        total += weight
        weighted += params.loc * weight
    return weighted / total - _source_daily_drift(candles)


def _split_log_return(log_return: float) -> tuple[float, ...]:
    n = 1
    while abs(math.exp(log_return / n) - 1.0) > MAX_DAILY_MOVE + 1e-12:
        n += 1
    piece = log_return / n
    return (piece,) * n


def _scaled(day, close: float, shape: BarShape, open_price: float) -> Candle:
    high = max(close * shape.high_ratio, open_price, close)
    low = min(close * shape.low_ratio, open_price, close)
    return Candle(day, low, high, open_price, close, shape.volume)
