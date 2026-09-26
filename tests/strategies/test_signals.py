"""SMA / dual / asymmetric / Donchian weekly signals. No backtest imports."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

import pytest

from price_forecast.strategies.signals import (
    asymmetric_sma_signal,
    donchian_signal,
    dual_sma_signal,
    sma_at,
    sma_signal,
)


def _weeks_from_closes(closes: Sequence[float], *, start: date = date(2022, 1, 9)) -> list[tuple[date, float]]:
    return [(start + timedelta(weeks=i), close) for i, close in enumerate(closes)]


def test_sma_at_t_uses_closes_through_t_inclusive():
    closes = [float(i + 1) for i in range(20)]

    at_t = sma_at(closes, 10, 8)
    without_future = sma_at(closes[:11], 10, 8)

    assert at_t == pytest.approx(sum(closes[3:11]) / 8)
    assert at_t == pytest.approx(without_future)
    assert at_t != pytest.approx(sum(closes[3:12]) / 8)


def test_sma_is_in_only_when_close_is_strictly_above_sma():
    # 8 weeks of 100, then 110. SMA8 at the last bar is (7*100+110)/8 = 101.25.
    weeks = _weeks_from_closes([100.0] * 7 + [110.0])

    signal = sma_signal(weeks, lookback=8)

    assert signal[-1] == 1
    assert all(s is None for s in signal[:-1])


def test_sma_is_out_when_close_equals_or_is_below_sma():
    weeks = _weeks_from_closes([100.0] * 8)

    signal = sma_signal(weeks, lookback=8)

    assert signal[-1] == 0


def test_sma_does_not_use_future_weeks():
    weeks = _weeks_from_closes([100.0] * 8 + [200.0])

    signal = sma_signal(weeks, lookback=8)

    # At week 8 (index 7) the later 200 must not have pulled the SMA up.
    assert signal[7] == 0
    assert signal[8] == 1


def test_dual_sma_is_in_when_fast_sma_is_above_slow_sma():
    # 14 weeks at 100, then 12 weeks at 200. At the last bar:
    # SMA12 = 200, SMA26 = (14*100 + 12*200) / 26 = 146.15...
    weeks = _weeks_from_closes([100.0] * 14 + [200.0] * 12)

    signal = dual_sma_signal(weeks, fast=12, slow=26)

    assert signal[-1] == 1
    assert all(s is None for s in signal[:25])


def test_dual_sma_is_out_when_fast_sma_is_at_or_below_slow_sma():
    weeks = _weeks_from_closes([100.0] * 26)

    signal = dual_sma_signal(weeks, fast=12, slow=26)

    assert signal[-1] == 0


def test_donchian_is_in_on_close_at_or_above_prior_12_week_high():
    weeks = _weeks_from_closes([100.0] * 12 + [100.0])

    signal = donchian_signal(weeks, lookback=12)

    assert signal[-1] == 1
    assert all(s is None for s in signal[:12])


def test_donchian_is_out_when_close_breaks_below_prior_12_week_high():
    weeks = _weeks_from_closes([100.0] * 12 + [99.0])

    signal = donchian_signal(weeks, lookback=12)

    assert signal[-1] == 0


def test_donchian_channel_excludes_this_week():
    # Prior 12 are 100; this week 200 must not raise its own entry bar.
    weeks = _weeks_from_closes([100.0] * 12 + [200.0, 150.0])

    signal = donchian_signal(weeks, lookback=12)

    # At the 150 bar, prior 12 include the 200, so 150 < 200 → out.
    # If this week were included in its own channel, 150 vs max(..., 150) could leak.
    assert signal[-1] == 0
    assert signal[-2] == 1


def test_asymmetric_sma_rejects_sell_weeks_not_longer_than_buy_weeks():
    weeks = _weeks_from_closes([100.0] * 12)

    with pytest.raises(ValueError, match="sell_weeks must be greater than buy_weeks"):
        asymmetric_sma_signal(weeks, buy_weeks=12, sell_weeks=12)


def test_asymmetric_sma_is_undefined_until_the_sell_sma_is_defined():
    weeks = _weeks_from_closes([100.0] * 10)

    signal = asymmetric_sma_signal(weeks, buy_weeks=2, sell_weeks=4)

    assert all(s is None for s in signal[:3])
    assert signal[3] is not None


def test_asymmetric_sma_sells_on_the_long_sma_not_the_short_while_in():
    # 170 is below SMA-2 (185) but above SMA-4 (167.5) → stay in.
    # 100 is below SMA-4 → sell. Using the short SMA would have sold at 170.
    weeks = _weeks_from_closes([100.0, 100.0, 200.0, 200.0, 170.0, 100.0])

    signal = asymmetric_sma_signal(weeks, buy_weeks=2, sell_weeks=4)

    assert signal[4] == 1
    assert signal[5] == 0


def test_asymmetric_sma_buys_on_the_short_sma_not_the_long_while_out():
    # After the 100 sell, 140 is above SMA-2 (120) but still below SMA-4 (152.5).
    weeks = _weeks_from_closes([100.0, 100.0, 200.0, 200.0, 170.0, 100.0, 140.0])

    signal = asymmetric_sma_signal(weeks, buy_weeks=2, sell_weeks=4)

    assert signal[5] == 0
    assert signal[6] == 1


def test_asymmetric_sma_does_not_use_future_weeks():
    base = [100.0, 100.0, 200.0, 200.0, 170.0, 100.0]
    without_future = asymmetric_sma_signal(
        _weeks_from_closes(base), buy_weeks=2, sell_weeks=4
    )
    with_future = asymmetric_sma_signal(
        _weeks_from_closes(base + [10_000.0]), buy_weeks=2, sell_weeks=4
    )

    assert with_future[: len(base)] == without_future
    assert without_future[5] == 0


def test_asymmetric_sma_stays_in_when_close_equals_the_sell_sma():
    weeks = _weeks_from_closes([100.0] * 4)

    signal = asymmetric_sma_signal(weeks, buy_weeks=2, sell_weeks=4)

    assert signal[3] == 1


def test_asymmetric_sma_stays_out_when_close_equals_the_buy_sma():
    weeks = _weeks_from_closes([100.0] * 4)

    signal = asymmetric_sma_signal(
        weeks, buy_weeks=2, sell_weeks=4, start_in_btc=False
    )

    assert signal[3] == 0
