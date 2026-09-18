"""Alternative.me Crypto Fear & Greed Index parser. No invented values."""

from __future__ import annotations

from datetime import date, datetime, timezone

from price_forecast.fng import FNG_SOURCE, bars_from_fng_payload


def test_fng_payload_uses_utc_unix_dates_and_integer_values():
    payload = {
        "name": "Fear and Greed Index",
        "data": [
            {
                "value": "40",
                "value_classification": "Fear",
                "timestamp": str(int(datetime(2019, 2, 26, tzinfo=timezone.utc).timestamp())),
            },
            {
                "value": "47",
                "value_classification": "Neutral",
                "timestamp": str(int(datetime(2019, 2, 25, tzinfo=timezone.utc).timestamp())),
            },
        ],
        "metadata": {"error": None},
    }

    bars = bars_from_fng_payload(payload)

    assert bars == {date(2019, 2, 25): 47, date(2019, 2, 26): 40}


def test_source_is_alternative_me():
    assert "Alternative.me" in FNG_SOURCE
