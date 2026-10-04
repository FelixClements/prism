"""CrashGateV1 buy gate: pre-breakout or breakout, and above the long averages.

The weekly close must also be above the 8-week average. That check lives in
the strategy. This module only answers the daily-path question, using the
same VCP screener calls as the locked 2026-09-28 bakeoff.
"""

from __future__ import annotations

import importlib
import os
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from price_forecast.data.candles import Candle

ENTRY_STATES = ("Pre-breakout", "Breakout")


def vcp_scripts_dir() -> Path:
    """Directory that contains ``screen_vcp.py``."""
    override = os.environ.get("CRASHGATE_VCP_SCRIPTS")
    if override:
        return Path(override)
    return Path.home() / ".agents" / "skills" / "vcp-screener" / "scripts"


class BaseBreakoutGate:
    """True when that session is a pre-breakout or breakout above SMA-150 and SMA-200."""

    def __init__(self, candles: Sequence[Candle]) -> None:
        scripts = vcp_scripts_dir()
        screen = scripts / "screen_vcp.py"
        if not screen.is_file():
            raise FileNotFoundError(
                f"missing {screen}. Install the vcp-screener skill or set CRASHGATE_VCP_SCRIPTS."
            )
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        self._analyze = importlib.import_module("screen_vcp").analyze_stock
        self._quote = importlib.import_module("historical_scanner").build_quote_from_history
        self._history = list(
            reversed(
                [
                    {
                        "date": candle.day.isoformat(),
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "adjClose": candle.close,
                        "volume": candle.volume or 0,
                    }
                    for candle in candles
                ]
            )
        )
        self._index = {bar["date"]: i for i, bar in enumerate(self._history)}
        self._cache: dict[date, tuple[bool, bool]] = {}

    def parts(self, day: date) -> tuple[bool, bool]:
        """`(base_or_breakout, above_long_averages)` for one session."""
        cached = self._cache.get(day)
        if cached is not None:
            return cached
        offset = self._index[day.isoformat()]
        quote = self._quote(self._history, offset)
        result = self._analyze(
            "BTC-USD", self._history, quote, self._history, as_of_offset=offset
        )
        above_long = result["trend_template"]["criteria"].get(
            "c1_price_above_sma150_200", {}
        ).get("passed")
        pair = (result.get("execution_state") in ENTRY_STATES, bool(above_long))
        self._cache[day] = pair
        return pair

    def __call__(self, day: date) -> bool:
        base, long = self.parts(day)
        return base and long
