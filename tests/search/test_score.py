import math

import pytest

from price_forecast.search.score import (
    PathMetrics,
    breeding_number,
    is_fragile,
    stress_result,
)


def _metrics(**overrides) -> PathMetrics:
    base = dict(
        total_return=1.0,
        edge=0.40,
        sharpe=1.0,
        max_drawdown=-0.20,
        win_rate=0.5,
        profit_factor=2.0,
        round_trips=4,
        end_dollars=20_000.0,
        start_dollars=10_000.0,
        trip_pnls=(2_500.0, 2_500.0, 2_500.0, 2_500.0),
        hodl_return=0.60,
    )
    base.update(overrides)
    return PathMetrics(**base)


def test_baseline_against_itself_is_five():
    metrics = _metrics()
    assert breeding_number(metrics, metrics) == pytest.approx(5.0)


def test_shallower_drawdown_raises_the_drawdown_ratio():
    baseline = _metrics(max_drawdown=-0.30)
    child = _metrics(max_drawdown=-0.10)
    # four ratios stay 1, drawdown ratio is 0.30/0.10 = 3, sum is 7
    assert breeding_number(child, baseline) == pytest.approx(7.0)


def test_volume_stress_leaves_remix_blank_and_uses_synthetic():
    passed, remix_mean, synthetic_mean = stress_result(1.0, [], [0.5, 0.5], require_remix=False)
    assert passed is True
    assert remix_mean is None
    assert synthetic_mean == pytest.approx(0.5)
    passed, remix_mean, _ = stress_result(1.0, [], [0.4, 0.4], require_remix=False)
    assert passed is False
    assert remix_mean is None


def test_stress_fails_when_either_family_is_under_half():
    passed, remix_mean, synthetic_mean = stress_result(1.0, [0.4, 0.4], [0.6, 0.6])
    assert passed is False
    assert remix_mean == pytest.approx(0.4)
    assert synthetic_mean == pytest.approx(0.6)
    passed, _, _ = stress_result(1.0, [0.5, 0.5], [0.5, 0.5])
    assert passed is True


def test_one_trip_that_holds_half_the_edge_is_fragile():
    # end 20000, start 10000, hodl 0. Edge = 1.0. One trip of 6000 cuts end to 14000, edge to 0.4.
    metrics = _metrics(
        edge=1.0,
        hodl_return=0.0,
        end_dollars=20_000.0,
        trip_pnls=(6_000.0, 1_000.0, 1_000.0, 2_000.0),
    )
    assert is_fragile(metrics) is True


def test_even_trips_are_not_fragile():
    metrics = _metrics(edge=1.0, hodl_return=0.0, end_dollars=20_000.0, trip_pnls=(2_500.0,) * 4)
    assert is_fragile(metrics) is False
    assert math.isfinite(metrics.edge)
