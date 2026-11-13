"""Daily funding aggregation and the pre-registered funding features.

Day assignment (no lookahead): a print's timestamp is rounded to the nearest
minute and assigned to the UTC calendar day it falls in. A print stamped
exactly 00:00 UTC on day D+1 therefore belongs to D+1, not D, even though it
coincides with D's close. Day D's value thus uses the 00:00, 08:00 and 16:00
UTC prints of D, all strictly before the D close at 24:00 UTC.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Mapping, Sequence

from price_forecast.funding.fetch import FundingPrint

MS_PER_MIN = 60_000
MS_PER_DAY = 86_400_000
EPOCH = date(1970, 1, 1)
PRINTS_PER_DAY = 3  # 8h funding interval
WINDOW_DAYS = 7


def print_day(time_ms: int) -> date:
    rounded = round(time_ms / MS_PER_MIN) * MS_PER_MIN
    return EPOCH + timedelta(days=rounded // MS_PER_DAY)


def daily_funding(prints: Iterable[FundingPrint]) -> dict[date, float]:
    """Daily rate = 3 x mean of the day's prints (= the sum when all 3 exist)."""
    buckets: dict[date, list[float]] = {}
    for p in prints:
        buckets.setdefault(print_day(p.time_ms), []).append(p.rate)
    return {d: PRINTS_PER_DAY * sum(v) / len(v) for d, v in sorted(buckets.items())}


def trailing_mean(daily: Mapping[date, float], window: int = WINDOW_DAYS) -> dict[date, float]:
    """Mean of daily values over [D-window+1, D]; defined only if every day exists."""
    out: dict[date, float] = {}
    for d in sorted(daily):
        vals = [daily.get(d - timedelta(days=i)) for i in range(window)]
        if all(v is not None for v in vals):
            out[d] = sum(vals) / window  # type: ignore[arg-type]
    return out


def venue_average(series: Sequence[Mapping[date, float]]) -> dict[date, float]:
    """Equal-weight mean across venues, defined only on days all venues have."""
    common = set(series[0])
    for s in series[1:]:
        common &= set(s)
    return {d: sum(s[d] for s in series) / len(series) for d in sorted(common)}


def build_features(prints_by_venue: Mapping[str, Iterable[FundingPrint]]) -> dict[str, dict[date, float]]:
    """Feature name -> {signal day: value}. Names: '<venue>_f7' and 'venue_avg_f7'."""
    f7 = {venue: trailing_mean(daily_funding(prints)) for venue, prints in prints_by_venue.items()}
    features = {f"{venue}_f7": series for venue, series in f7.items()}
    if len(f7) > 1:
        features["venue_avg_f7"] = venue_average(list(f7.values()))
    return features
