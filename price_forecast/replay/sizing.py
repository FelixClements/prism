"""Continuous-exposure baselines with no tuning. Pre-registered 2026-11-11.

These rules are the bar that CrashGate's complexity has to clear. Every number below
was fixed from the literature before any of these rules was run on BTC data, and
the commit that adds this file comes before the commit with their results. The
family counts as one trial; the report also shows the deflated Sharpe at N = 3.

Decisions are taken on each weekly close (Sunday by default) and filled at the next
daily close, like the CrashGate replay. Exposure is long-only in [0, 1], no leverage.

(a) ``voltarget``: exposure = min(1, 40% / forecast vol).
    40% annual vol per asset is the scaling in Moskowitz, Ooi & Pedersen (2012),
    "Time series momentum". The forecast is their estimator: exponentially weighted
    squared daily returns with a centre of mass of 60 days (delta = 60/61). We use a
    zero mean (RiskMetrics style) and annualise with 365 days, since BTC trades daily.
    The variance is seeded with the mean squared return of the first 30 daily
    returns, and the rule stays in cash until 60 daily returns exist.

(b) ``tsmom``: exposure = mean of 1[weekly close / close L weeks earlier > 1] over
    L = 2, 4, 8, 13, 26, 52 weeks. Before 52 weeks of history exist, the mean is over
    the lookbacks that do exist (the report also scores the subperiod where all six
    exist). With no lookback available the rule is in cash.

(c) ``voltarget_tsmom``: (a) times (b).

Neighbours are reported for robustness only, never to pick a variant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date
from typing import Sequence

from price_forecast.data.candles import Candle
from price_forecast.strategies.indicators import weekly_bars

TARGET_VOL = 0.40
VOL_COM_DAYS = 60
VOL_SEED_RETURNS = 30
DAYS_PER_YEAR = 365.0
TSMOM_WEEKS = (2, 4, 8, 13, 26, 52)
KINDS = ("voltarget", "tsmom", "voltarget_tsmom")


@dataclass(frozen=True)
class SizingRule:
    kind: str
    target_vol: float = TARGET_VOL
    vol_com_days: int = VOL_COM_DAYS
    lookbacks: tuple[int, ...] = TSMOM_WEEKS

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")


def describe_rule(rule: SizingRule) -> str:
    vol = f"min(1, {rule.target_vol:.0%} / EWMA vol, COM {rule.vol_com_days}d)"
    trend = "mean 1[ret>0] over " + "/".join(str(w) for w in rule.lookbacks) + " wk"
    if rule.kind == "voltarget":
        return vol
    if rule.kind == "tsmom":
        return trend
    return f"{vol} × {trend}"


def ewma_vol(candles: Sequence[Candle], com_days: int = VOL_COM_DAYS) -> dict[date, float]:
    """Annualised EWMA vol on each day, using daily returns up to and including that close."""
    if com_days < 1:
        raise ValueError("com_days must be at least 1")
    delta = com_days / (com_days + 1.0)
    returns = [candles[i].close / candles[i - 1].close - 1.0 for i in range(1, len(candles))]
    out: dict[date, float] = {}
    if len(returns) < VOL_SEED_RETURNS:
        return out
    variance = sum(r * r for r in returns[:VOL_SEED_RETURNS]) / VOL_SEED_RETURNS
    for i, value in enumerate(returns):
        if i >= VOL_SEED_RETURNS:
            variance = delta * variance + (1.0 - delta) * value * value
        if i + 1 >= com_days:
            out[candles[i + 1].day] = math.sqrt(variance * DAYS_PER_YEAR)
    return out


def tsmom_score(closes: Sequence[float], index: int, lookbacks: Sequence[int]) -> float:
    votes = [1.0 if closes[index] > closes[index - weeks] else 0.0 for weeks in lookbacks if index - weeks >= 0]
    return sum(votes) / len(votes) if votes else 0.0


def sizing_decisions(
    candles: Sequence[Candle],
    rule: SizingRule,
    *,
    anchor: int = 6,
    start_day: date,
) -> list[tuple[date, float]]:
    """One target per weekly close from ``start_day``, the last complete week excluded."""
    bars = weekly_bars(candles, week_end_weekday=anchor)
    closes = [bar.close for bar in bars]
    vols = ewma_vol(candles, rule.vol_com_days) if rule.kind != "tsmom" else {}
    out: list[tuple[date, float]] = []
    for index in range(len(bars) - 1):
        day = bars[index].day
        if day < start_day:
            continue
        size = 1.0
        if rule.kind != "tsmom":
            vol = vols.get(day)
            size = 0.0 if vol is None else (1.0 if vol <= 0.0 else min(1.0, rule.target_vol / vol))
        if rule.kind != "voltarget":
            size *= tsmom_score(closes, index, rule.lookbacks)
        out.append((day, size))
    return out


def sizing_neighbours(rule: SizingRule) -> list[tuple[str, SizingRule]]:
    """Fixed robustness grid: vol target 30/40/50%, COM 30/60/120 days, each lookback dropped."""
    out: list[tuple[str, SizingRule]] = []
    if rule.kind != "tsmom":
        for target in (0.30, 0.40, 0.50):
            for com in (30, 60, 120):
                out.append((describe_rule(replace(rule, target_vol=target, vol_com_days=com)),
                            replace(rule, target_vol=target, vol_com_days=com)))
    if rule.kind != "voltarget":
        for weeks in rule.lookbacks:
            kept = tuple(w for w in rule.lookbacks if w != weeks)
            candidate = replace(rule, lookbacks=kept)
            out.append((f"{describe_rule(candidate)} (drop {weeks})", candidate))
    return [((label + " (frozen)") if candidate == rule else label, candidate) for label, candidate in out]
