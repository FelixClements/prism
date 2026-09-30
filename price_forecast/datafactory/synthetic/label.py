"""Label each candle row as one of the six trend-by-volatility regimes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from price_forecast.data.candles import Candle

TREND_BARS = 365
VOL_BARS = 30
TREND_BAND = 0.25
REGIME_NAMES = (
    "bull_quiet",
    "bull_volatile",
    "bear_quiet",
    "bear_volatile",
    "sideways_quiet",
    "sideways_volatile",
)


@dataclass(frozen=True)
class LabelResult:
    labels: tuple[str | None, ...]
    vol_median: float


def label_candles(
    candles: Sequence[Candle],
    *,
    trend_bars: int = TREND_BARS,
    vol_bars: int = VOL_BARS,
    trend_band: float = TREND_BAND,
) -> LabelResult:
    if trend_bars < 1:
        raise ValueError("trend_bars must be at least 1")
    if vol_bars < 2:
        raise ValueError("vol_bars must be at least 2")
    if trend_band < 0:
        raise ValueError("trend_band must be non-negative")
    closes = [candle.close for candle in candles]
    first = max(trend_bars, vol_bars)
    vols: list[float] = []
    pending: list[tuple[int, str, float]] = []
    for index in range(first, len(closes)):
        simple = closes[index] / closes[index - trend_bars] - 1.0
        if simple > trend_band:
            trend = "bull"
        elif simple < -trend_band:
            trend = "bear"
        else:
            trend = "sideways"
        window = [
            math.log(closes[pos] / closes[pos - 1])
            for pos in range(index - vol_bars + 1, index + 1)
        ]
        vol = float(np.std(window, ddof=1))
        pending.append((index, trend, vol))
        vols.append(vol)
    if not pending:
        raise ValueError("no labeled rows")
    median = float(np.median(vols))
    labels: list[str | None] = [None] * len(closes)
    for index, trend, vol in pending:
        noise = "quiet" if vol <= median else "volatile"
        labels[index] = f"{trend}_{noise}"
    return LabelResult(tuple(labels), median)
