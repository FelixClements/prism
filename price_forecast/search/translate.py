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
