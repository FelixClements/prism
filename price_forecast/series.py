"""Daily close series with an as-of view that refuses future reads."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Iterable, Sequence


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
    """Deterministic daily series. A real BTC vendor can replace this later."""
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


def load_daily_closes(*, source: str = "synthetic", **kwargs) -> PriceSeries:
    """Loader seam. Only the synthetic stub is wired; pick a vendor later."""
    if source == "synthetic":
        return synthetic_daily(**kwargs)
    raise NotImplementedError(
        f"BTC vendor {source!r} is not wired yet; use source='synthetic'"
    )
