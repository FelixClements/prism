"""SMAGateV1: weekly BTC SMA-8 in / SMA-16 out. CLI orchestrator."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from price_forecast.data.candles import BTC_USD_DAILY_CSV, require_closes
from price_forecast.data.weekly import weekly_closes

BUY_WEEKS = 8
SELL_WEEKS = 16
FILL_COST = 0.0015
STARTING_DOLLARS = 10_000.0
WHIPSAW_MAX_HOLDING_BARS = 2
RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"


def main(argv: Sequence[str] | None = None) -> None:
    from price_forecast.backtest.engine import simulate_hodl, simulate_strategy
    from price_forecast.backtest.kpis import CHAPTER_SPECS, _monthly_from_paths, chapter_window, compute_kpis
    from price_forecast.backtest.reports import (
        format_compact_monthly_table,
        format_highlighted_chapters,
        format_monthly_csv,
        format_monthly_markdown,
        format_report,
    )

    parser = argparse.ArgumentParser(
        description="SMAGateV1: weekly BTC SMA-8 in / SMA-16 out same-bar KPIs vs buy-and-hold."
    )
    parser.add_argument(
        "--starting-dollars",
        type=float,
        default=STARTING_DOLLARS,
        help="Starting cash (default 10000).",
    )
    parser.add_argument("--csv", type=Path, default=BTC_USD_DAILY_CSV)
    args = parser.parse_args(argv)
    daily = require_closes(args.csv)
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
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "sma8_16_kpis_results.md"
    monthly_md_path = RESULTS_DIR / "sma8_16_kpis_monthly.md"
    monthly_csv_path = RESULTS_DIR / "sma8_16_kpis_monthly.csv"
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
