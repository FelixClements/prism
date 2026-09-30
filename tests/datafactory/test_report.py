from __future__ import annotations

import math
from datetime import date, timedelta

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.paths import PathResult
from price_forecast.datafactory.synthetic.report import format_synthetic_report, synthetic_report


def _row(index: int, close: float) -> Candle:
    day = date(2020, 1, 1) + timedelta(days=index)
    return Candle(day, close * 0.99, close * 1.01, close, close, 1.0)


def _path(regimes: tuple[str, ...], closes: list[float]) -> PathResult:
    candles = tuple(_row(index, close) for index, close in enumerate(closes))
    return PathResult(candles, regimes)


def test_report_names_facts_counts_and_na_when_a_side_is_thin():
    regimes = ("bull_quiet",) * 8
    closes = [100.0 * math.exp(0.01 * index) for index in range(8)]
    path = _path(regimes, closes)
    report = synthetic_report(path.candles, (path,), (path.candles,))
    text = format_synthetic_report(report)
    for key in (
        "daily_vol",
        "weekly_vol",
        "excess_kurtosis",
        "daily_p01",
        "hodl_max_dd",
        "acf_daily_1",
        "acf_weekly_1",
        "acf_weekly_4",
        "acf_weekly_8",
    ):
        assert key in text
    assert "synthetic median" in text
    assert "control median" in text
    assert "bull_quiet=7" in text
    assert "bear_quiet=0" in text
    assert "n/a" in text


def test_passing_checks_print_pass():
    regimes = (
        "bull_quiet",
        "bull_quiet",
        "bull_quiet",
        "bear_quiet",
        "bear_quiet",
        "bear_quiet",
        "sideways_volatile",
        "sideways_volatile",
        "sideways_volatile",
        "sideways_quiet",
        "sideways_quiet",
        "sideways_quiet",
    )
    closes = [100.0]
    jumps = {
        "bull_quiet": 0.02,
        "bear_quiet": -0.03,
        "sideways_volatile": 0.05,
        "sideways_quiet": 0.0,
    }
    # Alternate the volatile sign so its sample std is wide, and keep quiet flat.
    signs = [1, -1, 1]
    volatile_seen = 0
    for name in regimes[1:]:
        shock = jumps[name]
        if name.endswith("volatile"):
            shock = 0.05 * signs[volatile_seen]
            volatile_seen += 1
        closes.append(closes[-1] * math.exp(shock))
    path = _path(regimes, closes)
    text = format_synthetic_report(synthetic_report(path.candles, (path,), (path.candles,)))
    assert "bull_vs_bear pass" in text
    assert "quiet_vs_volatile pass" in text
