"""Crypto Fear & Greed Index from Alternative.me.

Source: https://alternative.me/crypto/fear-and-greed-index/
API: https://api.alternative.me/fng/?limit=0  (limit=0 returns full history)

Values are daily 0–100. We never invent missing dates.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

FNG_SOURCE = "Alternative.me Crypto Fear & Greed Index"
FNG_API_URL = "https://api.alternative.me/fng/?limit=0"
_USER_AGENT = "prism-price-forecast/0.1"


def bars_from_fng_payload(payload: dict[str, Any]) -> dict[date, int]:
    """Parse Alternative.me JSON to UTC dates. Duplicate days keep the last row."""
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise ValueError("F&G payload is missing a data list")
    by_day: dict[date, int] = {}
    for row in rows:
        ts = int(row["timestamp"])
        value = int(row["value"])
        day = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        by_day[day] = value
    return by_day


def load_fng() -> dict[date, int]:
    """Download the full official history. Empty history is an error, not zeros."""
    request = Request(
        FNG_API_URL,
        headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"F&G HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("F&G request failed") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("F&G payload was not an object")
    bars = bars_from_fng_payload(payload)
    if not bars:
        raise ValueError("F&G API returned no history")
    return bars
