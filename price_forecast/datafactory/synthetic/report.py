"""Real versus synthetic versus one-regime control."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from price_forecast.data.candles import Candle, closes_from_candles
from price_forecast.datafactory.remix import FACT_KEYS, correlation, stylized_facts
from price_forecast.datafactory.synthetic.label import REGIME_NAMES
from price_forecast.datafactory.synthetic.paths import PathResult

_FACT_KEYS = FACT_KEYS + ("range_abs_corr", "volume_abs_corr")


def synthetic_report(
    candles: Sequence[Candle],
    paths: Sequence[PathResult],
    controls: Sequence[Sequence[Candle]],
) -> dict[str, object]:
    if not paths:
        raise ValueError("need at least one path")
    days = {name: 0 for name in REGIME_NAMES}
    bull: list[float] = []
    bear: list[float] = []
    volatile: list[float] = []
    quiet: list[float] = []
    for path in paths:
        for index in range(1, len(path.candles)):
            name = path.regimes[index]
            days[name] = days[name] + 1
            shock = math.log(path.candles[index].close / path.candles[index - 1].close)
            if name.startswith("bull"):
                bull.append(shock)
            if name.startswith("bear"):
                bear.append(shock)
            if name.endswith("volatile"):
                volatile.append(shock)
            if name.endswith("quiet"):
                quiet.append(shock)
    return {
        "real": candle_facts(candles),
        "synthetic": _summary(path.candles for path in paths),
        "control": _summary(controls),
        "regime_days": days,
        "bull_vs_bear": _compare(bull, bear, kind="mean"),
        "quiet_vs_volatile": _compare(volatile, quiet, kind="std"),
    }


def format_synthetic_report(report: Mapping[str, object]) -> str:
    real = report["real"]
    synthetic = report["synthetic"]
    control = report["control"]
    lines = ["stylized fact       real            synthetic median  control median"]
    for key in _FACT_KEYS:
        lines.append(
            f"{key:<18} {_fmt(real[key]):<16} {_fmt(synthetic['median'][key]):<18} {_fmt(control['median'][key])}"
        )
    lines.append(f"n_paths synthetic={synthetic['n']} control={control['n']}")
    days = report["regime_days"]
    lines.append(" ".join(f"{name}={days[name]}" for name in REGIME_NAMES))
    bull = report["bull_vs_bear"]
    noisy = report["quiet_vs_volatile"]
    lines.append(
        f"bull_vs_bear {bull['verdict']} bull={_fmt(bull['left'])} bear={_fmt(bull['right'])}"
    )
    lines.append(
        "quiet_vs_volatile "
        f"{noisy['verdict']} volatile={_fmt(noisy['left'])} quiet={_fmt(noisy['right'])}"
    )
    return "\n".join(lines)


def candle_facts(candles: Sequence[Candle]) -> dict[str, float]:
    """Close facts, plus how wick range and volume track the size of the day's move."""
    facts = stylized_facts(closes_from_candles(candles))
    moves = [abs(math.log(candles[i].close / candles[i - 1].close)) for i in range(1, len(candles))]
    ranges = [math.log(candle.high / candle.low) for candle in candles[1:]]
    volumes = [candle.volume for candle in candles[1:]]
    facts["range_abs_corr"] = correlation(ranges, moves)
    facts["volume_abs_corr"] = (
        math.nan if None in volumes else correlation(volumes, moves)
    )
    return facts


def _summary(paths: Sequence[Sequence[Candle]]) -> dict[str, object]:
    rows = [candle_facts(path) for path in paths]
    median = {
        key: _upper_middle([row[key] for row in rows])
        for key in _FACT_KEYS
    }
    return {"n": len(rows), "median": median}


def _compare(left: Sequence[float], right: Sequence[float], *, kind: str) -> dict[str, object]:
    if len(left) < 2 or len(right) < 2:
        return {"left": math.nan, "right": math.nan, "verdict": "n/a"}
    left_stat = _mean(left) if kind == "mean" else _std(left)
    right_stat = _mean(right) if kind == "mean" else _std(right)
    verdict = "pass" if left_stat > right_stat else "fail"
    return {"left": left_stat, "right": right_stat, "verdict": verdict}


def _upper_middle(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return float(ordered[len(ordered) // 2])


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values))


def _std(values: Sequence[float]) -> float:
    mean = _mean(values)
    var = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return float(math.sqrt(var))


def _fmt(value: float) -> str:
    if value != value:
        return "nan"
    return f"{value:.6g}"
