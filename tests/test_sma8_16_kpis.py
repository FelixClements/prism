"""SMA-8 in / SMA-16 out weekly KPIs: same-bar fills, 0.15% per side."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Sequence

import pytest

from price_forecast.sma8_16_kpis import (
    BUY_WEEKS,
    FILL_COST,
    SELL_WEEKS,
    STARTING_DOLLARS,
    WHIPSAW_MAX_HOLDING_BARS,
    cagr,
    compute_kpis,
    format_compact_monthly_table,
    format_monthly_csv,
    format_monthly_markdown,
    format_report,
    mar_ratio,
    max_drawdown,
    monthly_kpis,
    profit_factor,
    simulate_hodl,
    simulate_strategy,
    sma_at,
    sortino_ratio,
)


def _weeks_from_closes(
    closes: Sequence[float], *, start: date = date(2022, 1, 9)
) -> list[tuple[date, float]]:
    return [(start + timedelta(weeks=i), close) for i, close in enumerate(closes)]


def test_defaults_match_the_stated_product_rule():
    assert BUY_WEEKS == 8
    assert SELL_WEEKS == 16
    assert FILL_COST == pytest.approx(0.0015)
    assert STARTING_DOLLARS == 10_000.0
    assert WHIPSAW_MAX_HOLDING_BARS == 2


def test_sma_at_t_uses_closes_through_t_inclusive():
    closes = [float(i + 1) for i in range(20)]

    at_t = sma_at(closes, 10, 8)
    without_future = sma_at(closes[:11], 10, 8)

    assert at_t == pytest.approx(sum(closes[3:11]) / 8)
    assert at_t == pytest.approx(without_future)
    assert at_t != pytest.approx(sum(closes[3:12]) / 8)


def test_no_trade_before_both_sma8_and_sma16_exist():
    weeks = _weeks_from_closes([200.0] * 15)

    with pytest.raises(ValueError, match="SMA-16"):
        simulate_strategy(weeks)


def test_does_not_buy_when_close_equals_sma8():
    weeks = _weeks_from_closes([100.0] * 16)

    path = simulate_strategy(weeks)

    assert path.fills == []
    assert path.long[-1] is False


def test_buys_when_close_is_strictly_above_sma8():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0])

    path = simulate_strategy(weeks)

    assert [fill.side for fill in path.fills] == ["BUY"]
    assert path.fills[0].index == 15
    assert path.fills[0].price == pytest.approx(110.0)
    assert path.long[-1] is True


def test_does_not_sell_when_close_equals_sma16_while_long():
    prefix = [100.0] * 15 + [110.0]
    # Next close C equals SMA-16 including C: 16C = sum(last 15) + C.
    equal_sma16 = sum(prefix[-15:]) / 15
    weeks = _weeks_from_closes(prefix + [equal_sma16])

    path = simulate_strategy(weeks)

    assert [fill.side for fill in path.fills] == ["BUY"]
    assert path.long[-1] is True


def test_sells_when_close_is_strictly_below_sma16_while_long():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0, 50.0])

    path = simulate_strategy(weeks)

    assert [fill.side for fill in path.fills] == ["BUY", "SELL"]
    assert path.fills[1].index == 16
    assert path.fills[1].price == pytest.approx(50.0)
    assert path.long[-1] is False


def test_stays_flat_when_close_is_below_sma8():
    # Strictly falling: each close is below its SMA-8, so never enter.
    closes = [200.0 - i for i in range(20)]
    weeks = _weeks_from_closes(closes)

    path = simulate_strategy(weeks)

    assert path.fills == []
    assert path.end_dollars == pytest.approx(STARTING_DOLLARS)
    assert all(long is False for long in path.long)


def test_stays_long_when_close_is_above_sma16():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [110.0, 120.0])

    path = simulate_strategy(weeks)

    assert [fill.side for fill in path.fills] == ["BUY"]
    assert path.long[-1] is True


def test_does_not_buy_and_sell_on_the_same_bar():
    # First valid bar is strictly above both SMAs. Evaluate from FLAT → BUY only.
    weeks = _weeks_from_closes([100.0] * 15 + [110.0])

    path = simulate_strategy(weeks)

    assert [fill.side for fill in path.fills] == ["BUY"]


def test_signal_and_fill_use_the_same_weekly_close():
    # Buy at 100 on the first valid bar; next week 200 must not be the fill.
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [200.0])

    path = simulate_strategy(weeks)

    assert path.fills[0].price == pytest.approx(110.0)
    assert path.equity[0] == pytest.approx(STARTING_DOLLARS * (1.0 - FILL_COST))
    assert path.equity[-1] == pytest.approx(
        STARTING_DOLLARS * (1.0 - FILL_COST) * 200.0 / 110.0
    )


def test_future_weeks_do_not_change_earlier_smas_or_fills():
    base = [100.0] * 15 + [110.0] + [110.0]
    without_future = simulate_strategy(_weeks_from_closes(base))
    with_future = simulate_strategy(_weeks_from_closes(base + [10_000.0]))

    assert sma_at(base + [10_000.0], 16, 16) == pytest.approx(sma_at(base, 16, 16))
    assert [(f.side, f.index, f.price) for f in with_future.fills[: len(without_future.fills)]] == [
        (f.side, f.index, f.price) for f in without_future.fills
    ]
    assert with_future.equity[: len(without_future.equity)] == pytest.approx(
        without_future.equity
    )


def test_one_buy_one_sell_applies_fifteen_bps_each_way():
    # Buy 110, ride 110 then 120, sell 50. Exact cash math is in the assertions.
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [110.0, 120.0, 50.0])

    path = simulate_strategy(weeks)

    after_buy = STARTING_DOLLARS * (1.0 - FILL_COST)
    btc = after_buy / 110.0
    proceeds = btc * 50.0
    after_sell = proceeds * (1.0 - FILL_COST)
    assert [fill.side for fill in path.fills] == ["BUY", "SELL"]
    assert path.fills[0].price == pytest.approx(110.0)
    assert path.fills[1].price == pytest.approx(50.0)
    assert path.end_dollars == pytest.approx(after_sell)
    assert path.fees_paid == pytest.approx(STARTING_DOLLARS * FILL_COST + proceeds * FILL_COST)
    assert path.completed_round_trips == 1


def test_hodl_pays_one_entry_fee_and_no_exit_fee():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [200.0])

    hodl = simulate_hodl(weeks)

    assert [fill.side for fill in hodl.fills] == ["BUY"]
    assert hodl.fills[0].price == pytest.approx(110.0)
    assert hodl.fees_paid == pytest.approx(STARTING_DOLLARS * FILL_COST)
    assert hodl.end_dollars == pytest.approx(
        STARTING_DOLLARS * (1.0 - FILL_COST) * 200.0 / 110.0
    )
    assert hodl.equity[0] == pytest.approx(STARTING_DOLLARS * (1.0 - FILL_COST))


def test_hodl_entry_matches_first_strategy_comparable_bar():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [110.0])

    strategy = simulate_strategy(weeks)
    hodl = simulate_hodl(weeks)

    assert strategy.dates[0] == hodl.dates[0]
    assert strategy.dates[0] == weeks[15][0]
    assert hodl.start_price == pytest.approx(110.0)


def test_open_position_is_marked_to_last_close_in_total_return():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [150.0])

    report = compute_kpis(weeks)

    assert report.strategy.completed_round_trips == 0
    assert report.strategy.end_dollars == pytest.approx(
        STARTING_DOLLARS * (1.0 - FILL_COST) * 150.0 / 110.0
    )
    assert report.strategy.total_return == pytest.approx(
        report.strategy.end_dollars / STARTING_DOLLARS - 1.0
    )


def test_profit_factor_includes_open_trade_mtm_as_virtual_close():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [150.0])

    report = compute_kpis(weeks)

    assert report.strategy.completed_round_trips == 0
    assert report.strategy.win_rate is None
    assert report.strategy.profit_factor == math.inf
    assert report.hodl.profit_factor is None


def test_profit_factor_is_winning_dollars_over_losing_dollars():
    assert profit_factor([100.0, -50.0]) == pytest.approx(2.0)
    assert profit_factor([100.0]) == math.inf
    assert profit_factor([-40.0, -10.0]) == pytest.approx(0.0)
    assert profit_factor([]) is None


def test_whipsaw_is_completed_round_trip_held_at_most_two_weekly_bars():
    # Holding period = exit_index - entry_index. Buy at 15, sell at 17 → 2 → whipsaw.
    short = simulate_strategy(_weeks_from_closes([100.0] * 15 + [110.0] + [200.0, 50.0]))
    # Buy at 15, hold 16 and 17, sell at 18 → 3 → not a whipsaw.
    longer = simulate_strategy(
        _weeks_from_closes([100.0] * 15 + [110.0] + [110.0, 120.0, 50.0])
    )

    assert short.fills[0].index == 15
    assert short.fills[1].index == 17
    assert short.whipsaws == 1
    assert longer.fills[1].index - longer.fills[0].index == 3
    assert longer.whipsaws == 0


def test_win_rate_uses_completed_round_trips_after_costs():
    # One completed losing round trip.
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [110.0, 120.0, 50.0])

    report = compute_kpis(weeks)

    assert report.strategy.completed_round_trips == 1
    assert report.strategy.win_rate == pytest.approx(0.0)
    assert report.hodl.win_rate is None
    assert report.hodl.completed_round_trips is None


def test_exposure_is_fraction_of_comparable_weeks_long_after_the_fill():
    # Buy at bar 15, sell at bar 16, then cash. Two comparable weeks: long, then cash.
    weeks = _weeks_from_closes([100.0] * 15 + [110.0, 50.0])

    path = simulate_strategy(weeks)

    assert path.long == [True, False]
    assert path.exposure == pytest.approx(0.5)


def test_max_drawdown_is_peak_to_trough_on_equity():
    assert max_drawdown([100.0, 110.0, 88.0]) == pytest.approx(88.0 / 110.0 - 1.0)
    assert max_drawdown([100.0, 120.0, 150.0]) == pytest.approx(0.0)


def test_sortino_is_na_when_there_are_no_downside_weeks():
    assert sortino_ratio([0.01, 0.02, 0.0]) is None
    assert sortino_ratio([-0.05]) is None


def test_sortino_uses_sample_stdev_of_negative_weeks_and_sqrt_52():
    returns = [0.10, -0.05, -0.10, 0.20]
    negatives = [-0.05, -0.10]
    mean = sum(returns) / 4
    neg_mean = sum(negatives) / 2
    downside = math.sqrt(sum((x - neg_mean) ** 2 for x in negatives) / (2 - 1))
    expected = (mean / downside) * math.sqrt(52)

    assert sortino_ratio(returns) == pytest.approx(expected)


def test_mar_is_na_when_max_drawdown_is_zero():
    assert mar_ratio(cagr=0.20, max_drawdown=0.0) is None
    assert mar_ratio(cagr=0.20, max_drawdown=-0.50) == pytest.approx(0.40)


def test_cagr_uses_elapsed_calendar_years():
    start = date(2020, 1, 5)
    end = date(2022, 1, 2)
    years = (end - start).days / 365.25
    expected = (2.0) ** (1.0 / years) - 1.0

    assert cagr(10_000.0, 20_000.0, start, end) == pytest.approx(expected)


def test_flat_never_entered_path_has_na_sortino_and_mar():
    weeks = _weeks_from_closes([200.0 - i for i in range(20)])

    report = compute_kpis(weeks)

    assert report.strategy.total_return == pytest.approx(0.0)
    assert report.strategy.max_drawdown == pytest.approx(0.0)
    assert report.strategy.sortino is None
    assert report.strategy.mar is None


def test_strategy_alpha_is_excess_total_return_not_capm():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [110.0, 120.0, 50.0])

    report = compute_kpis(weeks)

    assert report.strategy.alpha == pytest.approx(
        report.strategy.total_return - report.hodl.total_return
    )


def test_fee_drag_compares_no_fee_total_return_to_with_fee():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [200.0])

    report = compute_kpis(weeks)
    no_fee = simulate_strategy(weeks, cost=0.0)

    assert report.strategy.no_fee_total_return == pytest.approx(
        no_fee.end_dollars / STARTING_DOLLARS - 1.0
    )
    assert report.strategy.fee_drag_on_total_return == pytest.approx(
        report.strategy.no_fee_total_return - report.strategy.total_return
    )
    assert report.strategy.fees_pct_of_start == pytest.approx(
        report.strategy.fees_paid / STARTING_DOLLARS
    )


def test_starting_dollars_can_be_overridden():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0])

    path = simulate_strategy(weeks, starting_dollars=20_000.0)

    assert path.equity[0] == pytest.approx(20_000.0 * (1.0 - FILL_COST))


def test_report_table_marks_hodl_trade_kpis_na():
    weeks = _weeks_from_closes([100.0] * 15 + [110.0] + [110.0])

    text = format_report(compute_kpis(weeks))

    assert "Not investment advice" in text
    assert "SMAGateV1" in text
    assert "not the frozen t+1 bakeoff" in text.lower()
    assert "~30-40%" in text
    assert "Strategy" in text and "Buy & Hold" in text
    assert "n/a" in text
    assert "excess total return" in text.lower()
    assert "same-bar" in text.lower()
    assert "0.15%" in text
    assert "contemporaneous" in text.lower()
    assert "start in cash" in text.lower()


# First comparable bar is index 15. With Sunday 2021-10-03 that bar is 2022-01-16,
# so January has three weekly points (16, 23, 30) and February starts 2022-02-06.
_MONTH_SPAN_START = date(2021, 10, 3)


def _month_span_weeks(extra_closes: Sequence[float]) -> list[tuple[date, float]]:
    return _weeks_from_closes([100.0] * 15 + [110.0] + list(extra_closes), start=_MONTH_SPAN_START)


def test_monthly_rows_group_by_calendar_month_of_weekly_bar_date():
    # Comparable weeks: Jan 16/23/30 and Feb 6/13.
    weeks = _month_span_weeks([110.0, 120.0, 130.0, 140.0])

    rows = monthly_kpis(weeks)

    assert [row.year_month for row in rows] == ["2022-01", "2022-02"]
    assert rows[0].n_weeks == 3
    assert rows[1].n_weeks == 2
    path = simulate_strategy(weeks)
    jan_dates = [day for day in path.dates if day.year == 2022 and day.month == 1]
    assert jan_dates == [date(2022, 1, 16), date(2022, 1, 23), date(2022, 1, 30)]


def test_month_end_kpis_do_not_use_later_weeks():
    extra_jan_feb_mar = [110.0, 120.0, 50.0, 50.0, 50.0, 50.0, 200.0, 210.0]
    full = _month_span_weeks(extra_jan_feb_mar)
    through_february = [(day, close) for day, close in full if day < date(2022, 3, 1)]

    full_rows = monthly_kpis(full)
    truncated_rows = monthly_kpis(through_february)
    full_jan_feb = [row for row in full_rows if row.year_month in {"2022-01", "2022-02"}]

    assert any(row.year_month == "2022-03" for row in full_rows)
    assert [row.year_month for row in truncated_rows] == ["2022-01", "2022-02"]
    assert len(full_jan_feb) == 2

    truncated_path = simulate_strategy(through_february)
    assert full_jan_feb[1].strategy_end_dollars == pytest.approx(truncated_path.end_dollars)
    assert truncated_rows[1].strategy_end_dollars == pytest.approx(truncated_path.end_dollars)
    assert full_jan_feb[0].strategy_end_dollars == pytest.approx(
        truncated_rows[0].strategy_end_dollars
    )
    assert full_jan_feb[0].cum_profit_factor == pytest.approx(
        truncated_rows[0].cum_profit_factor
    )
    assert full_jan_feb[1].completed_round_trips == truncated_rows[1].completed_round_trips
    # March's 200 close must not change February's month-end mark.
    assert full_jan_feb[1].strategy_end_dollars != pytest.approx(
        STARTING_DOLLARS * (1.0 - FILL_COST) * 200.0 / 100.0
    )


def test_monthly_returns_compound_to_full_period_wealth():
    weeks = _month_span_weeks([110.0, 90.0, 120.0, 80.0, 130.0, 70.0, 140.0])
    rows = monthly_kpis(weeks)
    report = compute_kpis(weeks)

    strategy_wealth = STARTING_DOLLARS
    hodl_wealth = STARTING_DOLLARS
    for row in rows:
        strategy_wealth *= 1.0 + row.strategy_monthly_return
        hodl_wealth *= 1.0 + row.hodl_monthly_return

    assert strategy_wealth == pytest.approx(report.strategy.end_dollars)
    assert hodl_wealth == pytest.approx(report.hodl.end_dollars)
    assert rows[-1].strategy_end_dollars == pytest.approx(report.strategy.end_dollars)
    assert rows[-1].hodl_end_dollars == pytest.approx(report.hodl.end_dollars)
    assert rows[-1].cum_strategy_total_return == pytest.approx(report.strategy.total_return)
    assert rows[-1].cum_hodl_total_return == pytest.approx(report.hodl.total_return)
    assert rows[-1].cum_alpha == pytest.approx(report.strategy.alpha)
    assert rows[-1].cum_profit_factor == pytest.approx(report.strategy.profit_factor)
    assert rows[-1].cum_strategy_max_drawdown == pytest.approx(report.strategy.max_drawdown)
    assert rows[-1].cum_hodl_max_drawdown == pytest.approx(report.hodl.max_drawdown)
    assert rows[-1].cum_whipsaws == report.strategy.whipsaws
    assert rows[-1].cum_fees_paid == pytest.approx(report.strategy.fees_paid)
    assert rows[-1].cum_completed_round_trips == report.strategy.completed_round_trips
    for got, expected in (
        (rows[-1].cum_strategy_sortino, report.strategy.sortino),
        (rows[-1].cum_hodl_sortino, report.hodl.sortino),
        (rows[-1].cum_strategy_mar, report.strategy.mar),
        (rows[-1].cum_hodl_mar, report.hodl.mar),
        (rows[-1].cum_win_rate, report.strategy.win_rate),
    ):
        if expected is None:
            assert got is None
        else:
            assert got == pytest.approx(expected)


def test_intra_month_max_dd_uses_only_that_months_equity():
    # HODL is always long, so January equity tracks 100 → 110 → 88.
    weeks = _month_span_weeks([110.0, 88.0, 88.0, 88.0])
    rows = monthly_kpis(weeks)
    hodl = simulate_hodl(weeks)

    jan = next(row for row in rows if row.year_month == "2022-01")
    jan_equity = [
        equity
        for day, equity in zip(hodl.dates, hodl.equity)
        if day.year == 2022 and day.month == 1
    ]
    assert len(jan_equity) == 3
    assert jan.hodl_max_drawdown == pytest.approx(max_drawdown(jan_equity))
    assert jan.hodl_max_drawdown == pytest.approx(88.0 / 110.0 - 1.0)
    # Cumulative HODL DD can only be the same or worse than the January slice.
    assert jan.cum_hodl_max_drawdown <= jan.hodl_max_drawdown + 1e-12


def test_one_or_two_weekly_points_still_get_a_month_max_dd():
    # Index 15 on 2022-01-30 is the only January comparable bar.
    one_point = _weeks_from_closes([100.0] * 15 + [110.0] + [110.0], start=date(2021, 10, 17))
    two_points = _weeks_from_closes(
        [100.0] * 15 + [110.0, 88.0], start=date(2021, 10, 10)
    )

    one_rows = monthly_kpis(one_point)
    two_rows = monthly_kpis(two_points)
    jan_one = next(row for row in one_rows if row.year_month == "2022-01")
    jan_two = next(row for row in two_rows if row.year_month == "2022-01")

    assert jan_one.n_weeks == 1
    assert jan_one.strategy_max_drawdown == pytest.approx(0.0)
    assert jan_one.hodl_max_drawdown == pytest.approx(0.0)
    assert jan_two.n_weeks == 2
    assert jan_two.hodl_max_drawdown == pytest.approx(88.0 / 110.0 - 1.0)


def test_round_trips_and_fees_land_in_the_sell_month_not_the_buy_month():
    # Buy first comparable January bar; sell first February bar (close 50 < SMA-16).
    weeks = _month_span_weeks([110.0, 120.0, 50.0, 50.0])
    rows = monthly_kpis(weeks)
    path = simulate_strategy(weeks)
    jan = next(row for row in rows if row.year_month == "2022-01")
    feb = next(row for row in rows if row.year_month == "2022-02")

    assert [fill.side for fill in path.fills] == ["BUY", "SELL"]
    assert path.fills[0].date.month == 1
    assert path.fills[1].date.month == 2
    assert jan.completed_round_trips == 0
    assert jan.held == "BTC"
    assert jan.fees_paid == pytest.approx(path.fills[0].fee)
    assert jan.cum_completed_round_trips == 0
    assert jan.cum_win_rate is None
    january_mtm = path.equity[2] - (path.fills[0].equity_after + path.fills[0].fee)
    assert jan.cum_profit_factor == pytest.approx(profit_factor([january_mtm]))
    assert feb.completed_round_trips == 1
    assert feb.held == "cash"
    assert feb.fees_paid == pytest.approx(path.fills[1].fee)
    assert feb.cum_completed_round_trips == 1
    assert feb.cum_fees_paid == pytest.approx(path.fees_paid)
    assert feb.cum_win_rate == pytest.approx(0.0)
    assert jan.exposure == pytest.approx(1.0)
    # Sell week is cash after the fill, then the next week stays cash.
    assert feb.exposure == pytest.approx(0.0)


def test_monthly_csv_and_markdown_label_monthly_vs_cumulative_columns():
    weeks = _month_span_weeks([110.0, 120.0, 50.0, 50.0])
    rows = monthly_kpis(weeks)
    report = compute_kpis(weeks)
    csv_text = format_monthly_csv(rows)
    md_text = format_monthly_markdown(report, rows)
    compact = format_compact_monthly_table(rows)

    assert "year_month" in csv_text.splitlines()[0]
    assert "monthly_strategy_return" in csv_text
    assert "monthly_hodl_return" in csv_text
    assert "monthly_strategy_max_dd" in csv_text
    assert "cum_strategy_total_return" in csv_text
    assert "cum_alpha" in csv_text
    assert "cum_profit_factor" in csv_text
    assert "cum_strategy_sortino" in csv_text
    assert "cum_win_rate" in csv_text
    assert "Not investment advice" in md_text
    assert "monthly" in md_text.lower()
    assert "cumulative" in md_text.lower()
    assert "2022-01" in compact
    assert "Monthly return" in compact or "monthly return" in compact.lower()
    # Compact print is the return table, not the full cumulative grid.
    assert "cum_profit_factor" not in compact
