"""price_forecast still exports the walk-forward scoreboard."""

from pathlib import Path

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
from price_forecast.forecast.bakeoff import RESULTS_DIR


def test_package_exports_forecast_scoreboard():
    assert HORIZONS
    assert WINDOWS
    assert callable(evaluate)
    assert issubclass(LeakageError, Exception)


def test_bakeoff_results_dir_is_repo_results():
    root = Path(__file__).resolve().parents[2]
    assert RESULTS_DIR == root / "results"
