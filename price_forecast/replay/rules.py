"""The locked rules the replay harness scores, and the lazily built VCP gate they share."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from price_forecast.data.candles import Candle
from price_forecast.search.spec import Spec, locked_crashgate

STRATEGIES = {
    "crashgate_v1": locked_crashgate,
    "smagate_v1": lambda: Spec(mode="threshold", close_above_sma_weeks=8, close_below_sma_weeks=16),
}


class LazyGate:
    """Builds the VCP gate only if a spec actually asks for it."""

    def __init__(self, candles: Sequence[Candle]) -> None:
        self._candles = candles
        self._gate = None

    def __call__(self, day: date) -> tuple[bool, bool]:
        if self._gate is None:
            from price_forecast.strategies.crashgate_entry import BaseBreakoutGate

            self._gate = BaseBreakoutGate(self._candles)
        return self._gate.parts(day)
