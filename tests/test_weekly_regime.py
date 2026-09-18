"""Weekly in/out regime filter: leakage-safe signals and delayed fills."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

import pytest

from price_forecast.series import PriceSeries
from price_forecast.weekly_regime import (
    COST_BPS,
    SMA8_LOOKBACK,
    BacktestResult,
    align_fng_to_weeks,
    apply_fng_overlay,
    asymmetric_sma_signal,
    backtest,
    dollar_backtest,
    donchian_signal,
    dual_sma_signal,
    fng_only_signal,
    pass_a,
    pass_c,
    sma8_first_fill_date,
    sma_first_fill_date,
    sma_signal,
    weekly_closes,
)


def test_weekly_close_is_last_utc_daily_in_sunday_ending_week():
    # Monday 2022-01-03 .. Sunday 2022-01-09, rising $1/day.
    daily = []
    price = 100.0
    day = date(2022, 1, 3)
    while day <= date(2022, 1, 9):
        daily.append((day, price))
        price += 1.0
        day += timedelta(days=1)
    series = PriceSeries(daily)

    weeks = weekly_closes(series)

    assert weeks == [(date(2022, 1, 9), 106.0)]


def test_incomplete_trailing_week_is_dropped():
    # Full week Sun 2022-01-09, then Mon-Wed only.
    daily = []
    day = date(2022, 1, 3)
    price = 100.0
    while day <= date(2022, 1, 12):
        daily.append((day, price))
        price += 1.0
        day += timedelta(days=1)
    series = PriceSeries(daily)

    weeks = weekly_closes(series)

    assert [week_end for week_end, _close in weeks] == [date(2022, 1, 9)]


def _weeks_from_closes(closes: Sequence[float], *, start: date = date(2022, 1, 9)) -> list[tuple[date, float]]:
    return [(start + timedelta(weeks=i), close) for i, close in enumerate(closes)]


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


def test_signal_at_week_t_fills_at_next_week_close():
    # Inherited BTC. Cash signal at the 100 bar must not sell before the 200 bar.
    weeks = _weeks_from_closes([100.0, 200.0, 200.0])
    signals = [0, 0, 0]

    result = backtest(weeks, signals)

    assert result.terminal_wealth == pytest.approx(2.0 * (1 - COST_BPS / 10_000))
    assert result.round_trips == 1
    assert result.time_in_btc == pytest.approx(0.5)


def test_same_bar_fill_would_be_optimistic_and_is_not_used():
    weeks = _weeks_from_closes([100.0, 200.0, 200.0])
    signals = [0, 0, 0]

    result = backtest(weeks, signals)

    assert result.terminal_wealth > 1.5
    assert result.terminal_wealth != pytest.approx(1.0 * (1 - COST_BPS / 10_000))


def test_each_flip_costs_ten_bps_of_wealth():
    weeks = _weeks_from_closes([100.0, 100.0, 100.0, 100.0])
    # Fill at bar 1: cash; fill at bar 2: BTC. Two flips, flat price.
    signals = [0, 1, 1, 1]

    result = backtest(weeks, signals)

    assert result.terminal_wealth == pytest.approx((1 - COST_BPS / 10_000) ** 2)
    assert result.round_trips == 1


def test_cash_weeks_earn_zero():
    weeks = _weeks_from_closes([100.0, 200.0, 50.0])
    signals = [0, 0, 0]

    result = backtest(weeks, signals)

    # Hold BTC through 100→200, sell at 200, miss 200→50.
    assert result.terminal_wealth == pytest.approx(2.0 * (1 - COST_BPS / 10_000))


def test_undefined_signals_keep_inherited_btc():
    weeks = _weeks_from_closes([100.0, 110.0, 121.0])
    signals = [None, None, None]

    result = backtest(weeks, signals)

    assert result.terminal_wealth == pytest.approx(1.21)
    assert result.round_trips == 0
    assert result.time_in_btc == pytest.approx(1.0)


def test_fng_overlay_forces_cash_when_index_above_75():
    weeks = _weeks_from_closes([100.0, 100.0, 100.0])
    base = [1, 1, 1]
    fng = [80, 80, 80]

    overlaid = apply_fng_overlay(base, fng)

    assert overlaid == [0, 0, 0]


def test_fng_overlay_does_not_force_a_buy():
    weeks = _weeks_from_closes([100.0, 100.0])
    base = [0, 0]
    fng = [10, 10]

    overlaid = apply_fng_overlay(base, fng)

    assert overlaid == [0, 0]


def test_fng_overlay_skips_weeks_with_missing_index():
    base = [1, 1, 1]
    fng = [None, 80, None]

    overlaid = apply_fng_overlay(base, fng)

    assert overlaid == [1, 0, 1]


def test_fng_only_buys_below_25_sells_above_75_else_holds():
    fng = [50, 80, 80, 10, 50]

    signal = fng_only_signal(fng)

    # start BTC; 50 hold; 80 cash; 80 cash; 10 BTC; 50 hold BTC
    assert signal == [1, 0, 0, 1, 1]


def test_fng_only_does_not_invent_missing_values():
    fng = [None, None, 80]

    signal = fng_only_signal(fng)

    assert signal == [1, 1, 0]


def test_fng_at_week_close_uses_last_index_on_or_before_sunday():
    daily = {
        date(2022, 1, 8): 40,  # Saturday
        date(2022, 1, 10): 90,  # Monday after the week
    }
    weeks = _weeks_from_closes([100.0], start=date(2022, 1, 9))

    aligned = align_fng_to_weeks(weeks, daily)

    assert aligned == [40]


def test_fng_alignment_is_none_when_history_has_not_started():
    daily = {date(2022, 2, 1): 50}
    weeks = _weeks_from_closes([100.0], start=date(2022, 1, 9))

    aligned = align_fng_to_weeks(weeks, daily)

    assert aligned == [None]


def test_max_drawdown_is_peak_to_trough_on_wealth():
    weeks = _weeks_from_closes([100.0, 200.0, 100.0])
    signals = [1, 1, 1]

    result = backtest(weeks, signals)

    assert result.terminal_wealth == pytest.approx(1.0)
    assert result.max_drawdown == pytest.approx(-0.5)


def test_pass_a_needs_ten_percentage_points_better_drawdown():
    bh = BacktestResult(1.0, -0.50, 1.0, 0, date(2022, 1, 9), date(2022, 1, 23), 2)
    barely = BacktestResult(1.0, -0.49, 0.5, 1, date(2022, 1, 9), date(2022, 1, 23), 2)
    enough = BacktestResult(0.5, -0.40, 0.5, 1, date(2022, 1, 9), date(2022, 1, 23), 2)

    assert pass_a(barely, bh) is False
    assert pass_a(enough, bh) is True


def test_pass_c_needs_a_and_wealth_within_ten_percent_of_buy_hold():
    bh = BacktestResult(2.0, -0.50, 1.0, 0, date(2022, 1, 9), date(2022, 1, 23), 2)
    cheap_crash = BacktestResult(1.79, -0.40, 0.5, 1, date(2022, 1, 9), date(2022, 1, 23), 2)
    close_enough = BacktestResult(1.80, -0.40, 0.5, 1, date(2022, 1, 9), date(2022, 1, 23), 2)

    assert pass_c(cheap_crash, bh) is False
    assert pass_c(close_enough, bh) is True
    assert pass_a(cheap_crash, bh) is True


def test_window_starts_at_last_weekly_close_on_or_before_start_date():
    weeks = _weeks_from_closes([100.0, 110.0, 121.0], start=date(2021, 12, 26))
    signals = [1, 1, 1]

    result = backtest(weeks, signals, start=date(2022, 1, 1), end=date(2022, 1, 9))

    assert result.start == date(2021, 12, 26)
    assert result.end == date(2022, 1, 9)
    assert result.terminal_wealth == pytest.approx(1.21)


def test_window_inherits_already_filled_position_without_rechanging_cost():
    # Out before the window, stay out. $1 at window start is already cash.
    weeks = _weeks_from_closes([100.0] * 4)
    signals = [0, 0, 0, 0]

    result = backtest(
        weeks,
        signals,
        start=weeks[2][0],
        end=weeks[3][0],
    )

    assert result.round_trips == 0
    assert result.terminal_wealth == pytest.approx(1.0)
    assert result.time_in_btc == pytest.approx(0.0)


def test_dollar_backtest_converts_start_cash_to_btc_with_no_opening_fee():
    weeks = _weeks_from_closes([50_000.0, 100_000.0])
    signals = [1, 1]

    result = dollar_backtest(weeks, signals, starting_dollars=10_000.0)

    assert result.start_dollars == pytest.approx(10_000.0)
    assert result.start_btc == pytest.approx(10_000.0 / 50_000.0)
    assert result.end_dollars == pytest.approx(20_000.0)
    assert result.end_btc == pytest.approx(0.2)
    assert result.end_in_btc is True
    assert result.fees_paid == pytest.approx(0.0)
    assert result.flips == 0


def test_dollar_backtest_fresh_start_buys_btc_even_if_prior_signal_was_cash():
    weeks = _weeks_from_closes([100.0, 100.0, 200.0, 100.0])
    signals = [0, 0, 0, 0]
    inherited = backtest(weeks, signals, start=weeks[2][0], end=weeks[3][0])
    fresh = dollar_backtest(
        weeks,
        signals,
        start=weeks[2][0],
        end=weeks[3][0],
        starting_dollars=10_000.0,
    )

    assert inherited.terminal_wealth == pytest.approx(1.0)
    assert inherited.time_in_btc == pytest.approx(0.0)
    assert fresh.start_btc == pytest.approx(10_000.0 / 200.0)
    assert fresh.end_dollars == pytest.approx(5_000.0)
    assert fresh.end_in_btc is True
    assert fresh.time_in_btc == pytest.approx(1.0)


def test_dollar_backtest_charges_ten_bps_on_flips_not_the_opening_buy():
    weeks = _weeks_from_closes([100.0, 100.0, 100.0])
    signals = [0, 0, 0]

    result = dollar_backtest(weeks, signals, starting_dollars=10_000.0)

    assert result.fees_paid == pytest.approx(10.0)
    assert result.end_dollars == pytest.approx(9_990.0)
    assert result.flips == 1
    assert result.round_trips == 1
    assert result.end_in_btc is False
    assert result.end_cash == pytest.approx(9_990.0)
    assert result.last_flip == weeks[1][0]


def test_dollar_backtest_scales_inherited_unit_wealth_when_asked():
    weeks = _weeks_from_closes([100.0, 200.0, 100.0])
    signals = [1, 1, 1]
    unit = backtest(weeks, signals)
    dollars = dollar_backtest(
        weeks,
        signals,
        starting_dollars=10_000.0,
        inherit_position=True,
    )

    assert dollars.end_dollars == pytest.approx(10_000.0 * unit.terminal_wealth)
    assert dollars.max_drawdown == pytest.approx(unit.max_drawdown)
    assert dollars.max_drawdown_dollars == pytest.approx(10_000.0)


def test_sma8_first_fill_bar_is_the_week_after_sma8_is_defined():
    weeks = _weeks_from_closes([100.0] * 12)

    assert SMA8_LOOKBACK == 8
    assert sma8_first_fill_date(weeks) == weeks[8][0]
    assert sma_signal(weeks, lookback=8)[7] is not None
    assert sma_signal(weeks, lookback=8)[6] is None


def test_sma_first_fill_bar_is_the_week_after_lookback_is_defined():
    weeks = _weeks_from_closes([100.0] * 45)

    assert sma_first_fill_date(weeks, lookback=40) == weeks[40][0]


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
