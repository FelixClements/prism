"""SMAGateV1 markdown and CSV scoreboard writers."""

from __future__ import annotations

import csv
import io
import math
from datetime import date, datetime, timezone
from typing import Sequence

from price_forecast.data.series import (
    BTC_CLOSE_PRODUCT,
    BTC_CLOSE_SOURCE,
    BTC_CLOSE_TIMEZONE,
)
from price_forecast.backtest.kpis import (
    CHAPTER_SPECS,
    HIGHLIGHT_MONTH_RANGES,
    ChapterWindow,
    KpiReport,
    MonthKpis,
    _is_highlight_month,
    _ym_tuple,
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
        "# SMAGateV1 monthly KPIs vs buy-and-hold",
        "",
        "**SMAGateV1.** Not investment advice. Same same-bar weekly close, 0.15%/fill, "
        "start-cash rules as `sma8_16_kpis_results.md`. Still takes ~30-40% crash chapters.",
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
        ".venv/bin/python -m price_forecast.strategies.smagate_v1",
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
        "# SMAGateV1 — weekly BTC SMA-8 in / SMA-16 out vs buy-and-hold",
        "",
        "**SMAGateV1** (user-named freeze of the locked best-so-far, 2026-09-18). "
        "Not investment advice.",
        "This is a historical backtest of one execution design, not a product rule. "
        "V1 is this freeze, not a new rule.",
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
        "- Start in cash (FLAT) until the first close > SMA-8 after SMA-16 exists. "
        "The frozen $10k crash-window tables start in BTC.",
        "- 0.15% of notional on each fill. Frozen bakeoff uses 10 bps; this runner now also "
        "uses strict > / < (on the line is HOLD).",
        "- Not the frozen t+1 bakeoff (archived at `price_forecast/archive/frozen_t1_bakeoff/`).",
        "- Full-sample KPIs in this table. Monthly rows and the 2022 / Oct 2025–Jun 2026 "
        "chapters are in `sma8_16_kpis_monthly.md` (also `.csv`). A full-sample dollar "
        "figure can still hide a bad crash window; SMAGateV1 still takes ~30-40% crash "
        "chapters. Read those months.",
        "",
        "Same-bar fill at the weekly close (more optimistic than the frozen t+1 bakeoff).",
        "Cost is 0.15% per fill vs the frozen bakeoff's 10 bps. Entry uses close > SMA-8;",
        "exit uses close < SMA-16 (on the line is HOLD). Do not compare these",
        "dollars to `price_forecast/archive/frozen_t1_bakeoff/sma_asymmetric_10k_results.md` "
        "as if the rules were the same.",
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
        ".venv/bin/python -m price_forecast.strategies.smagate_v1",
        ".venv/bin/python -m price_forecast.strategies.smagate_v1 --starting-dollars 10000",
        "```",
        "",
        "Monthly + cumulative-to-date grid: `sma8_16_kpis_monthly.md` / `sma8_16_kpis_monthly.csv`.",
        "",
    ]
    return "\n".join(lines)
