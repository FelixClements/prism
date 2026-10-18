"""price_forecast still exports the walk-forward scoreboard."""

from price_forecast import (
    HORIZONS,
    WINDOWS,
    ArimaGarchPredictor,
    ChronosPredictor,
    Forecast,
    LastValuePredictor,
    LeakageError,
    ZeroReturnPredictor,
    evaluate,
    load_daily_closes,
    synthetic_daily,
)


def test_package_exports_forecast_scoreboard():
    assert HORIZONS
    assert WINDOWS
    assert callable(evaluate)
    assert issubclass(LeakageError, Exception)
