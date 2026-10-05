from __future__ import annotations

from datetime import date
from typing import Callable, Sequence

from price_forecast.backtest.engine import EquityPath, Fill
from price_forecast.search.spec import Spec
from price_forecast.strategies.indicators import WeekBar, series_values
from price_forecast.strategies.signals import sma_at

FILL_COST = 0.0015
STARTING_DOLLARS = 10_000.0
Gate = Callable[[date], tuple[bool, bool]]


def _lookback(spec: Spec) -> int:
    values = [
        value
        for value in (
            spec.close_above_sma_weeks,
            spec.close_below_sma_weeks,
            spec.slow_weeks,
            spec.prior_weeks,
        )
        if value
    ]
    return max(values) if values else 1


def _filters(spec: Spec, day: date, gate: Gate) -> bool:
    if not spec.base_or_breakout and not spec.above_long_averages:
        return True
    base, long = gate(day)
    if spec.base_or_breakout and not base:
        return False
    if spec.above_long_averages and not long:
        return False
    return True


def _threshold_entry(spec: Spec, closes: list[float], index: int, day: date, gate: Gate) -> bool:
    if not _filters(spec, day, gate):
        return False
    if spec.close_above_sma_weeks is None:
        return spec.base_or_breakout or spec.above_long_averages
    return closes[index] > sma_at(closes, index, spec.close_above_sma_weeks)


def _threshold_exit(spec: Spec, closes: list[float], index: int) -> bool:
    if spec.close_below_sma_weeks is not None and closes[index] < sma_at(
        closes, index, spec.close_below_sma_weeks
    ):
        return True
    if spec.down_week is None or index < 1:
        return False
    reference = spec.close_above_sma_weeks or spec.close_below_sma_weeks
    dropped = closes[index] <= closes[index - 1] * (1.0 - spec.down_week)
    under = closes[index] < sma_at(closes, index, reference)
    return dropped and under


def _compare(left: float, op: str, right: float) -> bool:
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    raise ValueError(op)


def _indicator_columns(spec: Spec, bars: Sequence[WeekBar]) -> dict:
    columns: dict[tuple, list[float | None]] = {}
    for condition in spec.conditions:
        for name, args in (
            (condition.left, condition.args),
            (condition.right_series, condition.right_args),
        ):
            if name is None or (name, args) in columns:
                continue
            columns[(name, args)] = series_values(name, args, bars)
    return columns


def _indicator_ready(spec: Spec, columns: dict, index: int) -> bool:
    for condition in spec.conditions:
        if columns[(condition.left, condition.args)][index] is None:
            return False
        if condition.right_series is None:
            continue
        if columns[(condition.right_series, condition.right_args)][index] is None:
            return False
    return True


def _indicator_want(spec: Spec, columns: dict, index: int, day: date, gate: Gate) -> int:
    if not _filters(spec, day, gate):
        return 0
    for condition in spec.conditions:
        left = columns[(condition.left, condition.args)][index]
        if condition.right_series is None:
            right = condition.right_value
        else:
            right = columns[(condition.right_series, condition.right_args)][index]
        if left is None or right is None or not _compare(left, condition.op, float(right)):
            return 0
    return 1


def _desired(spec: Spec, closes: list[float], index: int, day: date, gate: Gate) -> int:
    if not _filters(spec, day, gate):
        return 0
    if spec.mode == "dual_average":
        fast = sma_at(closes, index, spec.fast_weeks)
        slow = sma_at(closes, index, spec.slow_weeks)
        return 1 if fast > slow else 0
    prior = closes[index - spec.prior_weeks : index]
    return 1 if closes[index] >= max(prior) else 0


def simulate_spec(
    weeks: Sequence[tuple[date, float]],
    spec: Spec,
    gate: Gate,
    *,
    bars: Sequence[WeekBar] | None = None,
    starting_dollars: float = STARTING_DOLLARS,
    cost: float = FILL_COST,
) -> EquityPath:
    if starting_dollars <= 0:
        raise ValueError("starting_dollars must be positive")
    if cost < 0:
        raise ValueError("cost must be non-negative")
    columns = None
    if spec.mode == "indicator":
        if bars is None or len(bars) != len(weeks):
            raise ValueError("indicator spec needs weekly bars")
        columns = _indicator_columns(spec, bars)
        ready = [index for index in range(len(weeks)) if _indicator_ready(spec, columns, index)]
        if not ready:
            raise ValueError("indicator is undefined on every week")
        first = ready[0]
    else:
        first = _lookback(spec)
        if len(weeks) <= first:
            raise ValueError("need more weekly bars than the longest lookback")
    closes = [close for _day, close in weeks]
    position = 0
    wealth = starting_dollars
    btc = 0.0
    pending: str | None = None
    cash_before: float | None = None
    fees_paid = 0.0
    fills: list[Fill] = []
    dates: list[date] = []
    marked: list[float] = []
    equity: list[float] = []
    long_flags: list[bool] = []
    completed: list[float] = []

    for index in range(first, len(weeks)):
        day, close = weeks[index]
        if pending == "buy" and position == 0:
            fee = wealth * cost
            cash_before = wealth
            wealth -= fee
            fees_paid += fee
            btc = wealth / close
            position = 1
            pending = None
            fills.append(Fill(index, day, "BUY", close, fee, wealth))
        elif pending == "sell" and position == 1:
            proceeds = btc * close
            fee = proceeds * cost
            wealth = proceeds - fee
            fees_paid += fee
            assert cash_before is not None
            completed.append(wealth - cash_before)
            btc = 0.0
            position = 0
            cash_before = None
            pending = None
            fills.append(Fill(index, day, "SELL", close, fee, wealth))
        if position == 1:
            wealth = btc * close
        dates.append(day)
        marked.append(close)
        equity.append(wealth)
        long_flags.append(position == 1)
        if index + 1 >= len(weeks):
            continue
        if spec.mode == "threshold":
            if position == 0 and _threshold_entry(spec, closes, index, day, gate):
                pending = "buy"
            elif position == 1 and _threshold_exit(spec, closes, index):
                pending = "sell"
        elif spec.mode == "indicator":
            assert columns is not None
            want = _indicator_want(spec, columns, index, day, gate)
            if position == 0 and want == 1:
                pending = "buy"
            elif position == 1 and want == 0:
                pending = "sell"
        else:
            want = _desired(spec, closes, index, day, gate)
            if position == 0 and want == 1:
                pending = "buy"
            elif position == 1 and want == 0:
                pending = "sell"

    pf_pnls = list(completed)
    if position == 1:
        assert cash_before is not None
        pf_pnls.append(wealth - cash_before)
    count = len(equity)
    return EquityPath(
        dates=dates,
        closes=marked,
        equity=equity,
        long=long_flags,
        fills=fills,
        start_dollars=starting_dollars,
        end_dollars=wealth,
        start_price=weeks[first][1],
        end_price=weeks[-1][1],
        start=weeks[first][0],
        end=weeks[-1][0],
        fees_paid=fees_paid,
        completed_round_trips=len(completed),
        whipsaws=0,
        exposure=(sum(1 for flag in long_flags if flag) / count) if count else 0.0,
        completed_pnls=completed,
        pf_pnls=pf_pnls,
    )
