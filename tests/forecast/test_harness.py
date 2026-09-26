"""Harness tests for the walk-forward Bitcoin price-forecast scoreboard.

These tests prove the scoreboard itself. They do not fit ARIMA.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from price_forecast import (
    HORIZONS,
    WINDOWS,
    Forecast,
    LastValuePredictor,
    LeakageError,
    ZeroReturnPredictor,
    evaluate,
    synthetic_daily,
)


class PeekingPredictor:
    """Cheats by reading the close at t+1. The harness must reject this."""

    def forecast(self, history, origin, horizons):
        leaked = history.close_at(origin + timedelta(days=1))
        return [Forecast(origin=origin, horizon_days=h, point=leaked) for h in horizons]


def _row_keys(table):
    return {(row.window, row.horizon_days) for row in table}


def test_last_value_mae_is_zero_on_flat_series():
    series = synthetic_daily(
        start=date(2022, 1, 1),
        end=date(2022, 2, 15),
        start_price=100.0,
        daily_return=0.0,
    )
    table = evaluate(
        series,
        LastValuePredictor(),
        windows={"flat": (date(2022, 1, 1), date(2022, 1, 31))},
        horizons=HORIZONS,
    )

    assert table, "expected a results table"
    for row in table:
        assert row.horizon_days in HORIZONS
        assert row.n > 0
        assert row.mae == pytest.approx(0.0, abs=1e-12)


def test_peeking_model_that_reads_t_plus_one_is_rejected():
    series = synthetic_daily(
        start=date(2024, 1, 1),
        end=date(2024, 2, 15),
        start_price=40_000.0,
        daily_return=0.001,
    )

    with pytest.raises(LeakageError):
        evaluate(
            series,
            PeekingPredictor(),
            windows={"leak": (date(2024, 1, 1), date(2024, 1, 31))},
            horizons=HORIZONS,
        )


def test_baselines_run_full_loop_and_produce_window_by_horizon_table():
    series = synthetic_daily(
        start=date(2022, 1, 1),
        end=date(2027, 1, 15),
        start_price=20_000.0,
        daily_return=0.0005,
    )
    expected = {(name, h) for name in WINDOWS for h in HORIZONS}

    for predictor in (LastValuePredictor(), ZeroReturnPredictor()):
        table = evaluate(series, predictor, windows=WINDOWS, horizons=HORIZONS)
        assert _row_keys(table) == expected
        for row in table:
            assert row.n > 0
            assert row.mae >= 0
            assert row.mape >= 0
            assert 0.0 <= row.hit_rate <= 1.0
            assert row.coverage_80 is None
            assert row.coverage_90 is None
