"""Weekly in/out signals. Bars in; +1 / 0 / None out. No backtest imports."""

from __future__ import annotations

from datetime import date
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


def sma_signal(
    weeks: Sequence[tuple[date, float]],
    *,
    lookback: int,
) -> list[int | None]:
    """In (1) iff this week's close is strictly above the lookback SMA."""
    closes = [close for _week_end, close in weeks]
    signals: list[int | None] = []
    for i, close in enumerate(closes):
        if i + 1 < lookback:
            signals.append(None)
            continue
        sma = sma_at(closes, i, lookback)
        signals.append(1 if close > sma else 0)
    return signals


def dual_sma_signal(
    weeks: Sequence[tuple[date, float]],
    *,
    fast: int = 12,
    slow: int = 26,
) -> list[int | None]:
    """Classic dual MA: in iff SMA(fast) > SMA(slow). Both include this close."""
    if fast >= slow:
        raise ValueError("fast lookback must be shorter than slow")
    closes = [close for _week_end, close in weeks]
    signals: list[int | None] = []
    for i in range(len(closes)):
        if i + 1 < slow:
            signals.append(None)
            continue
        signals.append(1 if sma_at(closes, i, fast) > sma_at(closes, i, slow) else 0)
    return signals


def asymmetric_sma_signal(
    weeks: Sequence[tuple[date, float]],
    *,
    buy_weeks: int,
    sell_weeks: int,
    start_in_btc: bool = True,
) -> list[int | None]:
    """In/out state machine: sell on the long SMA, buy on the short SMA."""
    if sell_weeks <= buy_weeks:
        raise ValueError("sell_weeks must be greater than buy_weeks")
    closes = [close for _week_end, close in weeks]
    position = 1 if start_in_btc else 0
    signals: list[int | None] = []
    for i, close in enumerate(closes):
        if i + 1 < sell_weeks:
            signals.append(None)
            continue
        if position == 1 and close < sma_at(closes, i, sell_weeks):
            position = 0
        elif position == 0 and close > sma_at(closes, i, buy_weeks):
            position = 1
        signals.append(position)
    return signals


def donchian_signal(
    weeks: Sequence[tuple[date, float]],
    *,
    lookback: int = 12,
) -> list[int | None]:
    """In iff close >= max of the prior `lookback` weeks, excluding this week."""
    closes = [close for _week_end, close in weeks]
    signals: list[int | None] = []
    for i, close in enumerate(closes):
        if i < lookback:
            signals.append(None)
            continue
        channel = max(closes[i - lookback : i])
        signals.append(1 if close >= channel else 0)
    return signals
