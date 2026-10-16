"""Group each regime's real days by run, and count run successors."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.label import REGIME_NAMES, LabelResult

MIN_ROWS = 30
MIN_RUNS = 2
FLAT_VOL = 1e-12


@dataclass(frozen=True)
class RealDay:
    log_return: float
    high_ratio: float
    low_ratio: float
    volume: float


@dataclass(frozen=True)
class RegimeModel:
    chapters: tuple[tuple[RealDay, ...], ...]
    successors: tuple[str, ...]


@dataclass(frozen=True)
class TapeModel:
    runs: tuple[tuple[str, int], ...]
    regimes: dict[str, RegimeModel]


def real_day(candles: Sequence[Candle], index: int) -> RealDay:
    """Return, wicks, and volume of one source row, kept together."""
    candle = candles[index]
    if candle.volume is None:
        raise ValueError(f"row {index} has a blank volume")
    return RealDay(
        math.log(candle.close / candles[index - 1].close),
        candle.high / candle.close,
        candle.low / candle.close,
        float(candle.volume),
    )


def fit_tape(candles: Sequence[Candle], labeling: LabelResult) -> TapeModel:
    if len(labeling.labels) != len(candles):
        raise ValueError("labels must align with candles")
    spans: list[tuple[str, list[int]]] = []
    for index, name in enumerate(labeling.labels):
        if name is None:
            continue
        if name not in REGIME_NAMES:
            raise ValueError(f"unknown regime {name}")
        if not spans or spans[-1][0] != name:
            spans.append((name, [index]))
        else:
            spans[-1][1].append(index)
    chapters = {name: [] for name in REGIME_NAMES}
    successors = {name: [] for name in REGIME_NAMES}
    for pos, (name, indexes) in enumerate(spans):
        chapters[name].append(indexes)
        if pos + 1 < len(spans):
            successors[name].append(spans[pos + 1][0])
    regimes: dict[str, RegimeModel] = {}
    for name in REGIME_NAMES:
        runs = chapters[name]
        rows = sum(len(indexes) for indexes in runs)
        if rows < MIN_ROWS or len(runs) < MIN_RUNS:
            raise ValueError(f"{name} has {rows} labeled rows and {len(runs)} runs")
        try:
            days = tuple(tuple(real_day(candles, index) for index in indexes) for indexes in runs)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from exc
        returns = [day.log_return for chapter in days for day in chapter]
        if float(np.std(returns, ddof=1)) < FLAT_VOL:
            raise ValueError(f"{name} has zero volatility")
        regimes[name] = RegimeModel(days, tuple(successors[name]))
    return TapeModel(tuple((name, len(indexes)) for name, indexes in spans), regimes)
