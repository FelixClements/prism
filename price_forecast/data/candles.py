"""OHLC candle CSV and candlestick PNG. PriceSeries stays close-only."""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from price_forecast.data.series import PriceSeries, fetch_coinbase_ohlc

HEADER = ("time", "low", "high", "open", "close", "volume")
BTC_USD_DAILY_CSV = Path(__file__).resolve().parents[2] / "data" / "btc-usd-daily.csv"
REMIX_DIR = BTC_USD_DAILY_CSV.parent / "remix"
COINBASE_START = date(2018, 1, 1)


@dataclass(frozen=True)
class Candle:
    day: date
    low: float
    high: float
    open: float
    close: float
    volume: float | None


def candle_face(open_px: float, close_px: float) -> str:
    if close_px > open_px:
        return "green"
    return "red"


def closes_from_candles(candles: Sequence[Candle]) -> PriceSeries:
    return PriceSeries((candle.day, candle.close) for candle in candles)


def require_closes(path: Path) -> PriceSeries:
    if not Path(path).is_file():
        print(
            f"missing {path}. Run python -m price_forecast.data.candles",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return closes_from_candles(read_candles(path))


def read_candles(path: Path) -> tuple[Candle, ...]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != HEADER:
            raise ValueError("header must be time,low,high,open,close,volume")
        candles = tuple(_candle_from_row(row) for row in reader)
    _validate(candles)
    return candles


def write_candles(path: Path, candles: Sequence[Candle]) -> None:
    rows = _validate(candles)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    csv_tmp = dest.with_name(dest.name + ".tmp")
    png_path = dest.with_suffix(".png")
    png_tmp = png_path.with_name(png_path.name + ".tmp")
    try:
        _write_csv(csv_tmp, rows)
        draw_candle_chart(rows, png_tmp)
        os.replace(png_tmp, png_path)
        os.replace(csv_tmp, dest)
    except Exception:
        csv_tmp.unlink(missing_ok=True)
        png_tmp.unlink(missing_ok=True)
        raise


def draw_candle_chart(candles: Sequence[Candle], png_path: Path) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle

    rows = _validate(candles)
    fig = Figure(figsize=(12, 5))
    ax = fig.add_subplot(1, 1, 1)
    xs = list(range(len(rows)))
    for x, candle in zip(xs, rows):
        color = candle_face(candle.open, candle.close)
        ax.vlines(x, candle.low, candle.high, color=color, linewidth=0.6)
        body_low = min(candle.open, candle.close)
        height = abs(candle.close - candle.open)
        if height == 0.0:
            height = candle.close * 0.0005
            body_low = candle.close - height / 2
        ax.add_patch(
            Rectangle((x - 0.3, body_low), 0.6, height, facecolor=color, edgecolor=color)
        )
    step = max(1, len(rows) // 8)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels(
        [rows[i].day.isoformat() for i in xs[::step]], rotation=30, ha="right"
    )
    ax.set_xlim(-1, len(rows))
    fig.tight_layout()
    out = Path(png_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    FigureCanvasAgg(fig).print_png(out)


def parse_coinbase_ohlc(rows: Sequence[Sequence[float]]) -> tuple[Candle, ...]:
    by_day: dict[date, Candle] = {}
    for row in rows:
        if len(row) < 6:
            raise ValueError("coinbase candle is missing volume")
        day = datetime.fromtimestamp(int(row[0]), tz=timezone.utc).date()
        candle = Candle(
            day,
            float(row[1]),
            float(row[2]),
            float(row[3]),
            float(row[4]),
            float(row[5]),
        )
        by_day[day] = candle
    return _validate(tuple(by_day[day] for day in sorted(by_day)))


def update_coinbase_file(
    path: Path,
    *,
    today: date,
    fetch: Callable[[date, date], Sequence[Sequence[float]]],
) -> None:
    dest = Path(path)
    if dest.is_file():
        existing = read_candles(dest)
        start = existing[-1].day
    else:
        existing = ()
        start = COINBASE_START
    fetched = parse_coinbase_ohlc(fetch(start, today))
    if existing:
        last = existing[-1].day
        fetched_days = {candle.day for candle in fetched}
        if last in fetched_days:
            kept = tuple(candle for candle in existing if candle.day < last)
            fresh = tuple(candle for candle in fetched if candle.day >= last)
            rows = kept + fresh
        else:
            fresh = tuple(candle for candle in fetched if candle.day > last)
            rows = existing + fresh
    else:
        rows = fetched
    write_candles(dest, rows)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Download or extend data/btc-usd-daily.csv from Coinbase and write its PNG."
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=datetime.now(timezone.utc).date(),
        help="UTC end date (default: today).",
    )
    args = parser.parse_args(argv)
    update_coinbase_file(BTC_USD_DAILY_CSV, today=args.today, fetch=fetch_coinbase_ohlc)


def _validate(candles: Sequence[Candle]) -> tuple[Candle, ...]:
    rows = tuple(candles)
    if not rows:
        raise ValueError("no candles")
    previous: date | None = None
    for candle in rows:
        if previous is not None and candle.day <= previous:
            raise ValueError(f"dates must be strictly increasing, got {candle.day}")
        previous = candle.day
        for name, value in (
            ("low", candle.low),
            ("high", candle.high),
            ("open", candle.open),
            ("close", candle.close),
        ):
            if not math.isfinite(value) or not (value > 0):
                raise ValueError(f"{name} must be positive")
        if candle.high < candle.open or candle.high < candle.close:
            raise ValueError(f"high below open or close on {candle.day}")
        if candle.low > candle.open or candle.low > candle.close:
            raise ValueError(f"low above open or close on {candle.day}")
        if candle.volume is not None and (
            not math.isfinite(candle.volume) or not (candle.volume >= 0)
        ):
            raise ValueError(f"volume must be blank or >= 0 on {candle.day}")
    return rows


def _candle_from_row(row: dict[str, str | None]) -> Candle:
    raw_day = row.get("time") or ""
    try:
        day = datetime.strptime(raw_day, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"time {raw_day!r} is not YYYY-MM-DD") from exc
    if day.isoformat() != raw_day.strip():
        raise ValueError(f"time {raw_day!r} is not YYYY-MM-DD")
    return Candle(
        day,
        _price(row.get("low"), "low"),
        _price(row.get("high"), "high"),
        _price(row.get("open"), "open"),
        _price(row.get("close"), "close"),
        _volume(row.get("volume")),
    )


def _price(raw: str | None, name: str) -> float:
    if raw is None or raw.strip() == "":
        raise ValueError(f"{name} is missing")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} is not a number") from exc
    if not math.isfinite(value) or not (value > 0):
        raise ValueError(f"{name} must be positive")
    return value


def _volume(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("volume is not a number") from exc
    if not math.isfinite(value) or not (value >= 0):
        raise ValueError("volume must be blank or >= 0")
    return value


def _write_csv(path: Path, candles: Sequence[Candle]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADER)
        for candle in candles:
            volume = "" if candle.volume is None else format(candle.volume, ".12g")
            writer.writerow(
                [
                    candle.day.isoformat(),
                    format(candle.low, ".12g"),
                    format(candle.high, ".12g"),
                    format(candle.open, ".12g"),
                    format(candle.close, ".12g"),
                    volume,
                ]
            )


if __name__ == "__main__":
    main()
