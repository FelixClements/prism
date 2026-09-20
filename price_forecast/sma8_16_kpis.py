"""Weekly BTC SMA-8 entry / SMA-16 exit KPIs versus buy-and-hold.

Not investment advice. Current best-so-far scoreboard (user, 2026-09-18).
This is a separate same-bar, 0.15%-per-fill runner. It does not change the
frozen weekly bakeoff (t+1 fill, 10 bps, strict inequalities).

Rules
-----
- Asset: BTC. Timeframe: UTC Monday 00:00 through Sunday 24:00. Bar date is Sunday.
  Weekly close is the last Coinbase UTC daily close in that window. Incomplete
  trailing weeks are dropped (same `weekly_closes` helper as the bakeoff).
- Indicators: SMA-8 to enter, SMA-16 to exit. Each SMA includes this week's close.
  SMA at week t uses closes[0:t+1] only.
- Start FLAT. No trade until both SMAs exist (first bar is the week SMA-16 appears).
- If FLAT: BUY when weekly close >= SMA-8.
- If LONG: SELL when weekly close <= SMA-16.
- Else HOLD. One action per bar from the position at the start of the bar
  (no same-bar buy then sell).
- Fill at that same weekly close. This is more optimistic than the frozen t+1 bakeoff.
- Cost: 0.15% of notional on each fill (buy and sell each). Cash earns 0.
- Position is 100% BTC or 100% cash. Default start $10,000.
- HODL: buy 100% BTC on the first SMA-16 bar, hold to the last bar, pay 0.15% once
  at that entry. No weekly fees and no exit fee.

KPI definitions (after costs, same comparable window)
-----------------------------------------------------
- Absolute total return: end equity / start $ - 1.
- Strategy alpha: strategy total return minus HODL total return, in percentage
  points of total return. This is excess total return, not CAPM alpha.
- Profit factor: sum of winning round-trip $ / abs(sum of losing round-trip $).
  A round trip is buy → sell. An open position at the end is marked to the last
  close (no extra exit fee) and that MTM P&L is included so PF is defined.
  Completed-trade count / win rate / whipsaws ignore the open trade.
  No losses → inf. No round trips at all (never entered) → n/a.
- Max DD: peak-to-trough on the after-cost equity curve (fraction, ≤ 0).
- Sortino: mean weekly equity return / sample stdev (ddof=1) of strictly negative
  weekly returns, annualized * sqrt(52). rf = 0. Fewer than two downside weeks → n/a.
- MAR: CAGR / abs(Max DD). CAGR uses start $, end $, and elapsed calendar years
  (365.25). Max DD of 0 or undefined CAGR → n/a.
- Market exposure: fraction of comparable weeks that are long after that week's fill.
- Win rate: share of *completed* round trips with P&L > 0 after costs.
- Whipsaw: completed round trip whose holding period is <= 2 weekly bars.
  Holding period = exit_index - entry_index (Sunday bars between buy fill and sell fill).
- Fee drag: sum of fee dollars, fees / start $, and (no-fee total return − with-fee
  total return).

Usage:
    .venv/bin/python -m price_forecast.sma8_16_kpis
    .venv/bin/python -m price_forecast.sma8_16_kpis --starting-dollars 10000

Monthly file:
    price_forecast/sma8_16_kpis_monthly.md
    price_forecast/sma8_16_kpis_monthly.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from price_forecast.series import (
    BTC_CLOSE_PRODUCT,
    BTC_CLOSE_SOURCE,
    BTC_CLOSE_TIMEZONE,
    load_daily_closes,
)
from price_forecast.weekly_regime import weekly_closes

BUY_WEEKS = 8
SELL_WEEKS = 16
FILL_COST = 0.0015
STARTING_DOLLARS = 10_000.0
WHIPSAW_MAX_HOLDING_BARS = 2
_DAYS_PER_YEAR = 365.25
_WEEKS_PER_YEAR = 52


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


@dataclass(frozen=True)
class SideKpis:
    start_dollars: float
    end_dollars: float
    total_return: float
    alpha: float | None
    profit_factor: float | None
    max_drawdown: float
    sortino: float | None
    cagr: float | None
    mar: float | None
    exposure: float | None
    completed_round_trips: int | None
    win_rate: float | None
    whipsaws: int | None
    fees_paid: float
    fees_pct_of_start: float
    no_fee_total_return: float
    fee_drag_on_total_return: float


@dataclass(frozen=True)
class KpiReport:
    start: date
    end: date
    start_dollars: float
    start_price: float
    end_price: float
    n_comparable_weeks: int
    strategy: SideKpis
    hodl: SideKpis


@dataclass(frozen=True)
class MonthKpis:
    year_month: str
    n_weeks: int
    strategy_end_dollars: float
    strategy_monthly_return: float
    hodl_end_dollars: float
    hodl_monthly_return: float
    strategy_max_drawdown: float
    hodl_max_drawdown: float
    exposure: float
    completed_round_trips: int
    fees_paid: float
    held: str
    cum_strategy_total_return: float
    cum_hodl_total_return: float
    cum_alpha: float
    cum_profit_factor: float | None
    cum_strategy_max_drawdown: float
    cum_hodl_max_drawdown: float
    cum_strategy_sortino: float | None
    cum_hodl_sortino: float | None
    cum_strategy_mar: float | None
    cum_hodl_mar: float | None
    cum_win_rate: float | None
    cum_whipsaws: int
    cum_fees_paid: float
    cum_completed_round_trips: int


@dataclass(frozen=True)
class ChapterWindow:
    label: str
    start: date
    end: date
    n_weeks: int
    strategy_start_dollars: float
    strategy_end_dollars: float
    hodl_start_dollars: float
    hodl_end_dollars: float
    strategy_return: float
    hodl_return: float
    strategy_max_drawdown: float
    hodl_max_drawdown: float


HIGHLIGHT_MONTH_RANGES = (
    ("2022-01", "2022-12"),
    ("2025-10", "2026-06"),
)
CHAPTER_SPECS = (
    ("2022", date(2022, 1, 1), date(2022, 12, 31)),
    ("2025-10 through 2026-06", date(2025, 10, 1), date(2026, 6, 30)),
)
_MONTHLY_CSV_COLUMNS = (
    "year_month",
    "n_weeks",
    "monthly_strategy_end_usd",
    "monthly_strategy_return",
    "monthly_hodl_end_usd",
    "monthly_hodl_return",
    "monthly_strategy_max_dd",
    "monthly_hodl_max_dd",
    "monthly_exposure",
    "monthly_round_trips",
    "monthly_fees_usd",
    "month_end_held",
    "cum_strategy_total_return",
    "cum_hodl_total_return",
    "cum_alpha",
    "cum_profit_factor",
    "cum_strategy_max_dd",
    "cum_hodl_max_dd",
    "cum_strategy_sortino",
    "cum_hodl_sortino",
    "cum_strategy_mar",
    "cum_hodl_mar",
    "cum_win_rate",
    "cum_whipsaws",
    "cum_fees_usd",
    "cum_round_trips",
)


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
        if position == 0 and close >= sma8:
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
        elif position == 1 and close <= sma16:
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


def max_drawdown(equity: Sequence[float]) -> float:
    """Peak-to-trough on equity as a fraction ≤ 0."""
    if not equity:
        raise ValueError("equity curve is empty")
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def sortino_ratio(returns: Sequence[float]) -> float | None:
    """Annualized Sortino, rf=0. Downside = sample stdev of negative weekly returns."""
    if not returns:
        return None
    negatives = [value for value in returns if value < 0.0]
    if len(negatives) < 2:
        return None
    mean = sum(returns) / len(returns)
    neg_mean = sum(negatives) / len(negatives)
    downside = math.sqrt(
        sum((value - neg_mean) ** 2 for value in negatives) / (len(negatives) - 1)
    )
    if downside == 0.0:
        return None
    return (mean / downside) * math.sqrt(_WEEKS_PER_YEAR)


def cagr(
    start_equity: float,
    end_equity: float,
    start: date,
    end: date,
) -> float | None:
    span_days = (end - start).days
    if span_days <= 0 or start_equity <= 0 or end_equity <= 0:
        return None
    return (end_equity / start_equity) ** (_DAYS_PER_YEAR / span_days) - 1.0


def mar_ratio(cagr: float | None, max_drawdown: float) -> float | None:
    if cagr is None or max_drawdown == 0.0:
        return None
    return cagr / abs(max_drawdown)


def profit_factor(pnls: Sequence[float]) -> float | None:
    if not pnls:
        return None
    wins = sum(value for value in pnls if value > 0.0)
    losses = sum(value for value in pnls if value < 0.0)
    if losses == 0.0:
        return math.inf
    return wins / abs(losses)


def _weekly_returns(equity: Sequence[float]) -> list[float]:
    return [
        equity[i] / equity[i - 1] - 1.0
        for i in range(1, len(equity))
        if equity[i - 1] > 0
    ]


def _win_rate(completed_pnls: Sequence[float]) -> float | None:
    if not completed_pnls:
        return None
    wins = sum(1 for value in completed_pnls if value > 0.0)
    return wins / len(completed_pnls)


def compute_kpis(
    weeks: Sequence[tuple[date, float]],
    *,
    starting_dollars: float = STARTING_DOLLARS,
    cost: float = FILL_COST,
) -> KpiReport:
    strategy = simulate_strategy(
        weeks, starting_dollars=starting_dollars, cost=cost
    )
    hodl = simulate_hodl(weeks, starting_dollars=starting_dollars, cost=cost)
    strategy_gross = simulate_strategy(
        weeks, starting_dollars=starting_dollars, cost=0.0
    )
    hodl_gross = simulate_hodl(weeks, starting_dollars=starting_dollars, cost=0.0)

    strategy_tr = strategy.end_dollars / starting_dollars - 1.0
    hodl_tr = hodl.end_dollars / starting_dollars - 1.0
    strategy_cagr = cagr(
        starting_dollars, strategy.end_dollars, strategy.start, strategy.end
    )
    hodl_cagr = cagr(starting_dollars, hodl.end_dollars, hodl.start, hodl.end)
    strategy_dd = max_drawdown(strategy.equity)
    hodl_dd = max_drawdown(hodl.equity)
    strategy_no_fee_tr = strategy_gross.end_dollars / starting_dollars - 1.0
    hodl_no_fee_tr = hodl_gross.end_dollars / starting_dollars - 1.0

    return KpiReport(
        start=strategy.start,
        end=strategy.end,
        start_dollars=starting_dollars,
        start_price=strategy.start_price,
        end_price=strategy.end_price,
        n_comparable_weeks=len(strategy.equity),
        strategy=SideKpis(
            start_dollars=starting_dollars,
            end_dollars=strategy.end_dollars,
            total_return=strategy_tr,
            alpha=strategy_tr - hodl_tr,
            profit_factor=profit_factor(strategy.pf_pnls),
            max_drawdown=strategy_dd,
            sortino=sortino_ratio(_weekly_returns(strategy.equity)),
            cagr=strategy_cagr,
            mar=mar_ratio(strategy_cagr, strategy_dd),
            exposure=strategy.exposure,
            completed_round_trips=strategy.completed_round_trips,
            win_rate=_win_rate(strategy.completed_pnls),
            whipsaws=strategy.whipsaws,
            fees_paid=strategy.fees_paid,
            fees_pct_of_start=strategy.fees_paid / starting_dollars,
            no_fee_total_return=strategy_no_fee_tr,
            fee_drag_on_total_return=strategy_no_fee_tr - strategy_tr,
        ),
        hodl=SideKpis(
            start_dollars=starting_dollars,
            end_dollars=hodl.end_dollars,
            total_return=hodl_tr,
            alpha=None,
            profit_factor=None,
            max_drawdown=hodl_dd,
            sortino=sortino_ratio(_weekly_returns(hodl.equity)),
            cagr=hodl_cagr,
            mar=mar_ratio(hodl_cagr, hodl_dd),
            exposure=None,
            completed_round_trips=None,
            win_rate=None,
            whipsaws=None,
            fees_paid=hodl.fees_paid,
            fees_pct_of_start=hodl.fees_paid / starting_dollars,
            no_fee_total_return=hodl_no_fee_tr,
            fee_drag_on_total_return=hodl_no_fee_tr - hodl_tr,
        ),
    )


def year_month(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _ym_tuple(year_month_key: str) -> tuple[int, int]:
    year_s, month_s = year_month_key.split("-", 1)
    return int(year_s), int(month_s)


def _is_highlight_month(year_month_key: str) -> bool:
    key = _ym_tuple(year_month_key)
    return any(
        _ym_tuple(start) <= key <= _ym_tuple(end)
        for start, end in HIGHLIGHT_MONTH_RANGES
    )


def _month_groups(dates: Sequence[date]) -> list[tuple[str, int, int]]:
    """Inclusive start/end equity indices per UTC calendar month of the bar date."""
    groups: list[tuple[str, int, int]] = []
    for i, day in enumerate(dates):
        key = year_month(day)
        if not groups or groups[-1][0] != key:
            groups.append((key, i, i))
        else:
            start_i = groups[-1][1]
            groups[-1] = (key, start_i, i)
    return groups


def _completed_stats(
    fills: Sequence[Fill],
) -> tuple[list[float], int, float, Fill | None]:
    completed: list[float] = []
    whipsaws = 0
    fees = 0.0
    open_buy: Fill | None = None
    for fill in fills:
        fees += fill.fee
        if fill.side == "BUY":
            open_buy = fill
        elif fill.side == "SELL":
            if open_buy is None:
                raise ValueError("sell without a matching buy")
            cash_before = open_buy.equity_after + open_buy.fee
            completed.append(fill.equity_after - cash_before)
            if fill.index - open_buy.index <= WHIPSAW_MAX_HOLDING_BARS:
                whipsaws += 1
            open_buy = None
        else:
            raise ValueError(f"unknown fill side {fill.side!r}")
    return completed, whipsaws, fees, open_buy


def _monthly_from_paths(strategy: EquityPath, hodl: EquityPath) -> list[MonthKpis]:
    if strategy.dates != hodl.dates:
        raise ValueError("strategy and HODL dates must match")
    if strategy.start_dollars != hodl.start_dollars:
        raise ValueError("strategy and HODL start dollars must match")
    rows: list[MonthKpis] = []
    prev_strategy = strategy.start_dollars
    prev_hodl = hodl.start_dollars
    for key, start_i, end_i in _month_groups(strategy.dates):
        n_weeks = end_i - start_i + 1
        strat_slice = strategy.equity[start_i : end_i + 1]
        hodl_slice = hodl.equity[start_i : end_i + 1]
        long_slice = strategy.long[start_i : end_i + 1]
        strat_end = strat_slice[-1]
        hodl_end = hodl_slice[-1]
        last_date = strategy.dates[end_i]
        fills_to_date = [fill for fill in strategy.fills if fill.date <= last_date]
        month_fills = [fill for fill in fills_to_date if year_month(fill.date) == key]
        completed, whipsaws, fees, open_buy = _completed_stats(fills_to_date)
        pf_pnls = list(completed)
        if long_slice[-1]:
            if open_buy is None:
                raise ValueError("long at month-end without an open buy")
            cash_before = open_buy.equity_after + open_buy.fee
            pf_pnls.append(strat_end - cash_before)
        cum_equity_s = strategy.equity[: end_i + 1]
        cum_equity_h = hodl.equity[: end_i + 1]
        strat_dd = max_drawdown(cum_equity_s)
        hodl_dd = max_drawdown(cum_equity_h)
        strat_cagr = cagr(
            strategy.start_dollars, strat_end, strategy.start, last_date
        )
        hodl_cagr = cagr(hodl.start_dollars, hodl_end, hodl.start, last_date)
        strat_tr = strat_end / strategy.start_dollars - 1.0
        hodl_tr = hodl_end / hodl.start_dollars - 1.0
        rows.append(
            MonthKpis(
                year_month=key,
                n_weeks=n_weeks,
                strategy_end_dollars=strat_end,
                strategy_monthly_return=strat_end / prev_strategy - 1.0,
                hodl_end_dollars=hodl_end,
                hodl_monthly_return=hodl_end / prev_hodl - 1.0,
                strategy_max_drawdown=max_drawdown(strat_slice),
                hodl_max_drawdown=max_drawdown(hodl_slice),
                exposure=sum(1 for flag in long_slice if flag) / n_weeks,
                completed_round_trips=sum(
                    1 for fill in month_fills if fill.side == "SELL"
                ),
                fees_paid=sum(fill.fee for fill in month_fills),
                held="BTC" if long_slice[-1] else "cash",
                cum_strategy_total_return=strat_tr,
                cum_hodl_total_return=hodl_tr,
                cum_alpha=strat_tr - hodl_tr,
                cum_profit_factor=profit_factor(pf_pnls),
                cum_strategy_max_drawdown=strat_dd,
                cum_hodl_max_drawdown=hodl_dd,
                cum_strategy_sortino=sortino_ratio(_weekly_returns(cum_equity_s)),
                cum_hodl_sortino=sortino_ratio(_weekly_returns(cum_equity_h)),
                cum_strategy_mar=mar_ratio(strat_cagr, strat_dd),
                cum_hodl_mar=mar_ratio(hodl_cagr, hodl_dd),
                cum_win_rate=_win_rate(completed),
                cum_whipsaws=whipsaws,
                cum_fees_paid=fees,
                cum_completed_round_trips=len(completed),
            )
        )
        prev_strategy = strat_end
        prev_hodl = hodl_end
    return rows


def monthly_kpis(
    weeks: Sequence[tuple[date, float]],
    *,
    starting_dollars: float = STARTING_DOLLARS,
    cost: float = FILL_COST,
) -> list[MonthKpis]:
    """Per calendar month of the weekly bar date, plus cumulative-to-date KPIs."""
    strategy = simulate_strategy(
        weeks, starting_dollars=starting_dollars, cost=cost
    )
    hodl = simulate_hodl(weeks, starting_dollars=starting_dollars, cost=cost)
    return _monthly_from_paths(strategy, hodl)


def chapter_window(
    strategy: EquityPath,
    hodl: EquityPath,
    start: date,
    end: date,
    *,
    label: str,
) -> ChapterWindow | None:
    """Continuing-path chapter: return from the prior bar, DD inside the window."""
    if strategy.dates != hodl.dates:
        raise ValueError("strategy and HODL dates must match")
    idxs = [i for i, day in enumerate(strategy.dates) if start <= day <= end]
    if not idxs:
        return None
    first, last = idxs[0], idxs[-1]
    if first > 0:
        strat_start = strategy.equity[first - 1]
        hodl_start = hodl.equity[first - 1]
    else:
        strat_start = strategy.start_dollars
        hodl_start = hodl.start_dollars
    strat_end = strategy.equity[last]
    hodl_end = hodl.equity[last]
    return ChapterWindow(
        label=label,
        start=strategy.dates[first],
        end=strategy.dates[last],
        n_weeks=last - first + 1,
        strategy_start_dollars=strat_start,
        strategy_end_dollars=strat_end,
        hodl_start_dollars=hodl_start,
        hodl_end_dollars=hodl_end,
        strategy_return=strat_end / strat_start - 1.0,
        hodl_return=hodl_end / hodl_start - 1.0,
        strategy_max_drawdown=max_drawdown(strategy.equity[first : last + 1]),
        hodl_max_drawdown=max_drawdown(hodl.equity[first : last + 1]),
    )


def _csv_cell(value: float | None) -> str:
    if value is None:
        return ""
    if math.isinf(value):
        return "inf"
    return repr(value)


def format_monthly_csv(rows: Sequence[MonthKpis]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=list(_MONTHLY_CSV_COLUMNS), lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "year_month": row.year_month,
                "n_weeks": row.n_weeks,
                "monthly_strategy_end_usd": _csv_cell(row.strategy_end_dollars),
                "monthly_strategy_return": _csv_cell(row.strategy_monthly_return),
                "monthly_hodl_end_usd": _csv_cell(row.hodl_end_dollars),
                "monthly_hodl_return": _csv_cell(row.hodl_monthly_return),
                "monthly_strategy_max_dd": _csv_cell(row.strategy_max_drawdown),
                "monthly_hodl_max_dd": _csv_cell(row.hodl_max_drawdown),
                "monthly_exposure": _csv_cell(row.exposure),
                "monthly_round_trips": row.completed_round_trips,
                "monthly_fees_usd": _csv_cell(row.fees_paid),
                "month_end_held": row.held,
                "cum_strategy_total_return": _csv_cell(row.cum_strategy_total_return),
                "cum_hodl_total_return": _csv_cell(row.cum_hodl_total_return),
                "cum_alpha": _csv_cell(row.cum_alpha),
                "cum_profit_factor": _csv_cell(row.cum_profit_factor),
                "cum_strategy_max_dd": _csv_cell(row.cum_strategy_max_drawdown),
                "cum_hodl_max_dd": _csv_cell(row.cum_hodl_max_drawdown),
                "cum_strategy_sortino": _csv_cell(row.cum_strategy_sortino),
                "cum_hodl_sortino": _csv_cell(row.cum_hodl_sortino),
                "cum_strategy_mar": _csv_cell(row.cum_strategy_mar),
                "cum_hodl_mar": _csv_cell(row.cum_hodl_mar),
                "cum_win_rate": _csv_cell(row.cum_win_rate),
                "cum_whipsaws": row.cum_whipsaws,
                "cum_fees_usd": _csv_cell(row.cum_fees_paid),
                "cum_round_trips": row.cum_completed_round_trips,
            }
        )
    return buffer.getvalue()


def format_compact_monthly_table(rows: Sequence[MonthKpis]) -> str:
    header = (
        f"{'':1}{'Year-month':<9} {'Strat end$':>14} {'Strat m/m':>10} "
        f"{'HODL end$':>14} {'HODL m/m':>10} {'Strat DD':>10} {'HODL DD':>10} "
        f"{'Exp%':>8} {'Trips':>5} {'Fees':>12} {'Held':>5}"
    )
    lines = [
        "## Monthly returns vs buy-and-hold (compact)",
        "",
        "Each row is one UTC calendar month of Sunday weekly bars. "
        "Monthly return is that month's last equity / previous month-end equity − 1 "
        "(first month vs start $). Max DD is peak-to-trough on equity inside the month. "
        "`*` marks 2022 and 2025-10 through 2026-06.",
        "",
        header,
    ]
    for row in rows:
        mark = "*" if _is_highlight_month(row.year_month) else " "
        lines.append(
            f"{mark}{row.year_month:<9} "
            f"{_fmt_usd(row.strategy_end_dollars):>14} "
            f"{_fmt_pct(row.strategy_monthly_return):>10} "
            f"{_fmt_usd(row.hodl_end_dollars):>14} "
            f"{_fmt_pct(row.hodl_monthly_return):>10} "
            f"{_fmt_pct(row.strategy_max_drawdown):>10} "
            f"{_fmt_pct(row.hodl_max_drawdown):>10} "
            f"{_fmt_pct(row.exposure):>8} "
            f"{row.completed_round_trips:>5} "
            f"{_fmt_usd(row.fees_paid):>12} "
            f"{row.held:>5}"
        )
    lines.append("")
    return "\n".join(lines)


def _rows_in_range(
    rows: Sequence[MonthKpis], start_ym: str, end_ym: str
) -> list[MonthKpis]:
    lo, hi = _ym_tuple(start_ym), _ym_tuple(end_ym)
    return [row for row in rows if lo <= _ym_tuple(row.year_month) <= hi]


def format_chapter_window(window: ChapterWindow) -> str:
    return "\n".join(
        [
            f"Chapter window {window.start.isoformat()} → {window.end.isoformat()} "
            f"({window.n_weeks} weekly bars). "
            "Start $ is the prior bar's equity (continuing path, not a fresh $10k). "
            "Max DD is peak-to-trough inside the chapter.",
            f"  Strategy: {_fmt_usd(window.strategy_start_dollars)} → "
            f"{_fmt_usd(window.strategy_end_dollars)} "
            f"({_fmt_pct(window.strategy_return)}); "
            f"max DD {_fmt_pct(window.strategy_max_drawdown)}",
            f"  HODL:     {_fmt_usd(window.hodl_start_dollars)} → "
            f"{_fmt_usd(window.hodl_end_dollars)} "
            f"({_fmt_pct(window.hodl_return)}); "
            f"max DD {_fmt_pct(window.hodl_max_drawdown)}",
        ]
    )


def format_highlighted_chapters(
    rows: Sequence[MonthKpis],
    *,
    windows: Sequence[ChapterWindow | None] = (),
) -> str:
    blocks: list[str] = [
        "## Highlighted chapters",
        "",
        "Reprinted from the compact monthly table. Not investment advice.",
        "",
    ]
    window_by_label = {window.label: window for window in windows if window is not None}
    for (start_ym, end_ym), spec in zip(HIGHLIGHT_MONTH_RANGES, CHAPTER_SPECS):
        label, _start, _end = spec
        subset = _rows_in_range(rows, start_ym, end_ym)
        blocks.append(f"### {label}")
        blocks.append("")
        window = window_by_label.get(label)
        if window is not None:
            blocks.append(format_chapter_window(window))
            blocks.append("")
        if not subset:
            blocks.append("No weekly bars in this window.")
            blocks.append("")
            continue
        blocks.append(format_compact_monthly_table(subset))
    return "\n".join(blocks)


def _md_table(headers: Sequence[str], body_rows: Sequence[Sequence[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in body_rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def format_monthly_markdown(
    report: KpiReport,
    rows: Sequence[MonthKpis],
    *,
    windows: Sequence[ChapterWindow | None] = (),
) -> str:
    monthly_headers = [
        "year-month",
        "weeks",
        "monthly strategy end $",
        "monthly strategy return",
        "monthly HODL end $",
        "monthly HODL return",
        "monthly strategy max DD",
        "monthly HODL max DD",
        "monthly exposure",
        "monthly round trips",
        "monthly fees $",
        "month-end held",
    ]
    monthly_body = [
        [
            row.year_month,
            str(row.n_weeks),
            _fmt_usd(row.strategy_end_dollars),
            _fmt_pct(row.strategy_monthly_return),
            _fmt_usd(row.hodl_end_dollars),
            _fmt_pct(row.hodl_monthly_return),
            _fmt_pct(row.strategy_max_drawdown),
            _fmt_pct(row.hodl_max_drawdown),
            _fmt_pct(row.exposure),
            str(row.completed_round_trips),
            _fmt_usd(row.fees_paid),
            row.held,
        ]
        for row in rows
    ]
    cum_headers = [
        "year-month",
        "cumulative strategy total return",
        "cumulative HODL total return",
        "cumulative alpha vs HODL",
        "cumulative profit factor",
        "cumulative strategy max DD",
        "cumulative HODL max DD",
        "cumulative strategy Sortino",
        "cumulative HODL Sortino",
        "cumulative strategy MAR",
        "cumulative HODL MAR",
        "cumulative win rate",
        "cumulative whipsaws",
        "cumulative fees $",
        "cumulative round trips",
    ]
    cum_body = [
        [
            row.year_month,
            _fmt_pct(row.cum_strategy_total_return),
            _fmt_pct(row.cum_hodl_total_return),
            _fmt_pp(row.cum_alpha),
            _fmt_ratio(row.cum_profit_factor),
            _fmt_pct(row.cum_strategy_max_drawdown),
            _fmt_pct(row.cum_hodl_max_drawdown),
            _fmt_ratio(row.cum_strategy_sortino),
            _fmt_ratio(row.cum_hodl_sortino),
            _fmt_ratio(row.cum_strategy_mar),
            _fmt_ratio(row.cum_hodl_mar),
            _fmt_pct(row.cum_win_rate),
            str(row.cum_whipsaws),
            _fmt_usd(row.cum_fees_paid),
            str(row.cum_completed_round_trips),
        ]
        for row in rows
    ]
    lines = [
        "# SMA-8/16 monthly KPIs vs buy-and-hold",
        "",
        "**Not investment advice.** Same same-bar weekly close, 0.15%/fill, start-cash "
        "rules as `sma8_16_kpis_results.md`.",
        "",
        f"Full sample: {report.start.isoformat()} → {report.end.isoformat()}, "
        f"start {_fmt_usd(report.start_dollars)}, "
        f"strategy end {_fmt_usd(report.strategy.end_dollars)} vs "
        f"HODL {_fmt_usd(report.hodl.end_dollars)}.",
        "",
        "Monthly columns are that calendar month only (UTC month of the Sunday bar). "
        "Cumulative columns are from the first comparable bar through that month-end, "
        "using the same KPI definitions as the full-sample table (profit factor = "
        "completed round trips plus open-trade MTM, no extra exit fee).",
        "",
        format_compact_monthly_table(rows).rstrip(),
        "",
        format_highlighted_chapters(rows, windows=windows).rstrip(),
        "",
        "## Monthly columns",
        "",
        _md_table(monthly_headers, monthly_body),
        "",
        "## Cumulative-to-date columns",
        "",
        _md_table(cum_headers, cum_body),
        "",
        "How to re-run:",
        "",
        "```",
        ".venv/bin/python -m price_forecast.sma8_16_kpis",
        "```",
        "",
    ]
    return "\n".join(lines)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * value:.2f}%"


def _fmt_pp(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * value:+.2f} pp"


def _fmt_ratio(value: float | None) -> str:
    if value is None:
        return "n/a"
    if math.isinf(value):
        return "inf"
    return f"{value:.4f}"


def _fmt_int(value: int | None) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _fmt_usd(value: float) -> str:
    return f"${value:,.2f}"


def _row(name: str, strategy: str, hodl: str) -> str:
    return f"{name:<44} {strategy:>16} {hodl:>16}"


def format_report(report: KpiReport) -> str:
    strat = report.strategy
    hodl = report.hodl
    lines = [
        "# BTC weekly SMA-8 entry / SMA-16 exit vs buy-and-hold",
        "",
        "**Current best-so-far (user, 2026-09-18).** Not investment advice.",
        "This is a historical backtest of one execution design, not a product rule.",
        "",
        f"KPI snapshot: start {_fmt_usd(report.start_dollars)}; "
        f"{report.start.isoformat()} → {report.end.isoformat()} "
        f"({report.n_comparable_weeks} comparable weeks after SMA-16 warmup); "
        f"strategy end {_fmt_usd(strat.end_dollars)} vs HODL {_fmt_usd(hodl.end_dollars)}; "
        f"total return {_fmt_pct(strat.total_return)} vs HODL {_fmt_pct(hodl.total_return)}; "
        f"max DD {_fmt_pct(strat.max_drawdown)} vs HODL {_fmt_pct(hodl.max_drawdown)}; "
        f"alpha {_fmt_pp(strat.alpha)}; exposure {_fmt_pct(strat.exposure)}.",
        "",
        "Caveats:",
        "- Same-bar weekly close fill: SMA at week t includes close t and the fill is close t. "
        "That is contemporaneous fill, not future lookahead. It is more optimistic than the frozen t+1 bakeoff.",
        "- Start in cash (FLAT) until the first close >= SMA-8 after SMA-16 exists. "
        "The frozen $10k crash-window tables start in BTC.",
        "- 0.15% of notional on each fill. Frozen bakeoff uses 10 bps and strict inequalities.",
        "- Not the frozen t+1 bakeoff (`weekly_bakeoff` / `sma_asymmetric_10k`).",
        "- Full-sample KPIs in this table. Monthly rows and the 2022 / Oct 2025–Jun 2026 "
        "chapters are in `sma8_16_kpis_monthly.md` (also `.csv`). A full-sample dollar "
        "figure can still hide a bad crash window; read those months.",
        "",
        "Same-bar fill at the weekly close (more optimistic than the frozen t+1 bakeoff).",
        "Cost is 0.15% per fill vs the frozen bakeoff's 10 bps. Entry uses close >= SMA-8;",
        "exit uses close <= SMA-16 (frozen bakeoff uses strict > / <). Do not compare these",
        "dollars to `sma_asymmetric_10k_results.md` as if the rules were the same.",
        "",
        f"Date range: {report.start.isoformat()} → {report.end.isoformat()} "
        f"({report.n_comparable_weeks} comparable weekly bars after SMA-16 warmup).",
        f"Start $: {_fmt_usd(report.start_dollars)}",
        f"End $ strategy: {_fmt_usd(strat.end_dollars)}    End $ buy & hold: {_fmt_usd(hodl.end_dollars)}",
        f"Start BTC price: {_fmt_usd(report.start_price)}    End BTC price: {_fmt_usd(report.end_price)}",
        f"Series: weekly close from daily {BTC_CLOSE_PRODUCT} {BTC_CLOSE_SOURCE} ({BTC_CLOSE_TIMEZONE}).",
        "",
        "Whipsaw = completed round trip with holding period <= 2 weekly bars "
        "(holding period = sell bar index − buy bar index).",
        "Open trades are marked to the last close in total return and max DD; profit factor "
        "also includes that MTM as a virtual close (no extra 0.15% exit fee).",
        "Win rate / trade count / whipsaws count completed buy→sell round trips only.",
        "HODL pays 0.15% once at entry.",
        "",
        "Strategy alpha is excess total return (strategy TR − HODL TR), not CAPM alpha.",
        "",
        _row("KPI", "Strategy", "Buy & Hold"),
        _row("-" * 44, "-" * 16, "-" * 16),
        _row(
            "Absolute Total Return (%)",
            _fmt_pct(strat.total_return),
            _fmt_pct(hodl.total_return),
        ),
        _row(
            "Strategy Alpha (excess total return)",
            _fmt_pp(strat.alpha),
            "n/a",
        ),
        _row("Profit Factor", _fmt_ratio(strat.profit_factor), "n/a"),
        _row(
            "Max DD %",
            _fmt_pct(strat.max_drawdown),
            _fmt_pct(hodl.max_drawdown),
        ),
        _row("Sortino Ratio (ann., rf=0%)", _fmt_ratio(strat.sortino), _fmt_ratio(hodl.sortino)),
        _row("MAR Ratio", _fmt_ratio(strat.mar), _fmt_ratio(hodl.mar)),
        _row("Market Exposure Time %", _fmt_pct(strat.exposure), "n/a"),
        _row(
            "Completed round trips",
            _fmt_int(strat.completed_round_trips),
            "n/a",
        ),
        _row("Win Rate", _fmt_pct(strat.win_rate), "n/a"),
        _row("Whipsaws (<=2 weekly bars)", _fmt_int(strat.whipsaws), "n/a"),
        _row("Total fees $", _fmt_usd(strat.fees_paid), _fmt_usd(hodl.fees_paid)),
        _row(
            "Fees % of start $",
            _fmt_pct(strat.fees_pct_of_start),
            _fmt_pct(hodl.fees_pct_of_start),
        ),
        _row(
            "No-fee total return",
            _fmt_pct(strat.no_fee_total_return),
            _fmt_pct(hodl.no_fee_total_return),
        ),
        _row(
            "Fee drag on total return",
            _fmt_pp(strat.fee_drag_on_total_return),
            _fmt_pp(hodl.fee_drag_on_total_return),
        ),
        "",
        "How to re-run:",
        "",
        "```",
        ".venv/bin/python -m price_forecast.sma8_16_kpis",
        ".venv/bin/python -m price_forecast.sma8_16_kpis --starting-dollars 10000",
        "```",
        "",
        "Monthly + cumulative-to-date grid: `sma8_16_kpis_monthly.md` / `sma8_16_kpis_monthly.csv`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Weekly BTC SMA-8/SMA-16 same-bar KPIs vs buy-and-hold."
    )
    parser.add_argument(
        "--starting-dollars",
        type=float,
        default=STARTING_DOLLARS,
        help="Starting cash (default 10000).",
    )
    args = parser.parse_args(argv)
    daily = load_daily_closes(
        source="coinbase",
        start=date(2018, 1, 1),
        end=datetime.now(timezone.utc).date(),
    )
    weeks = weekly_closes(daily)
    report = compute_kpis(weeks, starting_dollars=args.starting_dollars)
    strategy = simulate_strategy(
        weeks, starting_dollars=args.starting_dollars
    )
    hodl = simulate_hodl(weeks, starting_dollars=args.starting_dollars)
    rows = _monthly_from_paths(strategy, hodl)
    windows = [
        chapter_window(strategy, hodl, start, end, label=label)
        for label, start, end in CHAPTER_SPECS
    ]
    text = format_report(report)
    compact = format_compact_monthly_table(rows)
    highlights = format_highlighted_chapters(rows, windows=windows)
    monthly_md = format_monthly_markdown(report, rows, windows=windows)
    monthly_csv = format_monthly_csv(rows)
    out_path = Path(__file__).with_name("sma8_16_kpis_results.md")
    monthly_md_path = Path(__file__).with_name("sma8_16_kpis_monthly.md")
    monthly_csv_path = Path(__file__).with_name("sma8_16_kpis_monthly.csv")
    out_path.write_text(text, encoding="utf-8")
    monthly_md_path.write_text(monthly_md, encoding="utf-8")
    monthly_csv_path.write_text(monthly_csv, encoding="utf-8")
    print(text)
    print(compact)
    print(highlights)
    print(
        "Full cumulative KPI grid (monthly + cumulative-to-date columns) is in "
        f"{monthly_md_path} and {monthly_csv_path}."
    )
    print(f"Wrote {out_path}", flush=True)
    print(f"Wrote {monthly_md_path}", flush=True)
    print(f"Wrote {monthly_csv_path}", flush=True)


if __name__ == "__main__":
    main()
