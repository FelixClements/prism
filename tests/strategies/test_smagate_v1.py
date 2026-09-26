"""SMAGateV1 freeze constants and CLI wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from price_forecast.strategies.smagate_v1 import (
    BUY_WEEKS,
    FILL_COST,
    RESULTS_DIR,
    SELL_WEEKS,
    STARTING_DOLLARS,
    WHIPSAW_MAX_HOLDING_BARS,
)


def test_defaults_match_the_stated_product_rule():
    assert BUY_WEEKS == 8
    assert SELL_WEEKS == 16
    assert FILL_COST == pytest.approx(0.0015)
    assert STARTING_DOLLARS == 10_000.0
    assert WHIPSAW_MAX_HOLDING_BARS == 2


def test_results_dir_is_repo_results_folder():
    root = Path(__file__).resolve().parents[2]
    assert (root / "pyproject.toml").is_file()
    assert RESULTS_DIR == root / "results"


def test_smagate_source_does_not_import_t1_or_archive():
    text = (
        Path(__file__).resolve().parents[2]
        / "price_forecast/strategies/smagate_v1.py"
    ).read_text(encoding="utf-8")
    assert "backtest.t1" not in text
    assert "archive" not in text


def test_engine_is_imported_only_inside_main():
    source = (
        Path(__file__).resolve().parents[2]
        / "price_forecast/strategies/smagate_v1.py"
    ).read_text(encoding="utf-8")
    header, _, rest = source.partition("def main")
    assert "price_forecast.backtest" not in header
    assert "price_forecast.backtest.engine" in rest
