from __future__ import annotations

import math
from dataclasses import dataclass

CLOSE_ABOVE = (4, 6, 8, 10, 12, 20)
CLOSE_BELOW = (12, 16, 20, 26, 30, 40)
DOWN_WEEK = (0.05, 0.08, 0.10, 0.12)
DUAL_PAIRS = ((4, 12), (8, 16), (8, 20), (10, 30), (12, 26))
PRIOR_WEEKS = (8, 12, 20, 26)

_THRESHOLD_KEYS = {
    "mode",
    "close_above_sma_weeks",
    "base_or_breakout",
    "above_long_averages",
    "close_below_sma_weeks",
    "down_week",
}
_DUAL_KEYS = {"mode", "fast_weeks", "slow_weeks", "base_or_breakout", "above_long_averages"}
_PRIOR_KEYS = {"mode", "prior_weeks", "base_or_breakout", "above_long_averages"}


@dataclass(frozen=True)
class Spec:
    mode: str
    close_above_sma_weeks: int | None = None
    base_or_breakout: bool = False
    above_long_averages: bool = False
    close_below_sma_weeks: int | None = None
    down_week: float | None = None
    fast_weeks: int | None = None
    slow_weeks: int | None = None
    prior_weeks: int | None = None


def locked_crashgate() -> Spec:
    return Spec(
        mode="threshold",
        close_above_sma_weeks=8,
        base_or_breakout=True,
        above_long_averages=True,
        close_below_sma_weeks=16,
        down_week=0.10,
    )


def spec_to_mapping(spec: Spec) -> dict:
    if spec.mode == "threshold":
        return {
            "mode": spec.mode,
            "close_above_sma_weeks": spec.close_above_sma_weeks,
            "base_or_breakout": spec.base_or_breakout,
            "above_long_averages": spec.above_long_averages,
            "close_below_sma_weeks": spec.close_below_sma_weeks,
            "down_week": spec.down_week,
        }
    if spec.mode == "dual_average":
        return {
            "mode": spec.mode,
            "fast_weeks": spec.fast_weeks,
            "slow_weeks": spec.slow_weeks,
            "base_or_breakout": spec.base_or_breakout,
            "above_long_averages": spec.above_long_averages,
        }
    if spec.mode == "prior_high":
        return {
            "mode": spec.mode,
            "prior_weeks": spec.prior_weeks,
            "base_or_breakout": spec.base_or_breakout,
            "above_long_averages": spec.above_long_averages,
        }
    raise ValueError(f"mode {spec.mode}")


def _canonical_down_week(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("down_week")
    for allowed in DOWN_WEEK:
        if math.isclose(float(value), allowed, rel_tol=0.0, abs_tol=1e-12):
            return allowed
    raise ValueError("down_week")


def _one_of(name: str, value: object, allowed: tuple[int, ...]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value not in allowed:
        raise ValueError(name)
    return value


def spec_from_mapping(data: dict) -> Spec:
    if not isinstance(data, dict):
        raise ValueError("spec")
    mode = data.get("mode")
    if mode == "threshold":
        extra = set(data) - _THRESHOLD_KEYS
        if extra:
            raise ValueError(sorted(extra)[0])
        missing = _THRESHOLD_KEYS - set(data)
        if missing:
            raise ValueError(sorted(missing)[0])
        close_above = _one_of("close_above_sma_weeks", data["close_above_sma_weeks"], CLOSE_ABOVE)
        close_below = _one_of("close_below_sma_weeks", data["close_below_sma_weeks"], CLOSE_BELOW)
        down_week = _canonical_down_week(data["down_week"])
        base = data["base_or_breakout"]
        long = data["above_long_averages"]
        if not isinstance(base, bool) or not isinstance(long, bool):
            raise ValueError("switch")
        entry_on = close_above is not None or base or long
        exit_on = close_below is not None or down_week is not None
        if not entry_on:
            raise ValueError("entry")
        if not exit_on:
            raise ValueError("exit")
        if down_week is not None and close_above is None and close_below is None:
            raise ValueError("down_week")
        return Spec(
            mode="threshold",
            close_above_sma_weeks=close_above,
            base_or_breakout=base,
            above_long_averages=long,
            close_below_sma_weeks=close_below,
            down_week=down_week,
        )
    if mode == "dual_average":
        extra = set(data) - _DUAL_KEYS
        if extra:
            raise ValueError(sorted(extra)[0])
        missing = _DUAL_KEYS - set(data)
        if missing:
            raise ValueError(sorted(missing)[0])
        pair = (_one_of("fast_weeks", data["fast_weeks"], tuple(p[0] for p in DUAL_PAIRS)),
                _one_of("slow_weeks", data["slow_weeks"], tuple(p[1] for p in DUAL_PAIRS)))
        if pair not in DUAL_PAIRS or pair[0] is None or pair[1] is None:
            raise ValueError("fast_weeks")
        base = data["base_or_breakout"]
        long = data["above_long_averages"]
        if not isinstance(base, bool) or not isinstance(long, bool):
            raise ValueError("switch")
        return Spec(
            mode="dual_average",
            fast_weeks=pair[0],
            slow_weeks=pair[1],
            base_or_breakout=base,
            above_long_averages=long,
        )
    if mode == "prior_high":
        extra = set(data) - _PRIOR_KEYS
        if extra:
            raise ValueError(sorted(extra)[0])
        missing = _PRIOR_KEYS - set(data)
        if missing:
            raise ValueError(sorted(missing)[0])
        prior = _one_of("prior_weeks", data["prior_weeks"], PRIOR_WEEKS)
        if prior is None:
            raise ValueError("prior_weeks")
        base = data["base_or_breakout"]
        long = data["above_long_averages"]
        if not isinstance(base, bool) or not isinstance(long, bool):
            raise ValueError("switch")
        return Spec(
            mode="prior_high",
            prior_weeks=prior,
            base_or_breakout=base,
            above_long_averages=long,
        )
    raise ValueError("mode")
