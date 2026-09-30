"""Candles whose six regimes each have at least 30 rows and 2 runs."""

from __future__ import annotations

import math
from datetime import date, timedelta

from price_forecast.data.candles import Candle

BLOCK_ORDER = (
    "bull_quiet",
    "bear_quiet",
    "bull_volatile",
    "bear_volatile",
    "sideways_quiet",
    "sideways_volatile",
)
QUIET_SHOCKS = (0.002, -0.001, -0.002, 0.001)
LOUD_SHOCKS = (0.12, -0.06, -0.12, 0.06)
MU = {"bull": 0.08, "bear": -0.09, "sideways": 0.0}


def candles_from_closes(closes: list[float], *, volume: float | None = 1.0) -> tuple[Candle, ...]:
    start = date(2020, 1, 1)
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            Candle(
                start + timedelta(days=index),
                close * 0.99,
                close * 1.01,
                close * 0.995,
                close,
                volume,
            )
        )
    return tuple(rows)


def balanced_tape() -> tuple[Candle, ...]:
    """40-row blocks, each regime twice, after a 4-row prefix."""
    prices = [100.0]
    for index in range(4):
        shock = 0.001 if index % 2 == 0 else -0.001
        prices.append(prices[-1] * math.exp(shock))
    for name in BLOCK_ORDER + BLOCK_ORDER:
        trend, noise = name.split("_")
        shocks = QUIET_SHOCKS if noise == "quiet" else LOUD_SHOCKS
        mu = MU[trend]
        for index in range(40):
            prices.append(prices[-1] * math.exp(mu + shocks[index % 4]))
    return candles_from_closes(prices)
