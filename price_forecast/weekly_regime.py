"""Weekly BTC in/out regime filter. Not a dollar-close forecast.

Frozen rules (do not retune after seeing results):

- Weeks: UTC, Monday 00:00 through Sunday 24:00. Bar date is the Sunday.
  Weekly close is the last Coinbase UTC daily close in that window.
  Incomplete trailing weeks are dropped.
- Fill: signal at week t close is executed at week t+1 close.
- SMA: in iff close > SMA (8 or 12). SMA includes this week's close.
- Dual SMA: classic crossover, in iff SMA12 > SMA26 (both include this close).
- Asymmetric SMA: while in BTC, sell iff close < SMA(sell); while in cash, buy iff close > SMA(buy).
- Donchian 12: in iff close >= max of the prior 12 weeks (excluding this week).
- Costs: 10 bps of wealth on each flip. Cash return is 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence

from price_forecast.series import PriceSeries

COST_BPS = 10
_COST = COST_BPS / 10_000
FNG_GREED_EXIT = 75
FNG_FEAR_ENTRY = 25
WEALTH_FLOOR = 0.9
DD_IMPROVEMENT = 0.10
SMA8_LOOKBACK = 8
_DAYS_PER_YEAR = 365.25


@dataclass(frozen=True)
class BacktestResult:
    terminal_wealth: float
    max_drawdown: float
    time_in_btc: float
    round_trips: int
    start: date
    end: date
    n_intervals: int


@dataclass(frozen=True)
class DollarBacktestResult:
    start_dollars: float
    end_dollars: float
    start_btc: float
    end_btc: float | None
    end_cash: float | None
    end_in_btc: bool
    max_drawdown: float
    max_drawdown_dollars: float
    total_return: float
    cagr: float | None
    time_in_btc: float
    round_trips: int
    flips: int
    fees_paid: float
    start: date
    end: date
    n_intervals: int
    last_flip: date | None
    last_signal: int | None
    start_price: float
    end_price: float


def _sunday_week_end(day: date) -> date:
    return day + timedelta(days=(6 - day.weekday()))


def weekly_closes(series: PriceSeries) -> list[tuple[date, float]]:
    """Last UTC daily close in each complete Sunday-ending week."""
    last_day = series.dates()[-1]
    buckets: dict[date, tuple[date, float]] = {}
    for day in series.dates():
        week_end = _sunday_week_end(day)
        buckets[week_end] = (day, series.close_at(day))
    weeks = []
    for week_end in sorted(buckets):
        if week_end > last_day:
            continue
        weeks.append((week_end, buckets[week_end][1]))
    return weeks


def sma_signal(
    weeks: Sequence[tuple[date, float]],
    *,
    lookback: int,
) -> list[int | None]:
    """In (1) iff this week's close is strictly above the lookback SMA."""
    closes = [close for _week_end, close in weeks]
    signals: list[int | None] = []
    for i, close in enumerate(closes):
        if i + 1 < lookback:
            signals.append(None)
            continue
        sma = sum(closes[i + 1 - lookback : i + 1]) / lookback
        signals.append(1 if close > sma else 0)
    return signals


def _sma_at(closes: Sequence[float], index: int, lookback: int) -> float:
    return sum(closes[index + 1 - lookback : index + 1]) / lookback


def dual_sma_signal(
    weeks: Sequence[tuple[date, float]],
    *,
    fast: int = 12,
    slow: int = 26,
) -> list[int | None]:
    """Classic dual MA: in iff SMA(fast) > SMA(slow). Both include this close."""
    if fast >= slow:
        raise ValueError("fast lookback must be shorter than slow")
    closes = [close for _week_end, close in weeks]
    signals: list[int | None] = []
    for i in range(len(closes)):
        if i + 1 < slow:
            signals.append(None)
            continue
        signals.append(1 if _sma_at(closes, i, fast) > _sma_at(closes, i, slow) else 0)
    return signals


def asymmetric_sma_signal(
    weeks: Sequence[tuple[date, float]],
    *,
    buy_weeks: int,
    sell_weeks: int,
    start_in_btc: bool = True,
) -> list[int | None]:
    """In/out state machine: sell on the long SMA, buy on the short SMA."""
    if sell_weeks <= buy_weeks:
        raise ValueError("sell_weeks must be greater than buy_weeks")
    closes = [close for _week_end, close in weeks]
    position = 1 if start_in_btc else 0
    signals: list[int | None] = []
    for i, close in enumerate(closes):
        if i + 1 < sell_weeks:
            signals.append(None)
            continue
        if position == 1 and close < _sma_at(closes, i, sell_weeks):
            position = 0
        elif position == 0 and close > _sma_at(closes, i, buy_weeks):
            position = 1
        signals.append(position)
    return signals


def donchian_signal(
    weeks: Sequence[tuple[date, float]],
    *,
    lookback: int = 12,
) -> list[int | None]:
    """In iff close >= max of the prior `lookback` weeks, excluding this week."""
    closes = [close for _week_end, close in weeks]
    signals: list[int | None] = []
    for i, close in enumerate(closes):
        if i < lookback:
            signals.append(None)
            continue
        channel = max(closes[i - lookback : i])
        signals.append(1 if close >= channel else 0)
    return signals


def backtest(
    weeks: Sequence[tuple[date, float]],
    signals: Sequence[int | None],
    *,
    start: date | None = None,
    end: date | None = None,
    start_in_btc: bool = True,
) -> BacktestResult:
    """Signal at week t fills at week t+1 close. Inherited long is BTC."""
    if len(weeks) != len(signals):
        raise ValueError("signals must align 1:1 with weekly bars")
    if len(weeks) < 2:
        raise ValueError("need at least two weekly closes")

    first = 0
    last = len(weeks) - 1
    if start is not None:
        first = _last_on_or_before(weeks, start)
    if end is not None:
        last = _last_on_or_before(weeks, end)
    if last <= first:
        raise ValueError("window does not contain a weekly return")

    position = 1 if start_in_btc else 0
    for k in range(1, first + 1):
        fill = signals[k - 1]
        if fill is not None:
            position = fill

    wealth = 1.0
    peak = 1.0
    max_dd = 0.0
    in_weeks = 0
    round_trips = 0
    for i in range(first, last):
        if i > first:
            fill = signals[i - 1]
            if fill is not None and fill != position:
                wealth *= 1.0 - _COST
                if position == 1 and fill == 0:
                    round_trips += 1
                position = fill
        if position == 1:
            wealth *= weeks[i + 1][1] / weeks[i][1]
            in_weeks += 1
        peak = max(peak, wealth)
        max_dd = min(max_dd, wealth / peak - 1.0)

    n_intervals = last - first
    return BacktestResult(
        terminal_wealth=wealth,
        max_drawdown=max_dd,
        time_in_btc=in_weeks / n_intervals,
        round_trips=round_trips,
        start=weeks[first][0],
        end=weeks[last][0],
        n_intervals=n_intervals,
    )


def sma_first_fill_date(weeks: Sequence[tuple[date, float]], lookback: int) -> date:
    """Sunday bar where the first SMA(lookback) signal can fill."""
    if lookback < 1:
        raise ValueError("lookback must be at least 1")
    if len(weeks) <= lookback:
        raise ValueError(f"need more than {lookback} weekly bars to fill SMA-{lookback}")
    return weeks[lookback][0]


def sma8_first_fill_date(weeks: Sequence[tuple[date, float]]) -> date:
    """Sunday bar where the first SMA-8 signal can fill (week after SMA-8 is defined)."""
    return sma_first_fill_date(weeks, SMA8_LOOKBACK)


def dollar_backtest(
    weeks: Sequence[tuple[date, float]],
    signals: Sequence[int | None],
    *,
    start: date | None = None,
    end: date | None = None,
    starting_dollars: float = 10_000.0,
    inherit_position: bool = False,
    start_in_btc: bool = True,
) -> DollarBacktestResult:
    """Same fills as `backtest`, in dollars. Default is a fresh BTC buy at window start."""
    if starting_dollars <= 0:
        raise ValueError("starting_dollars must be positive")
    if len(weeks) != len(signals):
        raise ValueError("signals must align 1:1 with weekly bars")
    if len(weeks) < 2:
        raise ValueError("need at least two weekly closes")

    first = 0
    last = len(weeks) - 1
    if start is not None:
        first = _last_on_or_before(weeks, start)
    if end is not None:
        last = _last_on_or_before(weeks, end)
    if last <= first:
        raise ValueError("window does not contain a weekly return")

    position = 1 if start_in_btc else 0
    if inherit_position:
        for k in range(1, first + 1):
            fill = signals[k - 1]
            if fill is not None:
                position = fill

    start_price = weeks[first][1]
    end_price = weeks[last][1]
    start_btc = (starting_dollars / start_price) if position == 1 else 0.0
    wealth = starting_dollars
    peak = wealth
    max_dd = 0.0
    max_dd_dollars = 0.0
    in_weeks = 0
    round_trips = 0
    flips = 0
    fees_paid = 0.0
    last_flip: date | None = None
    for i in range(first, last):
        if i > first:
            fill = signals[i - 1]
            if fill is not None and fill != position:
                fee = wealth * _COST
                wealth -= fee
                fees_paid += fee
                flips += 1
                if position == 1 and fill == 0:
                    round_trips += 1
                position = fill
                last_flip = weeks[i][0]
        if position == 1:
            wealth *= weeks[i + 1][1] / weeks[i][1]
            in_weeks += 1
        peak = max(peak, wealth)
        max_dd = min(max_dd, wealth / peak - 1.0)
        max_dd_dollars = max(max_dd_dollars, peak - wealth)

    n_intervals = last - first
    end_in_btc = position == 1
    span_days = (weeks[last][0] - weeks[first][0]).days
    total_return = wealth / starting_dollars - 1.0
    cagr = (
        (wealth / starting_dollars) ** (_DAYS_PER_YEAR / span_days) - 1.0
        if span_days > 0 and wealth > 0
        else None
    )
    return DollarBacktestResult(
        start_dollars=starting_dollars,
        end_dollars=wealth,
        start_btc=start_btc,
        end_btc=(wealth / end_price) if end_in_btc else None,
        end_cash=None if end_in_btc else wealth,
        end_in_btc=end_in_btc,
        max_drawdown=max_dd,
        max_drawdown_dollars=max_dd_dollars,
        total_return=total_return,
        cagr=cagr,
        time_in_btc=in_weeks / n_intervals,
        round_trips=round_trips,
        flips=flips,
        fees_paid=fees_paid,
        start=weeks[first][0],
        end=weeks[last][0],
        n_intervals=n_intervals,
        last_flip=last_flip,
        last_signal=signals[last],
        start_price=start_price,
        end_price=end_price,
    )


def _last_on_or_before(weeks: Sequence[tuple[date, float]], day: date) -> int:
    idx = None
    for i, (week_end, _close) in enumerate(weeks):
        if week_end <= day:
            idx = i
        else:
            break
    if idx is None:
        raise ValueError(f"no weekly close on or before {day}")
    return idx


def apply_fng_overlay(
    signals: Sequence[int | None],
    fng: Sequence[int | None],
    *,
    greed_exit: int = FNG_GREED_EXIT,
) -> list[int | None]:
    """Force cash when F&G > 75. Missing F&G leaves the base signal unchanged."""
    if len(signals) != len(fng):
        raise ValueError("F&G series must align 1:1 with signals")
    out: list[int | None] = []
    for signal, value in zip(signals, fng, strict=True):
        if value is not None and value > greed_exit:
            out.append(0)
        else:
            out.append(signal)
    return out


def fng_only_signal(
    fng: Sequence[int | None],
    *,
    greed_exit: int = FNG_GREED_EXIT,
    fear_entry: int = FNG_FEAR_ENTRY,
    start_in_btc: bool = True,
) -> list[int]:
    """F&G > 75 cash; F&G < 25 BTC; else keep previous. Start in BTC."""
    position = 1 if start_in_btc else 0
    signals: list[int] = []
    for value in fng:
        if value is None:
            signals.append(position)
            continue
        if value > greed_exit:
            position = 0
        elif value < fear_entry:
            position = 1
        signals.append(position)
    return signals


def align_fng_to_weeks(
    weeks: Sequence[tuple[date, float]],
    daily_fng: dict[date, int],
) -> list[int | None]:
    """Last Fear & Greed print on or before each week's Sunday close."""
    days = sorted(daily_fng)
    aligned: list[int | None] = []
    cursor = -1
    for week_end, _close in weeks:
        while cursor + 1 < len(days) and days[cursor + 1] <= week_end:
            cursor += 1
        aligned.append(None if cursor < 0 else daily_fng[days[cursor]])
    return aligned


def pass_a(strategy: BacktestResult, buy_hold: BacktestResult) -> bool:
    """Max DD at least 10 percentage points better than buy-and-hold."""
    return strategy.max_drawdown - buy_hold.max_drawdown >= DD_IMPROVEMENT - 1e-12


def pass_c(strategy: BacktestResult, buy_hold: BacktestResult) -> bool:
    """A plus terminal wealth within 10% relative of buy-and-hold."""
    return (
        pass_a(strategy, buy_hold)
        and strategy.terminal_wealth >= WEALTH_FLOOR * buy_hold.terminal_wealth
    )
