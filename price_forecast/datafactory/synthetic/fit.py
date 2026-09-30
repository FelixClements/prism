"""Measure Student-t moves, run lengths, successors, and bar shapes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.stats import t

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.label import REGIME_NAMES, LabelResult

MIN_ROWS = 30
MIN_RUNS = 2


@dataclass(frozen=True)
class BarShape:
    open_ratio: float
    high_ratio: float
    low_ratio: float
    volume: float


@dataclass(frozen=True)
class RegimeModel:
    df: float
    loc: float
    scale: float
    run_lengths: tuple[int, ...]
    successors: tuple[str, ...]
    shapes: tuple[BarShape, ...]


@dataclass(frozen=True)
class TapeModel:
    runs: tuple[tuple[str, int], ...]
    regimes: dict[str, RegimeModel]


def fit_tape(candles: Sequence[Candle], labeling: LabelResult) -> TapeModel:
    if len(labeling.labels) != len(candles):
        raise ValueError("labels must align with candles")
    groups = {name: [] for name in REGIME_NAMES}
    runs: list[tuple[str, int]] = []
    for index, name in enumerate(labeling.labels):
        if name is None:
            continue
        if name not in groups:
            raise ValueError(f"unknown regime {name}")
        groups[name].append(index)
        if not runs or runs[-1][0] != name:
            runs.append((name, 1))
        else:
            runs[-1] = (name, runs[-1][1] + 1)
    run_lengths = {name: [] for name in REGIME_NAMES}
    successors = {name: [] for name in REGIME_NAMES}
    for pos, (name, length) in enumerate(runs):
        run_lengths[name].append(length)
        if pos + 1 < len(runs):
            successors[name].append(runs[pos + 1][0])
    regimes: dict[str, RegimeModel] = {}
    for name in REGIME_NAMES:
        indexes = groups[name]
        lengths = run_lengths[name]
        if len(indexes) < MIN_ROWS or len(lengths) < MIN_RUNS:
            raise ValueError(
                f"{name} has {len(indexes)} labeled rows and {len(lengths)} runs"
            )
        for index in indexes:
            if candles[index].volume is None:
                raise ValueError(f"{name} has a blank volume")
        returns = np.array(
            [
                math.log(candles[index].close / candles[index - 1].close)
                for index in indexes
            ],
            dtype=float,
        )
        if returns.size < 2 or float(np.std(returns, ddof=1)) == 0.0:
            raise ValueError(f"{name} has zero volatility")
        df, loc, scale = t.fit(returns)
        df = float(df)
        loc = float(loc)
        scale = float(scale)
        if df <= 2.0 or not math.isfinite(df) or not math.isfinite(loc) or not math.isfinite(scale):
            raise ValueError(f"{name} student-t df={df}")
        shapes = tuple(
            BarShape(
                candles[index].open / candles[index].close,
                candles[index].high / candles[index].close,
                candles[index].low / candles[index].close,
                float(candles[index].volume),
            )
            for index in indexes
        )
        regimes[name] = RegimeModel(df, loc, scale, tuple(lengths), tuple(successors[name]), shapes)
    return TapeModel(tuple(runs), regimes)
