"""Predictors share one forecast API. ARIMA plugs in here later."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Protocol, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from price_forecast.series import PriceSeries


@dataclass(frozen=True)
class Forecast:
    origin: date
    horizon_days: int
    point: float
    lower_80: float | None = None
    upper_80: float | None = None
    lower_90: float | None = None
    upper_90: float | None = None


class Predictor(Protocol):
    def forecast(
        self,
        history: PriceSeries,
        origin: date,
        horizons: Sequence[int],
    ) -> Sequence[Forecast]:
        """Return one price forecast per horizon using only history ≤ origin."""


class LastValuePredictor:
    """Tomorrow's price is today's close, at every horizon."""

    def forecast(
        self,
        history: PriceSeries,
        origin: date,
        horizons: Sequence[int],
    ) -> list[Forecast]:
        last = history.last_close()
        return [
            Forecast(origin=origin, horizon_days=horizon, point=last)
            for horizon in horizons
        ]


class ZeroReturnPredictor:
    """Zero log-return from today's close. Same point as last-value for now."""

    def forecast(
        self,
        history: PriceSeries,
        origin: date,
        horizons: Sequence[int],
    ) -> list[Forecast]:
        last = history.last_close()
        return [
            Forecast(
                origin=origin,
                horizon_days=horizon,
                point=last * math.exp(0.0 * horizon),
            )
            for horizon in horizons
        ]
