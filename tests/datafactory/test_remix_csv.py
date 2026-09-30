"""Remix paths written as candle CSVs with scaled source wicks."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest

from price_forecast.data.candles import Candle, read_candles, write_candles
from price_forecast.datafactory.remix import main, remix_candle_paths, remix_daily_closes
from price_forecast.data.candles import closes_from_candles


def _source() -> tuple[Candle, ...]:
    return (
        Candle(date(2020, 1, 1), 80, 105, 90, 100, 1.0),
        Candle(date(2020, 1, 2), 100, 130, 108, 110, 2.0),
        Candle(date(2020, 1, 3), 120, 160, 140, 150, 3.0),
        Candle(date(2020, 1, 4), 90, 125, 100, 120, 4.0),
    )


def test_closes_match_remix_and_wick_is_the_landing_day():
    candles = _source()
    series = closes_from_candles(candles)
    expected = remix_daily_closes(series, n_paths=1, mean_block_bars=1, seed=0)[0]
    out = remix_candle_paths(candles, n_paths=1, mean_block_bars=1, seed=0)[0]
    assert [row.day for row in out] == list(expected.dates())
    assert [row.close for row in out] == pytest.approx(
        [expected.close_at(day) for day in expected.dates()]
    )
    assert out[0].open == pytest.approx(90)
    assert out[0].high == pytest.approx(105)
    assert out[0].low == pytest.approx(80)
    assert out[0].volume is None
    source_returns = [
        math.log(candles[i + 1].close / candles[i].close) for i in range(len(candles) - 1)
    ]
    for prev, row in zip(out, out[1:]):
        step = math.log(row.close / prev.close)
        matches = [
            i
            for i, ret in enumerate(source_returns)
            if math.isclose(ret, step, rel_tol=0, abs_tol=1e-9)
        ]
        assert len(matches) == 1
        landing = candles[matches[0] + 1]
        start = candles[matches[0]]
        assert row.high / row.close == pytest.approx(landing.high / landing.close)
        assert row.open / row.close == pytest.approx(landing.open / landing.close)
        assert row.low / row.close == pytest.approx(landing.low / landing.close)
        assert row.high / row.close != pytest.approx(start.high / start.close)
        assert row.volume is None


def test_main_writes_one_pair_per_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src = tmp_path / "src.csv"
    write_candles(src, _source())
    dest = tmp_path / "remix"
    monkeypatch.setattr("price_forecast.datafactory.remix.REMIX_DIR", dest)
    monkeypatch.setattr(
        "price_forecast.data.series.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")),
    )
    main(["--csv", str(src), "--n-paths", "2", "--seed", "7", "--mean-block-bars", "1"])
    for name in (
        "btc-usd-daily-seed7-path0.csv",
        "btc-usd-daily-seed7-path1.csv",
    ):
        csv_path = dest / name
        assert csv_path.is_file()
        assert csv_path.with_suffix(".png").is_file()
        assert all(row.volume is None for row in read_candles(csv_path))
