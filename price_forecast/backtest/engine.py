"""SMAGateV1 same-bar simulator and HODL path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from price_forecast.strategies.signals import sma_at
from price_forecast.strategies.smagate_v1 import (
    BUY_WEEKS,
    FILL_COST,
    SELL_WEEKS,
    STARTING_DOLLARS,
    WHIPSAW_MAX_HOLDING_BARS,
)

@dataclass(frozen=True)
class Fill:
    index: int
    date: date
    side: str
    price: float
    fee: float
    equity_after: float


@dataclass(frozen=True)
class EquityPath:
    dates: list[date]
    closes: list[float]
    equity: list[float]
    long: list[bool]
    fills: list[Fill]
    start_dollars: float
    end_dollars: float
    start_price: float
    end_price: float
    start: date
    end: date
    fees_paid: float
    completed_round_trips: int
    whipsaws: int
    exposure: float
    completed_pnls: list[float]
    pf_pnls: list[float]


def first_comparable_index() -> int:
    return SELL_WEEKS - 1


def _require_sma16(weeks: Sequence[tuple[date, float]]) -> int:
    first = first_comparable_index()
    if len(weeks) <= first:
        raise ValueError("need at least 16 weekly bars so SMA-16 exists")
    return first


def simulate_strategy(
    weeks: Sequence[tuple[date, float]],
    *,
    starting_dollars: float = STARTING_DOLLARS,
    cost: float = FILL_COST,
) -> EquityPath:
    """Same-bar SMA-8/16 state machine. Starts FLAT; fill at the signal close."""
    if starting_dollars <= 0:
        raise ValueError("starting_dollars must be positive")
    if cost < 0:
        raise ValueError("cost must be non-negative")
    first = _require_sma16(weeks)
    closes = [close for _day, close in weeks]
    position = 0
    wealth = starting_dollars
    btc = 0.0
    fees_paid = 0.0
    cash_before_open: float | None = None
    entry_index: int | None = None
    dates: list[date] = []
    marked_closes: list[float] = []
    equity: list[float] = []
    long_flags: list[bool] = []
    fills: list[Fill] = []
    completed_pnls: list[float] = []
    whipsaws = 0

    for i in range(first, len(weeks)):
        day, close = weeks[i]
        sma8 = sma_at(closes, i, BUY_WEEKS)
        sma16 = sma_at(closes, i, SELL_WEEKS)
        if position == 0 and close > sma8:
            fee = wealth * cost
            cash_before_open = wealth
            wealth -= fee
            fees_paid += fee
            btc = wealth / close
            position = 1
            entry_index = i
            fills.append(
                Fill(
                    index=i,
                    date=day,
                    side="BUY",
                    price=close,
                    fee=fee,
                    equity_after=wealth,
                )
            )
        elif position == 1 and close < sma16:
            proceeds = btc * close
            fee = proceeds * cost
            wealth = proceeds - fee
            fees_paid += fee
            btc = 0.0
            position = 0
            assert cash_before_open is not None and entry_index is not None
            completed_pnls.append(wealth - cash_before_open)
            holding = i - entry_index
            if holding <= WHIPSAW_MAX_HOLDING_BARS:
                whipsaws += 1
            cash_before_open = None
            entry_index = None
            fills.append(
                Fill(
                    index=i,
                    date=day,
                    side="SELL",
                    price=close,
                    fee=fee,
                    equity_after=wealth,
                )
            )
        if position == 1:
            wealth = btc * close
        dates.append(day)
        marked_closes.append(close)
        equity.append(wealth)
        long_flags.append(position == 1)

    pf_pnls = list(completed_pnls)
    if position == 1:
        assert cash_before_open is not None
        pf_pnls.append(wealth - cash_before_open)

    n = len(equity)
    return EquityPath(
        dates=dates,
        closes=marked_closes,
        equity=equity,
        long=long_flags,
        fills=fills,
        start_dollars=starting_dollars,
        end_dollars=wealth,
        start_price=weeks[first][1],
        end_price=weeks[-1][1],
        start=weeks[first][0],
        end=weeks[-1][0],
        fees_paid=fees_paid,
        completed_round_trips=len(completed_pnls),
        whipsaws=whipsaws,
        exposure=(sum(1 for flag in long_flags if flag) / n) if n else 0.0,
        completed_pnls=completed_pnls,
        pf_pnls=pf_pnls,
    )


def simulate_hodl(
    weeks: Sequence[tuple[date, float]],
    *,
    starting_dollars: float = STARTING_DOLLARS,
    cost: float = FILL_COST,
) -> EquityPath:
    """Buy on the first SMA-16 bar, hold to the end. One entry fee, no exit fee."""
    if starting_dollars <= 0:
        raise ValueError("starting_dollars must be positive")
    if cost < 0:
        raise ValueError("cost must be non-negative")
    first = _require_sma16(weeks)
    start_day, start_price = weeks[first]
    fee = starting_dollars * cost
    btc = (starting_dollars - fee) / start_price
    dates = [day for day, _close in weeks[first:]]
    closes = [close for _day, close in weeks[first:]]
    equity = [btc * close for close in closes]
    end_dollars = equity[-1]
    fill = Fill(
        index=first,
        date=start_day,
        side="BUY",
        price=start_price,
        fee=fee,
        equity_after=equity[0],
    )
    return EquityPath(
        dates=dates,
        closes=closes,
        equity=equity,
        long=[True] * len(equity),
        fills=[fill],
        start_dollars=starting_dollars,
        end_dollars=end_dollars,
        start_price=start_price,
        end_price=weeks[-1][1],
        start=start_day,
        end=weeks[-1][0],
        fees_paid=fee,
        completed_round_trips=0,
        whipsaws=0,
        exposure=1.0,
        completed_pnls=[],
        pf_pnls=[],
    )

