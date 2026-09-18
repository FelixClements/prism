"""Chronos must share the predictor API, stay as-of, and use only univariate close."""

from __future__ import annotations

import math
import random
from datetime import date, timedelta

import numpy as np
import pytest

from price_forecast import (
    HORIZONS,
    ChronosPredictor,
    Forecast,
    LastValuePredictor,
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


class _LastValuePipeline:
    """Stand-in Chronos API: median path equals the last observed close."""

    def __init__(self) -> None:
        self.inputs: np.ndarray | None = None
        self.prediction_length: int | None = None
        self.quantile_levels: list[float] | None = None

    def predict_quantiles(self, inputs, prediction_length, quantile_levels):
        self.inputs = np.asarray(inputs, dtype=float)
        self.prediction_length = int(prediction_length)
        self.quantile_levels = list(quantile_levels)
        last = float(self.inputs.reshape(-1)[-1])
        n_q = len(self.quantile_levels)
        quantiles = np.empty((1, prediction_length, n_q), dtype=float)
        for i, q in enumerate(self.quantile_levels):
            quantiles[0, :, i] = last * (0.9 + 0.2 * q)
        # Mean is deliberately not the last close so the adapter must use q0.5.
        mean = np.full((1, prediction_length), last * 1.5, dtype=float)
        return quantiles, mean


def test_peeking_model_is_still_rejected_when_chronos_is_present():
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


def test_chronos_does_not_read_past_origin():
    series = _noisy_daily(
        date(2022, 1, 1),
        date(2022, 3, 15),
        start_price=20_000.0,
        seed=2,
    )
    table = evaluate(
        series,
        ChronosPredictor(pipeline=_LastValuePipeline()),
        windows={"2022q1": (date(2022, 2, 1), date(2022, 2, 20))},
        horizons=HORIZONS,
    )
    assert table
    assert all(row.n > 0 for row in table)


def test_chronos_uses_only_univariate_close_history():
    series = _noisy_daily(
        date(2022, 1, 1),
        date(2022, 2, 20),
        start_price=30_000.0,
        seed=5,
    )
    origin = date(2022, 2, 10)
    history = series.as_of(origin)
    pipeline = _LastValuePipeline()
    forecasts = ChronosPredictor(pipeline=pipeline).forecast(history, origin, HORIZONS)
    assert [item.horizon_days for item in forecasts] == list(HORIZONS)
    assert pipeline.inputs is not None
    assert pipeline.inputs.ndim == 3
    assert pipeline.inputs.shape[0] == 1
    assert pipeline.inputs.shape[1] == 1
    context = np.asarray(pipeline.inputs, dtype=float).reshape(-1)
    expected = np.array(
        [history.close_at(day) for day in history.dates()], dtype=float
    )
    assert context.shape == expected.shape
    np.testing.assert_allclose(context, expected)
    assert pipeline.prediction_length == max(HORIZONS)
    assert history.dates()[-1] == origin


def test_chronos_median_path_scores_like_last_value_through_harness():
    series = _noisy_daily(
        date(2022, 1, 1),
        date(2022, 3, 1),
        start_price=25_000.0,
        seed=6,
    )
    window = {"synth": (date(2022, 2, 1), date(2022, 2, 10))}
    chronos = evaluate(
        series,
        ChronosPredictor(pipeline=_LastValuePipeline()),
        windows=window,
        horizons=HORIZONS,
    )
    last_value = evaluate(
        series,
        LastValuePredictor(),
        windows=window,
        horizons=HORIZONS,
    )
    assert {row.horizon_days for row in chronos} == set(HORIZONS)
    for left, right in zip(chronos, last_value, strict=True):
        assert left.horizon_days == right.horizon_days
        assert left.n == right.n
        assert left.mae == pytest.approx(right.mae, rel=1e-12, abs=1e-9)
        assert 0.0 <= left.hit_rate <= 1.0
