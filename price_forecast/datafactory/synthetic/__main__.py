"""Write synthetic regime candle paths.

Usage:
    python -m price_forecast.datafactory.synthetic
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Sequence

from price_forecast.data.candles import (
    BTC_USD_DAILY_CSV,
    SYNTHETIC_DIR,
    read_candles,
    require_closes,
    write_candles,
)
from price_forecast.datafactory.synthetic.fit import fit_tape
from price_forecast.datafactory.synthetic.label import label_candles
from price_forecast.datafactory.synthetic.paths import control_paths, synthetic_paths
from price_forecast.datafactory.synthetic.report import (
    format_synthetic_report,
    synthetic_report,
)


def write_regimes(path: Path, days: Sequence[str], regimes: Sequence[str]) -> None:
    if len(days) != len(regimes):
        raise ValueError("regime rows must align with candles")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("time", "regime"))
        writer.writerows(zip(days, regimes))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Write synthetic regime candle paths. Does not score a strategy."
    )
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--n-paths", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    source = BTC_USD_DAILY_CSV if args.csv is None else args.csv
    require_closes(source)
    if args.n_paths < 1:
        raise ValueError("n_paths must be at least 1")
    candles = read_candles(source)
    labeling = label_candles(candles)
    model = fit_tape(candles, labeling)
    paths = synthetic_paths(candles, model, n_paths=args.n_paths, seed=args.seed)
    controls = control_paths(candles, labeling, n_paths=args.n_paths, seed=args.seed)
    for index, path in enumerate(paths):
        stem = f"btc-usd-daily-seed{args.seed}-path{index}"
        write_candles(SYNTHETIC_DIR / f"{stem}.csv", path.candles)
        write_regimes(
            SYNTHETIC_DIR / f"{stem}-regimes.csv",
            [candle.day.isoformat() for candle in path.candles],
            path.regimes,
        )
    print(format_synthetic_report(synthetic_report(candles, paths, controls)))


if __name__ == "__main__":
    main()
