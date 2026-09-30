from __future__ import annotations

from pathlib import Path

import pytest

from price_forecast.data.candles import write_candles
from price_forecast.datafactory.synthetic.__main__ import main
from tests.datafactory.fixture import balanced_tape


def _csv(tmp_path: Path) -> Path:
    path = tmp_path / "source.csv"
    write_candles(path, balanced_tape())
    return path


def _short_windows(monkeypatch) -> None:
    from price_forecast.datafactory.synthetic.label import label_candles

    def _label(candles):
        return label_candles(candles, trend_bars=4, vol_bars=2)

    monkeypatch.setattr(
        "price_forecast.datafactory.synthetic.__main__.label_candles",
        _label,
    )


def test_command_writes_candle_png_and_sidecar(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    _short_windows(monkeypatch)
    main(["--csv", str(source), "--n-paths", "1", "--seed", "3"])
    stem = dest / "btc-usd-daily-seed3-path0"
    assert stem.with_suffix(".csv").is_file()
    assert stem.with_suffix(".png").read_bytes().startswith(b"\x89PNG")
    sidecar = dest / "btc-usd-daily-seed3-path0-regimes.csv"
    text = sidecar.read_text(encoding="utf-8").splitlines()
    assert text[0] == "time,regime"
    assert sidecar.with_suffix(".png").exists() is False
    assert len(text) == len(balanced_tape()) + 1
    assert sorted(path.name for path in dest.iterdir()) == [
        "btc-usd-daily-seed3-path0-regimes.csv",
        "btc-usd-daily-seed3-path0.csv",
        "btc-usd-daily-seed3-path0.png",
    ]


def test_more_paths_keep_path_zero_bytes(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    _short_windows(monkeypatch)
    main(["--csv", str(source), "--n-paths", "1", "--seed", "3"])
    candle = (dest / "btc-usd-daily-seed3-path0.csv").read_bytes()
    sidecar = (dest / "btc-usd-daily-seed3-path0-regimes.csv").read_bytes()
    main(["--csv", str(source), "--n-paths", "2", "--seed", "3"])
    assert (dest / "btc-usd-daily-seed3-path0.csv").read_bytes() == candle
    assert (dest / "btc-usd-daily-seed3-path0-regimes.csv").read_bytes() == sidecar
    assert (dest / "btc-usd-daily-seed3-path1.csv").is_file()


def test_missing_csv_writes_nothing(tmp_path, monkeypatch, capsys):
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    with pytest.raises(SystemExit) as exc:
        main(["--csv", str(tmp_path / "missing.csv")])
    assert exc.value.code == 1
    assert "python -m price_forecast.data.candles" in capsys.readouterr().err
    assert dest.exists() is False


def test_n_paths_below_one_writes_nothing(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    with pytest.raises(ValueError, match="n_paths"):
        main(["--csv", str(source), "--n-paths", "0"])
    assert dest.exists() is False


def test_fit_failure_writes_nothing(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    _short_windows(monkeypatch)
    monkeypatch.setattr(
        "price_forecast.datafactory.synthetic.fit.t.fit",
        lambda _returns: (1.0, 0.0, 0.01),
    )
    with pytest.raises(ValueError, match="bull_quiet"):
        main(["--csv", str(source)])
    assert dest.exists() is False


def test_non_finite_return_writes_nothing(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    _short_windows(monkeypatch)
    monkeypatch.setattr(
        "price_forecast.datafactory.synthetic.paths.t.rvs",
        lambda *args, **kwargs: float("nan"),
    )
    with pytest.raises(ValueError, match="non-finite"):
        main(["--csv", str(source), "--n-paths", "2"])
    assert list(dest.glob("*")) == []
