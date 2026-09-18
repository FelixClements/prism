"""Asymmetric SMA grid: longer SMA to sell, shorter SMA to buy. $10k fresh start.

Usage:
    .venv/bin/python -m price_forecast.sma_asymmetric_10k
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from price_forecast.series import (
    BTC_CLOSE_PRODUCT,
    BTC_CLOSE_SOURCE,
    BTC_CLOSE_TIMEZONE,
    load_daily_closes,
)
from price_forecast.sma8_10k import STARTING_DOLLARS
from price_forecast.weekly_bakeoff import CRASH_WINDOWS, LONG_RUN_WINDOW, WINDOWS
from price_forecast.weekly_regime import (
    COST_BPS,
    DD_IMPROVEMENT,
    SMA8_LOOKBACK,
    DollarBacktestResult,
    asymmetric_sma_signal,
    dollar_backtest,
    sma_first_fill_date,
    sma_signal,
    weekly_closes,
)

BUY_WEEKS = (4, 6, 8, 10, 12)
SELL_WEEKS = (12, 16, 20, 26, 40)
LONGEST_SMA = 40
FULL_WINDOW = "full-after-sma40-warmup"
SMA12_LOOKBACK = 12


def frozen_combos() -> list[tuple[int, int]]:
    return [(buy, sell) for buy in BUY_WEEKS for sell in SELL_WEEKS if sell > buy]


def dollar_window_specs(
    weeks: list[tuple[date, float]],
) -> dict[str, tuple[date, date]]:
    latest = weeks[-1][0]
    specs: dict[str, tuple[date, date]] = {
        FULL_WINDOW: (sma_first_fill_date(weeks, LONGEST_SMA), latest),
    }
    for name, (start, end) in WINDOWS.items():
        specs[name] = (start, end or latest)
    return specs


@dataclass(frozen=True)
class WindowGrid:
    window: str
    buy_hold: DollarBacktestResult
    sma8: DollarBacktestResult
    sma12: DollarBacktestResult
    combos: dict[tuple[int, int], DollarBacktestResult]


def combo_beats_sma8_and_keeps_both_crashes(
    *,
    full_end: float,
    sma8_end: float,
    crash_dds: list[tuple[float, float]],
) -> bool:
    """Beat SMA-8 on full-sample end $ and 10pp better max DD vs B&H on both crashes."""
    if full_end <= sma8_end:
        return False
    return all(
        strategy_dd - hold_dd >= DD_IMPROVEMENT - 1e-12
        for strategy_dd, hold_dd in crash_dds
    )


def score_grid(weeks: list[tuple[date, float]]) -> list[WindowGrid]:
    specs = dollar_window_specs(weeks)
    hold = [1] * len(weeks)
    sma8 = sma_signal(weeks, lookback=SMA8_LOOKBACK)
    sma12 = sma_signal(weeks, lookback=SMA12_LOOKBACK)
    combo_signals = {
        combo: asymmetric_sma_signal(weeks, buy_weeks=combo[0], sell_weeks=combo[1])
        for combo in frozen_combos()
    }
    rows = []
    for window, (start, end) in specs.items():
        kwargs = dict(start=start, end=end, starting_dollars=STARTING_DOLLARS)
        rows.append(
            WindowGrid(
                window=window,
                buy_hold=dollar_backtest(weeks, hold, **kwargs),
                sma8=dollar_backtest(weeks, sma8, **kwargs),
                sma12=dollar_backtest(weeks, sma12, **kwargs),
                combos={
                    combo: dollar_backtest(weeks, signals, **kwargs)
                    for combo, signals in combo_signals.items()
                },
            )
        )
    return rows


def qualifying_combos(grids: list[WindowGrid]) -> list[tuple[int, int]]:
    full = _grid(grids, FULL_WINDOW)
    crashes = [_grid(grids, name) for name in CRASH_WINDOWS]
    out = []
    for combo in frozen_combos():
        crash_dds = [
            (crash.combos[combo].max_drawdown, crash.buy_hold.max_drawdown)
            for crash in crashes
        ]
        if combo_beats_sma8_and_keeps_both_crashes(
            full_end=full.combos[combo].end_dollars,
            sma8_end=full.sma8.end_dollars,
            crash_dds=crash_dds,
        ):
            out.append(combo)
    return out


def closer_to_buy_hold_than_sma8_without_blowing_2022(
    grids: list[WindowGrid],
) -> list[tuple[int, int]]:
    long_run = _grid(grids, LONG_RUN_WINDOW)
    crash_2022 = _grid(grids, "2022")
    sma8_ratio = long_run.sma8.end_dollars / long_run.buy_hold.end_dollars
    out = []
    for combo in frozen_combos():
        result = long_run.combos[combo]
        ratio = result.end_dollars / long_run.buy_hold.end_dollars
        keeps_2022 = (
            crash_2022.combos[combo].max_drawdown
            - crash_2022.buy_hold.max_drawdown
            >= DD_IMPROVEMENT - 1e-12
        )
        if ratio > sma8_ratio and keeps_2022:
            out.append(combo)
    return out


def at_least_as_shallow_as_sma8_on_both_crashes(
    grids: list[WindowGrid],
    combos: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    crashes = [_grid(grids, name) for name in CRASH_WINDOWS]
    return [
        combo
        for combo in combos
        if all(
            crash.combos[combo].max_drawdown + 1e-12 >= crash.sma8.max_drawdown
            for crash in crashes
        )
    ]


def format_report(
    weeks: list[tuple[date, float]],
    grids: list[WindowGrid],
    *,
    daily_first: date,
    daily_last: date,
    n_daily: int,
) -> str:
    full = _grid(grids, FULL_WINDOW)
    long_run = _grid(grids, LONG_RUN_WINDOW)
    top = _top_combos(full, n=3)
    winners = qualifying_combos(grids)
    closer = closer_to_buy_hold_than_sma8_without_blowing_2022(grids)
    vs_sma8_crashes = at_least_as_shallow_as_sma8_on_both_crashes(grids, winners)
    sma8_long_ratio = long_run.sma8.end_dollars / long_run.buy_hold.end_dollars
    lines = [
        "# Asymmetric SMA grid vs SMA-8 and buy-and-hold, $10k start",
        "",
        "Not investment advice. This is a backtest of a frozen weekly grid, not a new product rule.",
        "",
        "## The answer in one paragraph",
        "",
        _lead(full, top, winners, closer, vs_sma8_crashes, sma8_long_ratio),
        "",
        "## Exact rule",
        "",
        "While holding BTC, sell to cash iff weekly close is strictly below the longer SMA; while in cash, buy BTC iff weekly close is strictly above the shorter SMA.",
        "",
        f"- Starting capital: ${STARTING_DOLLARS:,.0f} converted to 100% BTC at the first fill bar of each window (no fee on that opening buy).",
        "- Each window is its own $10k start. Signals walk the full weekly series; the dollar path does not inherit a pre-window position.",
        f"- Series: weekly close from daily {BTC_CLOSE_PRODUCT} {BTC_CLOSE_SOURCE} ({BTC_CLOSE_TIMEZONE}).",
        f"- Daily history: {daily_first.isoformat()} to {daily_last.isoformat()} ({n_daily} days).",
        f"- Weeks: UTC Monday–Sunday. Bar date is Sunday. Weekly close = last UTC daily close in that week. Incomplete trailing weeks dropped.",
        f"- Weekly bars: {weeks[0][0].isoformat()} to {weeks[-1][0].isoformat()} ({len(weeks)} weeks).",
        f"- Frozen grid: buy_weeks ∈ {list(BUY_WEEKS)}, sell_weeks ∈ {list(SELL_WEEKS)}, skip sell_weeks <= buy_weeks ({len(frozen_combos())} combos).",
        "- SMA includes this week's close, same as SMA-8. Warmup for the full-sample window is 40 weeks (longest SMA); first fill bar is week 41.",
        "- Fill: signal at week t close executes at week t+1 close. Cash return = 0.",
        f"- Costs: {COST_BPS} bps of wealth each way on flips. No liquidation cost at window end.",
        "- Position is 100% BTC or 100% cash. Do not use the short SMA while in; do not use the long SMA while out.",
        "- Baselines: buy-and-hold, symmetric SMA-8, symmetric SMA-12 (in iff close > SMA).",
        "- Window start = last weekly close on or before the calendar start; end = last weekly close on or before the calendar end.",
        f"- Full-sample dollars are not comparable to `sma8_10k`'s 8-week-warmup window. This full sample starts {full.buy_hold.start.isoformat()} at ${_price(full.buy_hold.start_price)}; that report starts after SMA-8 warmup (2018-03-04 at a higher BTC price).",
        f"- Calendar windows 2022, 2025-10-06..2026-06-30, and {LONG_RUN_WINDOW} use the same anchors as sma8_10k / weekly bakeoff.",
        "",
        "## This is a map, not a new frozen rule",
        "",
        "Picking the best cell after seeing the grid is overfitting. The 24 combos were frozen before looking at results. Do not quietly replace SMA-8 with the max cell.",
        "",
        "## Full sample after 40-week warmup",
        "",
        *_format_window(full),
        "## 2024 through latest",
        "",
        *_format_window(long_run),
        "## Crash windows",
        "",
        *_format_window(_grid(grids, "2022")),
        *_format_window(_grid(grids, "2025-10-06..2026-06-30")),
        "## Combos that beat SMA-8 without giving back the crash filter",
        "",
        _qualifying_section(grids, winners, vs_sma8_crashes),
        "",
        "## 2024–now vs SMA-8's share of buy-and-hold",
        "",
        _closer_section(grids, closer, sma8_long_ratio),
        "",
        "## What I would not do",
        "",
        "I would not replace frozen SMA-8 with whichever cell printed the highest full-sample end dollars. That selection uses the same sample the table is scored on. If a later product rule needs a different SMA pair, freeze it first, then score — do not crown a winner from this map.",
        "",
        "## How to re-run",
        "",
        "```",
        ".venv/bin/python -m price_forecast.sma_asymmetric_10k",
        "```",
        "",
        "Writes `price_forecast/sma_asymmetric_10k_results.md`. State machine is `asymmetric_sma_signal` in `price_forecast/weekly_regime.py`. Dollar fills reuse `dollar_backtest`.",
        "",
    ]
    return "\n".join(lines)


def _lead(
    full: WindowGrid,
    top: list[tuple[tuple[int, int], DollarBacktestResult]],
    winners: list[tuple[int, int]],
    closer: list[tuple[int, int]],
    vs_sma8_crashes: list[tuple[int, int]],
    sma8_long_ratio: float,
) -> str:
    hold = full.buy_hold
    sma8 = full.sma8
    top_bits = ", ".join(
        f"{_combo_label(*combo)} {_usd(row.end_dollars)} (max DD {_pct(row.max_drawdown)})"
        for combo, row in top
    )
    n = len(frozen_combos())
    if winners:
        win_text = (
            f"{len(winners)} of {n} combos beat SMA-8 on full-sample end $ and still had "
            "max DD at least 10pp better than buy-and-hold on both crash windows. "
            "That bar is vs buy-and-hold, not vs SMA-8's own crash path. "
            f"{len(vs_sma8_crashes)} of those were also at least as shallow as SMA-8 on both crashes."
        )
    else:
        win_text = (
            "Nothing in the frozen grid beats SMA-8 on full-sample end $ while keeping "
            "max DD at least 10pp better than buy-and-hold on both crash windows."
        )
    if closer:
        closer_text = (
            f"On 2024–latest, {len(closer)} of {n} combos finished closer to buy-and-hold "
            f"than SMA-8 ({_pct(sma8_long_ratio)} of B&H end $) without giving back the "
            "2022 10pp-vs-B&H drawdown filter."
        )
    else:
        closer_text = (
            "On 2024–latest, no combo finished closer to buy-and-hold than SMA-8 "
            f"({_pct(sma8_long_ratio)} of B&H end $) without giving back the 2022 10pp "
            "drawdown filter."
        )
    return (
        f"Full sample after 40-week warmup, fresh ${STARTING_DOLLARS:,.0f} in BTC: "
        f"buy-and-hold ends {_usd(hold.end_dollars)} (max DD {_pct(hold.max_drawdown)}); "
        f"symmetric SMA-8 ends {_usd(sma8.end_dollars)} (max DD {_pct(sma8.max_drawdown)}); "
        f"symmetric SMA-12 ends {_usd(full.sma12.end_dollars)} (max DD {_pct(full.sma12.max_drawdown)}). "
        f"Highest full-sample cells: {top_bits}. {win_text} {closer_text} "
        "Do not treat the top cell as a new frozen rule."
    )


def _qualifying_section(
    grids: list[WindowGrid],
    winners: list[tuple[int, int]],
    vs_sma8_crashes: list[tuple[int, int]],
) -> str:
    if not winners:
        return (
            "None. Several cells can look better than SMA-8 on full-sample end dollars, "
            "or calmer than buy-and-hold in one crash, without clearing both crash windows "
            "and beating SMA-8 at the same time. Slow-sell / fast-buy is not a free upgrade."
        )
    full = _grid(grids, FULL_WINDOW)
    crash_2022 = _grid(grids, "2022")
    crash_late = _grid(grids, "2025-10-06..2026-06-30")
    bits = [
        "Pre-declared callout: beat SMA-8 on full-sample end $ AND max DD at least 10pp "
        "better than buy-and-hold on both crash windows. Crash dollars below are those "
        "window paths, not the full-sample path.",
        "",
    ]
    for combo in winners:
        row = full.combos[combo]
        c22 = crash_2022.combos[combo]
        c25 = crash_late.combos[combo]
        bits.append(
            f"- {_combo_label(*combo)}: full-sample end {_usd(row.end_dollars)} "
            f"(SMA-8 {_usd(full.sma8.end_dollars)}); "
            f"2022 max DD {_pct(c22.max_drawdown)} "
            f"(SMA-8 {_pct(crash_2022.sma8.max_drawdown)}, "
            f"B&H {_pct(crash_2022.buy_hold.max_drawdown)}); "
            f"2025–26 max DD {_pct(c25.max_drawdown)} "
            f"(SMA-8 {_pct(crash_late.sma8.max_drawdown)}, "
            f"B&H {_pct(crash_late.buy_hold.max_drawdown)})."
        )
    bits.append("")
    if vs_sma8_crashes:
        bits.append(
            "Of those, also at least as shallow as SMA-8 on both crash windows: "
            f"{_combo_list(vs_sma8_crashes)}. The rest still cleared 10pp vs buy-and-hold "
            "but gave back some of SMA-8's own crash cut (typically sell=12 in 2022, "
            "sell=40 in 2025–26)."
        )
    else:
        bits.append(
            "None of those cells were as shallow as SMA-8 on both crash windows. "
            "They beat SMA-8 on full-sample end $ only by giving back some of SMA-8's crash cut."
        )
    bits.append("Those cells are still in-sample grid picks, not a new frozen product rule.")
    return "\n".join(bits)


def _closer_section(
    grids: list[WindowGrid],
    closer: list[tuple[int, int]],
    sma8_ratio: float,
) -> str:
    long_run = _grid(grids, LONG_RUN_WINDOW)
    crash_2022 = _grid(grids, "2022")
    hold_end = long_run.buy_hold.end_dollars
    sma8 = long_run.sma8
    head = (
        f"SMA-8 ends {_usd(sma8.end_dollars)} vs buy-and-hold {_usd(hold_end)} "
        f"({_pct(sma8_ratio)} of B&H). SMA-8 total return {_pct(sma8.total_return)} "
        f"vs B&H {_pct(long_run.buy_hold.total_return)}. "
        "The 2022 filter here is 10pp vs buy-and-hold, the same bar SMA-8 itself clears."
    )
    if not closer:
        return (
            f"{head} No frozen combo both exceeded that SMA-8 share of buy-and-hold "
            "and kept 2022 max DD at least 10pp better than buy-and-hold."
        )
    vs_sma8_2022 = [
        combo
        for combo in closer
        if crash_2022.combos[combo].max_drawdown + 1e-12 >= crash_2022.sma8.max_drawdown
    ]
    bits = [head, "Combos that did both:"]
    for combo in closer:
        row = long_run.combos[combo]
        bits.append(
            f"- {_combo_label(*combo)}: end {_usd(row.end_dollars)} "
            f"({_pct(row.end_dollars / hold_end)} of B&H); "
            f"2022 max DD {_pct(crash_2022.combos[combo].max_drawdown)} "
            f"(SMA-8 {_pct(crash_2022.sma8.max_drawdown)})."
        )
    bits.append("")
    if vs_sma8_2022:
        bits.append(
            "Of those, 2022 max DD at least as shallow as SMA-8: "
            f"{_combo_list(vs_sma8_2022)}."
        )
    else:
        bits.append(
            "None of those 2024–latest cells also matched SMA-8's 2022 drawdown. "
            "They got closer to buy-and-hold by giving back some of SMA-8's 2022 cut."
        )
    return "\n".join(bits)


def _format_window(grid: WindowGrid) -> list[str]:
    hold = grid.buy_hold
    lines = [
        f"### {grid.window}",
        "",
        f"Anchors: {hold.start.isoformat()} → {hold.end.isoformat()} "
        f"({hold.n_intervals} weekly returns). "
        f"Start BTC price ${_price(hold.start_price)}; end ${_price(hold.end_price)}.",
        "",
        "| combo | End $ | Max DD $ | Max DD % | Total return | Time in BTC | Round trips | Fees $ | vs B&H end | vs SMA-8 end $ | vs SMA-8 max DD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        _metric_row("buy-and-hold", hold, hold, grid.sma8),
        _metric_row("SMA-8", grid.sma8, hold, grid.sma8),
        _metric_row("SMA-12", grid.sma12, hold, grid.sma8),
    ]
    for combo in frozen_combos():
        lines.append(
            _metric_row(_combo_label(*combo), grid.combos[combo], hold, grid.sma8)
        )
    lines.append("")
    return lines


def _metric_row(
    label: str,
    row: DollarBacktestResult,
    hold: DollarBacktestResult,
    sma8: DollarBacktestResult,
) -> str:
    vs_hold = row.end_dollars / hold.end_dollars
    vs_sma8_end = row.end_dollars - sma8.end_dollars
    vs_sma8_dd = row.max_drawdown - sma8.max_drawdown
    return (
        f"| {label} | {_usd(row.end_dollars)} | {_usd(row.max_drawdown_dollars)} | "
        f"{_pct(row.max_drawdown)} | {_pct(row.total_return)} | {_pct(row.time_in_btc)} | "
        f"{row.round_trips} | {_usd(row.fees_paid)} | {_pct(vs_hold)} | "
        f"{_usd_delta(vs_sma8_end)} | {_pp(vs_sma8_dd)} |"
    )


def _top_combos(
    grid: WindowGrid, n: int
) -> list[tuple[tuple[int, int], DollarBacktestResult]]:
    ranked = sorted(
        grid.combos.items(),
        key=lambda item: item[1].end_dollars,
        reverse=True,
    )
    return ranked[:n]


def _grid(grids: list[WindowGrid], window: str) -> WindowGrid:
    return next(row for row in grids if row.window == window)


def _combo_label(buy: int, sell: int) -> str:
    return f"buy{buy}/sell{sell}"


def _combo_list(combos: list[tuple[int, int]]) -> str:
    return ", ".join(_combo_label(*combo) for combo in combos)


def _usd(value: float) -> str:
    return f"${value:,.2f}"


def _usd_delta(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def _price(value: float) -> str:
    return f"{value:,.2f}"


def _pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def _pp(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}{100.0 * abs(value):.1f}pp"


def main() -> None:
    daily = load_daily_closes(
        source="coinbase",
        start=date(2018, 1, 1),
        end=datetime.now(timezone.utc).date(),
    )
    weeks = weekly_closes(daily)
    grids = score_grid(weeks)
    report = format_report(
        weeks,
        grids,
        daily_first=daily.dates()[0],
        daily_last=daily.dates()[-1],
        n_daily=len(daily.dates()),
    )
    out_path = Path(__file__).with_name("sma_asymmetric_10k_results.md")
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
