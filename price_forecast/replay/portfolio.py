"""Fractional-exposure replay: weekday-anchor ensembles and no-tuning sizing baselines.

    python -m price_forecast.replay.portfolio --strategy all

Writes ``results/replay/<candidate>.md`` for each scored candidate and
``results/replay/baselines_vs_crashgate.md`` with the head-to-head.

An *ensemble* runs one locked weekly rule on all seven weekday anchors. Each anchor is
a sleeve with 1/7 of the capital, so total BTC exposure moves in steps between 0 and 1
and no single anchor's luck decides the result. The *sizing baselines* are fixed in
``price_forecast/replay/sizing.py`` and were committed before they were first run.
Every candidate starts on the same day, so all rows share one HODL benchmark.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Sequence

import numpy as np

from price_forecast.data.candles import BTC_USD_DAILY_CSV, Candle, read_candles
from price_forecast.replay.book import (
    Book,
    BookMetrics,
    Decisions,
    TimingTest,
    book_metrics,
    book_weekly_returns,
    circular_shift_test,
    constant_decisions,
    hold_decisions,
    run_sleeves,
    sharpe_diff,
    slice_book,
    spell_shuffle_test,
)
from price_forecast.replay.engine import FILL_COST
from price_forecast.replay.robustness import WEEKDAYS, describe, neighbours
from price_forecast.replay.rules import STRATEGIES, LazyGate
from price_forecast.replay.selection import DeflatedSharpe, deflated_sharpe, load_ledger, sharpe_variance_per_week
from price_forecast.replay.sizing import SizingRule, describe_rule, sizing_decisions, sizing_neighbours
from price_forecast.search.runner import Gate, SpecSignal
from price_forecast.search.spec import Spec, spec_to_mapping
from price_forecast.strategies.indicators import weekly_bars

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results" / "replay"
LEDGER = ROOT / "results" / "search" / "ledger.jsonl"
POOL = ROOT / "results" / "search" / "pool.json"
ANCHORS = tuple(range(7))
FILL_GRID = (("same_close", 0.0), ("next_day", 0.0), ("next_day", 0.0010), ("next_day", 0.0030))
COMPARISON = "baselines_vs_crashgate"


@dataclass(frozen=True)
class Candidate:
    name: str
    label: str
    spec_name: str | None = None
    sizing: SizingRule | None = None
    anchors: tuple[int, ...] = (6,)
    scored: bool = True

    @property
    def binary(self) -> bool:
        return self.spec_name is not None

    @property
    def ensemble(self) -> bool:
        return len(self.anchors) > 1

    def rule(self) -> str:
        if self.spec_name is not None:
            return describe(STRATEGIES[self.spec_name]())
        assert self.sizing is not None
        return describe_rule(self.sizing)


CANDIDATES = (
    Candidate("crashgate_v1_ensemble", "CrashGateV1, 7-anchor ensemble", spec_name="crashgate_v1", anchors=ANCHORS),
    Candidate("smagate_v1_ensemble", "SMAGateV1, 7-anchor ensemble", spec_name="smagate_v1", anchors=ANCHORS),
    Candidate("voltarget", "Vol target 40%", sizing=SizingRule("voltarget")),
    Candidate("tsmom", "TSMOM average", sizing=SizingRule("tsmom")),
    Candidate("voltarget_tsmom", "Vol target × TSMOM", sizing=SizingRule("voltarget_tsmom")),
)
SINGLES = (
    Candidate("crashgate_v1_sunday", "CrashGateV1, Sunday only", spec_name="crashgate_v1", scored=False),
    Candidate("smagate_v1_sunday", "SMAGateV1, Sunday only", spec_name="smagate_v1", scored=False),
)
CHALLENGERS = ("crashgate_v1_sunday", "crashgate_v1_ensemble", "smagate_v1_ensemble")
BASELINES = ("voltarget", "tsmom", "voltarget_tsmom")


# --- decisions ------------------------------------------------------------------


def _spec_weeks(candles: Sequence[Candle], spec: Spec, gate: Gate, anchor: int):
    bars = weekly_bars(candles, week_end_weekday=anchor)
    weeks = [(bar.day, bar.close) for bar in bars]
    return weeks, SpecSignal(weeks, spec, gate, bars=bars)


def spec_decisions(
    candles: Sequence[Candle], spec: Spec, gate: Gate, anchor: int, start_day: date
) -> list[tuple[date, float]]:
    """0/1 targets of a locked rule on one anchor, from ``start_day``.

    The rule's state runs from its own first week, so a sleeve that starts later
    picks up whatever position the rule already holds.
    """
    weeks, signal = _spec_weeks(candles, spec, gate, anchor)
    position = 0
    out: list[tuple[date, float]] = []
    for index in range(signal.first, len(weeks) - 1):
        side = signal.decide(index, position)
        if side == "buy":
            position = 1
        elif side == "sell":
            position = 0
        if weeks[index][0] >= start_day:
            out.append((weeks[index][0], float(position)))
    return out


def natural_start(candles: Sequence[Candle], gate: Gate, candidate: Candidate) -> date:
    """First day every sleeve of ``candidate`` can make a decision."""
    days = []
    for anchor in candidate.anchors:
        if candidate.spec_name is not None:
            weeks, signal = _spec_weeks(candles, STRATEGIES[candidate.spec_name](), gate, anchor)
            days.append(weeks[signal.first][0])
        else:
            assert candidate.sizing is not None
            bars = weekly_bars(candles, week_end_weekday=anchor)
            days.append(bars[min(candidate.sizing.lookbacks)].day)
            if candidate.sizing.kind != "tsmom":
                days.append(candles[candidate.sizing.vol_com_days].day)
    return max(days)


@dataclass
class Context:
    candles: Sequence[Candle]
    gate: Gate
    start: date
    slippage: float
    books: dict[str, Book] = field(default_factory=dict)

    def run(self, sleeves: Sequence[Decisions], *, fill: str = "next_day", slippage: float | None = None) -> Book:
        return run_sleeves(
            self.candles,
            sleeves,
            start_day=self.start,
            fill=fill,
            cost=FILL_COST,
            slippage=self.slippage if slippage is None else slippage,
        )

    def sleeves(
        self,
        candidate: Candidate,
        *,
        spec: Spec | None = None,
        sizing: SizingRule | None = None,
        anchors: Sequence[int] | None = None,
    ) -> list[list[tuple[date, float]]]:
        anchors = candidate.anchors if anchors is None else anchors
        if candidate.spec_name is not None:
            rule = spec or STRATEGIES[candidate.spec_name]()
            return [spec_decisions(self.candles, rule, self.gate, a, self.start) for a in anchors]
        rule_sizing = sizing or candidate.sizing
        assert rule_sizing is not None
        return [sizing_decisions(self.candles, rule_sizing, anchor=a, start_day=self.start) for a in anchors]

    def hodl(self) -> Book:
        if "hodl" not in self.books:
            self.books["hodl"] = self.run([hold_decisions(self.start)], fill="same_close")
        return self.books["hodl"]


# --- formatting -----------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "n/a" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value * 100:,.1f}%"


def _num(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _usd(value: float) -> str:
    return f"${value:,.0f}"


METRIC_HEADER = (
    "| Run | Total return | CAGR | Max DD (daily) | Sharpe | Sortino | Avg exposure | Turnover/yr | Fills | End $ |\n"
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
)


def _row(label: str, result: BookMetrics) -> str:
    return (
        f"| {label} | {_pct(result.total_return)} | {_pct(result.cagr)} | {_pct(result.max_drawdown)} "
        f"| {_num(result.sharpe)} | {_num(result.sortino)} | {_pct(result.exposure)} "
        f"| {result.turnover:.1f}× | {result.trades} | {_usd(result.end_dollars)} |"
    )


@dataclass(frozen=True)
class Variant:
    label: str
    result: BookMetrics


def _variant_lines(variants: Sequence[Variant], hold: BookMetrics) -> list[str]:
    lines = [
        "| Variant | Total return | Edge vs HODL | CAGR | Max DD | Sharpe | Avg exposure | Turnover/yr |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in variants:
        r = item.result
        lines.append(
            f"| {item.label} | {_pct(r.total_return)} | {_pct(r.total_return - hold.total_return)} "
            f"| {_pct(r.cagr)} | {_pct(r.max_drawdown)} | {_num(r.sharpe)} | {_pct(r.exposure)} "
            f"| {r.turnover:.1f}× |"
        )
    beat = sum(1 for item in variants if item.result.total_return > hold.total_return)
    beat_sharpe = sum(1 for item in variants if (item.result.sharpe or 0.0) > (hold.sharpe or 0.0))
    sharpes = sorted(item.result.sharpe or 0.0 for item in variants)
    worst_dd = min(item.result.max_drawdown for item in variants)
    lines += [
        "",
        f"Beat HODL on total return: **{beat}/{len(variants)}**. "
        f"Beat HODL on Sharpe ({_num(hold.sharpe)}): **{beat_sharpe}/{len(variants)}**. "
        f"Sharpe min / median / max: {_num(sharpes[0])} / {_num(float(np.median(sharpes)))} / {_num(sharpes[-1])}. "
        f"Worst max DD: {_pct(worst_dd)}.",
    ]
    return lines


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool | None
    detail: str


def _mark(check: Check) -> str:
    return "–" if check.passed is None else ("PASS" if check.passed else "FAIL")


def _timing_lines(observed: BookMetrics, tests: Sequence[TimingTest]) -> list[str]:
    lines = [
        "| Test | Paths | Sharpe | Random median Sharpe | p (Sharpe) | p (total return) | p (max DD) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for test in tests:
        lines.append(
            f"| {test.name} | {test.runs:,} | {_num(observed.sharpe)} | {_num(test.sharpe_median)} "
            f"| {test.sharpe_p:.3f} | {test.total_return_p:.3f} | {test.drawdown_p:.3f} |"
        )
    return lines


# --- scorecard ------------------------------------------------------------------


@dataclass(frozen=True)
class Ledger:
    variance: float
    unique: int | None
    note: str


def _ledger(path: Path, pool: Path) -> Ledger:
    if not path.is_file():
        return Ledger(sharpe_variance_per_week([0.5, 1.0, 1.5]), None, "No search ledger found.")
    ledger = load_ledger(path, pool)
    variance = sharpe_variance_per_week(ledger.sharpes_ann)
    return Ledger(
        variance,
        len(ledger.unique_specs),
        f"Cross-trial Sharpe variance from `{path.name}` ({len(ledger.unique_specs):,} unique specs, "
        f"Sharpe SD {math.sqrt(variance * 52):.2f} annualised).",
    )


def score(candidate: Candidate, ctx: Context, ledger: Ledger, *, mc_runs: int, seed: int, csv: Path) -> str:
    started = time.time()
    sleeves = ctx.sleeves(candidate)
    book = ctx.books.get(candidate.name) or ctx.run(sleeves)
    ctx.books[candidate.name] = book
    strat = book_metrics(book)
    hold = book_metrics(ctx.hodl())

    # 1. Fill models
    fill_rows = [
        (f"{fill}, {slip * 10_000:g} bps", book_metrics(ctx.run(sleeves, fill=fill, slippage=slip)))
        for fill, slip in FILL_GRID
    ]

    # 2. Benchmarks
    mix = book_metrics(ctx.run([constant_decisions(book.days, ctx.start, strat.exposure)], fill="same_close"))
    tests = [circular_shift_test(ctx.candles, sleeves, strat, run=ctx.run)]
    if candidate.binary:
        tests.append(spell_shuffle_test(sleeves, strat, runs=mc_runs, seed=seed, run=ctx.run))

    # 3. Anchors
    if candidate.ensemble:
        single = [
            Variant(f"{WEEKDAYS[a]} sleeve alone", book_metrics(ctx.run([sleeves[i]])))
            for i, a in enumerate(candidate.anchors)
        ]
        loo = [
            Variant(f"without {WEEKDAYS[a]}", book_metrics(ctx.run([s for j, s in enumerate(sleeves) if j != i])))
            for i, a in enumerate(candidate.anchors)
        ]
    else:
        single = [
            Variant(f"{WEEKDAYS[a]} close", book_metrics(ctx.run(ctx.sleeves(candidate, anchors=[a]))))
            for a in ANCHORS
        ]
        loo = []

    # 4. Neighbours
    near: list[Variant] = []
    if candidate.spec_name is not None:
        for label, spec in neighbours(STRATEGIES[candidate.spec_name]()):
            near.append(Variant(label, book_metrics(ctx.run(ctx.sleeves(candidate, spec=spec)))))
    else:
        assert candidate.sizing is not None
        for label, rule in sizing_neighbours(candidate.sizing):
            near.append(Variant(label, book_metrics(ctx.run(ctx.sleeves(candidate, sizing=rule)))))

    # 5. Selection bias
    returns = book_weekly_returns(book)
    counts = [("1", 1), ("3", 3), ("10", 10), ("100", 100), ("1,000", 1000)]
    if ledger.unique:
        counts.append((f"{ledger.unique:,} (unique CrashGate ledger specs)", ledger.unique))
    dsr: list[tuple[str, DeflatedSharpe]] = [
        (label, deflated_sharpe(returns, n_trials=n, sharpe_variance=ledger.variance)) for label, n in counts
    ]
    if candidate.spec_name == "crashgate_v1" and ledger.unique:
        honest_label, honest = dsr[-1][0], dsr[-1][1]
        dsr_check = Check(f"Deflated Sharpe > 0.95 at N = {honest_label}", honest.dsr > 0.95, f"DSR = {honest.dsr:.3f}")
    elif candidate.sizing is not None:
        honest = dsr[1][1]
        dsr_check = Check("Deflated Sharpe > 0.95 at N = 3 (the pre-registered family)", honest.dsr > 0.95,
                          f"DSR = {honest.dsr:.3f}")
    else:
        dsr_check = Check("Deflated Sharpe > 0.95", None, "rule was not picked from the ledger; see section 5")

    beat_near = sum(1 for item in near if item.result.total_return > hold.total_return)
    checks = [
        Check("Edge over HODL survives the default fill", strat.total_return > hold.total_return,
              f"{_pct(strat.total_return)} vs HODL {_pct(hold.total_return)}"),
        Check("Sharpe above HODL", (strat.sharpe or 0.0) > (hold.sharpe or 0.0),
              f"{_num(strat.sharpe)} vs {_num(hold.sharpe)}"),
        Check("Beats constant exposure at the same average exposure (Sharpe)",
              (strat.sharpe or 0.0) > (mix.sharpe or 0.0), f"{_num(strat.sharpe)} vs {_num(mix.sharpe)}"),
        *[
            Check(f"Random timing, {test.name.split(' (')[0]}: Sharpe p < 0.05", test.sharpe_p < 0.05,
                  f"p = {test.sharpe_p:.3f}")
            for test in tests
        ],
    ]
    if candidate.ensemble:
        beat_loo = sum(1 for item in loo if item.result.total_return > hold.total_return)
        beat_single = sum(1 for item in single if item.result.total_return > hold.total_return)
        checks.append(Check("Every leave-one-anchor-out ensemble beats HODL", beat_loo == len(loo),
                            f"{beat_loo}/{len(loo)} (single sleeves: {beat_single}/{len(single)})"))
    else:
        beat_single = sum(1 for item in single if item.result.total_return > hold.total_return)
        checks.append(Check("At least 6 of 7 weekday anchors beat HODL", beat_single >= 6, f"{beat_single}/7"))
    checks += [
        Check("At least 80% of neighbours beat HODL", beat_near >= 0.8 * len(near), f"{beat_near}/{len(near)}"),
        dsr_check,
    ]

    spec_line = (
        f"Spec: `{json.dumps(spec_to_mapping(STRATEGIES[candidate.spec_name]()))}` on anchors "
        + ", ".join(WEEKDAYS[a] for a in candidate.anchors)
        if candidate.spec_name is not None
        else f"Sizing rule: `{candidate.sizing}` (frozen in `price_forecast/replay/sizing.py`)"
    )
    lines = [
        f"# Fractional replay — {candidate.name}",
        "",
        "Not investment advice. Generated by `python -m price_forecast.replay.portfolio`.",
        "",
        f"{candidate.label}. Rule: {candidate.rule()}  ",
        f"{spec_line}  ",
        f"Data: `{csv.name}` {ctx.candles[0].day} → {ctx.candles[-1].day}. Replay starts {ctx.start} "
        "(first day every candidate in the comparison can trade, so all share one HODL).  ",
        f"Cost {FILL_COST * 100:.2f}% of traded notional per fill. Default fill: **next_day, "
        f"{ctx.slippage * 10_000:g} bps slippage**. Equity marked daily; Sharpe from Sunday-to-Sunday returns.",
        "",
    ]
    if candidate.ensemble:
        lines += [
            "Each weekday anchor is a sleeve with 1/7 of the starting capital. Sleeves are never "
            "rebalanced against each other, so total exposure moves in steps of about 1/7.",
            "",
        ]
    lines += [
        "## Scorecard",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
        *[f"| {c.name} | {_mark(c)} | {c.detail} |" for c in checks],
        "",
        "## 1. Fill models",
        "",
        METRIC_HEADER,
        *[_row(label, result) for label, result in fill_rows],
        _row(f"HODL, {ctx.slippage * 10_000:g} bps", hold),
        "",
        "## 2. Benchmarks (default fill)",
        "",
        METRIC_HEADER,
        _row("Strategy", strat),
        _row("HODL", hold),
        _row(f"Constant {strat.exposure * 100:.0f}% exposure, weekly rebalance", mix),
        "",
        "Random timing. *Circular shift* rotates every sleeve's target series by the same number of weeks "
        "(at least 26 either way), keeping exposure, turnover and the series' own persistence. "
        + ("*Spell shuffle* reorders each sleeve's in-market and in-cash spell lengths, as in the all-in harness. "
           + ("Sleeves are shuffled independently, which breaks their correlation, so these random paths are "
              "smoother than the real ensemble and this null is harsher than the circular shift. "
              if candidate.ensemble else "")
           if candidate.binary else "")
        + "p is the share of random paths at least as good, +1 corrected.",
        "",
        *_timing_lines(strat, tests),
        "",
    ]
    if candidate.ensemble:
        lines += [
            "## 3. Anchors",
            "",
            "Each sleeve alone with all the capital, then the ensemble with one sleeve left out "
            "(capital split 1/6).",
            "",
            *_variant_lines(single, hold),
            "",
            *_variant_lines(loo, hold),
            "",
        ]
    else:
        lines += [
            "## 3. Weekday anchors",
            "",
            "Same rule, decisions on each weekday's close.",
            "",
            *_variant_lines(single, hold),
            "",
        ]
    lines += [
        "## 4. Neighbours",
        "",
        ("Every combination within one search-grid step of each knob, plus each gate toggled, "
         "each run as a 7-anchor ensemble." if candidate.spec_name is not None else
         "Fixed grid: vol target 30/40/50% × EWMA centre of mass 30/60/120 days, and each TSMOM "
         "lookback dropped in turn. Reported for robustness, never used to pick."),
        "",
        *_variant_lines(near, hold),
        "",
        "## 5. Selection bias",
        "",
        ledger.note,
        "",
        "| Trials N | E[max null Sharpe] | Sharpe | DSR |",
        "|---|---:|---:|---:|",
        *[f"| {label} | {d.expected_max_null_ann:.2f} | {d.sharpe_ann:.2f} | {d.dsr:.3f} |" for label, d in dsr],
        "",
        "## How to re-run",
        "",
        "```",
        f"python -m price_forecast.replay.portfolio --strategy {candidate.name} --csv <path to btc-usd-daily.csv>",
        "```",
        "",
        f"Runtime {time.time() - started:.0f}s.",
        "",
    ]
    return "\n".join(lines)


# --- head to head ---------------------------------------------------------------


def comparison(ctx: Context, *, csv: Path, boot_runs: int, seed: int) -> str:
    everyone = [*SINGLES, *CANDIDATES]
    for candidate in everyone:
        if candidate.name not in ctx.books:
            ctx.books[candidate.name] = ctx.run(ctx.sleeves(candidate))
    hold = ctx.hodl()
    labels = {c.name: c.label for c in everyone} | {"hodl": "HODL"}
    order = ["hodl", *[c.name for c in SINGLES], *[c.name for c in CANDIDATES]]

    full_lookback = weekly_bars(ctx.candles)[max(SizingRule("tsmom").lookbacks)].day
    later = {name: slice_book(ctx.books[name], full_lookback) for name in order}

    def table(books: dict[str, Book]) -> list[str]:
        return [METRIC_HEADER, *[_row(labels[name], book_metrics(books[name])) for name in order]]

    returns = {name: book_weekly_returns(ctx.books[name]) for name in order}
    late_returns = {name: book_weekly_returns(later[name]) for name in order}

    def duel_lines(series: dict[str, list[float]]) -> list[str]:
        lines = [
            "| Challenger | Baseline | Sharpe A | Sharpe B | Δ Sharpe | 90% CI | p (A not better) |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for a in CHALLENGERS:
            for b in (*BASELINES, "hodl"):
                d = sharpe_diff(series[a], series[b], runs=boot_runs, seed=seed)
                lines.append(
                    f"| {labels[a]} | {labels[b]} | {d.sharpe_a:.2f} | {d.sharpe_b:.2f} | {d.diff:+.2f} "
                    f"| {d.low:+.2f} … {d.high:+.2f} | {d.p_not_better:.3f} |"
                )
        return lines

    best = max(BASELINES, key=lambda name: book_metrics(ctx.books[name]).sharpe or 0.0)
    verdicts = []
    for a in CHALLENGERS:
        d = sharpe_diff(returns[a], returns[best], runs=boot_runs, seed=seed)
        earned = d.p_not_better < 0.05
        verdicts.append(
            f"- {labels[a]} vs best baseline ({labels[best]}): Δ Sharpe {d.diff:+.2f}, "
            f"p = {d.p_not_better:.3f} → {'beats it at p < 0.05' if earned else 'does not beat it at p < 0.05'}."
        )

    lines = [
        "# Baselines vs CrashGate",
        "",
        "Not investment advice. Generated by `python -m price_forecast.replay.portfolio --strategy all`.",
        "",
        f"Data: `{csv.name}` {ctx.candles[0].day} → {ctx.candles[-1].day}. All runs start {ctx.start}, "
        f"next-day fill, {FILL_COST * 100:.2f}% fee + {ctx.slippage * 10_000:g} bps slippage on traded notional, "
        "long-only, no leverage.",
        "",
        "Baselines (frozen before their first run, see `price_forecast/replay/sizing.py`):",
        "",
        *[f"- **{labels[name]}**: {describe_rule(SizingRule(name))}" for name in BASELINES],
        "",
        "## Verdict",
        "",
        *verdicts,
        "",
        "## Full window",
        "",
        *table(ctx.books | {"hodl": hold}),
        "",
        f"## From {full_lookback} (all TSMOM lookbacks exist)",
        "",
        "Same runs, rebased to this day, so TSMOM's warm-up with fewer lookbacks drops out. "
        "Costs before this day are not shown, and End $ is still from the original $10,000.",
        "",
        *table(later),
        "",
        "## Head to head",
        "",
        "Paired circular block bootstrap of Sunday-to-Sunday returns (13-week blocks, "
        f"{boot_runs:,} resamples). p is the share of resamples where the challenger's Sharpe is not higher.",
        "",
        "Full window:",
        "",
        *duel_lines(returns),
        "",
        f"From {full_lookback}:",
        "",
        *duel_lines(late_returns),
        "",
    ]
    return "\n".join(lines)


# --- main -----------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> None:
    names = [c.name for c in CANDIDATES]
    parser = argparse.ArgumentParser(description="Fractional-exposure replay: anchor ensembles and sizing baselines.")
    parser.add_argument("--strategy", choices=[*names, "all"], default="all")
    parser.add_argument("--csv", type=Path, default=BTC_USD_DAILY_CSV)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--mc-runs", type=int, default=2000)
    parser.add_argument("--boot-runs", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--pool", type=Path, default=POOL)
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    if not args.csv.is_file():
        raise SystemExit(f"missing {args.csv}. Run python -m price_forecast.data.candles or pass --csv")
    candles = read_candles(args.csv)
    gate = LazyGate(candles)
    start = max(natural_start(candles, gate, c) for c in (*SINGLES, *CANDIDATES))
    ctx = Context(candles, gate, start, args.slippage_bps / 10_000.0)
    ledger = _ledger(args.ledger, args.pool)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    chosen = CANDIDATES if args.strategy == "all" else [c for c in CANDIDATES if c.name == args.strategy]
    for candidate in chosen:
        text = score(candidate, ctx, ledger, mc_runs=args.mc_runs, seed=args.seed, csv=args.csv)
        out = args.out_dir / f"{candidate.name}.md"
        out.write_text(text, encoding="utf-8")
        print(f"Wrote {out}", flush=True)
    if args.strategy == "all":
        text = comparison(ctx, csv=args.csv, boot_runs=args.boot_runs, seed=args.seed)
        out = args.out_dir / f"{COMPARISON}.md"
        out.write_text(text, encoding="utf-8")
        print(text)
        print(f"Wrote {out}", flush=True)


if __name__ == "__main__":
    main()
