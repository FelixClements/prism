"""Daily BTC close loader: synthetic stub stays for tests; Coinbase UTC is the real series."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from price_forecast.series import (
    BTC_CLOSE_SOURCE,
    BTC_CLOSE_TIMEZONE,
    bars_from_coinbase_candles,
    load_daily_closes,
)


def test_synthetic_loader_stub_still_works():
    series = load_daily_closes(
        source="synthetic",
        start=date(2022, 1, 1),
        end=date(2022, 1, 3),
        start_price=100.0,
        daily_return=0.0,
    )
    assert series.dates() == [date(2022, 1, 1), date(2022, 1, 2), date(2022, 1, 3)]
    assert series.last_close() == pytest.approx(100.0)


def test_real_source_is_coinbase_utc():
    assert BTC_CLOSE_SOURCE == "coinbase"
    assert BTC_CLOSE_TIMEZONE == "UTC"


def test_coinbase_candles_are_utc_daily_closes():
    # Coinbase: [time, low, high, open, close, volume]; time is Unix seconds, UTC.
    day = datetime(2022, 1, 2, tzinfo=timezone.utc)
    payload = [
        [int(day.timestamp()), 40_000.0, 43_000.0, 41_000.0, 42_000.0, 12.0],
        [int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp()), 39_000.0, 41_000.0, 40_000.0, 40_500.0, 8.0],
    ]
    bars = bars_from_coinbase_candles(payload)
    assert bars == [
        (date(2022, 1, 1), 40_500.0),
        (date(2022, 1, 2), 42_000.0),
    ]


def test_unknown_vendor_is_rejected():
    with pytest.raises(NotImplementedError):
        load_daily_closes(source="yahoo")
