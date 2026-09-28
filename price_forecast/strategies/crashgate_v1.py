"""CrashGateV1: base-or-breakout buy, 16-week sell, plus a 10% down-week sell.

Buy on the weekly close when all three are true:
- close is strictly above the 8-week average
- the daily path is in a pre-breakout or a breakout
- price is above both the 150-day and the 200-day averages

Sell on the weekly close when either is true:
- close is strictly below the 16-week average
- the week fell 10% or more and the close is strictly below the 8-week average

The fill is the next weekly close. Cost is 0.15% per fill. Start in cash.
SMAGateV1 is unchanged.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Sequence

from price_forecast.data.candles import BTC_USD_DAILY_CSV, Candle, read_candles
from price_forecast.strategies.signals import sma_at

BUY_WEEKS = 8
SELL_WEEKS = 16
WEEK_DROP = 0.10
FILL_COST = 0.0015
STARTING_DOLLARS = 10_000.0
WHIPSAW_MAX_HOLDING_BARS = 2
# Locked 2026-09-28 bakeoff starts one week after SMA-16 first exists.
FIRST_BAR = 16
RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"


def weekly_sessions(candles: Sequence[Candle]) -> list[tuple[date, float]]:
    """Last UTC session of each complete Sunday-ending week, and that close."""
    if not candles:
        raise ValueError("candles are empty")
    last_day = candles[-1].day
    buckets: dict[date, tuple[date, float]] = {}
    for candle in candles:
        week_end = candle.day + timedelta(days=(6 - candle.day.weekday()))
        current = buckets.get(week_end)
        if current is None or candle.day >= current[0]:
            buckets[week_end] = (candle.day, candle.close)
    weeks = []
    for week_end in sorted(buckets):
        if week_end <= last_day:
            weeks.append(buckets[week_end])
    return weeks


def _fast_sell(closes: Sequence[float], index: int) -> bool:
    """10% drop from the prior week, and this close is under the 8-week average."""
    if index < 1:
        return False
    close = closes[index]
    week_drop = close <= closes[index - 1] * (1.0 - WEEK_DROP)
    under_fast = close < sma_at(closes, index, BUY_WEEKS)
    return week_drop and under_fast


def simulate_crashgate(
    weeks: Sequence[tuple[date, float]],
    buy_allowed: Callable[[date], bool],
    *,
    starting_dollars: float = STARTING_DOLLARS,
    cost: float = FILL_COST,
):
    """Next-week fill. ``buy_allowed`` is the daily base-or-breakout gate."""
    from price_forecast.backtest.engine import EquityPath, Fill

    if starting_dollars <= 0:
        raise ValueError("starting_dollars must be positive")
    if cost < 0:
        raise ValueError("cost must be non-negative")
    if len(weeks) <= FIRST_BAR:
        raise ValueError("need more than 16 weekly bars")
    closes = [close for _day, close in weeks]
    position = 0
    wealth = starting_dollars
    btc = 0.0
    pending: str | None = None
    cash_before: float | None = None
    entry_index: int | None = None
    fees_paid = 0.0
    fills: list[Fill] = []
    dates: list[date] = []
    marked: list[float] = []
    equity: list[float] = []
    long_flags: list[bool] = []
    completed: list[float] = []
    whipsaws = 0

    for i in range(FIRST_BAR, len(weeks)):
        day, close = weeks[i]
        if pending == "buy" and position == 0:
            fee = wealth * cost
            cash_before = wealth
            wealth -= fee
            fees_paid += fee
            btc = wealth / close
            position = 1
            entry_index = i
            pending = None
            fills.append(Fill(i, day, "BUY", close, fee, wealth))
        elif pending == "sell" and position == 1:
            proceeds = btc * close
            fee = proceeds * cost
            wealth = proceeds - fee
            fees_paid += fee
            assert cash_before is not None and entry_index is not None
            completed.append(wealth - cash_before)
            if i - entry_index <= WHIPSAW_MAX_HOLDING_BARS:
                whipsaws += 1
            btc = 0.0
            position = 0
            cash_before = None
            entry_index = None
            pending = None
            fills.append(Fill(i, day, "SELL", close, fee, wealth))
        if position == 1:
            wealth = btc * close
        dates.append(day)
        marked.append(close)
        equity.append(wealth)
        long_flags.append(position == 1)
        if i + 1 >= len(weeks):
            continue
        if position == 0 and close > sma_at(closes, i, BUY_WEEKS) and buy_allowed(day):
            pending = "buy"
        elif position == 1 and (
            close < sma_at(closes, i, SELL_WEEKS) or _fast_sell(closes, i)
        ):
            pending = "sell"

    pf_pnls = list(completed)
    if position == 1:
        assert cash_before is not None
        pf_pnls.append(wealth - cash_before)
    n = len(equity)
    return EquityPath(
        dates=dates,
        closes=marked,
        equity=equity,
        long=long_flags,
        fills=fills,
        start_dollars=starting_dollars,
        end_dollars=wealth,
        start_price=weeks[FIRST_BAR][1],
        end_price=weeks[-1][1],
        start=weeks[FIRST_BAR][0],
        end=weeks[-1][0],
        fees_paid=fees_paid,
        completed_round_trips=len(completed),
        whipsaws=whipsaws,
        exposure=(sum(1 for flag in long_flags if flag) / n) if n else 0.0,
        completed_pnls=completed,
        pf_pnls=pf_pnls,
    )


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _pp(value: float) -> str:
    return f"{value * 100:+.2f} pp"


def _usd(value: float) -> str:
    return f"${value:,.2f}"


def _row(name: str, strategy: str, hodl: str) -> str:
    return f"{name:<44} {strategy:>16} {hodl:>16}"


def _format_report(report) -> str:
    strat = report.strategy
    hodl = report.hodl
    lines = [
        "# CrashGateV1 — base-or-breakout buy, 16-week sell, 10% week under the 8-week average",
        "",
        "Not investment advice. This is the locked 2026-09-28 rule, not SMAGateV1.",
        "Signal on the weekly close. Fill on the next weekly close. Cost is 0.15% per fill.",
        "Start in cash.",
        "",
        "Buy when the weekly close is above the 8-week average, the daily path is a",
        "pre-breakout or a breakout, and price is above both the 150-day and 200-day averages.",
        "Sell when the weekly close is below the 16-week average, or when the week falls",
        "10% or more and that close is below the 8-week average.",
        "",
        f"Date range: {report.start.isoformat()} → {report.end.isoformat()} "
        f"({report.n_comparable_weeks} weekly bars).",
        f"Start $: {_usd(report.start_dollars)}",
        f"End $ strategy: {_usd(strat.end_dollars)}    End $ buy & hold: {_usd(hodl.end_dollars)}",
        f"Start BTC price: {_usd(report.start_price)}    End BTC price: {_usd(report.end_price)}",
        "",
        "Strategy alpha is excess total return (strategy total return − buy-and-hold total return).",
        "HODL pays 0.15% once at the first bar of this window.",
        "",
        _row("KPI", "Strategy", "Buy & Hold"),
        _row("-" * 44, "-" * 16, "-" * 16),
        _row("Absolute Total Return (%)", _pct(strat.total_return), _pct(hodl.total_return)),
        _row("Strategy Alpha (excess total return)", _pp(strat.alpha), "n/a"),
        _row("Profit Factor", f"{strat.profit_factor:.4f}", "n/a"),
        _row("Max DD %", _pct(strat.max_drawdown), _pct(hodl.max_drawdown)),
        _row("Sortino Ratio (ann., rf=0%)", f"{strat.sortino:.4f}", f"{hodl.sortino:.4f}"),
        _row("CAGR", _pct(strat.cagr), _pct(hodl.cagr)),
        _row("MAR Ratio", f"{strat.mar:.4f}", f"{hodl.mar:.4f}"),
        _row("Market Exposure Time %", _pct(strat.exposure), "n/a"),
        _row("Completed round trips", str(strat.completed_round_trips), "n/a"),
        _row("Win Rate", _pct(strat.win_rate), "n/a"),
        _row("Whipsaws (<=2 weekly bars)", str(strat.whipsaws), "n/a"),
        _row("Total fees $", _usd(strat.fees_paid), _usd(hodl.fees_paid)),
        _row("Fees % of start $", _pct(strat.fees_pct_of_start), _pct(hodl.fees_pct_of_start)),
        _row("No-fee total return", _pct(strat.no_fee_total_return), _pct(hodl.no_fee_total_return)),
        _row(
            "Fee drag on total return",
            _pp(strat.fee_drag_on_total_return),
            _pp(hodl.fee_drag_on_total_return),
        ),
        "",
        "How to re-run:",
        "",
        "```",
        "python -m price_forecast.strategies.crashgate_v1",
        "```",
        "",
    ]
    return "\n".join(lines)


def _hodl(template, cost: float):
    from price_forecast.backtest.engine import EquityPath, Fill

    fee = template.start_dollars * cost
    cash = template.start_dollars - fee
    btc = cash / template.closes[0]
    equity = [btc * price for price in template.closes]
    return EquityPath(
        dates=list(template.dates),
        closes=list(template.closes),
        equity=equity,
        long=[True] * len(equity),
        fills=[Fill(FIRST_BAR, template.start, "BUY", template.start_price, fee, cash)],
        start_dollars=template.start_dollars,
        end_dollars=equity[-1],
        start_price=template.start_price,
        end_price=template.end_price,
        start=template.start,
        end=template.end,
        fees_paid=fee,
        completed_round_trips=0,
        whipsaws=0,
        exposure=1.0,
        completed_pnls=[],
        pf_pnls=[],
    )


def _score(net, gross, hodl, hodl_gross, starting_dollars: float):
    from price_forecast.backtest.kpis import (
        KpiReport,
        SideKpis,
        _weekly_returns,
        _win_rate,
        cagr,
        mar_ratio,
        max_drawdown,
        profit_factor,
        sortino_ratio,
    )

    strat_tr = net.end_dollars / starting_dollars - 1.0
    hodl_tr = hodl.end_dollars / starting_dollars - 1.0
    strat_cagr = cagr(starting_dollars, net.end_dollars, net.start, net.end)
    hodl_cagr = cagr(starting_dollars, hodl.end_dollars, hodl.start, hodl.end)
    strat_dd = max_drawdown(net.equity)
    hodl_dd = max_drawdown(hodl.equity)
    no_fee = gross.end_dollars / starting_dollars - 1.0
    hodl_no = hodl_gross.end_dollars / starting_dollars - 1.0
    return KpiReport(
        start=net.start,
        end=net.end,
        start_dollars=starting_dollars,
        start_price=net.start_price,
        end_price=net.end_price,
        n_comparable_weeks=len(net.equity),
        strategy=SideKpis(
            starting_dollars,
            net.end_dollars,
            strat_tr,
            strat_tr - hodl_tr,
            profit_factor(net.pf_pnls),
            strat_dd,
            sortino_ratio(_weekly_returns(net.equity)),
            strat_cagr,
            mar_ratio(strat_cagr, strat_dd),
            net.exposure,
            net.completed_round_trips,
            _win_rate(net.completed_pnls),
            net.whipsaws,
            net.fees_paid,
            net.fees_paid / starting_dollars,
            no_fee,
            no_fee - strat_tr,
        ),
        hodl=SideKpis(
            starting_dollars,
            hodl.end_dollars,
            hodl_tr,
            None,
            None,
            hodl_dd,
            sortino_ratio(_weekly_returns(hodl.equity)),
            hodl_cagr,
            mar_ratio(hodl_cagr, hodl_dd),
            None,
            None,
            None,
            None,
            hodl.fees_paid,
            hodl.fees_paid / starting_dollars,
            hodl_no,
            hodl_no - hodl_tr,
        ),
    )


def main(argv: Sequence[str] | None = None) -> None:
    from price_forecast.backtest.kpis import CHAPTER_SPECS, chapter_window
    from price_forecast.backtest.reports import format_chapter_window
    from price_forecast.strategies.crashgate_entry import BaseBreakoutGate

    parser = argparse.ArgumentParser(description="CrashGateV1 next-week KPI report vs buy-and-hold.")
    parser.add_argument("--starting-dollars", type=float, default=STARTING_DOLLARS)
    parser.add_argument("--csv", type=Path, default=BTC_USD_DAILY_CSV)
    args = parser.parse_args(argv)
    csv_path = Path(args.csv)
    if not csv_path.is_file():
        raise SystemExit(f"missing {csv_path}. Run python -m price_forecast.data.candles")
    candles = read_candles(csv_path)
    weeks = weekly_sessions(candles)
    gate = BaseBreakoutGate(candles)
    net = simulate_crashgate(weeks, gate, starting_dollars=args.starting_dollars)
    gross = simulate_crashgate(weeks, gate, starting_dollars=args.starting_dollars, cost=0.0)
    hodl = _hodl(net, FILL_COST)
    hodl_gross = _hodl(net, 0.0)
    report = _score(net, gross, hodl, hodl_gross, args.starting_dollars)
    chapters = [
        chapter_window(net, hodl, start, end, label=label)
        for label, start, end in CHAPTER_SPECS
    ]
    text = _format_report(report)
    chapter_text = "\n".join(format_chapter_window(window) for window in chapters if window)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "crashgate_v1_kpis.md"
    out_path.write_text(text + "\n" + chapter_text + "\n", encoding="utf-8")
    print(text)
    print(chapter_text)
    print(f"Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
