from __future__ import annotations

from dataclasses import replace

import numpy as np

from price_forecast.search.spec import (
    CLOSE_ABOVE,
    CLOSE_BELOW,
    DOWN_WEEK,
    DUAL_PAIRS,
    PRIOR_WEEKS,
    Spec,
    spec_from_mapping,
    spec_to_mapping,
)


def _defaults(mode: str) -> Spec:
    if mode == "threshold":
        return Spec(
            mode="threshold",
            close_above_sma_weeks=4,
            close_below_sma_weeks=12,
        )
    if mode == "dual_average":
        return Spec(mode="dual_average", fast_weeks=4, slow_weeks=12)
    if mode == "prior_high":
        return Spec(mode="prior_high", prior_weeks=8)
    raise ValueError(mode)


def _neighbors(value: int | float | None, ladder: tuple) -> list:
    ordered = (None,) + tuple(ladder)
    index = ordered.index(value)
    found = []
    if index > 0:
        found.append(ordered[index - 1])
    if index + 1 < len(ordered):
        found.append(ordered[index + 1])
    return found


def _keep(spec: Spec) -> Spec | None:
    try:
        return spec_from_mapping(spec_to_mapping(spec))
    except ValueError:
        return None


def _numeric_neighbors(series: str, arg_index: int, value: int | float, *, is_value: bool) -> list[int | float]:
    if is_value and series == "rel_volume":
        step = 0.1
    elif (not is_value) and series in {"bb_upper", "bb_mid", "bb_lower"} and arg_index == 1:
        step = 0.5
    else:
        step = 1.0
    found: list[int | float] = []
    for direction in (-1, 1):
        nxt = round(float(value) + direction * step, 10)
        if float(nxt).is_integer():
            nxt = int(nxt)
        found.append(nxt)
    return found


def _swap_condition(parent: Spec, index: int, condition) -> Spec:
    conditions = list(parent.conditions)
    conditions[index] = condition
    return replace(parent, conditions=tuple(conditions))


def _indicator_edits(parent: Spec) -> list[Spec]:
    found: list[Spec] = []
    for index, condition in enumerate(parent.conditions):
        for arg_index, value in enumerate(condition.args):
            for nxt in _numeric_neighbors(condition.left, arg_index, value, is_value=False):
                args = list(condition.args)
                args[arg_index] = nxt
                found.append(_swap_condition(parent, index, replace(condition, args=tuple(args))))
        for arg_index, value in enumerate(condition.right_args):
            series = condition.right_series or condition.left
            for nxt in _numeric_neighbors(series, arg_index, value, is_value=False):
                args = list(condition.right_args)
                args[arg_index] = nxt
                found.append(_swap_condition(parent, index, replace(condition, right_args=tuple(args))))
        if condition.right_value is not None:
            for nxt in _numeric_neighbors(condition.left, 0, condition.right_value, is_value=True):
                found.append(_swap_condition(parent, index, replace(condition, right_value=nxt)))
    valid: list[Spec] = []
    for spec in found:
        kept = _keep(spec)
        if kept is not None:
            valid.append(kept)
    return valid


def legal_edits(parent: Spec) -> list[Spec]:
    if parent.mode == "indicator":
        valid = _indicator_edits(parent)
        if not valid:
            raise RuntimeError("no legal edit")
        return valid
    found: list[Spec] = []
    for mode in ("threshold", "dual_average", "prior_high"):
        if mode != parent.mode:
            found.append(_defaults(mode))
    if parent.mode == "threshold":
        for value in _neighbors(parent.close_above_sma_weeks, CLOSE_ABOVE):
            found.append(replace(parent, close_above_sma_weeks=value))
        for value in _neighbors(parent.close_below_sma_weeks, CLOSE_BELOW):
            found.append(replace(parent, close_below_sma_weeks=value))
        for value in _neighbors(parent.down_week, DOWN_WEEK):
            found.append(replace(parent, down_week=value))
    elif parent.mode == "dual_average":
        index = DUAL_PAIRS.index((parent.fast_weeks, parent.slow_weeks))
        if index > 0:
            fast, slow = DUAL_PAIRS[index - 1]
            found.append(replace(parent, fast_weeks=fast, slow_weeks=slow))
        if index + 1 < len(DUAL_PAIRS):
            fast, slow = DUAL_PAIRS[index + 1]
            found.append(replace(parent, fast_weeks=fast, slow_weeks=slow))
    elif parent.mode == "prior_high":
        for value in _neighbors(parent.prior_weeks, PRIOR_WEEKS):
            if value is not None:
                found.append(replace(parent, prior_weeks=value))
    found.append(replace(parent, base_or_breakout=not parent.base_or_breakout))
    found.append(replace(parent, above_long_averages=not parent.above_long_averages))
    valid = []
    for spec in found:
        kept = _keep(spec)
        if kept is not None:
            valid.append(kept)
    if not valid:
        raise RuntimeError("no legal edit")
    return valid


def mutate(parent: Spec, *, run_seed: int = 0, cycle: int, rng=None) -> Spec:
    choices = legal_edits(parent)
    if rng is None:
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([run_seed, cycle])))
    return choices[int(rng.integers(0, len(choices)))]
