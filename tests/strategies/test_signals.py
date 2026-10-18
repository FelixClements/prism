"""Weekly SMA helper. No backtest imports."""

from __future__ import annotations

import pytest

from price_forecast.strategies.signals import sma_at


def test_sma_at_t_uses_closes_through_t_inclusive():
    closes = [float(i + 1) for i in range(20)]

    at_t = sma_at(closes, 10, 8)
    without_future = sma_at(closes[:11], 10, 8)

    assert at_t == pytest.approx(sum(closes[3:11]) / 8)
    assert at_t == pytest.approx(without_future)
    assert at_t != pytest.approx(sum(closes[3:12]) / 8)


def test_sma_at_rejects_an_index_before_the_warmup():
    with pytest.raises(ValueError, match="SMA-8 is not defined"):
        sma_at([100.0] * 8, 6, 8)
