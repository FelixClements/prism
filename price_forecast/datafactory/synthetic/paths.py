"""Draw synthetic candle paths and the one-regime control."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.stats import t

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.fit import BarShape, TapeModel
from price_forecast.datafactory.synthetic.label import LabelResult


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
    while remaining > 0:
        params = model.regimes[regime]
        length = int(params.run_lengths[int(rng.integers(0, len(params.run_lengths)))])
        take = min(length, remaining)
        for _ in range(take):
            shock = float(t.rvs(params.df, loc=params.loc, scale=params.scale, random_state=rng))
            close = rows[-1].close * math.exp(shock) if math.isfinite(shock) else float("nan")
            if not math.isfinite(shock) or not math.isfinite(close) or close <= 0.0:
                raise ValueError(f"non-finite return in {regime}")
            shape = params.shapes[int(rng.integers(0, len(params.shapes)))]
            day = candles[len(rows)].day
            rows.append(_scaled(day, close, shape))
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
    for index in range(1, len(candles)):
        shock = float(t.rvs(df, loc=loc, scale=scale, random_state=rng))
        close = rows[-1].close * math.exp(shock) if math.isfinite(shock) else float("nan")
        if not math.isfinite(shock) or not math.isfinite(close) or close <= 0.0:
            raise ValueError("non-finite return in control")
        shape = shapes[int(rng.integers(0, len(shapes)))]
        rows.append(_scaled(candles[index].day, close, shape))
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


def _scaled(day, close: float, shape: BarShape) -> Candle:
    return Candle(
        day,
        close * shape.low_ratio,
        close * shape.high_ratio,
        close * shape.open_ratio,
        close,
        shape.volume,
    )
