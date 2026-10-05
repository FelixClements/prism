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
_INDICATOR_KEYS = {"mode", "conditions", "base_or_breakout", "above_long_averages"}
_OPS = {">", ">=", "<", "<="}
_SERIES_ARITY = {
    "close": 0,
    "sma": 1,
    "ema": 1,
    "rsi": 1,
    "macd": 2,
    "macd_signal": 3,
    "macd_hist": 3,
    "bb_upper": 2,
    "bb_mid": 2,
    "bb_lower": 2,
    "atr": 1,
    "stoch": 1,
    "stoch_d": 2,
    "adx": 1,
    "donchian_high": 1,
    "donchian_low": 1,
    "prior_close_high": 1,
    "roc": 1,
    "obv": 0,
    "obv_sma": 1,
    "rel_volume": 1,
}
_LEVEL_SERIES = {"rsi", "stoch", "stoch_d", "adx"}
_WIDTH_SERIES = {"bb_upper", "bb_mid", "bb_lower"}
_MACD_SERIES = {"macd", "macd_signal", "macd_hist"}
_VOLUME_SERIES = {"obv", "obv_sma", "rel_volume"}
_DUAL_KEYS = {"mode", "fast_weeks", "slow_weeks", "base_or_breakout", "above_long_averages"}
_PRIOR_KEYS = {"mode", "prior_weeks", "base_or_breakout", "above_long_averages"}


@dataclass(frozen=True)
class Condition:
    left: str
    args: tuple[int | float, ...]
    op: str
    right_value: int | float | None = None
    right_series: str | None = None
    right_args: tuple[int | float, ...] = ()


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
    conditions: tuple[Condition, ...] = ()


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
    if spec.mode == "indicator":
        return {
            "mode": spec.mode,
            "conditions": [_condition_mapping(condition) for condition in spec.conditions],
            "base_or_breakout": spec.base_or_breakout,
            "above_long_averages": spec.above_long_averages,
        }
    raise ValueError(f"mode {spec.mode}")


def needs_volume(spec: Spec) -> bool:
    if spec.mode != "indicator":
        return False
    names = {condition.left for condition in spec.conditions}
    names.update(
        condition.right_series for condition in spec.conditions if condition.right_series is not None
    )
    return bool(names & _VOLUME_SERIES)


def _condition_mapping(condition: Condition) -> dict:
    if condition.right_series is not None:
        right: dict = {"series": condition.right_series, "args": list(condition.right_args)}
    else:
        right = {"value": condition.right_value}
    return {
        "left": condition.left,
        "args": list(condition.args),
        "op": condition.op,
        "right": right,
    }


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
    if mode == "indicator":
        return _indicator_spec(data)
    raise ValueError("mode")


def _canonical_number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("number")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("number")
        if value.is_integer() and abs(value) < 1e15:
            return int(value)
        return value
    return value


def _period(value: object) -> int:
    number = _canonical_number(value)
    if isinstance(number, float) or not 2 <= number <= 260:
        raise ValueError("period")
    return number


def _series_args(name: str, raw: object) -> tuple[int | float, ...]:
    if name not in _SERIES_ARITY:
        raise ValueError(name)
    if not isinstance(raw, (list, tuple)) or len(raw) != _SERIES_ARITY[name]:
        raise ValueError(name)
    if name in _WIDTH_SERIES:
        period = _period(raw[0])
        width = _canonical_number(raw[1])
        if not 0.5 <= float(width) <= 4.0:
            raise ValueError("width")
        return (period, width)
    if name in _MACD_SERIES:
        periods = tuple(_period(arg) for arg in raw)
        if periods[0] >= periods[1]:
            raise ValueError("fast")
        return periods
    return tuple(_period(arg) for arg in raw)


def _threshold_number(left: str, value: object) -> int | float:
    number = _canonical_number(value)
    if left in _LEVEL_SERIES and not 0 <= float(number) <= 100:
        raise ValueError("level")
    if left == "rel_volume" and float(number) <= 0.0:
        raise ValueError("multiple")
    return number


def _condition_from_mapping(data: object) -> Condition:
    if not isinstance(data, dict):
        raise ValueError("conditions")
    left = data.get("left")
    op = data.get("op")
    if not isinstance(left, str) or op not in _OPS:
        raise ValueError("op")
    args = _series_args(left, data.get("args"))
    right = data.get("right")
    if not isinstance(right, dict):
        raise ValueError("right")
    has_value = "value" in right
    has_series = "series" in right
    if has_value == has_series:
        raise ValueError("right")
    if has_value:
        return Condition(left=left, args=args, op=op, right_value=_threshold_number(left, right["value"]))
    series = right.get("series")
    if not isinstance(series, str):
        raise ValueError("right")
    return Condition(
        left=left,
        args=args,
        op=op,
        right_series=series,
        right_args=_series_args(series, right.get("args")),
    )


def _indicator_spec(data: dict) -> Spec:
    extra = set(data) - _INDICATOR_KEYS
    if extra:
        raise ValueError(sorted(extra)[0])
    missing = _INDICATOR_KEYS - set(data)
    if missing:
        raise ValueError(sorted(missing)[0])
    raw_conditions = data["conditions"]
    if not isinstance(raw_conditions, list) or not raw_conditions:
        raise ValueError("conditions")
    conditions = tuple(_condition_from_mapping(item) for item in raw_conditions)
    if not any(condition.args or condition.right_args or condition.right_value is not None for condition in conditions):
        raise ValueError("number")
    base = data["base_or_breakout"]
    long = data["above_long_averages"]
    if not isinstance(base, bool) or not isinstance(long, bool):
        raise ValueError("switch")
    return Spec(
        mode="indicator",
        base_or_breakout=base,
        above_long_averages=long,
        conditions=conditions,
    )
