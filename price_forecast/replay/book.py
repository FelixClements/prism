"""Daily-marked replay of a fractional BTC exposure (0..1), and books built from several sleeves.

A *decision* is ``(day, target)``: at the close of ``day`` the rule wants ``target`` of
its wealth in BTC. The fill happens at one of:

- ``same_close``: the close that produced the decision (optimistic, not tradable)
- ``next_day``: the next daily close (what a person can trade)

Each rebalance pays ``cost + slippage`` on the traded notional. A buy spends cash
including its fee, so a target of 1 never borrows. For 0/1 targets the result is
identical to :func:`price_forecast.replay.engine.replay`.

A *book* is the sum of sleeves that each start with a share of the capital and are
never rebalanced against each other (for example one sleeve per weekday anchor).
Equity is marked on every daily close; weekly returns use the Sunday closes.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date
from typing import Callable, Sequence

import numpy as np

from price_forecast.data.candles import Candle
from price_forecast.replay.benchmarks import shuffled_targets
from price_forecast.replay.engine import FILL_COST, STARTING_DOLLARS, max_drawdown, sharpe, sortino

BOOK_FILLS = ("same_close", "next_day")
MARK_WEEKDAY = 6  # Sunday
_EPS = 1e-9

Decisions = Sequence[tuple[date, float]]


@dataclass(frozen=True)
class Book:
    days: list[date]
    equity: list[float]
    exposure: list[float]  # BTC value / wealth at each daily close, after any fill
    traded: list[float]  # absolute traded notional on each day
    trades: int
    costs_paid: float
    start_dollars: float

    @property
    def end_dollars(self) -> float:
        return self.equity[-1] if self.equity else self.start_dollars


def replay_targets(
    candles: Sequence[Candle],
    decisions: Decisions,
    *,
    start_day: date | None = None,
    fill: str = "next_day",
    cost: float = FILL_COST,
    slippage: float = 0.0,
    starting_dollars: float = STARTING_DOLLARS,
) -> Book:
    """Replay a list of exposure decisions. Before the first fill the book sits in cash."""
    if fill not in BOOK_FILLS:
        raise ValueError(f"fill must be one of {BOOK_FILLS}")
    if cost < 0 or slippage < 0:
        raise ValueError("cost and slippage must be non-negative")
    if starting_dollars <= 0:
        raise ValueError("starting_dollars must be positive")
    if not decisions:
        raise ValueError("need at least one decision")
    targets: dict[date, float] = {}
    for day, target in decisions:
        if not 0.0 <= target <= 1.0:
            raise ValueError(f"target {target} on {day} is outside [0, 1]")
        targets[day] = float(target)
    start = start_day if start_day is not None else decisions[0][0]
    rate = cost + slippage

    cash = starting_dollars
    btc = 0.0
    costs_paid = 0.0
    trades = 0
    pending: tuple[date, float] | None = None
    days: list[date] = []
    equity: list[float] = []
    exposure: list[float] = []
    traded: list[float] = []

    def rebalance(target: float, price: float) -> float:
        nonlocal cash, btc, costs_paid, trades
        wealth = cash + btc * price
        held = btc * price
        want = target * wealth
        if want > held + _EPS * wealth:
            spend = min(cash, (want - held) / (1.0 - rate))
            if spend <= 0.0:
                return 0.0
            fee = spend * rate
            btc += (spend - fee) / price
            cash -= spend
            notional = spend
        elif want < held - _EPS * wealth:
            notional = held - want
            fee = notional * rate
            btc = 0.0 if target == 0.0 else btc - notional / price
            cash += notional - fee
        else:
            return 0.0
        costs_paid += fee
        trades += 1
        return notional

    for k, candle in enumerate(candles):
        day = candle.day
        if day < start:
            continue
        price = candle.close
        notional = 0.0
        if pending is not None and pending[0] == day:
            notional += rebalance(pending[1], price)
            pending = None
        target = targets.get(day)
        if target is not None:
            if fill == "same_close":
                notional += rebalance(target, price)
            elif k + 1 < len(candles):
                pending = (candles[k + 1].day, target)
        wealth = cash + btc * price
        days.append(day)
        equity.append(wealth)
        exposure.append(btc * price / wealth if wealth > 0.0 else 0.0)
        traded.append(notional)
    if not days:
        raise ValueError("start_day is after the last candle")
    return Book(days, equity, exposure, traded, trades, costs_paid, starting_dollars)


def combine(books: Sequence[Book]) -> Book:
    """Sum sleeves that were marked on the same days."""
    if not books:
        raise ValueError("need at least one sleeve")
    days = books[0].days
    for book in books[1:]:
        if book.days != days:
            raise ValueError("sleeves must share the same daily marks")
    equity = [sum(values) for values in zip(*(book.equity for book in books))]
    held = [sum(e * x for e, x in pairs) for pairs in zip(*(zip(b.equity, b.exposure) for b in books))]
    return Book(
        days=list(days),
        equity=equity,
        exposure=[h / e if e > 0.0 else 0.0 for h, e in zip(held, equity)],
        traded=[sum(values) for values in zip(*(book.traded for book in books))],
        trades=sum(book.trades for book in books),
        costs_paid=sum(book.costs_paid for book in books),
        start_dollars=sum(book.start_dollars for book in books),
    )


def run_sleeves(
    candles: Sequence[Candle],
    sleeves: Sequence[Decisions],
    *,
    start_day: date,
    starting_dollars: float = STARTING_DOLLARS,
    **kwargs,
) -> Book:
    """Split the capital equally across ``sleeves`` and sum them."""
    share = starting_dollars / len(sleeves)
    return combine(
        [replay_targets(candles, item, start_day=start_day, starting_dollars=share, **kwargs) for item in sleeves]
    )


def slice_book(book: Book, start_day: date) -> Book:
    """The same book seen from ``start_day`` on, rebased to its equity on that day."""
    index = next((i for i, day in enumerate(book.days) if day >= start_day), None)
    if index is None:
        raise ValueError("start_day is after the last mark")
    return Book(
        days=book.days[index:],
        equity=book.equity[index:],
        exposure=book.exposure[index:],
        traded=[0.0] + book.traded[index + 1 :],
        trades=sum(1 for value in book.traded[index + 1 :] if value > 0.0),
        costs_paid=float("nan"),
        start_dollars=book.equity[index],
    )


def week_marks(book: Book, weekday: int = MARK_WEEKDAY) -> list[float]:
    return [value for day, value in zip(book.days, book.equity) if day.weekday() == weekday]


def book_weekly_returns(book: Book, weekday: int = MARK_WEEKDAY) -> list[float]:
    marks = week_marks(book, weekday)
    return [marks[i] / marks[i - 1] - 1.0 for i in range(1, len(marks)) if marks[i - 1] > 0.0]


@dataclass(frozen=True)
class BookMetrics:
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: float | None
    sortino: float | None
    exposure: float
    turnover: float  # traded notional / wealth, per year
    trades: int
    end_dollars: float
    costs_paid: float


def book_metrics(book: Book) -> BookMetrics:
    growth = book.end_dollars / book.start_dollars
    years = (book.days[-1] - book.days[0]).days / 365.25 if len(book.days) > 1 else 0.0
    returns = book_weekly_returns(book)
    turnover = sum(t / e for t, e in zip(book.traded, book.equity) if e > 0.0)
    return BookMetrics(
        total_return=growth - 1.0,
        cagr=growth ** (1.0 / years) - 1.0 if years > 0 and growth > 0 else 0.0,
        max_drawdown=max_drawdown(book.equity),
        sharpe=sharpe(returns),
        sortino=sortino(returns),
        exposure=sum(book.exposure) / len(book.exposure),
        turnover=turnover / years if years > 0 else 0.0,
        trades=book.trades,
        end_dollars=book.end_dollars,
        costs_paid=book.costs_paid,
    )


# --- benchmarks -----------------------------------------------------------------


def hold_decisions(start_day: date) -> list[tuple[date, float]]:
    return [(start_day, 1.0)]


def constant_decisions(days: Sequence[date], start_day: date, exposure: float) -> list[tuple[date, float]]:
    """Rebalance to ``exposure`` at the start and on every Sunday close after it (except the last)."""
    sundays = [day for day in days if day.weekday() == MARK_WEEKDAY and day > start_day]
    return [(start_day, exposure)] + [(day, exposure) for day in sundays[:-1]]


# --- random timing --------------------------------------------------------------


@dataclass(frozen=True)
class TimingTest:
    name: str
    runs: int
    sharpe_p: float
    total_return_p: float
    drawdown_p: float
    sharpe_median: float
    total_return_median: float
    drawdown_median: float


def _p_at_least(values: Sequence[float], observed: float) -> float:
    return (1 + sum(1 for value in values if value >= observed)) / (1 + len(values))


def _timing_test(name: str, observed: BookMetrics, books: Sequence[Book]) -> TimingTest:
    results = [book_metrics(book) for book in books]
    sharpes = [item.sharpe if item.sharpe is not None else 0.0 for item in results]
    totals = [item.total_return for item in results]
    drawdowns = [item.max_drawdown for item in results]
    return TimingTest(
        name=name,
        runs=len(results),
        sharpe_p=_p_at_least(sharpes, observed.sharpe or 0.0),
        total_return_p=_p_at_least(totals, observed.total_return),
        drawdown_p=_p_at_least(drawdowns, observed.max_drawdown),
        sharpe_median=float(np.median(sharpes)),
        total_return_median=float(np.median(totals)),
        drawdown_median=float(np.median(drawdowns)),
    )


def circular_shift_test(
    candles: Sequence[Candle],
    sleeves: Sequence[Decisions],
    observed: BookMetrics,
    *,
    min_shift: int = 26,
    run: Callable[[Sequence[Decisions]], Book],
) -> TimingTest:
    """Rotate every sleeve's target series by the same number of decisions.

    Exposure level, turnover and the target series' own autocorrelation are kept;
    only the alignment with prices changes. Every shift of at least ``min_shift``
    decisions (in both directions) is one path.
    """
    length = min(len(item) for item in sleeves)
    if length <= 2 * min_shift:
        raise ValueError("series too short for the shift test")
    books = []
    for shift in range(min_shift, length - min_shift + 1):
        moved = []
        for item in sleeves:
            values = [target for _day, target in item]
            rolled = values[-shift:] + values[:-shift]
            moved.append([(day, value) for (day, _old), value in zip(item, rolled)])
        books.append(run(moved))
    return _timing_test(f"circular shift ({len(books)} shifts of {min_shift}+ weeks)", observed, books)


def spell_shuffle_test(
    sleeves: Sequence[Decisions],
    observed: BookMetrics,
    *,
    runs: int,
    seed: int,
    run: Callable[[Sequence[Decisions]], Book],
) -> TimingTest:
    """Shuffle each 0/1 sleeve's in-market and in-cash spell lengths independently."""
    for item in sleeves:
        if any(target not in (0.0, 1.0) for _day, target in item):
            raise ValueError("spell shuffle needs 0/1 targets")
    rng = random.Random(seed)
    books = []
    for _ in range(runs):
        moved = []
        for item in sleeves:
            values = shuffled_targets([int(target) for _day, target in item], rng)
            moved.append([(day, float(value)) for (day, _old), value in zip(item, values)])
        books.append(run(moved))
    return _timing_test(f"spell shuffle ({runs:,} paths)", observed, books)


# --- head to head ---------------------------------------------------------------


@dataclass(frozen=True)
class SharpeDiff:
    weeks: int
    sharpe_a: float
    sharpe_b: float
    diff: float
    low: float
    high: float
    p_not_better: float


def _ann_sharpe(values: np.ndarray) -> np.ndarray:
    sd = values.std(axis=-1, ddof=1)
    return np.where(sd > 0, values.mean(axis=-1) / np.where(sd > 0, sd, 1.0), 0.0) * math.sqrt(52.0)


def sharpe_diff(
    a: Sequence[float],
    b: Sequence[float],
    *,
    block: int = 13,
    runs: int = 5000,
    seed: int = 0,
) -> SharpeDiff:
    """Paired circular block bootstrap of the annualised Sharpe difference ``a - b``.

    ``p_not_better`` is the share of resamples where ``a`` does not beat ``b``.
    The interval is the central 90%.
    """
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if x.shape != y.shape or x.size < 2 * block:
        raise ValueError("need two aligned return series longer than two blocks")
    n = x.size
    rng = np.random.default_rng(seed)
    count = -(-n // block)
    starts = rng.integers(0, n, size=(runs, count))
    index = ((starts[:, :, None] + np.arange(block)[None, None, :]) % n).reshape(runs, -1)[:, :n]
    diffs = _ann_sharpe(x[index]) - _ann_sharpe(y[index])
    sa = float(_ann_sharpe(x))
    sb = float(_ann_sharpe(y))
    return SharpeDiff(
        weeks=n,
        sharpe_a=sa,
        sharpe_b=sb,
        diff=sa - sb,
        low=float(np.quantile(diffs, 0.05)),
        high=float(np.quantile(diffs, 0.95)),
        p_not_better=float((diffs <= 0.0).mean()),
    )
