"""ARIMA+GARCH must share the predictor API, stay as-of, and emit bands."""

from __future__ import annotations

import math
import random
from datetime import date, timedelta

import pytest

from price_forecast import (
    HORIZONS,
    ArimaGarchPredictor,
    Forecast,
    LeakageError,
    evaluate,
)
from price_forecast.series import PriceSeries


def _noisy_daily(
    start: date,
    end: date,
    *,
    start_price: float,
    mean_return: float = 0.0005,
    shock_vol: float = 0.02,
    seed: int = 0,
) -> PriceSeries:
    rng = random.Random(seed)
    bars: list[tuple[date, float]] = []
    price = start_price
    day = start
    step = timedelta(days=1)
    while day <= end:
        bars.append((day, price))
        price *= math.exp(mean_return + rng.gauss(0.0, shock_vol))
        day += step
    return PriceSeries(bars)


class PeekingPredictor:
    def forecast(self, history, origin, horizons):
        leaked = history.close_at(origin + timedelta(days=1))
        return [Forecast(origin=origin, horizon_days=h, point=leaked) for h in horizons]


def test_peeking_model_is_still_rejected_when_arima_is_present():
    series = _noisy_daily(
        date(2024, 1, 1),
        date(2024, 2, 15),
        start_price=40_000.0,
        seed=1,
    )
    with pytest.raises(LeakageError):
        evaluate(
            series,
            PeekingPredictor(),
            windows={"leak": (date(2024, 1, 1), date(2024, 1, 31))},
            horizons=HORIZONS,
        )


def test_arima_garch_does_not_read_past_origin():
    series = _noisy_daily(
        date(2022, 1, 1),
        date(2022, 3, 15),
        start_price=20_000.0,
        seed=2,
    )
    table = evaluate(
        series,
        ArimaGarchPredictor(),
        windows={"2022q1": (date(2022, 2, 1), date(2022, 2, 20))},
        horizons=HORIZONS,
    )
    assert table
    assert all(row.n > 0 for row in table)


def test_arima_garch_runs_on_synthetic_data():
    series = _noisy_daily(
        date(2022, 1, 1),
        date(2022, 4, 1),
        start_price=100.0,
        mean_return=0.001,
        shock_vol=0.015,
        seed=3,
    )
    table = evaluate(
        series,
        ArimaGarchPredictor(),
        windows={"synth": (date(2022, 2, 1), date(2022, 2, 28))},
        horizons=HORIZONS,
    )
    assert {row.horizon_days for row in table} == set(HORIZONS)
    for row in table:
        assert row.n > 0
        assert row.mae >= 0
        assert row.mape >= 0
        assert 0.0 <= row.hit_rate <= 1.0


def test_arima_garch_produces_price_bands():
    series = _noisy_daily(
        date(2022, 1, 1),
        date(2022, 3, 1),
        start_price=30_000.0,
        mean_return=0.0,
        shock_vol=0.02,
        seed=4,
    )
    origin = date(2022, 2, 15)
    forecasts = ArimaGarchPredictor().forecast(
        series.as_of(origin), origin, HORIZONS
    )
    assert [item.horizon_days for item in forecasts] == list(HORIZONS)
    for item in forecasts:
        assert item.lower_80 is not None and item.upper_80 is not None
        assert item.lower_90 is not None and item.upper_90 is not None
        assert item.lower_90 <= item.lower_80 <= item.point <= item.upper_80 <= item.upper_90
        assert item.lower_80 > 0
        assert item.upper_80 >= item.lower_80

    table = evaluate(
        series,
        ArimaGarchPredictor(),
        windows={"bands": (date(2022, 2, 1), date(2022, 2, 10))},
        horizons=HORIZONS,
    )
    for row in table:
        assert row.coverage_80 is not None
        assert row.coverage_90 is not None
        assert 0.0 <= row.coverage_80 <= 1.0
        assert 0.0 <= row.coverage_90 <= 1.0
