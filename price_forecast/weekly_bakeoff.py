"""Weekly in/out bakeoff. Frozen rules; no retuning after seeing the table.

Usage:
    .venv/bin/python -m price_forecast.weekly_bakeoff
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from price_forecast.fng import FNG_API_URL, FNG_SOURCE, load_fng
from price_forecast.series import (
    BTC_CLOSE_PRODUCT,
    BTC_CLOSE_SOURCE,
    BTC_CLOSE_TIMEZONE,
    load_daily_closes,
)
from price_forecast.weekly_regime import (
    COST_BPS,
    FNG_FEAR_ENTRY,
    FNG_GREED_EXIT,
    WEALTH_FLOOR,
    BacktestResult,
    align_fng_to_weeks,
    apply_fng_overlay,
    backtest,
    donchian_signal,
    dual_sma_signal,
    fng_only_signal,
    pass_a,
    pass_c,
    sma_signal,
    weekly_closes,
)

STRATEGIES = [
    "buy-hold",
    "sma-8",
    "sma-12",
    "dual-sma-12-26",
    "donchian-12",
    "sma-8+fng",
    "sma-12+fng",
    "dual-sma-12-26+fng",
    "donchian-12+fng",
    "fng-only",
]

CRASH_WINDOWS = ("2022", "2025-10-06..2026-06-30")
LONG_RUN_WINDOW = "2024-01-01..latest"
DUAL_MA_SLOW = 26

WINDOWS: dict[str, tuple[date, date | None]] = {
    "2022": (date(2022, 1, 1), date(2022, 12, 31)),
    "2025-10-06..2026-06-30": (date(2025, 10, 6), date(2026, 6, 30)),
    LONG_RUN_WINDOW: (date(2024, 1, 1), None),
}


@dataclass(frozen=True)
class WindowScore:
    strategy: str
    window: str
    result: BacktestResult
    buy_hold: BacktestResult
    pass_c: bool
    pass_a: bool


def strategy_signals(
    name: str,
    weeks: list[tuple[date, float]],
    fng_aligned: list[int | None],
) -> list[int | None]:
    if name == "buy-hold":
        return [1] * len(weeks)
    if name == "sma-8":
        return sma_signal(weeks, lookback=8)
    if name == "sma-12":
        return sma_signal(weeks, lookback=12)
    if name == "dual-sma-12-26":
        return dual_sma_signal(weeks, fast=12, slow=DUAL_MA_SLOW)
    if name == "donchian-12":
        return donchian_signal(weeks, lookback=12)
    if name.endswith("+fng"):
        base = strategy_signals(name.removesuffix("+fng"), weeks, fng_aligned)
        return apply_fng_overlay(base, fng_aligned)
    if name == "fng-only":
        return list(fng_only_signal(fng_aligned))
    raise KeyError(name)


def window_specs(
    weeks: list[tuple[date, float]],
) -> dict[str, tuple[date, date]]:
    latest = weeks[-1][0]
    specs = {}
    for name, (start, end) in WINDOWS.items():
        specs[name] = (start, end or latest)
    if len(weeks) > DUAL_MA_SLOW:
        specs["full-after-warmup"] = (weeks[DUAL_MA_SLOW][0], latest)
    return specs


def score_windows(
    weeks: list[tuple[date, float]],
    fng_aligned: list[int | None],
) -> dict[str, list[WindowScore]]:
    specs = window_specs(weeks)
    hold = strategy_signals("buy-hold", weeks, fng_aligned)
    by_window: dict[str, list[WindowScore]] = {}
    for window, (start, end) in specs.items():
        bh = backtest(weeks, hold, start=start, end=end)
        rows = []
        for name in STRATEGIES:
            result = backtest(weeks, strategy_signals(name, weeks, fng_aligned), start=start, end=end)
            if name == "buy-hold":
                c_ok, a_ok = False, False
            else:
                c_ok = pass_c(result, bh)
                a_ok = pass_a(result, bh)
            rows.append(
                WindowScore(
                    strategy=name,
                    window=window,
                    result=result,
                    buy_hold=bh,
                    pass_c=c_ok,
                    pass_a=a_ok,
                )
            )
        by_window[window] = rows
    return by_window


def winner_line(by_window: dict[str, list[WindowScore]]) -> str:
    if any(name not in by_window for name in CRASH_WINDOWS):
        return "Winner: none passed C or A on both crash windows."
    c_winners: list[str] = []
    a_winners: list[str] = []
    for name in STRATEGIES:
        if name == "buy-hold":
            continue
        crash_rows = []
        missing = False
        for window in CRASH_WINDOWS:
            match = next((row for row in by_window[window] if row.strategy == name), None)
            if match is None:
                missing = True
                break
            crash_rows.append(match)
        if missing:
            continue
        if all(row.pass_c for row in crash_rows):
            c_winners.append(name)
        elif all(row.pass_a for row in crash_rows):
            a_winners.append(name)
    if c_winners:
        return f"Winner (C on both crash windows): {', '.join(c_winners)}."
    if a_winners:
        return f"Winner (A only on both crash windows): {', '.join(a_winners)}."
    return "Winner: none passed C or A on both crash windows."


def product_c_names(by_window: dict[str, list[WindowScore]]) -> list[str]:
    """C on both crashes and long-run wealth within 10% of buy-and-hold."""
    if LONG_RUN_WINDOW not in by_window:
        return []
    names = []
    for name in STRATEGIES:
        if name == "buy-hold":
            continue
        crash_ok = True
        for window in CRASH_WINDOWS:
            if window not in by_window:
                crash_ok = False
                break
            row = next(r for r in by_window[window] if r.strategy == name)
            if not row.pass_c:
                crash_ok = False
                break
        if not crash_ok:
            continue
        long_run = next(r for r in by_window[LONG_RUN_WINDOW] if r.strategy == name)
        if long_run.result.terminal_wealth >= WEALTH_FLOOR * long_run.buy_hold.terminal_wealth:
            names.append(name)
    return names


def fng_coverage(
    weeks: list[tuple[date, float]],
    fng_aligned: list[int | None],
    start: date,
    end: date,
) -> tuple[int, int]:
    have = 0
    total = 0
    for (week_end, _close), value in zip(weeks, fng_aligned, strict=True):
        if start <= week_end <= end:
            total += 1
            if value is not None:
                have += 1
    return have, total


def format_report(
    weeks: list[tuple[date, float]],
    fng_aligned: list[int | None],
    by_window: dict[str, list[WindowScore]],
    *,
    daily_first: date,
    daily_last: date,
    n_daily: int,
    fng_first: date | None,
    fng_last: date | None,
) -> str:
    lines = [
        "# Weekly in/out bakeoff",
        "",
        "Not investment advice. Frozen rules; no lookback or F&G-threshold search after seeing results.",
        "",
        "## Exact rules",
        "",
        f"- Series: weekly close from daily {BTC_CLOSE_PRODUCT} {BTC_CLOSE_SOURCE} ({BTC_CLOSE_TIMEZONE}).",
        f"- Daily history: {daily_first.isoformat()} to {daily_last.isoformat()} ({n_daily} days).",
        f"- Weeks: UTC Monday–Sunday. Bar date is Sunday. Weekly close = last UTC daily close in that week. Incomplete trailing weeks dropped.",
        f"- Weekly bars: {weeks[0][0].isoformat()} to {weeks[-1][0].isoformat()} ({len(weeks)} weeks).",
        "- Fill: signal at week t close executes at week t+1 close. Start inherited 100% BTC. Cash return = 0.",
        f"- Costs: {COST_BPS} bps of wealth each way on every flip (20 bps round trip). No liquidation cost at window end. No fee on the inherited opening long.",
        "- SMA 8 / SMA 12: 100% BTC iff weekly close > SMA including this week; else 100% cash.",
        "- Dual SMA: classic crossover, 100% BTC iff 12-week SMA > 26-week SMA (both include this week); else cash.",
        "- Donchian 12: 100% BTC iff close >= max of the prior 12 weeks excluding this week; else cash. Channel is leakage-safe (this week is not inside its own high).",
        f"- F&G source: {FNG_SOURCE}. Endpoint `{FNG_API_URL}`.",
        f"- F&G align: last index with UTC date <= that week's Sunday. No interpolation.",
        f"- F&G overlay (one overlay, not a grid): if F&G > {FNG_GREED_EXIT}, force cash (cannot re-enter; if in, exit). F&G does not force a buy. Missing F&G leaves the base signal.",
        f"- F&G-only: F&G > {FNG_GREED_EXIT} cash; F&G < {FNG_FEAR_ENTRY} BTC; else keep previous (start BTC).",
        f"- C pass: max DD at least 10 percentage points better than buy-and-hold AND terminal wealth >= {WEALTH_FLOOR:.0%} of buy-and-hold.",
        "- A pass: max DD at least 10 percentage points better than buy-and-hold.",
        "- Product C also needs long-run (2024-01-01 through latest) terminal wealth within 10% of buy-and-hold.",
        "- Full-after-warmup starts at the weekly close that can fill a 26-week dual SMA (common start for every strategy).",
        "- Window start = last weekly close on or before the window's start date; end = last weekly close on or before the window's end date.",
        "",
    ]
    if fng_first is None:
        lines.append("- F&G history: none downloaded.")
    else:
        lines.append(
            f"- F&G history: {fng_first.isoformat()} to {fng_last.isoformat()} "
            f"({sum(1 for v in fng_aligned if v is not None)} of {len(weeks)} weekly bars have an index)."
        )
    lines.append("")
    lines.append("## Scoreboard")
    lines.append("")
    for window, rows in by_window.items():
        bh = rows[0].buy_hold
        have, total = fng_coverage(weeks, fng_aligned, bh.start, bh.end)
        lines.append(f"### {window}")
        lines.append("")
        lines.append(
            f"Anchors: {bh.start.isoformat()} → {bh.end.isoformat()} "
            f"({bh.n_intervals} weekly returns). "
            f"F&G coverage: {have}/{total} weekly bars in this span."
        )
        if have < total:
            lines.append(
                "Overlay skipped on weeks with no F&G print (base signal used; no invented values)."
            )
        lines.append("")
        lines.append(
            "| Strategy | Terminal $1 | vs B&H | Max DD | B&H DD | Time in BTC | Round trips | C? | A? |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |")
        for row in rows:
            vs = row.result.terminal_wealth / row.buy_hold.terminal_wealth
            c_mark = "—" if row.strategy == "buy-hold" else ("yes" if row.pass_c else "no")
            a_mark = "—" if row.strategy == "buy-hold" else ("yes" if row.pass_a else "no")
            lines.append(
                "| {name} | {term} | {vs} | {dd} | {bhdd} | {tin} | {rt} | {c} | {a} |".format(
                    name=row.strategy,
                    term=f"{row.result.terminal_wealth:.3f}",
                    vs=f"{vs:.3f}",
                    dd=_fmt_dd(row.result.max_drawdown),
                    bhdd=_fmt_dd(row.buy_hold.max_drawdown),
                    tin=f"{100.0 * row.result.time_in_btc:.1f}%",
                    rt=row.result.round_trips,
                    c=c_mark,
                    a=a_mark,
                )
            )
        lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(winner_line(by_window))
    product = product_c_names(by_window)
    if product:
        lines.append(
            "Product C (C on both crash windows and long-run wealth not much worse): "
            + ", ".join(product)
            + "."
        )
    else:
        lines.append(
            "Product C (C on both crash windows and long-run wealth not much worse): none."
        )
    lines.append("")
    lines.append(_fng_overlay_blurb(by_window))
    lines.append("")
    lines.append("Command: `.venv/bin/python -m price_forecast.weekly_bakeoff`")
    lines.append("")
    return "\n".join(lines)


def _fmt_dd(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def _fng_overlay_blurb(by_window: dict[str, list[WindowScore]]) -> str:
    pairs = [
        ("sma-8", "sma-8+fng"),
        ("sma-12", "sma-12+fng"),
        ("dual-sma-12-26", "dual-sma-12-26+fng"),
        ("donchian-12", "donchian-12+fng"),
    ]

    def _compare(window: str) -> tuple[str, list[str]]:
        helped = 0
        hurt = 0
        same = 0
        details = []
        for base, over in pairs:
            rows = {row.strategy: row for row in by_window[window]}
            before, after = rows[base], rows[over]
            delta = after.result.max_drawdown - before.result.max_drawdown
            wealth_delta = after.result.terminal_wealth - before.result.terminal_wealth
            if delta > 1e-12:
                helped += 1
                tag = "helped DD"
            elif delta < -1e-12:
                hurt += 1
                tag = "hurt DD"
            else:
                same += 1
                tag = "same DD"
            details.append(
                f"{over} vs {base} on {window}: {tag} "
                f"({_fmt_dd(before.result.max_drawdown)} → {_fmt_dd(after.result.max_drawdown)}, "
                f"wealth {before.result.terminal_wealth:.3f} → {after.result.terminal_wealth:.3f}, "
                f"Δwealth {wealth_delta:+.3f})."
            )
        if helped and not hurt:
            headline = f"{window}: overlay helped crash/path DD."
        elif hurt and not helped:
            headline = f"{window}: overlay hurt DD."
        elif not helped and not hurt:
            headline = f"{window}: overlay unchanged DD."
        else:
            headline = f"{window}: overlay mixed on DD."
        return headline, details

    crash = [w for w in CRASH_WINDOWS if w in by_window]
    if not crash:
        return "F&G overlay: not scored on crash windows."
    crash_headlines = []
    crash_details = []
    crash_unchanged = True
    for window in crash:
        headline, details = _compare(window)
        crash_headlines.append(headline)
        crash_details.extend(details)
        if "unchanged DD" not in headline:
            crash_unchanged = False
    if crash_unchanged:
        headline = "F&G overlay: nothing on the two crash windows (DD and wealth identical to the un-overlaid sibling)."
    else:
        headline = "F&G overlay on crash windows: " + " ".join(crash_headlines)
    extra = []
    for window in (LONG_RUN_WINDOW, "full-after-warmup"):
        if window in by_window:
            h, d = _compare(window)
            extra.append(h)
            extra.extend(d)
    return headline + " " + " ".join(crash_details + extra)


def main() -> None:
    daily = load_daily_closes(
        source="coinbase",
        start=date(2018, 1, 1),
        end=datetime.now(timezone.utc).date(),
    )
    weeks = weekly_closes(daily)
    fng_daily = load_fng()
    fng_aligned = align_fng_to_weeks(weeks, fng_daily)
    by_window = score_windows(weeks, fng_aligned)
    fng_days = sorted(fng_daily)
    report = format_report(
        weeks,
        fng_aligned,
        by_window,
        daily_first=daily.dates()[0],
        daily_last=daily.dates()[-1],
        n_daily=len(daily.dates()),
        fng_first=fng_days[0] if fng_days else None,
        fng_last=fng_days[-1] if fng_days else None,
    )
    out_path = Path(__file__).with_name("weekly_bakeoff_results.md")
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
