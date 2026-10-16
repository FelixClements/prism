"""Draw synthetic candle paths and the one-regime control.

A chapter copies consecutive real days of its regime, starting anywhere in a
random real run of that regime. Each day keeps its own return, wicks, and
volume, so crash days, wick size, and volume stay tied to the move.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Sequence

import numpy as np

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.fit import FLAT_VOL, RealDay, TapeModel, real_day
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
    shift = _drift_shift(
        candles,
        [day for params in model.regimes.values() for chapter in params.chapters for day in chapter],
    )
    while len(rows) < len(candles):
        params = model.regimes[regime]
        length = len(params.chapters[int(rng.integers(0, len(params.chapters)))])
        take = min(length, len(candles) - len(rows))
        chapter = params.chapters[int(rng.integers(0, len(params.chapters)))]
        offset = int(rng.integers(0, len(chapter)))
        for _ in range(take):
            if offset == len(chapter):
                chapter = params.chapters[int(rng.integers(0, len(params.chapters)))]
                offset = 0
            rows.append(_next_row(rows[-1], chapter[offset], shift, regime))
            regimes.append(regime)
            offset += 1
        if len(rows) < len(candles):
            regime = params.successors[int(rng.integers(0, len(params.successors)))]
    return PathResult(tuple(rows), tuple(regimes))


def _flat_path(
    candles: Sequence[Candle],
    pooled: tuple[RealDay, ...],
    rng: np.random.Generator,
) -> tuple[Candle, ...]:
    rows = [candles[0]]
    shift = _drift_shift(candles, pooled)
    while len(rows) < len(candles):
        day = pooled[int(rng.integers(0, len(pooled)))]
        rows.append(_next_row(rows[-1], day, shift, "control"))
    return tuple(rows)


def _pooled(candles: Sequence[Candle], labeling: LabelResult) -> tuple[RealDay, ...]:
    if len(labeling.labels) != len(candles):
        raise ValueError("labels must align with candles")
    indexes = [index for index, name in enumerate(labeling.labels) if name is not None]
    if len(indexes) < 30:
        raise ValueError("pooled regime has fewer than 30 labeled rows")
    try:
        days = tuple(real_day(candles, index) for index in indexes)
    except ValueError as exc:
        raise ValueError(f"pooled regime: {exc}") from exc
    if float(np.std([day.log_return for day in days], ddof=1)) < FLAT_VOL:
        raise ValueError("pooled regime has zero volatility")
    return days


def _source_daily_drift(candles: Sequence[Candle]) -> float:
    steps = len(candles) - 1
    return math.log(candles[-1].close / candles[0].close) / steps


def _drift_shift(candles: Sequence[Candle], days: Sequence[RealDay]) -> float:
    """Labeled days skip the unlabeled prefix; pull their mean back to the source climb."""
    mean = sum(day.log_return for day in days) / len(days)
    return mean - _source_daily_drift(candles)


def _next_row(previous: Candle, day: RealDay, shift: float, regime: str) -> Candle:
    close = previous.close * math.exp(day.log_return - shift)
    if not math.isfinite(close) or close <= 0.0:
        raise ValueError(f"non-finite return in {regime}")
    open_price = previous.close
    return Candle(
        previous.day + timedelta(days=1),
        min(close * day.low_ratio, open_price, close),
        max(close * day.high_ratio, open_price, close),
        open_price,
        close,
        day.volume,
    )
