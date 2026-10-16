"""Label each candle row as one of the six trend-by-volatility regimes.

A run shorter than MIN_RUN_BARS joins the run before it, so a regime is a
chapter, not a day of chatter around the volatility median.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from price_forecast.data.candles import Candle

TREND_BARS = 365
VOL_BARS = 30
TREND_BAND = 0.25
MIN_RUN_BARS = 7
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
    min_run_bars: int = MIN_RUN_BARS,
) -> LabelResult:
    if trend_bars < 1:
        raise ValueError("trend_bars must be at least 1")
    if vol_bars < 2:
        raise ValueError("vol_bars must be at least 2")
    if trend_band < 0:
        raise ValueError("trend_band must be non-negative")
    if min_run_bars < 1:
        raise ValueError("min_run_bars must be at least 1")
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
    return LabelResult(_merge_short_runs(labels, min_run_bars), median)


def _merge_short_runs(labels: list[str | None], min_run_bars: int) -> tuple[str | None, ...]:
    spans: list[list] = []
    for index, name in enumerate(labels):
        if name is None:
            continue
        if spans and spans[-1][0] == name:
            spans[-1][2] = index + 1
        else:
            spans.append([name, index, index + 1])
    kept: list[list] = []
    for span in spans:
        if kept and (span[2] - span[1] < min_run_bars or kept[-1][0] == span[0]):
            kept[-1][2] = span[2]
        else:
            kept.append(span)
    if len(kept) > 1 and kept[0][2] - kept[0][1] < min_run_bars:
        kept[1][1] = kept[0][1]
        kept.pop(0)
    merged: list[str | None] = [None] * len(labels)
    for name, start, end in kept:
        merged[start:end] = [name] * (end - start)
    return tuple(merged)
