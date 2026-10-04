from __future__ import annotations

import json
import os
from pathlib import Path


def _replace(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def append_jsonl(path: Path, row: dict) -> None:
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    _replace(path, existing + json.dumps(row, sort_keys=True) + "\n")


def load_pool(path: Path) -> dict:
    if not path.is_file():
        return {"members": [], "champion_id": None, "stall": 0, "trial_count": 0}
    return json.loads(path.read_text(encoding="utf-8"))


def save_pool(path: Path, pool: dict) -> None:
    _replace(path, json.dumps(pool, sort_keys=True, indent=2) + "\n")


def _eligible(candidate: dict) -> bool:
    number = candidate.get("breeding_number")
    return (
        isinstance(number, (int, float))
        and candidate.get("coinbase_edge", 0.0) > 0.0
        and candidate.get("stress_pass") is True
        and candidate.get("fragile") is False
    )


def insert_member(members: list[dict], candidate: dict, *, cap: int = 20, seed: bool = False) -> list[dict]:
    if seed:
        return [candidate]
    if not _eligible(candidate):
        return list(members)
    if len(members) < cap:
        return list(members) + [candidate]
    weakest = min(member["breeding_number"] for member in members)
    if candidate["breeding_number"] <= weakest:
        return list(members)
    newest = max(
        (member for member in members if member["breeding_number"] == weakest),
        key=lambda member: member["inserted_cycle"],
    )
    return [member for member in members if member["id"] != newest["id"]] + [candidate]


def champion_of(members: list[dict]) -> dict:
    return min(members, key=lambda member: (-member["breeding_number"], member["inserted_cycle"]))
