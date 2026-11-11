"""Benchmarks that a timing rule has to beat to show skill.

- buy-and-hold from the strategy's first bar
- constant exposure: hold the strategy's average exposure every week, rebalanced weekly
- random timing: shuffle the strategy's own in-market and in-cash spell lengths,
  so exposure and trade count match exactly and only the timing differs
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from typing import Callable, Sequence

from price_forecast.data.candles import Candle
from price_forecast.replay.engine import (
    FILL_COST,
    STARTING_DOLLARS,
    FlagSignal,
    Metrics,
    ReplayPath,
    metrics,
    replay,
)


def hodl(
    candles: Sequence[Candle],
    weeks: Sequence[tuple[date, float]],
    first: int,
    *,
    cost: float = FILL_COST,
    slippage: float = 0.0,
    starting_dollars: float = STARTING_DOLLARS,
) -> ReplayPath:
    """Buy at the close of week ``first`` and hold. One entry cost, no exit cost."""
    signal = FlagSignal([True] * len(weeks), first)
    return replay(
        candles,
        weeks,
        signal,
        fill="same_close",
        cost=cost,
        slippage=slippage,
        starting_dollars=starting_dollars,
    )


def constant_exposure(
    candles: Sequence[Candle],
    weeks: Sequence[tuple[date, float]],
    first: int,
    exposure: float,
    *,
    cost: float = FILL_COST,
    slippage: float = 0.0,
    starting_dollars: float = STARTING_DOLLARS,
) -> ReplayPath:
    """Hold ``exposure`` of wealth in BTC, rebalanced on each weekly close."""
    if not 0.0 <= exposure <= 1.0:
        raise ValueError("exposure must be in [0, 1]")
    rate = cost + slippage
    week_set = {day for day, _close in weeks[first:]}
    start_day = weeks[first][0]
    last_week = weeks[-1][0]
    cash = starting_dollars
    btc = 0.0
    costs_paid = 0.0
    days: list[date] = []
    equity: list[float] = []
    week_days: list[date] = []
    week_equity: list[float] = []
    for candle in candles:
        if candle.day < start_day:
            continue
        price = candle.close
        wealth = cash + btc * price
        if candle.day in week_set and candle.day != last_week:
            trade = exposure * wealth - btc * price
            fee = abs(trade) * rate
            btc += trade / price
            cash -= trade + fee
            costs_paid += fee
            wealth = cash + btc * price
        days.append(candle.day)
        equity.append(wealth)
        if candle.day in week_set:
            week_days.append(candle.day)
            week_equity.append(wealth)
    return ReplayPath(
        days=days,
        equity=equity,
        long=[exposure > 0.0] * len(days),
        week_days=week_days,
        week_equity=week_equity,
        week_long=[exposure > 0.0] * len(week_days),
        targets=[],
        fills=[],
        trip_returns=[],
        open_trip_return=None,
        start_dollars=starting_dollars,
        end_dollars=equity[-1],
        costs_paid=costs_paid,
    )


def spells(targets: Sequence[int]) -> list[tuple[int, int]]:
    """Run-length encode a 0/1 sequence as ``(state, length)`` pairs."""
    runs: list[tuple[int, int]] = []
    for value in targets:
        if runs and runs[-1][0] == value:
            runs[-1] = (value, runs[-1][1] + 1)
        else:
            runs.append((value, 1))
    return runs


def shuffled_targets(targets: Sequence[int], rng: random.Random) -> list[int]:
    """Same spells in the same in/out order, with lengths shuffled within each state."""
    runs = spells(targets)
    ins = [length for state, length in runs if state == 1]
    outs = [length for state, length in runs if state == 0]
    rng.shuffle(ins)
    rng.shuffle(outs)
    out: list[int] = []
    for state, _length in runs:
        length = ins.pop() if state == 1 else outs.pop()
        out.extend([state] * length)
    return out


@dataclass(frozen=True)
class RandomTiming:
    runs: int
    total_return_p: float
    sharpe_p: float
    drawdown_p: float
    total_return_median: float
    sharpe_median: float
    drawdown_median: float
    total_return_pct: float
    sharpe_pct: float
    drawdown_pct: float


def _p_at_least(values: Sequence[float], observed: float) -> float:
    return (1 + sum(1 for value in values if value >= observed)) / (1 + len(values))


def _share_below(values: Sequence[float], observed: float) -> float:
    return sum(1 for value in values if value < observed) / len(values)


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def random_timing(
    candles: Sequence[Candle],
    weeks: Sequence[tuple[date, float]],
    strategy: ReplayPath,
    first: int,
    *,
    runs: int = 2000,
    seed: int = 0,
    run_replay: Callable[..., ReplayPath] = replay,
    **replay_kwargs,
) -> RandomTiming:
    """Monte Carlo p-values for the strategy against shuffled timing.

    p is the share of random paths at least as good, with a +1 correction.
    Drawdown is "at least as good" when the random path's drawdown is no deeper.
    """
    observed = metrics(strategy)
    if observed.sharpe is None:
        raise ValueError("strategy Sharpe is undefined")
    rng = random.Random(seed)
    returns: list[float] = []
    sharpes: list[float] = []
    drawdowns: list[float] = []
    for _ in range(runs):
        flags = [False] * len(weeks)
        for offset, state in enumerate(shuffled_targets(strategy.targets, rng)):
            flags[first + offset] = bool(state)
        path = run_replay(candles, weeks, FlagSignal(flags, first), **replay_kwargs)
        result: Metrics = metrics(path)
        returns.append(result.total_return)
        sharpes.append(result.sharpe if result.sharpe is not None else 0.0)
        drawdowns.append(result.max_drawdown)
    return RandomTiming(
        runs=runs,
        total_return_p=_p_at_least(returns, observed.total_return),
        sharpe_p=_p_at_least(sharpes, observed.sharpe),
        drawdown_p=_p_at_least(drawdowns, observed.max_drawdown),
        total_return_median=_median(returns),
        sharpe_median=_median(sharpes),
        drawdown_median=_median(drawdowns),
        total_return_pct=_share_below(returns, observed.total_return),
        sharpe_pct=_share_below(sharpes, observed.sharpe),
        drawdown_pct=_share_below(drawdowns, observed.max_drawdown),
    )
