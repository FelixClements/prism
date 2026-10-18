"""Weekly SMA helper. No backtest imports."""

from __future__ import annotations

from typing import Sequence


def sma_at(closes: Sequence[float], index: int, lookback: int) -> float:
    """Mean of closes[index + 1 - lookback : index + 1]. Includes week t, not t+1."""
    if lookback < 1:
        raise ValueError("lookback must be at least 1")
    if index < 0 or index >= len(closes):
        raise ValueError("index is outside the close series")
    if index + 1 < lookback:
        raise ValueError(f"SMA-{lookback} is not defined at index {index}")
    window = closes[index + 1 - lookback : index + 1]
    return sum(window) / lookback

