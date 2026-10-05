"""Weekly indicator series. Bars in, one number per week out. No backtest imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence

from price_forecast.data.candles import Candle


@dataclass(frozen=True)
class WeekBar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None


def weekly_bars(candles: Sequence[Candle]) -> list[WeekBar]:
    """Sunday-ending weeks. The close matches weekly_sessions."""
    if not candles:
        raise ValueError("candles are empty")
    last_day = candles[-1].day
    buckets: dict[date, list[Candle]] = {}
    for candle in candles:
        week_end = candle.day + timedelta(days=(6 - candle.day.weekday()))
        buckets.setdefault(week_end, []).append(candle)
    bars: list[WeekBar] = []
    for week_end in sorted(buckets):
        if week_end > last_day:
            continue
        days = sorted(buckets[week_end], key=lambda candle: candle.day)
        volumes = [candle.volume for candle in days]
        volume = None if any(value is None for value in volumes) else float(sum(volumes))
        bars.append(
            WeekBar(
                day=days[-1].day,
                open=days[0].open,
                high=max(candle.high for candle in days),
                low=min(candle.low for candle in days),
                close=days[-1].close,
                volume=volume,
            )
        )
    return bars


def series_values(name: str, args: tuple, bars: Sequence[WeekBar]) -> list[float | None]:
    """One value per bar. None means the series is not defined on that week."""
    closes = [bar.close for bar in bars]
    if name == "close":
        return [float(close) for close in closes]
    if name == "sma":
        return _sma(closes, int(args[0]))
    if name == "ema":
        return _ema(closes, int(args[0]))
    if name == "rsi":
        return _rsi(closes, int(args[0]))
    if name == "roc":
        return _roc(closes, int(args[0]))
    if name == "macd":
        return _macd(closes, int(args[0]), int(args[1]), int(args[2]) if len(args) > 2 else 9)[0]
    if name == "macd_signal":
        return _macd(closes, int(args[0]), int(args[1]), int(args[2]))[1]
    if name == "macd_hist":
        return _macd(closes, int(args[0]), int(args[1]), int(args[2]))[2]
    if name == "bb_upper":
        return _bollinger(closes, int(args[0]), float(args[1]))[0]
    if name == "bb_mid":
        return _bollinger(closes, int(args[0]), float(args[1]))[1]
    if name == "bb_lower":
        return _bollinger(closes, int(args[0]), float(args[1]))[2]
    if name == "atr":
        return _atr(bars, int(args[0]))
    if name == "stoch":
        return _stoch_k(bars, int(args[0]))
    if name == "stoch_d":
        return _stoch_d(bars, int(args[0]), int(args[1]))
    if name == "adx":
        return _adx(bars, int(args[0]))
    if name == "donchian_high":
        return _prior_extreme([bar.high for bar in bars], int(args[0]), high=True)
    if name == "donchian_low":
        return _prior_extreme([bar.low for bar in bars], int(args[0]), high=False)
    if name == "prior_close_high":
        return _prior_extreme(closes, int(args[0]), high=True)
    if name == "obv":
        return _obv(bars)
    if name == "obv_sma":
        return _sma_optional(_obv(bars), int(args[0]))
    if name == "rel_volume":
        return _rel_volume(bars, int(args[0]))
    raise ValueError(name)


def _sma(closes: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    for index in range(period - 1, len(closes)):
        window = closes[index + 1 - period : index + 1]
        out[index] = sum(window) / period
    return out


def _sma_optional(values: Sequence[float | None], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = values[index + 1 - period : index + 1]
        if any(value is None for value in window):
            continue
        out[index] = sum(window) / period
    return out


def _ema(closes: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) < period:
        return out
    k = 2.0 / (period + 1)
    current = sum(closes[:period]) / period
    out[period - 1] = current
    for index in range(period, len(closes)):
        current = closes[index] * k + current * (1.0 - k)
        out[index] = current
    return out


def _rsi(closes: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        gains.append(change if change > 0.0 else 0.0)
        losses.append(-change if change < 0.0 else 0.0)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = _rsi_value(avg_gain, avg_loss)
    for offset in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[offset]) / period
        avg_loss = (avg_loss * (period - 1) + losses[offset]) / period
        out[offset + 1] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0 and avg_gain > 0.0:
        return 100.0
    if avg_gain == 0.0 and avg_loss == 0.0:
        return 50.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def _roc(closes: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    for index in range(period, len(closes)):
        base = closes[index - period]
        if base == 0.0:
            continue
        out[index] = (closes[index] / base - 1.0) * 100.0
    return out


def _macd(
    closes: Sequence[float], fast: int, slow: int, signal: int
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    fast_ema = _ema(closes, fast)
    slow_ema = _ema(closes, slow)
    line: list[float | None] = [
        None if left is None or right is None else left - right
        for left, right in zip(fast_ema, slow_ema)
    ]
    signal_line: list[float | None] = [None] * len(closes)
    hist: list[float | None] = [None] * len(closes)
    defined = [index for index, value in enumerate(line) if value is not None]
    if len(defined) < signal:
        return line, signal_line, hist
    seed_at = defined[:signal]
    current = sum(line[index] for index in seed_at) / signal
    k = 2.0 / (signal + 1)
    signal_line[seed_at[-1]] = current
    hist[seed_at[-1]] = line[seed_at[-1]] - current
    for index in range(seed_at[-1] + 1, len(closes)):
        if line[index] is None:
            continue
        current = line[index] * k + current * (1.0 - k)
        signal_line[index] = current
        hist[index] = line[index] - current
    return line, signal_line, hist


def _bollinger(
    closes: Sequence[float], period: int, width: float
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    upper: list[float | None] = [None] * len(closes)
    mid: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)
    for index in range(period - 1, len(closes)):
        window = closes[index + 1 - period : index + 1]
        mean = sum(window) / period
        var = sum((value - mean) ** 2 for value in window) / period
        std = var ** 0.5
        mid[index] = mean
        upper[index] = mean + width * std
        lower[index] = mean - width * std
    return upper, mid, lower


def _true_ranges(bars: Sequence[WeekBar]) -> list[float | None]:
    out: list[float | None] = [None] * len(bars)
    for index in range(1, len(bars)):
        high = bars[index].high
        low = bars[index].low
        previous = bars[index - 1].close
        out[index] = max(high - low, abs(high - previous), abs(low - previous))
    return out


def _atr(bars: Sequence[WeekBar], period: int) -> list[float | None]:
    ranges = _true_ranges(bars)
    out: list[float | None] = [None] * len(bars)
    if len(bars) <= period:
        return out
    current = sum(ranges[1 : period + 1]) / period
    out[period] = current
    for index in range(period + 1, len(bars)):
        current = (current * (period - 1) + ranges[index]) / period
        out[index] = current
    return out


def _stoch_k(bars: Sequence[WeekBar], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(bars)
    for index in range(period - 1, len(bars)):
        window = bars[index + 1 - period : index + 1]
        highest = max(bar.high for bar in window)
        lowest = min(bar.low for bar in window)
        if highest == lowest:
            continue
        out[index] = 100.0 * (bars[index].close - lowest) / (highest - lowest)
    return out


def _stoch_d(bars: Sequence[WeekBar], k_period: int, d_period: int) -> list[float | None]:
    return _sma_optional(_stoch_k(bars, k_period), d_period)


def _adx(bars: Sequence[WeekBar], period: int) -> list[float | None]:
    count = len(bars)
    out: list[float | None] = [None] * count
    if count <= period:
        return out
    plus_dm: list[float | None] = [None] * count
    minus_dm: list[float | None] = [None] * count
    ranges = _true_ranges(bars)
    for index in range(1, count):
        up = bars[index].high - bars[index - 1].high
        down = bars[index - 1].low - bars[index].low
        plus_dm[index] = up if up > down and up > 0.0 else 0.0
        minus_dm[index] = down if down > up and down > 0.0 else 0.0
    smooth_plus = _wilder_sum(plus_dm, period)
    smooth_minus = _wilder_sum(minus_dm, period)
    smooth_range = _wilder_sum(ranges, period)
    dx: list[float | None] = [None] * count
    for index in range(period, count):
        span = smooth_range[index]
        if span is None or span == 0.0 or smooth_plus[index] is None or smooth_minus[index] is None:
            continue
        plus_di = 100.0 * smooth_plus[index] / span
        minus_di = 100.0 * smooth_minus[index] / span
        denom = plus_di + minus_di
        if denom == 0.0:
            continue
        dx[index] = 100.0 * abs(plus_di - minus_di) / denom
    defined = [index for index, value in enumerate(dx) if value is not None]
    if len(defined) < period:
        return out
    seed_at = defined[:period]
    current = sum(dx[index] for index in seed_at) / period
    out[seed_at[-1]] = current
    for index in range(seed_at[-1] + 1, count):
        if dx[index] is None:
            continue
        current = (current * (period - 1) + dx[index]) / period
        out[index] = current
    return out


def _wilder_sum(values: Sequence[float | None], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    first = [index for index, value in enumerate(values) if value is not None]
    if len(first) < period:
        return out
    seed_at = first[:period]
    current = sum(values[index] for index in seed_at)
    out[seed_at[-1]] = current
    for index in range(seed_at[-1] + 1, len(values)):
        if values[index] is None:
            continue
        current = current - current / period + values[index]
        out[index] = current
    return out


def _prior_extreme(values: Sequence[float], period: int, *, high: bool) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for index in range(period, len(values)):
        window = values[index - period : index]
        out[index] = max(window) if high else min(window)
    return out


def _obv(bars: Sequence[WeekBar]) -> list[float | None]:
    out: list[float | None] = [None] * len(bars)
    if not bars or bars[0].volume is None:
        return out
    current: float | None = float(bars[0].volume)
    out[0] = current
    for index in range(1, len(bars)):
        volume = bars[index].volume
        if volume is None or current is None:
            current = None
            continue
        if bars[index].close > bars[index - 1].close:
            current += volume
        elif bars[index].close < bars[index - 1].close:
            current -= volume
        out[index] = current
    return out


def _rel_volume(bars: Sequence[WeekBar], period: int) -> list[float | None]:
    volumes: list[float | None] = [None if bar.volume is None else float(bar.volume) for bar in bars]
    averages = _sma_optional(volumes, period)
    out: list[float | None] = [None] * len(bars)
    for index, average in enumerate(averages):
        volume = volumes[index]
        if average is None or volume is None or average == 0.0:
            continue
        out[index] = volume / average
    return out
