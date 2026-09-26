"""Bakeoff reads a candle CSV and does not download."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from price_forecast.data.candles import Candle, write_candles
from price_forecast.forecast.bakeoff import main


def test_bakeoff_loads_csv_before_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    csv_path = tmp_path / "tape.csv"
    write_candles(
        csv_path,
        (
            Candle(date(2020, 1, 1), 9, 11, 10, 10, 1),
            Candle(date(2020, 1, 2), 10, 12, 11, 12, 1),
        ),
    )
    monkeypatch.setattr(
        "price_forecast.data.series.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")),
    )

    def reached():
        raise RuntimeError("reached-models")

    monkeypatch.setattr("price_forecast.forecast.bakeoff.ChronosPredictor", reached)
    with pytest.raises(RuntimeError, match="reached-models"):
        main(["--csv", str(csv_path)])


def test_bakeoff_missing_csv_does_not_load_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(
        "price_forecast.data.series.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")),
    )
    monkeypatch.setattr(
        "price_forecast.forecast.bakeoff.ChronosPredictor",
        lambda: (_ for _ in ()).throw(AssertionError("model")),
    )
    with pytest.raises(SystemExit) as exc:
        main(["--csv", str(tmp_path / "missing.csv")])
    assert exc.value.code == 1
    assert "python -m price_forecast.data.candles" in capsys.readouterr().err
