"""Daily close series with an as-of view that refuses future reads.

Real BTC closes come from Coinbase Exchange public daily candles (BTC-USD).
Each bar is the UTC calendar-day close (granularity 86400, unix time in UTC).
The synthetic loader stays for unit tests.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BTC_CLOSE_SOURCE = "coinbase"
BTC_CLOSE_TIMEZONE = "UTC"
BTC_CLOSE_PRODUCT = "BTC-USD"
_COINBASE_CANDLES_URL = (
    f"https://api.exchange.coinbase.com/products/{BTC_CLOSE_PRODUCT}/candles"
)
_COINBASE_MAX_CANDLES = 300
_COINBASE_USER_AGENT = "prism-price-forecast/0.1"


class LeakageError(Exception):
    """Raised when a predictor reads a close after its origin timestamp."""


class PriceSeries:
    """Sorted daily closes. Pass `as_of(t)` into models so they cannot see t+1."""

    def __init__(
        self,
        bars: Iterable[tuple[date, float]],
        *,
        origin: date | None = None,
    ) -> None:
        cleaned = tuple(sorted(bars, key=lambda bar: bar[0]))
        dates = [day for day, _price in cleaned]
        if len(dates) != len(set(dates)):
            raise ValueError("duplicate dates in price series")
        if any(price <= 0 for _day, price in cleaned):
            raise ValueError("closes must be positive")
        self._bars = cleaned
        self._by_date = dict(cleaned)
        self._origin = origin

    def as_of(self, origin: date) -> PriceSeries:
        visible = [(day, price) for day, price in self._bars if day <= origin]
        if not visible:
            raise ValueError(f"no history on or before {origin}")
        return PriceSeries(visible, origin=origin)

    def close_at(self, day: date) -> float:
        if self._origin is not None and day > self._origin:
            raise LeakageError(
                f"predictor read close at {day}, after origin {self._origin}"
            )
        try:
            return self._by_date[day]
        except KeyError:
            raise KeyError(f"no close on {day}") from None

    def last_close(self) -> float:
        return self._bars[-1][1]

    def dates(self) -> Sequence[date]:
        return [day for day, _price in self._bars]

    def actual_close(self, day: date) -> float | None:
        """Unguarded lookup for scoring. Models should not call this."""
        if self._origin is not None and day > self._origin:
            raise LeakageError(
                f"predictor read close at {day}, after origin {self._origin}"
            )
        return self._by_date.get(day)


def synthetic_daily(
    start: date,
    end: date,
    *,
    start_price: float = 100.0,
    daily_return: float = 0.0,
) -> PriceSeries:
    """Deterministic daily series used by unit tests. Real BTC is `source='coinbase'`."""
    if end < start:
        raise ValueError("end before start")
    bars: list[tuple[date, float]] = []
    price = start_price
    day = start
    step = timedelta(days=1)
    while day <= end:
        bars.append((day, price))
        price *= math.exp(daily_return)
        day += step
    return PriceSeries(bars)


def bars_from_coinbase_candles(
    candles: Sequence[Sequence[float]],
) -> list[tuple[date, float]]:
    """Parse Coinbase `[time, low, high, open, close, volume]` rows to UTC dates."""
    by_day: dict[date, float] = {}
    for row in candles:
        if len(row) < 5:
            raise ValueError("coinbase candle is missing a close")
        ts = int(row[0])
        close = float(row[4])
        if close <= 0:
            raise ValueError("closes must be positive")
        day = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        by_day[day] = close
    return sorted(by_day.items(), key=lambda bar: bar[0])


def load_coinbase_btc_usd(
    *,
    start: date | None = None,
    end: date | None = None,
) -> PriceSeries:
    """Download daily BTC-USD closes from Coinbase. Times are UTC."""
    start = start or date(2018, 1, 1)
    end = end or datetime.now(timezone.utc).date()
    if end < start:
        raise ValueError("end before start")
    candles: list[Sequence[float]] = []
    chunk_start = start
    span = timedelta(days=_COINBASE_MAX_CANDLES - 1)
    one = timedelta(days=1)
    while chunk_start <= end:
        chunk_end = min(chunk_start + span, end)
        candles.extend(_fetch_coinbase_candles(chunk_start, chunk_end))
        chunk_start = chunk_end + one
    bars = bars_from_coinbase_candles(candles)
    if not bars:
        raise ValueError("coinbase returned no BTC-USD daily closes")
    return PriceSeries(bars)


def _fetch_coinbase_candles(start: date, end: date) -> list[Sequence[float]]:
    query = urlencode(
        {
            "granularity": 86400,
            "start": _utc_midnight_iso(start),
            "end": _utc_midnight_iso(end),
        }
    )
    request = Request(
        f"{_COINBASE_CANDLES_URL}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": _COINBASE_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(
            f"coinbase candles HTTP {exc.code} for {start.isoformat()}..{end.isoformat()}"
        ) from exc
    except URLError as exc:
        raise RuntimeError("coinbase candles request failed") from exc
    if not isinstance(payload, list):
        raise RuntimeError("coinbase candles payload was not a list")
    return payload


def _utc_midnight_iso(day: date) -> str:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT00:00:00Z"
    )


def load_daily_closes(*, source: str = "synthetic", **kwargs) -> PriceSeries:
    """Load a daily close series. `synthetic` is the unit-test stub; `coinbase` is real BTC."""
    if source == "synthetic":
        return synthetic_daily(**kwargs)
    if source == BTC_CLOSE_SOURCE:
        return load_coinbase_btc_usd(**kwargs)
    raise NotImplementedError(
        f"BTC vendor {source!r} is not wired; use source='synthetic' or source='coinbase'"
    )
