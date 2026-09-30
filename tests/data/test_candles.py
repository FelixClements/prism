"""Candle CSV round trip, validation, and PNG."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from price_forecast.data import series as series_mod
from price_forecast.data.candles import (
    COINBASE_START,
    Candle,
    candle_face,
    draw_candle_chart,
    parse_coinbase_ohlc,
    read_candles,
    require_closes,
    update_coinbase_file,
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


def test_rejects_nan_close_on_read_and_write(tmp_path: Path):
    path = tmp_path / "nan.csv"
    path.write_text(
        "time,low,high,open,close,volume\n2020-01-01,9,11,10,nan,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        read_candles(path)
    nan_close = (Candle(date(2020, 1, 1), 9, 11, 10, float("nan"), None),)
    with pytest.raises(ValueError):
        write_candles(path, nan_close)


def test_rejects_nan_volume_on_read_and_write(tmp_path: Path):
    path = tmp_path / "nan.csv"
    path.write_text(
        "time,low,high,open,close,volume\n2020-01-01,9,11,10,10.5,nan\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        read_candles(path)
    nan_volume = (Candle(date(2020, 1, 1), 9, 11, 10, 10.5, float("nan")),)
    with pytest.raises(ValueError):
        write_candles(path, nan_volume)


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
    for line in (
        "data/btc-usd-daily.csv",
        "data/btc-usd-daily.png",
        "data/remix/",
        "data/synthetic/",
    ):
        assert line in lines


def _raw(day: date, close: float) -> list[float]:
    ts = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
    return [float(ts), close - 2, close + 2, close - 1, close, 1.0]


def test_parse_coinbase_keeps_ohlc_order():
    day = date(2020, 1, 2)
    rows = parse_coinbase_ohlc([_raw(day, 42)])
    assert rows[0].low == pytest.approx(40)
    assert rows[0].high == pytest.approx(44)
    assert rows[0].open == pytest.approx(41)
    assert rows[0].close == pytest.approx(42)
    assert rows[0].volume == pytest.approx(1)


def test_update_keeps_last_candle_when_refetch_omits_it(tmp_path: Path):
    path = tmp_path / "btc.csv"
    calls: list[tuple[date, date]] = []

    def fetch(start: date, end: date):
        calls.append((start, end))
        if len(calls) == 1:
            return [_raw(date(2020, 1, 1), 10), _raw(date(2020, 1, 3), 30)]
        return [_raw(date(2020, 1, 5), 50)]

    update_coinbase_file(path, today=date(2020, 1, 3), fetch=fetch)
    update_coinbase_file(path, today=date(2020, 1, 5), fetch=fetch)
    rows = read_candles(path)
    assert [row.day for row in rows] == [
        date(2020, 1, 1),
        date(2020, 1, 3),
        date(2020, 1, 5),
    ]
    assert rows[1].close == pytest.approx(30)
    assert rows[2].close == pytest.approx(50)


def test_update_replaces_last_day_and_keeps_earlier_hole(tmp_path: Path):
    path = tmp_path / "btc.csv"
    calls: list[tuple[date, date]] = []

    def fetch(start: date, end: date):
        calls.append((start, end))
        if len(calls) == 1:
            return [_raw(date(2020, 1, 1), 10), _raw(date(2020, 1, 3), 30)]
        return [_raw(date(2020, 1, 3), 31), _raw(date(2020, 1, 5), 50)]

    update_coinbase_file(path, today=date(2020, 1, 3), fetch=fetch)
    assert calls[0] == (COINBASE_START, date(2020, 1, 3))
    update_coinbase_file(path, today=date(2020, 1, 5), fetch=fetch)
    assert calls[1] == (date(2020, 1, 3), date(2020, 1, 5))
    rows = read_candles(path)
    assert [row.day for row in rows] == [
        date(2020, 1, 1),
        date(2020, 1, 3),
        date(2020, 1, 5),
    ]
    assert rows[0].close == pytest.approx(10)
    assert rows[1].close == pytest.approx(31)
    assert rows[2].close == pytest.approx(50)


def test_failed_fetch_leaves_csv_and_png(tmp_path: Path):
    path = tmp_path / "btc.csv"

    def fetch(start: date, end: date):
        return [_raw(date(2020, 1, 1), 10), _raw(date(2020, 1, 2), 11)]

    update_coinbase_file(path, today=date(2020, 1, 2), fetch=fetch)
    csv_bytes = path.read_bytes()
    png_bytes = path.with_suffix(".png").read_bytes()

    def boom(start: date, end: date):
        raise RuntimeError("coinbase down")

    with pytest.raises(RuntimeError, match="coinbase down"):
        update_coinbase_file(path, today=date(2020, 1, 3), fetch=boom)
    assert path.read_bytes() == csv_bytes
    assert path.with_suffix(".png").read_bytes() == png_bytes


def test_fetch_coinbase_ohlc_chunks_and_keeps_raw_rows(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[date, date]] = []

    def fake(start: date, end: date):
        calls.append((start, end))
        return [_raw(start, 5)]

    monkeypatch.setattr(series_mod, "_fetch_coinbase_candles", fake)
    end = COINBASE_START + timedelta(days=series_mod._COINBASE_MAX_CANDLES)
    rows = series_mod.fetch_coinbase_ohlc(COINBASE_START, end)
    assert len(calls) == 2
    assert calls[0][0] == COINBASE_START
    assert rows[0][4] == pytest.approx(5)
    assert len(rows[0]) == 6


def test_empty_first_fetch_writes_nothing(tmp_path: Path):
    path = tmp_path / "btc.csv"

    def fetch(start: date, end: date):
        return []

    with pytest.raises(ValueError):
        update_coinbase_file(path, today=date(2020, 1, 2), fetch=fetch)
    assert not path.exists()
    assert not path.with_suffix(".png").exists()


def test_main_writes_the_default_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dest = tmp_path / "btc-usd-daily.csv"
    monkeypatch.setattr("price_forecast.data.candles.BTC_USD_DAILY_CSV", dest)

    def fetch(start: date, end: date):
        assert start == COINBASE_START
        assert end == date(2020, 1, 2)
        return [_raw(date(2020, 1, 1), 10), _raw(date(2020, 1, 2), 11)]

    monkeypatch.setattr("price_forecast.data.candles.fetch_coinbase_ohlc", fetch)
    from price_forecast.data.candles import main

    main(["--today", "2020-01-02"])
    rows = read_candles(dest)
    assert [row.day for row in rows] == [date(2020, 1, 1), date(2020, 1, 2)]
    assert rows[1].close == pytest.approx(11)
    assert dest.with_suffix(".png").is_file()
