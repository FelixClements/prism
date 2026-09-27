"""SMAGateV1 freeze constants and CLI wiring."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from price_forecast.data.candles import Candle, write_candles
from price_forecast.strategies import smagate_v1
from price_forecast.strategies.smagate_v1 import (
    BUY_WEEKS,
    FILL_COST,
    RESULTS_DIR,
    SELL_WEEKS,
    STARTING_DOLLARS,
    WHIPSAW_MAX_HOLDING_BARS,
    main,
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


def _tape(path: Path) -> None:
    day = date(2022, 1, 1)
    rows = []
    for i in range(140):
        close = 100.0 + i
        rows.append(Candle(day, close - 1, close + 1, close - 0.5, close, 1.0))
        day += timedelta(days=1)
    write_candles(path, rows)


def test_smagate_scores_csv_without_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    csv_path = tmp_path / "tape.csv"
    _tape(csv_path)
    monkeypatch.setattr(smagate_v1, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(
        "price_forecast.data.series.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")),
    )
    main(["--csv", str(csv_path), "--starting-dollars", "10000"])
    assert (tmp_path / "results" / "sma8_16_kpis_results.md").is_file()


def test_smagate_missing_csv_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(smagate_v1, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(
        "price_forecast.data.series.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")),
    )
    with pytest.raises(SystemExit) as exc:
        main(["--csv", str(tmp_path / "missing.csv")])
    assert exc.value.code == 1
    assert "python -m price_forecast.data.candles" in capsys.readouterr().err
    assert not (tmp_path / "results").exists()
