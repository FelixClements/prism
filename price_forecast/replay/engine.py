"""Daily-marked replay of a weekly long/flat signal under a chosen fill model.

The signal is read on a weekly close. The fill happens at one of:

- ``same_close``: the close that produced the signal (optimistic, SMAGateV1 style)
- ``next_day``: the next daily close after the signal (what a person can trade)
- ``next_week``: the next weekly close (what the CrashGate search scored)

Each fill pays ``cost + slippage`` as a fraction of the traded notional.
Equity is marked on every daily close, so drawdowns include mid-week moves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Protocol, Sequence

from price_forecast.data.candles import Candle

FILL_MODELS = ("same_close", "next_day", "next_week")
STARTING_DOLLARS = 10_000.0
FILL_COST = 0.0015
WEEKS_PER_YEAR = 52.0


class Signal(Protocol):
    first: int

    def decide(self, index: int, position: int) -> str | None: ...


@dataclass(frozen=True)
class ReplayFill:
    day: date
    side: str
    price: float
    cost_paid: float


@dataclass(frozen=True)
class ReplayPath:
    days: list[date]
    equity: list[float]
    long: list[bool]
    week_days: list[date]
    week_equity: list[float]
    week_long: list[bool]
    targets: list[int]
    fills: list[ReplayFill]
    trip_returns: list[float]
    open_trip_return: float | None
    start_dollars: float
    end_dollars: float
    costs_paid: float


class FlagSignal:
    """Hold long whenever ``flags[index]`` is true. Used for benchmarks."""

    def __init__(self, flags: Sequence[bool], first: int) -> None:
        self.flags = list(flags)
        self.first = first

    def decide(self, index: int, position: int) -> str | None:
        want = self.flags[index]
        if position == 0 and want:
            return "buy"
        if position == 1 and not want:
            return "sell"
        return None


def replay(
    candles: Sequence[Candle],
    weeks: Sequence[tuple[date, float]],
    signal: Signal,
    *,
    fill: str = "next_day",
    cost: float = FILL_COST,
    slippage: float = 0.0,
    starting_dollars: float = STARTING_DOLLARS,
) -> ReplayPath:
    if fill not in FILL_MODELS:
        raise ValueError(f"fill must be one of {FILL_MODELS}")
    if cost < 0 or slippage < 0:
        raise ValueError("cost and slippage must be non-negative")
    if starting_dollars <= 0:
        raise ValueError("starting_dollars must be positive")
    first = signal.first
    if first >= len(weeks):
        raise ValueError("signal starts after the last week")
    week_index = {day: index for index, (day, _close) in enumerate(weeks)}
    start_day = weeks[first][0]
    rate = cost + slippage

    position = 0
    cash = starting_dollars
    btc = 0.0
    cash_before: float | None = None
    costs_paid = 0.0
    pending: tuple[date, str] | None = None
    fills: list[ReplayFill] = []
    trips: list[float] = []
    days: list[date] = []
    equity: list[float] = []
    long_flags: list[bool] = []
    week_days: list[date] = []
    week_equity: list[float] = []
    week_long: list[bool] = []
    targets: list[int] = []

    def execute(side: str, day: date, price: float) -> None:
        nonlocal position, cash, btc, cash_before, costs_paid
        if side == "buy" and position == 0:
            fee = cash * rate
            cash_before = cash
            btc = (cash - fee) / price
            cash = 0.0
            position = 1
        elif side == "sell" and position == 1:
            proceeds = btc * price
            fee = proceeds * rate
            cash = proceeds - fee
            btc = 0.0
            position = 0
            assert cash_before is not None
            trips.append(cash / cash_before - 1.0)
            cash_before = None
        else:
            return
        costs_paid += fee
        fills.append(ReplayFill(day, side.upper(), price, fee))

    for k, candle in enumerate(candles):
        day = candle.day
        if day < start_day:
            continue
        price = candle.close
        if pending is not None and pending[0] == day:
            execute(pending[1], day, price)
            pending = None
        index = week_index.get(day)
        if index is not None and index >= first and index + 1 < len(weeks):
            side = signal.decide(index, position)
            if side is not None:
                if fill == "same_close":
                    execute(side, day, price)
                elif fill == "next_day":
                    if k + 1 < len(candles):
                        pending = (candles[k + 1].day, side)
                else:
                    pending = (weeks[index + 1][0], side)
            target = position
            if side == "buy":
                target = 1
            elif side == "sell":
                target = 0
            targets.append(target)
        wealth = btc * price if position == 1 else cash
        days.append(day)
        equity.append(wealth)
        long_flags.append(position == 1)
        if index is not None and index >= first:
            week_days.append(day)
            week_equity.append(wealth)
            week_long.append(position == 1)

    end = equity[-1] if equity else starting_dollars
    open_trip = None
    if position == 1 and cash_before is not None:
        open_trip = end / cash_before - 1.0
    return ReplayPath(
        days=days,
        equity=equity,
        long=long_flags,
        week_days=week_days,
        week_equity=week_equity,
        week_long=week_long,
        targets=targets,
        fills=fills,
        trip_returns=trips,
        open_trip_return=open_trip,
        start_dollars=starting_dollars,
        end_dollars=end,
        costs_paid=costs_paid,
    )


@dataclass(frozen=True)
class Metrics:
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: float | None
    sortino: float | None
    round_trips: int
    win_rate: float | None
    exposure: float
    end_dollars: float
    costs_paid: float


def weekly_returns(path: ReplayPath) -> list[float]:
    values = path.week_equity
    return [values[i] / values[i - 1] - 1.0 for i in range(1, len(values)) if values[i - 1] > 0.0]


def max_drawdown(equity: Sequence[float]) -> float:
    peak = -math.inf
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0.0:
            worst = min(worst, value / peak - 1.0)
    return worst


def sharpe(returns: Sequence[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    if var <= 0.0:
        return None
    return mean / math.sqrt(var) * math.sqrt(WEEKS_PER_YEAR)


def sortino(returns: Sequence[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    downside = sum(min(0.0, value) ** 2 for value in returns) / len(returns)
    if downside <= 0.0:
        return None
    return mean / math.sqrt(downside) * math.sqrt(WEEKS_PER_YEAR)


def metrics(path: ReplayPath) -> Metrics:
    total = path.end_dollars / path.start_dollars - 1.0
    years = (path.days[-1] - path.days[0]).days / 365.25 if len(path.days) > 1 else 0.0
    growth = path.end_dollars / path.start_dollars
    cagr = growth ** (1.0 / years) - 1.0 if years > 0 and growth > 0 else 0.0
    returns = weekly_returns(path)
    trips = path.trip_returns
    wins = sum(1 for value in trips if value > 0.0)
    exposure = sum(path.week_long) / len(path.week_long) if path.week_long else 0.0
    return Metrics(
        total_return=total,
        cagr=cagr,
        max_drawdown=max_drawdown(path.equity),
        sharpe=sharpe(returns),
        sortino=sortino(returns),
        round_trips=len(trips),
        win_rate=(wins / len(trips)) if trips else None,
        exposure=exposure,
        end_dollars=path.end_dollars,
        costs_paid=path.costs_paid,
    )
