"""Weekday-anchor and parameter-neighbour sweeps around one frozen spec."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from typing import Sequence

from price_forecast.data.candles import Candle
from price_forecast.replay.benchmarks import hodl
from price_forecast.replay.engine import Metrics, metrics, replay
from price_forecast.search.runner import Gate, SpecSignal
from price_forecast.search.spec import CLOSE_ABOVE, CLOSE_BELOW, DOWN_WEEK, Spec
from price_forecast.strategies.indicators import weekly_bars

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class Variant:
    label: str
    spec: Spec
    anchor: int
    result: Metrics
    hodl: Metrics

    @property
    def edge(self) -> float:
        return self.result.total_return - self.hodl.total_return


def run_variant(
    candles: Sequence[Candle],
    spec: Spec,
    gate: Gate,
    *,
    label: str,
    anchor: int = 6,
    **replay_kwargs,
) -> Variant:
    bars = weekly_bars(candles, week_end_weekday=anchor)
    weeks = [(bar.day, bar.close) for bar in bars]
    signal = SpecSignal(weeks, spec, gate, bars=bars)
    path = replay(candles, weeks, signal, **replay_kwargs)
    hold_kwargs = {key: value for key, value in replay_kwargs.items() if key != "fill"}
    base = hodl(candles, weeks, signal.first, **hold_kwargs)
    return Variant(label, spec, anchor, metrics(path), metrics(base))


def anchor_sweep(candles: Sequence[Candle], spec: Spec, gate: Gate, **replay_kwargs) -> list[Variant]:
    return [
        run_variant(candles, spec, gate, label=f"{WEEKDAYS[anchor]} close", anchor=anchor, **replay_kwargs)
        for anchor in range(7)
    ]


def _grid_steps(value, grid: Sequence) -> list:
    if value is None or value not in grid:
        return [value]
    position = list(grid).index(value)
    return [grid[i] for i in range(max(0, position - 1), min(len(grid), position + 2))]


def describe(spec: Spec) -> str:
    parts = []
    if spec.close_above_sma_weeks is not None:
        parts.append(f"in>SMA{spec.close_above_sma_weeks}")
    if spec.close_below_sma_weeks is not None:
        parts.append(f"out<SMA{spec.close_below_sma_weeks}")
    if spec.down_week is not None:
        parts.append(f"drop{spec.down_week:.0%}")
    if spec.base_or_breakout:
        parts.append("VCP")
    if spec.above_long_averages:
        parts.append("SMA150/200")
    return " ".join(parts) or spec.mode


def neighbours(spec: Spec) -> list[tuple[str, Spec]]:
    """Every combination within one grid step on each numeric knob, then each gate toggled.

    Only threshold specs without indicator add-ons have a grid to step on.
    The centre spec is included and labelled ``(frozen)``.
    """
    if spec.mode != "threshold" or spec.conditions or spec.exit_conditions:
        raise ValueError("neighbours only covers plain threshold specs")
    out: list[tuple[str, Spec]] = []
    seen: set[Spec] = set()
    for above, below, drop in itertools.product(
        _grid_steps(spec.close_above_sma_weeks, CLOSE_ABOVE),
        _grid_steps(spec.close_below_sma_weeks, CLOSE_BELOW),
        _grid_steps(spec.down_week, DOWN_WEEK),
    ):
        candidate = replace(spec, close_above_sma_weeks=above, close_below_sma_weeks=below, down_week=drop)
        if candidate not in seen:
            seen.add(candidate)
            out.append((describe(candidate), candidate))
    toggles = [
        replace(spec, base_or_breakout=not spec.base_or_breakout),
        replace(spec, above_long_averages=not spec.above_long_averages),
        replace(spec, down_week=None) if spec.down_week is not None else None,
    ]
    for candidate in toggles:
        if candidate is not None and candidate not in seen:
            seen.add(candidate)
            out.append((describe(candidate), candidate))
    return [((label + " (frozen)") if candidate == spec else label, candidate) for label, candidate in out]


def neighbour_sweep(candles: Sequence[Candle], spec: Spec, gate: Gate, **replay_kwargs) -> list[Variant]:
    return [
        run_variant(candles, candidate, gate, label=label, **replay_kwargs)
        for label, candidate in neighbours(spec)
    ]
