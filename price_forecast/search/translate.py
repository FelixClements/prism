from __future__ import annotations

import json
import os
from pathlib import Path

from price_forecast.search.spec import (
    CLOSE_ABOVE,
    CLOSE_BELOW,
    DOWN_WEEK,
    DUAL_PAIRS,
    PRIOR_WEEKS,
    Spec,
    spec_from_mapping,
)


class Unmapped(ValueError):
    def __init__(self, phrase: str) -> None:
        self.phrase = phrase
        super().__init__(phrase)


def _strings(draft: dict) -> list[str]:
    found: list[str] = []
    for key in ("conditions",):
        for item in draft.get(key) or []:
            if not isinstance(item, str):
                raise Unmapped(str(item))
            found.append(item)
    for block_name in ("entry", "exit"):
        block = draft.get(block_name) or {}
        if not isinstance(block, dict):
            raise Unmapped(block_name)
        for item in block.get("conditions") or []:
            if not isinstance(item, str):
                raise Unmapped(str(item))
            found.append(item)
    for item in draft.get("trend_filter") or []:
        if not isinstance(item, str):
            raise Unmapped(str(item))
        found.append(item)
    return found


def translate(draft: dict) -> Spec:
    phrases = _strings(draft)
    try:
        return _translate_original(phrases)
    except Unmapped:
        return _translate_indicator(phrases)


def _translate_original(phrases: list[str]) -> Spec:
    close_above = None
    close_below = None
    down_week = None
    base = False
    long = False
    pair = None
    prior = None
    for phrase in phrases:
        if phrase == "base_or_breakout":
            base = True
            continue
        if phrase == "above_long_averages":
            long = True
            continue
        matched = False
        for weeks in CLOSE_ABOVE:
            if phrase == f"weekly_close > sma_{weeks}":
                close_above = weeks
                matched = True
        for weeks in CLOSE_BELOW:
            if phrase == f"weekly_close < sma_{weeks}":
                close_below = weeks
                matched = True
        for value in DOWN_WEEK:
            text = f"{value:.2f}"
            if phrase == f"down_week {text}":
                down_week = value
                matched = True
        for fast, slow in DUAL_PAIRS:
            if phrase == f"sma_{fast} > sma_{slow}":
                pair = (fast, slow)
                matched = True
        for weeks in PRIOR_WEEKS:
            if phrase == f"close >= prior_high_{weeks}":
                prior = weeks
                matched = True
        if not matched:
            raise Unmapped(phrase)
    if pair and (close_above or close_below or down_week or prior):
        raise Unmapped("mixed modes")
    if prior and (close_above or close_below or down_week or pair):
        raise Unmapped("mixed modes")
    if pair:
        data = {
            "mode": "dual_average",
            "fast_weeks": pair[0],
            "slow_weeks": pair[1],
            "base_or_breakout": base,
            "above_long_averages": long,
        }
    elif prior:
        data = {
            "mode": "prior_high",
            "prior_weeks": prior,
            "base_or_breakout": base,
            "above_long_averages": long,
        }
    else:
        data = {
            "mode": "threshold",
            "close_above_sma_weeks": close_above,
            "base_or_breakout": base,
            "above_long_averages": long,
            "close_below_sma_weeks": close_below,
            "down_week": down_week,
        }
    try:
        return spec_from_mapping(data)
    except ValueError as exc:
        raise Unmapped(str(exc)) from exc


_TOKEN_SHAPES = (
    ("macd_signal_", "macd_signal", 3),
    ("macd_hist_", "macd_hist", 3),
    ("macd_", "macd", 2),
    ("bb_upper_", "bb_upper", 2),
    ("bb_mid_", "bb_mid", 2),
    ("bb_lower_", "bb_lower", 2),
    ("stoch_d_", "stoch_d", 2),
    ("donchian_high_", "donchian_high", 1),
    ("donchian_low_", "donchian_low", 1),
    ("prior_high_", "prior_close_high", 1),
    ("obv_sma_", "obv_sma", 1),
    ("rel_volume_", "rel_volume", 1),
    ("sma_", "sma", 1),
    ("ema_", "ema", 1),
    ("rsi_", "rsi", 1),
    ("atr_", "atr", 1),
    ("stoch_", "stoch", 1),
    ("adx_", "adx", 1),
    ("roc_", "roc", 1),
)


def _split_comparison(phrase: str) -> tuple[str, str, str]:
    hits: list[tuple[int, str, str]] = []
    for op in (">=", "<=", ">", "<"):
        needle = f" {op} "
        start = 0
        while True:
            at = phrase.find(needle, start)
            if at < 0:
                break
            hits.append((at, op, needle))
            start = at + len(needle)
    if len(hits) != 1:
        raise Unmapped(phrase)
    at, op, needle = hits[0]
    left = phrase[:at].strip()
    right = phrase[at + len(needle) :].strip()
    if not left or not right:
        raise Unmapped(phrase)
    return left, op, right


def _number_token(text: str, phrase: str) -> int | float:
    try:
        if any(char in text for char in ".eE"):
            value: int | float = float(text)
        else:
            value = int(text)
    except ValueError as exc:
        raise Unmapped(phrase) from exc
    if isinstance(value, float) and value != value:
        raise Unmapped(phrase)
    return value


def _token(text: str, phrase: str) -> tuple[str, tuple[int | float, ...]]:
    if text in ("close", "price", "weekly_close"):
        return "close", ()
    if text == "obv":
        return "obv", ()
    for prefix, name, count in _TOKEN_SHAPES:
        if not text.startswith(prefix):
            continue
        parts = text[len(prefix) :].split("_")
        if len(parts) != count or any(part == "" for part in parts):
            raise Unmapped(phrase)
        return name, tuple(_number_token(part, phrase) for part in parts)
    raise Unmapped(phrase)


def _translate_indicator(phrases: list[str]) -> Spec:
    base = False
    long = False
    conditions: list[dict] = []
    for phrase in phrases:
        if phrase == "base_or_breakout":
            base = True
            continue
        if phrase == "above_long_averages":
            long = True
            continue
        if phrase.startswith("down_week"):
            raise Unmapped(phrase)
        left_text, op, right_text = _split_comparison(phrase)
        left, left_args = _token(left_text, phrase)
        if _looks_numeric(right_text):
            right: dict = {"value": _number_token(right_text, phrase)}
        else:
            series, series_args = _token(right_text, phrase)
            right = {"series": series, "args": list(series_args)}
        condition = {"left": left, "args": list(left_args), "op": op, "right": right}
        try:
            spec_from_mapping(
                {
                    "mode": "indicator",
                    "conditions": [condition],
                    "base_or_breakout": False,
                    "above_long_averages": False,
                }
            )
        except ValueError as exc:
            raise Unmapped(phrase) from exc
        conditions.append(condition)
    try:
        return spec_from_mapping(
            {
                "mode": "indicator",
                "conditions": conditions,
                "base_or_breakout": base,
                "above_long_averages": long,
            }
        )
    except ValueError as exc:
        raise Unmapped(phrases[0] if phrases else "conditions") from exc


def _looks_numeric(text: str) -> bool:
    if text in ("close", "price", "weekly_close", "obv"):
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


def append_side_pile(path: Path, *, draft_id: str, phrase: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    line = json.dumps({"draft_id": draft_id, "phrase": phrase}, sort_keys=True) + "\n"
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(existing + line, encoding="utf-8")
    os.replace(temp, path)
    return len((existing + line).splitlines())
