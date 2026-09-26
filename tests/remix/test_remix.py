"""Stationary-bootstrap remixed daily BTC paths. Offline fixtures only."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from price_forecast.remix.remix import (
    MEAN_BLOCK_BARS,
    main,
    remix_daily_closes,
    remix_sanity,
    stylized_facts,
)
from price_forecast.data.series import PriceSeries
from price_forecast.backtest.engine import simulate_strategy
from price_forecast.data.weekly import weekly_closes


def _closes(series: PriceSeries) -> list[float]:
    return [series.close_at(day) for day in series.dates()]


def _seasonal_daily(n: int = 728, *, start: date = date(2018, 1, 1)) -> PriceSeries:
    """Slow yearly cycle so weekly lag-8 ACF is real before short-block scramble."""
    bars: list[tuple[date, float]] = []
    for i in range(n):
        price = 100.0 * math.exp(0.5 * math.sin(2.0 * math.pi * i / 364.0))
        bars.append((start + timedelta(days=i), price))
    return PriceSeries(bars)


def test_default_mean_block_is_twenty_six_weeks_of_daily_bars():
    assert MEAN_BLOCK_BARS == 182


def test_remix_keeps_dates_length_positive_prices_and_does_not_mutate_source():
    series = _seasonal_daily(n=40)
    before = [(day, series.close_at(day)) for day in series.dates()]

    paths = remix_daily_closes(series, n_paths=3, mean_block_bars=8, seed=7)

    assert len(paths) == 3
    for path in paths:
        assert list(path.dates()) == list(series.dates())
        prices = _closes(path)
        assert len(prices) == 40
        assert all(price > 0.0 for price in prices)
        assert prices[0] == pytest.approx(before[0][1])
    assert [(day, series.close_at(day)) for day in series.dates()] == before


def test_same_seed_reproduces_the_same_paths():
    series = _seasonal_daily(n=50)
    first = remix_daily_closes(series, n_paths=2, mean_block_bars=10, seed=11)
    second = remix_daily_closes(series, n_paths=2, mean_block_bars=10, seed=11)
    third = remix_daily_closes(series, n_paths=2, mean_block_bars=10, seed=12)

    assert _closes(first[0]) == _closes(second[0])
    assert _closes(first[1]) == _closes(second[1])
    assert _closes(first[0]) != _closes(third[0])


def test_short_blocks_destroy_weekly_lag8_acf_relative_to_long_blocks():
    series = _seasonal_daily(n=728)
    n_returns = len(series.dates()) - 1
    iid = remix_daily_closes(series, n_paths=20, mean_block_bars=1, seed=3)
    long = remix_daily_closes(
        series, n_paths=20, mean_block_bars=n_returns, seed=3
    )

    def median_abs_weekly_acf8(paths: tuple[PriceSeries, ...]) -> float:
        values = [abs(stylized_facts(path)["acf_weekly_8"]) for path in paths]
        values.sort()
        return values[len(values) // 2]

    assert median_abs_weekly_acf8(long) > median_abs_weekly_acf8(iid)


def test_remixed_path_feeds_weekly_sma_without_error():
    series = _seasonal_daily(n=200)
    path = remix_daily_closes(series, n_paths=1, mean_block_bars=30, seed=0)[0]
    weeks = weekly_closes(path)
    simulate_strategy(weeks)


def test_sanity_compares_real_remixed_and_iid_control():
    series = _seasonal_daily(n=400)
    remixed = remix_daily_closes(series, n_paths=4, mean_block_bars=40, seed=1)
    iid = remix_daily_closes(series, n_paths=4, mean_block_bars=1, seed=2)
    report = remix_sanity(series, remixed, iid_paths=iid)

    for bucket in ("real", "remixed", "iid_control"):
        assert bucket in report
    facts = report["real"]
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
        assert key in facts
        assert key in report["remixed"]["median"]
        assert key in report["iid_control"]["median"]
    assert report["remixed"]["n"] == 4
    assert facts["hodl_max_dd"] <= 0.0


def test_main_prints_sanity_without_network(capsys):
    series = _seasonal_daily(n=250)
    main(["--n-paths", "2", "--seed", "0", "--mean-block-bars", "40"], series=series)
    out = capsys.readouterr().out
    assert "hodl_max_dd" in out
    assert "acf_weekly_8" in out
    assert "optimal_block_length" in out


def test_rejects_empty_and_single_bar_series():
    empty_day = date(2020, 1, 1)
    one = PriceSeries([(empty_day, 100.0)])
    with pytest.raises(ValueError, match="at least two"):
        remix_daily_closes(one, n_paths=1, seed=0)
    with pytest.raises(ValueError, match="n_paths"):
        remix_daily_closes(_seasonal_daily(n=10), n_paths=0, seed=0)
    with pytest.raises(ValueError, match="mean_block_bars"):
        remix_daily_closes(_seasonal_daily(n=10), n_paths=1, mean_block_bars=0, seed=0)
