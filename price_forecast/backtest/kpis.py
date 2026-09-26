"""SMAGateV1 KPI math and monthly chapters."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from price_forecast.backtest.engine import EquityPath, Fill, simulate_hodl, simulate_strategy
from price_forecast.strategies.smagate_v1 import (
    FILL_COST,
    STARTING_DOLLARS,
    WHIPSAW_MAX_HOLDING_BARS,
)

_DAYS_PER_YEAR = 365.25
_WEEKS_PER_YEAR = 52


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


