"""Candle CSV round trip, validation, and PNG."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from price_forecast.data.candles import (
    Candle,
    candle_face,
    draw_candle_chart,
    read_candles,
    require_closes,
    write_candles,
)


def _pair() -> tuple[Candle, Candle]:
    return (
        Candle(date(2020, 1, 1), 9.0, 11.0, 10.0, 10.5, None),
        Candle(date(2020, 1, 2), 10.0, 12.0, 11.0, 11.5, 0.0),
    )


def test_round_trip_keeps_blank_volume_and_builds_closes(tmp_path: Path):
    path = tmp_path / "tape.csv"
    write_candles(path, _pair())
    assert path.read_text(encoding="utf-8").splitlines()[0] == (
        "time,low,high,open,close,volume"
    )
    rows = read_candles(path)
    assert rows[0].volume is None
    assert rows[1].volume == pytest.approx(0.0)
    assert rows[0].close == pytest.approx(10.5)
    series = require_closes(path)
    assert series.dates() == [date(2020, 1, 1), date(2020, 1, 2)]
    assert series.close_at(date(2020, 1, 2)) == pytest.approx(11.5)
    png = path.with_suffix(".png")
    assert png.read_bytes().startswith(b"\x89PNG")


def test_candle_face_colors():
    assert candle_face(10.0, 11.0) == "green"
    assert candle_face(11.0, 10.0) == "red"
    assert candle_face(10.0, 10.0) == "red"


def test_rejects_bad_candles(tmp_path: Path):
    path = tmp_path / "bad.csv"
    duplicate = (
        Candle(date(2020, 1, 1), 9, 11, 10, 10.5, 1),
        Candle(date(2020, 1, 1), 9, 11, 10, 10.5, 1),
    )
    non_positive = (Candle(date(2020, 1, 1), 9, 11, 10, 0, 1),)
    high_below_low = (Candle(date(2020, 1, 1), 12, 11, 11, 11.5, 1),)
    high_below_close = (Candle(date(2020, 1, 1), 9, 11, 10, 12, 1),)
    unsorted = (
        Candle(date(2020, 1, 2), 9, 11, 10, 10.5, 1),
        Candle(date(2020, 1, 1), 9, 11, 10, 10.5, 1),
    )
    negative_volume = (Candle(date(2020, 1, 1), 9, 11, 10, 10.5, -0.1),)
    for rows in (
        duplicate,
        non_positive,
        high_below_low,
        high_below_close,
        unsorted,
        negative_volume,
    ):
        with pytest.raises(ValueError):
            write_candles(path, rows)
        assert not path.exists()


def test_rejects_bad_header_and_text(tmp_path: Path):
    path = tmp_path / "bad.csv"
    path.write_text("day,close\n2020-01-01,1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_candles(path)
    path.write_text(
        "time,low,high,open,close,volume\n2020-1-1,9,11,10,10.5,1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        read_candles(path)


def test_png_failure_keeps_previous_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "c.csv"
    write_candles(path, _pair())
    csv_bytes = path.read_bytes()
    png_bytes = path.with_suffix(".png").read_bytes()

    def boom(_candles, _png_path):
        raise RuntimeError("draw failed")

    monkeypatch.setattr("price_forecast.data.candles.draw_candle_chart", boom)
    with pytest.raises(RuntimeError, match="draw failed"):
        write_candles(path, _pair())
    assert path.read_bytes() == csv_bytes
    assert path.with_suffix(".png").read_bytes() == png_bytes
    assert list(tmp_path.glob("*.tmp")) == []


def test_missing_csv_exits_with_hint(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    missing = tmp_path / "missing.csv"
    with pytest.raises(SystemExit) as exc:
        require_closes(missing)
    assert exc.value.code == 1
    assert "python -m price_forecast.data.candles" in capsys.readouterr().err


def test_draw_writes_png(tmp_path: Path):
    png = tmp_path / "only.png"
    draw_candle_chart(_pair(), png)
    assert png.read_bytes().startswith(b"\x89PNG")


def test_gitignore_lists_generated_candle_files():
    root = Path(__file__).resolve().parents[2]
    lines = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    for line in ("data/btc-usd-daily.csv", "data/btc-usd-daily.png", "data/remix/"):
        assert line in lines
