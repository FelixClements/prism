"""Perpetual funding-rate history from free public APIs, cached as CSV.

Venues (BitMEX stopped trading on 2026-09-23 and its API returns 403):
- ``bybit_btcusd``: Bybit inverse (coin-margined) BTCUSD perp, from 2018-11-15.
- ``binance_btcusdt``: Binance USDT-margined BTCUSDT perp, from 2019-09-10.

Each cache file holds one row per funding print: ``funding_time_ms,rate``,
where ``rate`` is the per-interval rate as a fraction (0.0001 = 0.01%).
Run ``python -m price_forecast.funding.fetch`` to create or extend the cache.
"""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import requests

FUNDING_DIR = Path(__file__).resolve().parents[2] / "data" / "funding"
HEADER = ("funding_time_ms", "rate")
USER_AGENT = "prism-research/0.1"

BYBIT_URL = "https://api.bybit.com/v5/market/funding/history"
BINANCE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
BYBIT_START_MS = 1_541_030_400_000  # 2018-11-01, before the first print
BINANCE_START_MS = 1_567_296_000_000  # 2019-09-01, before the first print


@dataclass(frozen=True)
class FundingPrint:
    time_ms: int
    rate: float


GetJson = Callable[[str, dict], object]


def http_get_json(url: str, params: dict, *, attempts: int = 5) -> object:
    """GET with exponential backoff on 429/5xx and network errors."""
    delay = 1.0
    for attempt in range(attempts):
        try:
            resp = requests.get(url, params=params, timeout=30, headers={"User-Agent": USER_AGENT})
        except requests.RequestException:
            if attempt == attempts - 1:
                raise
        else:
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code not in (418, 429) and resp.status_code < 500:
                raise RuntimeError(f"{url} -> HTTP {resp.status_code}: {resp.text[:200]}")
            if attempt == attempts - 1:
                raise RuntimeError(f"{url} -> HTTP {resp.status_code} after {attempts} tries")
        time.sleep(delay)
        delay *= 2
    raise AssertionError("unreachable")


def fetch_binance(start_ms: int, *, get: GetJson = http_get_json, symbol: str = "BTCUSDT") -> list[FundingPrint]:
    """All prints with time >= start_ms. Binance pages ascending, 1000 per call."""
    out: list[FundingPrint] = []
    cursor = start_ms
    while True:
        rows = get(BINANCE_URL, {"symbol": symbol, "startTime": cursor, "limit": 1000})
        if not isinstance(rows, list):
            raise RuntimeError(f"unexpected Binance payload: {str(rows)[:200]}")
        batch = [FundingPrint(int(r["fundingTime"]), float(r["fundingRate"])) for r in rows]
        batch = [p for p in batch if p.time_ms >= cursor]
        if not batch:
            return out
        out.extend(batch)
        cursor = max(p.time_ms for p in batch) + 1
        if len(rows) < 1000:
            return out


def fetch_bybit(start_ms: int, *, get: GetJson = http_get_json, symbol: str = "BTCUSD", now_ms: int | None = None) -> list[FundingPrint]:
    """All prints with time >= start_ms. Bybit pages newest-first, so walk endTime back."""
    out: list[FundingPrint] = []
    end = int(time.time() * 1000) if now_ms is None else now_ms
    while end >= start_ms:
        payload = get(BYBIT_URL, {"category": "inverse", "symbol": symbol, "endTime": end, "limit": 200})
        if not isinstance(payload, dict) or payload.get("retCode") != 0:
            raise RuntimeError(f"unexpected Bybit payload: {str(payload)[:200]}")
        rows = payload["result"]["list"]
        batch = [FundingPrint(int(r["fundingRateTimestamp"]), float(r["fundingRate"])) for r in rows]
        batch = [p for p in batch if start_ms <= p.time_ms <= end]
        if not batch:
            break
        out.extend(batch)
        end = min(p.time_ms for p in batch) - 1
    return sorted(out, key=lambda p: p.time_ms)


VENUES: dict[str, tuple[Callable[..., list[FundingPrint]], int]] = {
    "bybit_btcusd": (fetch_bybit, BYBIT_START_MS),
    "binance_btcusdt": (fetch_binance, BINANCE_START_MS),
}


def read_prints(path: Path) -> list[FundingPrint]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != HEADER:
            raise ValueError(f"{path}: header must be {','.join(HEADER)}")
        prints = [FundingPrint(int(r["funding_time_ms"]), float(r["rate"])) for r in reader]
    return merge_prints(prints)


def write_prints(path: Path, prints: Iterable[FundingPrint]) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for p in merge_prints(prints):
            writer.writerow((p.time_ms, repr(p.rate)))
    tmp.replace(dest)


def merge_prints(prints: Iterable[FundingPrint]) -> list[FundingPrint]:
    """Sort by time and keep one print per timestamp (the last one seen)."""
    by_time: dict[int, FundingPrint] = {}
    for p in prints:
        by_time[p.time_ms] = p
    return [by_time[t] for t in sorted(by_time)]


def update_venue(venue: str, cache_dir: Path = FUNDING_DIR, *, get: GetJson = http_get_json) -> Path:
    fetcher, first_ms = VENUES[venue]
    path = Path(cache_dir) / f"{venue}.csv"
    cached = read_prints(path) if path.is_file() else []
    start = cached[-1].time_ms + 1 if cached else first_ms
    fresh = fetcher(start, get=get)
    write_prints(path, [*cached, *fresh])
    return path


def load_venue(venue: str, cache_dir: Path = FUNDING_DIR) -> list[FundingPrint]:
    path = Path(cache_dir) / f"{venue}.csv"
    if not path.is_file():
        raise SystemExit(f"missing {path}. Run python -m price_forecast.funding.fetch")
    return read_prints(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--venue", choices=[*VENUES, "all"], default="all")
    parser.add_argument("--cache-dir", type=Path, default=FUNDING_DIR)
    args = parser.parse_args(argv)
    venues = list(VENUES) if args.venue == "all" else [args.venue]
    for venue in venues:
        path = update_venue(venue, args.cache_dir)
        prints = read_prints(path)
        first = time.strftime("%Y-%m-%d %H:%M", time.gmtime(prints[0].time_ms / 1000))
        last = time.strftime("%Y-%m-%d %H:%M", time.gmtime(prints[-1].time_ms / 1000))
        print(f"{venue}: {len(prints)} prints {first} .. {last} UTC -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
