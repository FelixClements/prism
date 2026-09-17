"""Walk-forward loop: at each day t, forecast t+1/3/7/10 from data ≤ t."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping, Sequence

from price_forecast.predictors import Forecast, Predictor
from price_forecast.series import PriceSeries

HORIZONS: tuple[int, ...] = (1, 3, 7, 10)
WINDOWS: dict[str, tuple[date, date]] = {
    "2022": (date(2022, 1, 1), date(2022, 12, 31)),
    "2024-2026": (date(2024, 1, 1), date(2026, 12, 31)),
}


@dataclass(frozen=True)
class HorizonResult:
    window: str
    horizon_days: int
    n: int
    mae: float
    mape: float
    hit_rate: float
    coverage_80: float | None
    coverage_90: float | None


def evaluate(
    series: PriceSeries,
    predictor: Predictor,
    windows: Mapping[str, tuple[date, date]] | None = None,
    horizons: Sequence[int] | None = None,
) -> list[HorizonResult]:
    """Score a predictor walk-forward. Rows are window × horizon."""
    windows = windows or WINDOWS
    horizons = tuple(horizons or HORIZONS)
    rows: list[HorizonResult] = []
    for window_name, (start, end) in windows.items():
        scored: dict[int, list[tuple[float, Forecast, float]]] = {
            horizon: [] for horizon in horizons
        }
        for origin in _origins(series, start, end):
            history = series.as_of(origin)
            origin_price = history.last_close()
            forecasts = {
                item.horizon_days: item
                for item in predictor.forecast(history, origin, horizons)
            }
            for horizon in horizons:
                forecast = forecasts.get(horizon)
                if forecast is None:
                    raise ValueError(
                        f"{type(predictor).__name__} did not forecast horizon {horizon}"
                    )
                actual = series.actual_close(origin + timedelta(days=horizon))
                if actual is None:
                    continue
                scored[horizon].append((origin_price, forecast, actual))
        for horizon in horizons:
            rows.append(_score(window_name, horizon, scored[horizon]))
    return rows


def _origins(series: PriceSeries, start: date, end: date) -> list[date]:
    return [day for day in series.dates() if start <= day <= end]


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _score(
    window: str,
    horizon: int,
    rows: Sequence[tuple[float, Forecast, float]],
) -> HorizonResult:
    if not rows:
        return HorizonResult(
            window=window,
            horizon_days=horizon,
            n=0,
            mae=0.0,
            mape=0.0,
            hit_rate=0.0,
            coverage_80=None,
            coverage_90=None,
        )
    abs_errors = [abs(forecast.point - actual) for _origin, forecast, actual in rows]
    pct_errors = [
        abs(forecast.point - actual) / actual for _origin, forecast, actual in rows
    ]
    hits = [
        _sign(forecast.point - origin_price) == _sign(actual - origin_price)
        for origin_price, forecast, actual in rows
    ]
    n = len(rows)
    return HorizonResult(
        window=window,
        horizon_days=horizon,
        n=n,
        mae=sum(abs_errors) / n,
        mape=sum(pct_errors) / n,
        hit_rate=sum(hits) / n,
        coverage_80=_coverage(rows, "80"),
        coverage_90=_coverage(rows, "90"),
    )


def _coverage(
    rows: Sequence[tuple[float, Forecast, float]],
    level: str,
) -> float | None:
    inside: list[bool] = []
    for _origin, forecast, actual in rows:
        if level == "80":
            lower, upper = forecast.lower_80, forecast.upper_80
        else:
            lower, upper = forecast.lower_90, forecast.upper_90
        if lower is None or upper is None:
            return None
        inside.append(lower <= actual <= upper)
    return sum(inside) / len(inside)
