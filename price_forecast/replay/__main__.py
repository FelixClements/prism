"""Frozen replay: does a locked weekly rule survive honest fills, anchors, neighbours and selection bias?

    python -m price_forecast.replay --strategy crashgate_v1

Writes ``results/replay/<strategy>.md``.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

import numpy as np

from price_forecast.data.candles import BTC_USD_DAILY_CSV, Candle, read_candles
from price_forecast.replay.benchmarks import RandomTiming, constant_exposure, hodl, random_timing
from price_forecast.replay.engine import FILL_COST, Metrics, metrics, replay, weekly_returns
from price_forecast.replay.robustness import Variant, describe, anchor_sweep, neighbour_sweep
from price_forecast.replay.selection import (
    DeflatedSharpe,
    Pbo,
    cscv_pbo,
    deflated_sharpe,
    load_ledger,
    sharpe_variance_per_week,
)
from price_forecast.search.runner import SpecSignal, simulate_spec
from price_forecast.search.spec import Spec, locked_crashgate, spec_from_mapping, spec_to_mapping
from price_forecast.strategies.indicators import weekly_bars

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results" / "replay"
CACHE_DIR = RESULTS_DIR / "cache"
LEDGER = ROOT / "results" / "search" / "ledger.jsonl"
POOL = ROOT / "results" / "search" / "pool.json"

STRATEGIES = {
    "crashgate_v1": locked_crashgate,
    "smagate_v1": lambda: Spec(mode="threshold", close_above_sma_weeks=8, close_below_sma_weeks=16),
}
FILL_GRID = (
    ("same_close", 0.0),
    ("next_day", 0.0),
    ("next_day", 0.0010),
    ("next_day", 0.0030),
    ("next_week", 0.0),
    ("next_week", 0.0010),
)


class LazyGate:
    """Builds the VCP gate only if a spec actually asks for it."""

    def __init__(self, candles: Sequence[Candle]) -> None:
        self._candles = candles
        self._gate = None

    def __call__(self, day: date) -> tuple[bool, bool]:
        if self._gate is None:
            from price_forecast.strategies.crashgate_entry import BaseBreakoutGate

            self._gate = BaseBreakoutGate(self._candles)
        return self._gate.parts(day)


# --- ledger return matrix -------------------------------------------------------

_WORKER: dict = {}


def _init_worker(candles, gate) -> None:
    bars = weekly_bars(candles)
    _WORKER["bars"] = bars
    _WORKER["weeks"] = [(bar.day, bar.close) for bar in bars]
    _WORKER["gate"] = gate


def _spec_returns(mapping: dict) -> tuple[date, list[float]] | None:
    try:
        spec = spec_from_mapping(mapping)
        path = simulate_spec(_WORKER["weeks"], spec, _WORKER["gate"], bars=_WORKER["bars"], cost=FILL_COST)
    except Exception:
        return None
    equity = path.equity
    returns = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]
    return path.start, returns


def ledger_matrix(candles, gate, specs: list[dict], *, workers: int) -> np.ndarray:
    """Weekly returns of every ledger spec on the Coinbase tape, aligned on a common start."""
    _init_worker(candles, gate)
    for day, _close in _WORKER["weeks"]:
        try:
            gate(day)
        except Exception:
            break
    if workers > 1:
        context = multiprocessing.get_context("fork")
        with context.Pool(workers) as pool:
            results = pool.map(_spec_returns, specs, chunksize=64)
    else:
        results = [_spec_returns(spec) for spec in specs]
    # A spec sits in cash until its longest lookback exists, so pad those weeks with 0.
    position = {day: index for index, (day, _close) in enumerate(_WORKER["weeks"])}
    transitions = len(_WORKER["weeks"]) - 1
    columns = []
    for item in results:
        if item is None or not item[1]:
            continue
        start, returns = item
        column = np.zeros(transitions)
        offset = position[start]
        column[offset : offset + len(returns)] = returns
        columns.append(column)
    matrix = np.array(columns, dtype=float).T
    active = np.flatnonzero(np.abs(matrix).sum(axis=1) > 0.0)
    matrix = matrix[active[0] :] if active.size else matrix
    return np.unique(matrix.round(12), axis=1)


# --- formatting -----------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:,.1f}%"


def _num(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _usd(value: float) -> str:
    return f"${value:,.0f}"


def _metric_row(label: str, result: Metrics) -> str:
    return (
        f"| {label} | {_pct(result.total_return)} | {_pct(result.cagr)} | {_pct(result.max_drawdown)} "
        f"| {_num(result.sharpe)} | {result.round_trips} | {_pct(result.exposure)} | {_usd(result.end_dollars)} |"
    )


METRIC_HEADER = (
    "| Run | Total return | CAGR | Max DD (daily) | Sharpe | Trips | Exposure | End $ |\n"
    "|---|---:|---:|---:|---:|---:|---:|---:|"
)


def _variant_table(variants: Sequence[Variant]) -> list[str]:
    lines = [
        "| Variant | Total return | HODL same start | Edge | CAGR | Max DD | Sharpe | Trips |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in variants:
        result = item.result
        lines.append(
            f"| {item.label} | {_pct(result.total_return)} | {_pct(item.hodl.total_return)} "
            f"| {_pct(item.edge)} | {_pct(result.cagr)} | {_pct(result.max_drawdown)} "
            f"| {_num(result.sharpe)} | {result.round_trips} |"
        )
    return lines


def _spread(variants: Sequence[Variant]) -> str:
    edges = sorted(item.edge for item in variants)
    sharpes = sorted(item.result.sharpe or 0.0 for item in variants)
    drawdowns = sorted(item.result.max_drawdown for item in variants)
    beat = sum(1 for edge in edges if edge > 0.0)
    shallower = sum(1 for item in variants if item.result.max_drawdown > item.hodl.max_drawdown)
    return (
        f"Beat HODL on total return: **{beat}/{len(edges)}**. "
        f"Shallower max DD than HODL: **{shallower}/{len(edges)}**. "
        f"Edge min / median / max: {_pct(edges[0])} / {_pct(float(np.median(edges)))} / {_pct(edges[-1])}. "
        f"Sharpe min / median / max: {_num(sharpes[0])} / {_num(float(np.median(sharpes)))} / {_num(sharpes[-1])}. "
        f"Worst max DD: {_pct(drawdowns[0])}."
    )


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool | None
    detail: str


def _check_mark(check: Check) -> str:
    if check.passed is None:
        return "–"
    return "PASS" if check.passed else "FAIL"


# --- main -----------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Frozen replay harness for a locked weekly BTC rule.")
    parser.add_argument("--strategy", choices=sorted(STRATEGIES), default="crashgate_v1")
    parser.add_argument("--csv", type=Path, default=BTC_USD_DAILY_CSV)
    parser.add_argument("--fill", choices=("same_close", "next_day", "next_week"), default="next_day")
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--mc-runs", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--pool", type=Path, default=POOL)
    parser.add_argument("--skip-pbo", action="store_true")
    parser.add_argument("--pbo-blocks", type=int, default=16)
    parser.add_argument("--workers", type=int, default=max(1, (multiprocessing.cpu_count() or 2) - 1))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if not args.csv.is_file():
        raise SystemExit(f"missing {args.csv}. Run python -m price_forecast.data.candles or pass --csv")
    started = time.time()
    candles = read_candles(args.csv)
    spec = STRATEGIES[args.strategy]()
    gate = LazyGate(candles)
    slippage = args.slippage_bps / 10_000.0
    default_kwargs = {"fill": args.fill, "cost": FILL_COST, "slippage": slippage}
    default_label = f"{args.fill}, {args.slippage_bps:g} bps slippage"

    bars = weekly_bars(candles)
    weeks = [(bar.day, bar.close) for bar in bars]
    signal = SpecSignal(weeks, spec, gate, bars=bars)
    first = signal.first

    # 1. Fill models
    fill_rows = []
    for fill, slip in FILL_GRID:
        path = replay(candles, weeks, signal, fill=fill, cost=FILL_COST, slippage=slip)
        fill_rows.append((f"{fill}, {slip * 10_000:g} bps", metrics(path), path))
    hold_path = hodl(candles, weeks, first, cost=FILL_COST, slippage=slippage)
    hold = metrics(hold_path)

    # 2. Benchmarks under the default fill
    strat_path = replay(candles, weeks, signal, **default_kwargs)
    strat = metrics(strat_path)
    mix = metrics(constant_exposure(candles, weeks, first, strat.exposure, cost=FILL_COST, slippage=slippage))
    timing: RandomTiming = random_timing(
        candles, weeks, strat_path, first, runs=args.mc_runs, seed=args.seed, **default_kwargs
    )

    # 3. Anchors and 4. neighbours
    anchors = anchor_sweep(candles, spec, gate, **default_kwargs)
    try:
        near = neighbour_sweep(candles, spec, gate, **default_kwargs)
    except ValueError:
        near = []

    # 5. Selection bias
    dsr_rows: list[tuple[str, DeflatedSharpe, DeflatedSharpe]] = []
    pbo: Pbo | None = None
    ledger_note = "No search ledger found, so trial counts are illustrative only."
    search_path = replay(candles, weeks, signal, fill="next_week", cost=FILL_COST, slippage=0.0)
    search_returns = weekly_returns(search_path)
    default_returns = weekly_returns(strat_path)
    variance = sharpe_variance_per_week([item.result.sharpe or 0.0 for item in near] or [0.0, 0.0])
    trial_counts: list[tuple[str, int]] = [("1 (no search)", 1), ("10", 10), ("100", 100), ("1,000", 1000)]
    if args.ledger.is_file():
        ledger = load_ledger(args.ledger, args.pool)
        variance = sharpe_variance_per_week(ledger.sharpes_ann)
        trial_counts.append((f"{len(ledger.unique_specs):,} (unique ledger specs)", len(ledger.unique_specs)))
        trial_counts.append((f"{ledger.scored:,} (scored ledger rows)", ledger.scored))
        ledger_note = (
            f"Ledger `{args.ledger.name}`: {ledger.rows:,} rows, {ledger.scored:,} scored, "
            f"{len(ledger.unique_specs):,} unique specs. Cross-spec Sharpe SD "
            f"{math.sqrt(variance) * math.sqrt(52):.2f} (annualised)."
        )
        if not args.skip_pbo and len(ledger.unique_specs) > 1:
            cache = CACHE_DIR / f"ledger_returns_v2_{len(ledger.unique_specs)}.npz"
            if cache.is_file():
                matrix = np.load(cache)["matrix"]
            else:
                matrix = ledger_matrix(candles, gate, ledger.unique_specs, workers=args.workers)
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(cache, matrix=matrix)
            pbo = cscv_pbo(matrix, blocks=args.pbo_blocks)
    else:
        ledger_note += " Cross-trial Sharpe variance taken from the neighbour sweep."
    for label, count in trial_counts:
        dsr_rows.append(
            (
                label,
                deflated_sharpe(search_returns, n_trials=count, sharpe_variance=variance),
                deflated_sharpe(default_returns, n_trials=count, sharpe_variance=variance),
            )
        )

    # Scorecard
    picked_from_ledger = args.strategy == "crashgate_v1"
    honest = next((row for row in dsr_rows if "unique" in row[0]), dsr_rows[-1])
    ledger_dsr = honest[2]
    checks = [
        Check(
            "Edge over HODL survives the default fill",
            strat.total_return > hold.total_return,
            f"{_pct(strat.total_return)} vs HODL {_pct(hold.total_return)}",
        ),
        Check(
            "Beats constant exposure at the same average exposure (Sharpe)",
            (strat.sharpe or 0.0) > (mix.sharpe or 0.0),
            f"Sharpe {_num(strat.sharpe)} vs {_num(mix.sharpe)}",
        ),
        Check(
            "Random timing with the same spells: Sharpe p < 0.05",
            timing.sharpe_p < 0.05,
            f"p = {timing.sharpe_p:.3f}",
        ),
        Check(
            "At least 6 of 7 weekday anchors beat HODL",
            sum(1 for item in anchors if item.edge > 0.0) >= 6,
            f"{sum(1 for item in anchors if item.edge > 0.0)}/7",
        ),
        Check(
            "At least 80% of parameter neighbours beat HODL",
            (sum(1 for item in near if item.edge > 0.0) >= 0.8 * len(near)) if near else None,
            f"{sum(1 for item in near if item.edge > 0.0)}/{len(near)}" if near else "spec has no grid",
        ),
        Check(
            f"Deflated Sharpe > 0.95 at N = {honest[0]}",
            (ledger_dsr.dsr > 0.95) if picked_from_ledger else None,
            f"DSR = {ledger_dsr.dsr:.3f}"
            if picked_from_ledger
            else "rule was not picked from this ledger; see the N table in section 5",
        ),
        Check(
            "Search PBO < 0.2",
            (pbo.pbo < 0.2) if pbo and picked_from_ledger else None,
            (f"PBO = {pbo.pbo:.2f}" if pbo else "not run")
            + ("" if picked_from_ledger else " (CrashGate search, not this rule's)"),
        ),
    ]

    lines = [
        f"# Frozen replay — {args.strategy}",
        "",
        "Not investment advice. Generated by `python -m price_forecast.replay`.",
        "",
        f"Spec: `{json.dumps(spec_to_mapping(spec))}`  ",
        f"Rule: {describe(spec)}  ",
        f"Data: `{args.csv.name}` {candles[0].day} → {candles[-1].day}. "
        f"Replay starts {weeks[first][0]} (first week every lookback exists).  ",
        f"Cost {FILL_COST * 100:.2f}% per fill. Default fill model for sections 2–4: **{default_label}**. "
        "Equity is marked daily, so max DD includes mid-week moves.",
        "",
        "## Scorecard",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
        *[f"| {check.name} | {_check_mark(check)} | {check.detail} |" for check in checks],
        "",
        "## 1. Fill models",
        "",
        "`same_close` fills at the close that made the signal (SMAGateV1 style, not tradable). "
        "`next_day` fills at the next daily close. `next_week` fills at the next weekly close "
        "(what the CrashGate search scored).",
        "",
        METRIC_HEADER,
        *[_metric_row(label, result) for label, result, _path in fill_rows],
        _metric_row(f"HODL, {args.slippage_bps:g} bps", hold),
        "",
        f"## 2. Benchmarks ({default_label})",
        "",
        METRIC_HEADER,
        _metric_row("Strategy", strat),
        _metric_row("HODL", hold),
        _metric_row(f"Constant {strat.exposure * 100:.0f}% exposure, weekly rebalance", mix),
        "",
        f"Random timing: {timing.runs:,} paths that keep the strategy's own in-market and in-cash spell "
        "lengths (so exposure and trade count match) but shuffle their order.",
        "",
        "| Metric | Strategy | Random median | Strategy percentile | p (random ≥ strategy) |",
        "|---|---:|---:|---:|---:|",
        f"| Total return | {_pct(strat.total_return)} | {_pct(timing.total_return_median)} "
        f"| {timing.total_return_pct * 100:.1f} | {timing.total_return_p:.3f} |",
        f"| Sharpe | {_num(strat.sharpe)} | {_num(timing.sharpe_median)} "
        f"| {timing.sharpe_pct * 100:.1f} | {timing.sharpe_p:.3f} |",
        f"| Max DD | {_pct(strat.max_drawdown)} | {_pct(timing.drawdown_median)} "
        f"| {timing.drawdown_pct * 100:.1f} | {timing.drawdown_p:.3f} |",
        "",
        f"## 3. Weekday anchors ({default_label})",
        "",
        "Same rule, weekly bars ending on each weekday. Each row is compared with HODL from its own start.",
        "",
        *_variant_table(anchors),
        "",
        _spread(anchors),
        "",
        f"## 4. Parameter neighbours ({default_label})",
        "",
    ]
    if near:
        lines += [
            "Every combination within one grid step of each numeric knob (search grid in "
            "`price_forecast/search/spec.py`), plus each gate switched on or off.",
            "",
            *_variant_table(near),
            "",
            _spread(near),
            "",
        ]
    else:
        lines += ["This spec has no grid to step on.", ""]
    lines += [
        "## 5. Selection bias",
        "",
        ledger_note,
        "",
        "Deflated Sharpe: the probability the true Sharpe beats the best Sharpe expected from N "
        "skill-less trials. Above 0.95 is the usual bar. The ledger counts only the CrashGate breed; "
        "the earlier SMA search and bakeoff are not in it, so the real N is higher.",
        "",
        "| Trials N | E[max null Sharpe] | Sharpe (search fills) | DSR (search fills) | Sharpe (default fill) | DSR (default fill) |",
        "|---|---:|---:|---:|---:|---:|",
        *[
            f"| {label} | {search.expected_max_null_ann:.2f} | {search.sharpe_ann:.2f} | {search.dsr:.3f} "
            f"| {default.sharpe_ann:.2f} | {default.dsr:.3f} |"
            for label, search, default in dsr_rows
        ],
        "",
    ]
    if pbo:
        lines += [
            f"CSCV probability of backtest overfitting over {pbo.strategies:,} distinct ledger return streams, "
            f"{pbo.weeks} weeks in {pbo.blocks} blocks ({pbo.splits:,} splits), next-week fills as searched:",
            "",
            "| PBO | Median logit | Picked strategy loses OOS | Median IS Sharpe of pick | Median OOS Sharpe of pick |",
            "|---:|---:|---:|---:|---:|",
            f"| {pbo.pbo:.2f} | {pbo.median_logit:.2f} | {_pct(pbo.oos_loss_rate)} "
            f"| {pbo.is_sharpe_median_ann:.2f} | {pbo.oos_sharpe_median_ann:.2f} |",
            "",
            "PBO is the share of splits where the in-sample winner ranks at or below the median out of sample. "
            "Near 0 means the search's ranking carries over; 0.5 means picking the winner is a coin flip.",
            "",
        ]
    lines += [
        "## How to re-run",
        "",
        "```",
        f"python -m price_forecast.replay --strategy {args.strategy} --csv <path to btc-usd-daily.csv>",
        "```",
        "",
        f"Runtime {time.time() - started:.0f}s.",
        "",
    ]
    text = "\n".join(lines)
    out = args.out or RESULTS_DIR / f"{args.strategy}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"Wrote {out}", flush=True)


if __name__ == "__main__":
    main()
