# CrashGate Search Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an unattended search that breeds specs from the locked CrashGateV1 rule, scores them on Coinbase plus 100 remix and 100 synthetic paths, and stores a ledger without editing the locked strategy file.

**Architecture:** `spec.py` is the only legal rule document. `mutate.py` makes one legal edit. `translate.py` turns a draft into a spec or a side-pile line. `runner.py` simulates a spec with next-week fills. `score.py` computes the breeding number, fragility, and the half-edge stress check. `ledger.py` appends atomic JSONL and keeps a pool of 20. `__main__.py` runs preflight, then the contest.

**Tech Stack:** Python 3, numpy Generator, pytest, the existing weekly candle helpers, `backtest-expert`'s `evaluate`, `edge-strategy-reviewer`'s `review_draft`.

**Spec:** `docs/superpowers/specs/2026-10-02-crashgate-search-design.md`

## Global Constraints

- Do not edit `price_forecast/strategies/crashgate_v1.py` or its fill, fee, or locked behavior.
- Do not edit `routing-crypto-strategy-skills`, `backtest-expert`, or `edge-strategy-reviewer`.
- Fill is the next weekly close. Fee is 0.15% of wealth per fill. Start in cash, start flat. A spec has no field for fill, fee, or starting cash.
- Trade count is stored. Fewer than 30 Coinbase round trips does not remove a pool member. Remix and synthetic round trips are not added to the Coinbase count.
- A child enters the pool only when its Coinbase edge is strictly positive, `stress_pass` is true, `fragile` is false, and its breeding number strictly beats the weakest member once the pool is full.
- The seed member is the locked threshold spec and is inserted even if it would fail stress or fragility.
- Stress files are seed 0, paths 0 through 99, under `data/remix/` and `data/synthetic/`. A mean edge under half of that child's own Coinbase edge fails that child.
- A non-positive Coinbase edge skips the 200 paths. Means are null and `stress_pass` is false.
- Unknown draft phrases go to `results/search/side_pile.jsonl` and get no score.
- Preflight failures (missing Coinbase file, factory failure, skill import or call raising) exit 1 and leave `results/search/` unchanged.
- Ledger and pool writes use a temp file and `os.replace`. `results/search/` is gitignored.
- Tests use small fixtures. They do not call the VCP screener and do not generate 200 paths.

## File map

- `price_forecast/search/spec.py` — parse, validate, and emit a spec. Produces `Spec`, `locked_crashgate`, `spec_from_mapping`, `spec_to_mapping`.
- `price_forecast/search/mutate.py` — one edit. Produces `legal_edits`, `mutate`.
- `price_forecast/search/translate.py` — draft to spec, or a side-pile line. Produces `Unmapped`, `translate`, `append_side_pile`.
- `price_forecast/search/runner.py` — next-week simulation. Produces `FILL_COST`, `STARTING_DOLLARS`, `simulate_spec`.
- `price_forecast/search/score.py` — metrics, breeding number, fragility, stress means, skill-warning dict. Produces `PathMetrics`, `metrics_from_path`, `breeding_number`, `baseline_is_usable`, `is_fragile`, `stress_result`, `skill_warnings`.
- `price_forecast/search/ledger.py` — atomic JSONL, pool of 20, champion. Produces `append_jsonl`, `insert_member`, `champion_of`, `load_pool`, `save_pool`.
- `price_forecast/search/__main__.py` — preflight and the cycle loop. Produces `main`.
- Modify: `.gitignore` only.

## Review focus

- A mode change is one edit and resets the new mode to its first listed values with both filters off (Task 2).
- Drawdown ratio is `abs(baseline) / abs(child)`, clipped to 0..3, and is 3 when the child drawdown is 0 (Task 5).
- Half of a non-positive Coinbase edge is never used as a pass (Task 5 and Task 7).
- Equal breeding numbers do not kick out the older pool member (Task 6).
- Preflight steps 1–3 write nothing under `results/search/` (Task 7).

---

### Task 1: Spec document

**Files:**
- Create: `price_forecast/search/__init__.py`
- Create: `price_forecast/search/spec.py`
- Create: `tests/search/__init__.py`
- Test: `tests/search/test_spec.py`

**Interfaces:**
- Consumes: nothing from later tasks.
- Produces: `Spec` (frozen dataclass) and these functions.

```python
def locked_crashgate() -> Spec: ...
def spec_from_mapping(data: dict) -> Spec: ...
def spec_to_mapping(spec: Spec) -> dict: ...
```

`Spec` fields: `mode: str`, `close_above_sma_weeks: int | None = None`, `base_or_breakout: bool = False`, `above_long_averages: bool = False`, `close_below_sma_weeks: int | None = None`, `down_week: float | None = None`, `fast_weeks: int | None = None`, `slow_weeks: int | None = None`, `prior_weeks: int | None = None`.

- [ ] **Step 1: Write the failing test**

Create `tests/search/__init__.py` as an empty file.

`tests/search/test_spec.py`:

```python
import pytest

from price_forecast.search.spec import locked_crashgate, spec_from_mapping, spec_to_mapping


def test_locked_rule_fields():
    spec = locked_crashgate()
    assert spec.mode == "threshold"
    assert spec.close_above_sma_weeks == 8
    assert spec.base_or_breakout is True
    assert spec.above_long_averages is True
    assert spec.close_below_sma_weeks == 16
    assert spec.down_week == pytest.approx(0.10)
    assert spec_to_mapping(spec).keys().isdisjoint({"cost", "fill", "starting_dollars"})


def test_round_trip():
    spec = locked_crashgate()
    assert spec_from_mapping(spec_to_mapping(spec)) == spec


def test_unknown_field_is_rejected():
    data = spec_to_mapping(locked_crashgate())
    data["funding"] = "negative"
    with pytest.raises(ValueError, match="funding"):
        spec_from_mapping(data)


def test_unknown_number_is_rejected():
    data = spec_to_mapping(locked_crashgate())
    data["close_above_sma_weeks"] = 7
    with pytest.raises(ValueError, match="close_above_sma_weeks"):
        spec_from_mapping(data)


def test_down_week_without_an_average_is_rejected():
    with pytest.raises(ValueError, match="down_week"):
        spec_from_mapping(
            {
                "mode": "threshold",
                "close_above_sma_weeks": None,
                "base_or_breakout": True,
                "above_long_averages": False,
                "close_below_sma_weeks": None,
                "down_week": 0.10,
            }
        )


def test_threshold_needs_an_entry_and_an_exit():
    with pytest.raises(ValueError, match="entry"):
        spec_from_mapping(
            {
                "mode": "threshold",
                "close_above_sma_weeks": None,
                "base_or_breakout": False,
                "above_long_averages": False,
                "close_below_sma_weeks": 16,
                "down_week": None,
            }
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/search/test_spec.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.search'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/search/__init__.py`:

```python
"""Search loop for CrashGate-style specs. Does not edit the locked strategy."""
```

`price_forecast/search/spec.py`:

```python
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
```

`_one_of` rejects `None` for dual weeks because `pair not in DUAL_PAIRS` when either side is `None`. That is the intended rejection.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/search/test_spec.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/search/__init__.py price_forecast/search/spec.py tests/search/__init__.py tests/search/test_spec.py
git commit -m "$(cat <<'EOF'
Add the CrashGate search spec grammar.

EOF
)"
```

---

### Task 2: One-edit mutator

**Files:**
- Create: `price_forecast/search/mutate.py`
- Test: `tests/search/test_mutate.py`

**Interfaces:**
- Consumes: `Spec`, `spec_from_mapping`, `spec_to_mapping`, `locked_crashgate` from `price_forecast.search.spec`.
- Produces:

```python
def legal_edits(parent: Spec) -> list[Spec]: ...
def mutate(parent: Spec, *, run_seed: int = 0, cycle: int, rng=None) -> Spec: ...
```

`rng`, when passed, must provide `integers(low, high) -> int` with `low == 0` and `high == len(legal_edits(parent))`. When `rng` is omitted, use `numpy.random.Generator(numpy.random.PCG64(numpy.random.SeedSequence([run_seed, cycle])))`.

- [ ] **Step 1: Write the failing test**

`tests/search/test_mutate.py`:

```python
from dataclasses import fields

from price_forecast.search.mutate import legal_edits, mutate
from price_forecast.search.spec import Spec, locked_crashgate, spec_from_mapping, spec_to_mapping


class _Pick:
    def __init__(self, index: int):
        self.index = index

    def integers(self, low: int, high: int) -> int:
        assert low == 0
        assert high > self.index
        return self.index


def _differing_names(left: Spec, right: Spec) -> list[str]:
    names = []
    for field in fields(Spec):
        if getattr(left, field.name) != getattr(right, field.name):
            names.append(field.name)
    return names


def test_first_edit_switches_mode_to_the_first_dual_pair():
    child = mutate(locked_crashgate(), cycle=0, rng=_Pick(0))
    assert child == Spec(
        mode="dual_average",
        fast_weeks=4,
        slow_weeks=12,
        base_or_breakout=False,
        above_long_averages=False,
    )


def test_same_mode_edit_changes_one_field():
    parent = locked_crashgate()
    edits = legal_edits(parent)
    same_mode = [edit for edit in edits if edit.mode == parent.mode]
    assert same_mode
    for edit in same_mode:
        changed = _differing_names(parent, edit)
        assert len(changed) == 1
        spec_from_mapping(spec_to_mapping(edit))


def test_same_seed_and_cycle_match_and_the_next_cycle_does_not():
    parent = locked_crashgate()
    assert mutate(parent, run_seed=0, cycle=3) == mutate(parent, run_seed=0, cycle=3)
    assert mutate(parent, run_seed=0, cycle=3) != mutate(parent, run_seed=0, cycle=4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/search/test_mutate.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.search.mutate'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/search/mutate.py`:

```python
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


def legal_edits(parent: Spec) -> list[Spec]:
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
```

A dual-pair step changes `fast_weeks` and `slow_weeks` together. That is one allowed-pair step, not two independent edits. The test's "one field" assertion applies only to threshold same-mode edits, where each neighbor touches one field. A switch flip touches one field. Do not count a pair step as two edits.

`_neighbors` for `down_week` uses tuple identity. Store `down_week` as the canonical `DOWN_WEEK` member from Task 1 so `ordered.index(value)` finds it.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/search/test_mutate.py tests/search/test_spec.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/search/mutate.py tests/search/test_mutate.py
git commit -m "$(cat <<'EOF'
Mutate a search spec by one legal edit.

EOF
)"
```

---

### Task 3: Draft translator and side pile

**Files:**
- Create: `price_forecast/search/translate.py`
- Test: `tests/search/test_translate.py`

**Interfaces:**
- Consumes: `Spec`, `spec_from_mapping` from `price_forecast.search.spec`.
- Produces:

```python
class Unmapped(ValueError):
    def __init__(self, phrase: str) -> None: ...

def translate(draft: dict) -> Spec: ...
def append_side_pile(path: Path, *, draft_id: str, phrase: str) -> int: ...
```

`append_side_pile` returns the new line count. It writes one JSON object per line: `{"draft_id": ..., "phrase": ...}`.

Accepted condition strings, and only these:

- `weekly_close > sma_N` for N in 4, 6, 8, 10, 12, 20
- `weekly_close < sma_N` for N in 12, 16, 20, 26, 30, 40
- `base_or_breakout`
- `above_long_averages`
- `down_week 0.05`, `down_week 0.08`, `down_week 0.10`, `down_week 0.12`
- `sma_F > sma_S` for the five dual pairs
- `close >= prior_high_N` for N in 8, 12, 20, 26

Read strings from `draft["conditions"]` when it is a list, plus `draft["entry"]["conditions"]`, `draft["exit"]["conditions"]`, and `draft["trend_filter"]` when those lists exist. A missing list is empty. Any non-string entry raises `Unmapped` with `phrase` equal to `str(entry)`.

A dual phrase selects `dual_average`. A prior-high phrase selects `prior_high`. Otherwise the mode is `threshold`. A draft that mixes a dual phrase with a threshold close comparison, or a prior-high phrase with either of those, raises `Unmapped("mixed modes")`.

- [ ] **Step 1: Write the failing test**

`tests/search/test_translate.py`:

```python
import json

import pytest

from price_forecast.search.spec import locked_crashgate
from price_forecast.search.translate import Unmapped, append_side_pile, translate


def test_known_conditions_become_the_locked_spec():
    draft = {
        "id": "locked",
        "entry": {"conditions": ["weekly_close > sma_8", "base_or_breakout", "above_long_averages"]},
        "exit": {"conditions": ["weekly_close < sma_16", "down_week 0.10"]},
    }
    assert translate(draft) == locked_crashgate()


def test_funding_is_unmapped_and_adds_one_side_pile_line(tmp_path):
    draft = {"id": "fund", "conditions": ["funding"]}
    with pytest.raises(Unmapped) as caught:
        translate(draft)
    assert caught.value.phrase == "funding"
    path = tmp_path / "side_pile.jsonl"
    assert append_side_pile(path, draft_id="fund", phrase=caught.value.phrase) == 1
    line = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert line == {"draft_id": "fund", "phrase": "funding"}
    assert append_side_pile(path, draft_id="fund", phrase="funding") == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/search/test_translate.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.search.translate'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/search/translate.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/search/test_translate.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/search/translate.py tests/search/test_translate.py
git commit -m "$(cat <<'EOF'
Translate mapped drafts and pile up the ones this grammar cannot run.

EOF
)"
```

---

### Task 4: Next-week runner

**Files:**
- Create: `price_forecast/search/runner.py`
- Test: `tests/search/test_runner.py`

**Interfaces:**
- Consumes: `Spec`, `sma_at` from `price_forecast.strategies.signals`, `EquityPath` and `Fill` from `price_forecast.backtest.engine`.
- Produces:

```python
FILL_COST = 0.0015
STARTING_DOLLARS = 10_000.0

def simulate_spec(
    weeks: list[tuple[date, float]],
    spec: Spec,
    gate,
    *,
    starting_dollars: float = STARTING_DOLLARS,
    cost: float = FILL_COST,
) -> EquityPath: ...
```

`gate(day) -> tuple[bool, bool]` is `(base_or_breakout, above_long_averages)`. Call it only when the spec has at least one of those switches on.

Do not call `simulate_hodl`. Do not import `crashgate_v1`.

The first simulated index is the spec's longest lookback (`close_above_sma_weeks`, `close_below_sma_weeks`, `slow_weeks`, or `prior_weeks`; at least 1). That matches the locked rule: longest lookback 16, so the loop starts at index 16, one week after SMA-16 first exists.

Threshold mode is a state machine, copied from `simulate_crashgate`: a signal on this weekly close sets a pending buy or sell, and the fill happens on the next weekly close. Dual-average mode's desired position is 1 when the fast average is above the slow average and every on filter passes. Prior-high mode's desired position is 1 when the close is at or above the max of the prior N closes, excluding this close, and every on filter passes. Both of those modes also fill on the next week: if desired is 1 and the position is flat, pend a buy; if desired is 0 and the position is long, pend a sell.

A pending fill is applied at the start of the next index, before the mark and before a new signal. Fee on a buy is `wealth * cost`. Fee on a sell is `proceeds * cost`. Completed round-trip pnl is wealth after the sell minus wealth before the buy fee. An open trip is not a completed round trip. Put the open pnl only in `pf_pnls`, as `simulate_crashgate` does.

- [ ] **Step 1: Write the failing test**

`tests/search/test_runner.py`:

```python
from datetime import date, timedelta

import pytest

from price_forecast.search.runner import FILL_COST, simulate_spec
from price_forecast.search.spec import Spec, spec_to_mapping


def _weeks(closes: list[float]):
    start = date(2018, 1, 7)
    return [(start + timedelta(days=7 * i), close) for i, close in enumerate(closes)]


def test_spec_cannot_name_fill_or_fee():
    spec = Spec(mode="threshold", close_above_sma_weeks=4, close_below_sma_weeks=12)
    assert spec_to_mapping(spec).keys().isdisjoint({"cost", "fill", "starting_dollars"})
    assert FILL_COST == pytest.approx(0.0015)


def test_buy_fills_next_week_and_charges_fifteen_bps():
    closes = [100.0] * 20 + [200.0] * 8
    calls = {"n": 0}

    def gate(_day):
        calls["n"] += 1
        return True, True

    spec = Spec(mode="threshold", close_above_sma_weeks=4, close_below_sma_weeks=12)
    path = simulate_spec(_weeks(closes), spec, gate)
    buys = [fill for fill in path.fills if fill.side == "BUY"]
    assert buys
    assert buys[0].price == pytest.approx(200.0)
    assert buys[0].fee == pytest.approx(10_000.0 * 0.0015)
    assert calls["n"] == 0


def test_gate_false_blocks_the_buy():
    closes = [100.0] * 20 + [200.0] * 8
    spec = Spec(
        mode="threshold",
        close_above_sma_weeks=4,
        base_or_breakout=True,
        close_below_sma_weeks=12,
    )
    path = simulate_spec(_weeks(closes), spec, lambda _day: (False, True))
    assert path.fills == []
    assert path.end_dollars == pytest.approx(10_000.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/search/test_runner.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.search.runner'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/search/runner.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Callable, Sequence

from price_forecast.backtest.engine import EquityPath, Fill
from price_forecast.search.spec import Spec
from price_forecast.strategies.signals import sma_at

FILL_COST = 0.0015
STARTING_DOLLARS = 10_000.0
Gate = Callable[[date], tuple[bool, bool]]


def _lookback(spec: Spec) -> int:
    values = [
        value
        for value in (
            spec.close_above_sma_weeks,
            spec.close_below_sma_weeks,
            spec.slow_weeks,
            spec.prior_weeks,
        )
        if value
    ]
    return max(values) if values else 1


def _filters(spec: Spec, day: date, gate: Gate) -> bool:
    if not spec.base_or_breakout and not spec.above_long_averages:
        return True
    base, long = gate(day)
    if spec.base_or_breakout and not base:
        return False
    if spec.above_long_averages and not long:
        return False
    return True


def _threshold_entry(spec: Spec, closes: list[float], index: int, day: date, gate: Gate) -> bool:
    if not _filters(spec, day, gate):
        return False
    if spec.close_above_sma_weeks is None:
        return spec.base_or_breakout or spec.above_long_averages
    return closes[index] > sma_at(closes, index, spec.close_above_sma_weeks)


def _threshold_exit(spec: Spec, closes: list[float], index: int) -> bool:
    if spec.close_below_sma_weeks is not None and closes[index] < sma_at(
        closes, index, spec.close_below_sma_weeks
    ):
        return True
    if spec.down_week is None or index < 1:
        return False
    reference = spec.close_above_sma_weeks or spec.close_below_sma_weeks
    dropped = closes[index] <= closes[index - 1] * (1.0 - spec.down_week)
    under = closes[index] < sma_at(closes, index, reference)
    return dropped and under


def _desired(spec: Spec, closes: list[float], index: int, day: date, gate: Gate) -> int:
    if not _filters(spec, day, gate):
        return 0
    if spec.mode == "dual_average":
        fast = sma_at(closes, index, spec.fast_weeks)
        slow = sma_at(closes, index, spec.slow_weeks)
        return 1 if fast > slow else 0
    prior = closes[index - spec.prior_weeks : index]
    return 1 if closes[index] >= max(prior) else 0


def simulate_spec(
    weeks: Sequence[tuple[date, float]],
    spec: Spec,
    gate: Gate,
    *,
    starting_dollars: float = STARTING_DOLLARS,
    cost: float = FILL_COST,
) -> EquityPath:
    if starting_dollars <= 0:
        raise ValueError("starting_dollars must be positive")
    if cost < 0:
        raise ValueError("cost must be non-negative")
    first = _lookback(spec)
    if len(weeks) <= first:
        raise ValueError("need more weekly bars than the longest lookback")
    closes = [close for _day, close in weeks]
    position = 0
    wealth = starting_dollars
    btc = 0.0
    pending: str | None = None
    cash_before: float | None = None
    fees_paid = 0.0
    fills: list[Fill] = []
    dates: list[date] = []
    marked: list[float] = []
    equity: list[float] = []
    long_flags: list[bool] = []
    completed: list[float] = []

    for index in range(first, len(weeks)):
        day, close = weeks[index]
        if pending == "buy" and position == 0:
            fee = wealth * cost
            cash_before = wealth
            wealth -= fee
            fees_paid += fee
            btc = wealth / close
            position = 1
            pending = None
            fills.append(Fill(index, day, "BUY", close, fee, wealth))
        elif pending == "sell" and position == 1:
            proceeds = btc * close
            fee = proceeds * cost
            wealth = proceeds - fee
            fees_paid += fee
            assert cash_before is not None
            completed.append(wealth - cash_before)
            btc = 0.0
            position = 0
            cash_before = None
            pending = None
            fills.append(Fill(index, day, "SELL", close, fee, wealth))
        if position == 1:
            wealth = btc * close
        dates.append(day)
        marked.append(close)
        equity.append(wealth)
        long_flags.append(position == 1)
        if index + 1 >= len(weeks):
            continue
        if spec.mode == "threshold":
            if position == 0 and _threshold_entry(spec, closes, index, day, gate):
                pending = "buy"
            elif position == 1 and _threshold_exit(spec, closes, index):
                pending = "sell"
        else:
            want = _desired(spec, closes, index, day, gate)
            if position == 0 and want == 1:
                pending = "buy"
            elif position == 1 and want == 0:
                pending = "sell"

    pf_pnls = list(completed)
    if position == 1:
        assert cash_before is not None
        pf_pnls.append(wealth - cash_before)
    count = len(equity)
    return EquityPath(
        dates=dates,
        closes=marked,
        equity=equity,
        long=long_flags,
        fills=fills,
        start_dollars=starting_dollars,
        end_dollars=wealth,
        start_price=weeks[first][1],
        end_price=weeks[-1][1],
        start=weeks[first][0],
        end=weeks[-1][0],
        fees_paid=fees_paid,
        completed_round_trips=len(completed),
        whipsaws=0,
        exposure=(sum(1 for flag in long_flags if flag) / count) if count else 0.0,
        completed_pnls=completed,
        pf_pnls=pf_pnls,
    )
```

The buy test's first lookback is 12. Index 20 is the first close of 200. SMA-4 of the prior weeks is 100, so 200 is above it and a buy is pended. The next week, index 21, fills at 200. The fee is `10000 * 0.0015`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/search/test_runner.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/search/runner.py tests/search/test_runner.py
git commit -m "$(cat <<'EOF'
Simulate a search spec on the next weekly close.

EOF
)"
```

---

### Task 5: Breeding number, fragility, and stress means

**Files:**
- Create: `price_forecast/search/score.py`
- Test: `tests/search/test_score.py`

**Interfaces:**
- Consumes: `EquityPath` from `price_forecast.backtest.engine`, `max_drawdown` and `profit_factor` from `price_forecast.backtest.kpis`.
- Produces:

```python
@dataclass(frozen=True)
class PathMetrics:
    total_return: float
    edge: float
    sharpe: float | None
    max_drawdown: float
    win_rate: float | None
    profit_factor: float | None
    round_trips: int
    end_dollars: float
    start_dollars: float
    trip_pnls: tuple[float, ...]
    hodl_return: float

def hodl_return(first_price: float, last_price: float, cost: float) -> float: ...
def metrics_from_path(path: EquityPath, *, first_price: float, last_price: float, cost: float) -> PathMetrics: ...
def breeding_number(child: PathMetrics, baseline: PathMetrics) -> float: ...
def baseline_is_usable(baseline: PathMetrics) -> bool: ...
def is_fragile(metrics: PathMetrics) -> bool: ...
def stress_result(coinbase_edge: float, remix_edges: list[float], synthetic_edges: list[float]) -> tuple[bool, float, float]: ...
def skill_warnings(metrics: PathMetrics, *, evaluate, review) -> dict: ...
```

`hodl_return` is `(1 - cost) * (last_price / first_price) - 1`. Strategy total return is `end_dollars / start_dollars - 1`. Edge is strategy total return minus that HODL return.

Sharpe uses weekly equity simple returns, sample standard deviation (`ddof=1`), risk-free rate 0, and `math.sqrt(52)`. Zero variance or fewer than two returns makes Sharpe `None`.

`profit_factor` of `math.inf`, a `None` Sharpe, a `None` win rate, or zero round trips is an unusable metric. `breeding_number` is not called on those rows. `baseline_is_usable` is false when any of total return, Sharpe, absolute max drawdown, win rate, or profit factor is missing, non-finite, or 0.

Drawdown ratio is `abs(baseline.max_drawdown) / abs(child.max_drawdown)`. A child drawdown of 0 uses 3. Every ratio is clipped to 0 through 3. The breeding number is the sum. The baseline against itself is 5.

`is_fragile` is false when net profit (`end_dollars - start_dollars`) is not strictly positive or when `edge` is not strictly positive. Otherwise subtract each trip pnl from `end_dollars` once, recompute edge with the same HODL return, and return true if any omission makes the new edge `<= 0.5 * edge` or `<= 0`.

`stress_result` returns `(passed, remix_mean, synthetic_mean)`. `passed` is true only when `coinbase_edge > 0` and both means are `>= 0.5 * coinbase_edge`. The caller skips this function when Coinbase edge is not strictly positive.

`skill_warnings` calls `evaluate(total_trades=round_trips, win_rate=win_rate*100, avg_win_pct, avg_loss_pct, max_drawdown_pct=abs(max_drawdown)*100, years_tested=1, num_parameters=1, slippage_tested=True)`. Average win and average loss are the mean positive trip pnl and the mean absolute negative trip pnl, each divided by `start_dollars` and multiplied by 100. No wins uses `avg_win_pct=0`. No losses uses `avg_loss_pct=0`. The returned dict is:

```python
{
    "backtest_expert_verdict": result["verdict"],
    "small_sample": any(flag["id"] == "small_sample" for flag in result["red_flags"]),
    "reviewer_verdict": review.verdict,
    "reviewer_sample_warning": warning,
}
```

`warning` is the `reason` of the finding whose `criterion` is `C3_sample_adequacy` when its `severity` is not `pass`, else `None`. `review` is called with:

```python
{
    "id": "search",
    "thesis": "Weekly Bitcoin close versus a moving average.",
    "regime": "Neutral",
    "entry": {"conditions": ["weekly_close > sma_8"]},
    "exit": {"stop_loss_pct": 0.08, "take_profit_rr": 1.5},
    "risk": {"risk_per_trade": 0.01, "max_positions": 1},
}
```

- [ ] **Step 1: Write the failing test**

`tests/search/test_score.py`:

```python
import math

import pytest

from price_forecast.search.score import (
    PathMetrics,
    breeding_number,
    is_fragile,
    stress_result,
)


def _metrics(**overrides) -> PathMetrics:
    base = dict(
        total_return=1.0,
        edge=0.40,
        sharpe=1.0,
        max_drawdown=-0.20,
        win_rate=0.5,
        profit_factor=2.0,
        round_trips=4,
        end_dollars=20_000.0,
        start_dollars=10_000.0,
        trip_pnls=(2_500.0, 2_500.0, 2_500.0, 2_500.0),
        hodl_return=0.60,
    )
    base.update(overrides)
    return PathMetrics(**base)


def test_baseline_against_itself_is_five():
    metrics = _metrics()
    assert breeding_number(metrics, metrics) == pytest.approx(5.0)


def test_shallower_drawdown_raises_the_drawdown_ratio():
    baseline = _metrics(max_drawdown=-0.30)
    child = _metrics(max_drawdown=-0.10)
    # four ratios stay 1, drawdown ratio is 0.30/0.10 = 3, sum is 7
    assert breeding_number(child, baseline) == pytest.approx(7.0)


def test_stress_fails_when_either_family_is_under_half():
    passed, remix_mean, synthetic_mean = stress_result(1.0, [0.4, 0.4], [0.6, 0.6])
    assert passed is False
    assert remix_mean == pytest.approx(0.4)
    assert synthetic_mean == pytest.approx(0.6)
    passed, _, _ = stress_result(1.0, [0.5, 0.5], [0.5, 0.5])
    assert passed is True


def test_one_trip_that_holds_half_the_edge_is_fragile():
    # end 20000, start 10000, hodl 0. Edge = 1.0. One trip of 6000 cuts end to 14000, edge to 0.4.
    metrics = _metrics(
        edge=1.0,
        hodl_return=0.0,
        end_dollars=20_000.0,
        trip_pnls=(6_000.0, 1_000.0, 1_000.0, 2_000.0),
    )
    assert is_fragile(metrics) is True


def test_even_trips_are_not_fragile():
    metrics = _metrics(edge=1.0, hodl_return=0.0, end_dollars=20_000.0, trip_pnls=(2_500.0,) * 4)
    assert is_fragile(metrics) is False
    assert math.isfinite(metrics.edge)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/search/test_score.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.search.score'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/search/score.py`:

```python
from __future__ import annotations

import math
from dataclasses import dataclass

from price_forecast.backtest.engine import EquityPath
from price_forecast.backtest.kpis import max_drawdown, profit_factor


@dataclass(frozen=True)
class PathMetrics:
    total_return: float
    edge: float
    sharpe: float | None
    max_drawdown: float
    win_rate: float | None
    profit_factor: float | None
    round_trips: int
    end_dollars: float
    start_dollars: float
    trip_pnls: tuple[float, ...]
    hodl_return: float


def hodl_return(first_price: float, last_price: float, cost: float) -> float:
    return (1.0 - cost) * (last_price / first_price) - 1.0


def _sharpe(equity: list[float]) -> float | None:
    returns = [
        equity[i] / equity[i - 1] - 1.0
        for i in range(1, len(equity))
        if equity[i - 1] > 0.0
    ]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    if var == 0.0:
        return None
    return (mean / math.sqrt(var)) * math.sqrt(52.0)


def metrics_from_path(
    path: EquityPath, *, first_price: float, last_price: float, cost: float
) -> PathMetrics:
    total = path.end_dollars / path.start_dollars - 1.0
    hold = hodl_return(first_price, last_price, cost)
    wins = sum(1 for value in path.completed_pnls if value > 0.0)
    rate = (wins / len(path.completed_pnls)) if path.completed_pnls else None
    factor = profit_factor(path.completed_pnls)
    if factor is not None and not math.isfinite(factor):
        factor = None
    return PathMetrics(
        total_return=total,
        edge=total - hold,
        sharpe=_sharpe(list(path.equity)),
        max_drawdown=max_drawdown(path.equity),
        win_rate=rate,
        profit_factor=factor,
        round_trips=path.completed_round_trips,
        end_dollars=path.end_dollars,
        start_dollars=path.start_dollars,
        trip_pnls=tuple(path.completed_pnls),
        hodl_return=hold,
    )


def _clip(value: float) -> float:
    return min(3.0, max(0.0, value))


def breeding_number(child: PathMetrics, baseline: PathMetrics) -> float:
    drawdown = 3.0 if child.max_drawdown == 0.0 else abs(baseline.max_drawdown) / abs(child.max_drawdown)
    parts = [
        child.total_return / baseline.total_return,
        child.sharpe / baseline.sharpe,
        drawdown,
        child.win_rate / baseline.win_rate,
        child.profit_factor / baseline.profit_factor,
    ]
    return sum(_clip(part) for part in parts)


def baseline_is_usable(baseline: PathMetrics) -> bool:
    values = [
        baseline.total_return,
        baseline.sharpe,
        abs(baseline.max_drawdown),
        baseline.win_rate,
        baseline.profit_factor,
    ]
    return all(value is not None and math.isfinite(value) and value != 0.0 for value in values)


def is_fragile(metrics: PathMetrics) -> bool:
    if metrics.end_dollars - metrics.start_dollars <= 0.0 or metrics.edge <= 0.0:
        return False
    for pnl in metrics.trip_pnls:
        end = metrics.end_dollars - pnl
        total = end / metrics.start_dollars - 1.0
        edge = total - metrics.hodl_return
        if edge <= 0.5 * metrics.edge or edge <= 0.0:
            return True
    return False


def stress_result(
    coinbase_edge: float, remix_edges: list[float], synthetic_edges: list[float]
) -> tuple[bool, float, float]:
    remix_mean = sum(remix_edges) / len(remix_edges)
    synthetic_mean = sum(synthetic_edges) / len(synthetic_edges)
    passed = coinbase_edge > 0.0 and remix_mean >= 0.5 * coinbase_edge and synthetic_mean >= 0.5 * coinbase_edge
    return passed, remix_mean, synthetic_mean


def skill_warnings(metrics: PathMetrics, *, evaluate, review) -> dict:
    wins = [value for value in metrics.trip_pnls if value > 0.0]
    losses = [value for value in metrics.trip_pnls if value < 0.0]
    avg_win = (sum(wins) / len(wins) / metrics.start_dollars * 100.0) if wins else 0.0
    avg_loss = (sum(abs(value) for value in losses) / len(losses) / metrics.start_dollars * 100.0) if losses else 0.0
    rate = 0.0 if metrics.win_rate is None else metrics.win_rate * 100.0
    result = evaluate(
        total_trades=metrics.round_trips,
        win_rate=rate,
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        max_drawdown_pct=abs(metrics.max_drawdown) * 100.0,
        years_tested=1,
        num_parameters=1,
        slippage_tested=True,
    )
    reviewed = review(
        {
            "id": "search",
            "thesis": "Weekly Bitcoin close versus a moving average.",
            "regime": "Neutral",
            "entry": {"conditions": ["weekly_close > sma_8"]},
            "exit": {"stop_loss_pct": 0.08, "take_profit_rr": 1.5},
            "risk": {"risk_per_trade": 0.01, "max_positions": 1},
        }
    )
    warning = None
    for finding in reviewed.findings:
        if finding.criterion == "C3_sample_adequacy" and finding.severity != "pass":
            warning = finding.reason
    return {
        "backtest_expert_verdict": result["verdict"],
        "small_sample": any(flag["id"] == "small_sample" for flag in result["red_flags"]),
        "reviewer_verdict": reviewed.verdict,
        "reviewer_sample_warning": warning,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/search/test_score.py -q`

Expected: PASS

The fragility fixture uses four trip pnls that sum to 10000, matching `end_dollars - start_dollars`. The 6000 omission leaves edge 0.4, which is under half of 1.0.

- [ ] **Step 5: Commit**

```bash
git add price_forecast/search/score.py tests/search/test_score.py
git commit -m "$(cat <<'EOF'
Score a search spec on edge, fragility, and stress means.

EOF
)"
```

---

### Task 6: Atomic ledger and pool of 20

**Files:**
- Create: `price_forecast/search/ledger.py`
- Modify: `.gitignore`
- Test: `tests/search/test_ledger.py`

**Interfaces:**
- Consumes: nothing from the runner. Members are dicts.
- Produces:

```python
def append_jsonl(path: Path, row: dict) -> None: ...
def insert_member(members: list[dict], candidate: dict, *, cap: int = 20, seed: bool = False) -> list[dict]: ...
def champion_of(members: list[dict]) -> dict: ...
def load_pool(path: Path) -> dict: ...
def save_pool(path: Path, pool: dict) -> None: ...
```

A member dict has `id`, `spec`, `breeding_number`, `inserted_cycle`, `trial_count`. `insert_member` with `seed=True` returns `[candidate]` and ignores eligibility. Otherwise the candidate is added only when `coinbase_edge > 0`, `stress_pass` is true, `fragile` is false, and `breeding_number` is a number. If the pool has fewer than `cap` members, append it. If it is full, append it only when `breeding_number` is strictly greater than the lowest `breeding_number`, and drop the oldest member among those that share that lowest number (`inserted_cycle`, then list order). An equal number does not insert.

`champion_of` returns the member with the highest `breeding_number`. A tie returns the smaller `inserted_cycle`.

`save_pool` and `append_jsonl` write a sibling temp file and `os.replace` it onto the target. `load_pool` on a missing file returns `{"members": [], "champion_id": None, "stall": 0, "trial_count": 0}`.

Add this line to `.gitignore`:

```
results/search/
```

- [ ] **Step 1: Write the failing test**

`tests/search/test_ledger.py`:

```python
import json

from price_forecast.search.ledger import append_jsonl, champion_of, insert_member, load_pool


def _member(id_: str, number: float, cycle: int, *, edge: float = 1.0, stress: bool = True, fragile: bool = False):
    return {
        "id": id_,
        "spec": {"mode": "threshold"},
        "breeding_number": number,
        "inserted_cycle": cycle,
        "trial_count": cycle,
        "coinbase_edge": edge,
        "stress_pass": stress,
        "fragile": fragile,
    }


def test_seed_is_kept_when_stress_fails():
    failed = _member("seed", 5.0, 0, stress=False)
    assert [item["id"] for item in insert_member([], failed, seed=True)] == ["seed"]


def test_failed_stress_does_not_enter():
    pool = insert_member([], _member("seed", 5.0, 0), seed=True)
    child = _member("c1", 9.0, 1, stress=False)
    assert [item["id"] for item in insert_member(pool, child)] == ["seed"]


def test_tie_keeps_the_older_member_and_the_higher_number_replaces_the_weakest():
    members = [_member("a", 5.0, 0), _member("b", 4.0, 1)]
    tied = _member("c", 4.0, 2)
    assert [item["id"] for item in insert_member(members, tied, cap=2)] == ["a", "b"]
    stronger = _member("d", 4.1, 3)
    assert [item["id"] for item in insert_member(members, stronger, cap=2)] == ["a", "d"]


def test_champion_tie_keeps_the_older_member():
    members = [_member("old", 5.0, 0), _member("new", 5.0, 1)]
    assert champion_of(members)["id"] == "old"


def test_temp_replace_leaves_the_previous_line_when_replace_is_the_commit(tmp_path):
    path = tmp_path / "ledger.jsonl"
    append_jsonl(path, {"id": "seed", "status": "ok"})
    append_jsonl(path, {"id": "c1", "status": "ok"})
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in rows] == ["seed", "c1"]
    assert load_pool(tmp_path / "missing.json")["members"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/search/test_ledger.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.search.ledger'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/search/ledger.py`:

```python
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
    oldest = min(
        (member for member in members if member["breeding_number"] == weakest),
        key=lambda member: member["inserted_cycle"],
    )
    return [member for member in members if member["id"] != oldest["id"]] + [candidate]


def champion_of(members: list[dict]) -> dict:
    return min(members, key=lambda member: (-member["breeding_number"], member["inserted_cycle"]))
```

Append `results/search/` as its own line at the end of `.gitignore`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/search/test_ledger.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/search/ledger.py tests/search/test_ledger.py .gitignore
git commit -m "$(cat <<'EOF'
Keep an atomic search ledger and a pool of twenty specs.

EOF
)"
```

---

### Task 7: Preflight and the breeding loop

**Files:**
- Create: `price_forecast/search/__main__.py`
- Test: `tests/search/test_preflight.py`

**Interfaces:**
- Consumes: `locked_crashgate`, `spec_to_mapping`, `mutate`, `translate`, `Unmapped`, `append_side_pile`, `simulate_spec`, `FILL_COST`, `metrics_from_path`, `breeding_number`, `baseline_is_usable`, `is_fragile`, `stress_result`, `skill_warnings`, `append_jsonl`, `insert_member`, `champion_of`, `load_pool`, `save_pool`.
- Produces: `def main(argv: list[str] | None = None) -> int`.

`main` parses `--cycles` (optional int), `--run-seed` (default 0), `--results` (default `<repo>/results/search`), `--coinbase` (default `BTC_USD_DAILY_CSV`), `--path-count` (default 100). Tests call `main` with explicit paths and with these seams patched on the module: `build_remix`, `build_synthetic`, `smoke_skills`, `read_candles`, `weekly_sessions`, `gate_for`, `pivot_runner`.

Startup order inside `main`:

1. If `coinbase` is not a file, return 1. Do not create `results`.
2. For each index in `range(path_count)`, require `remix_dir / f"btc-usd-daily-seed0-path{index}.csv"` and the same name under `synthetic_dir`. `remix_dir` is `coinbase.parent / "remix"`. `synthetic_dir` is `coinbase.parent / "synthetic"`. If any remix file is missing, call `build_remix(coinbase, path_count)`. If any synthetic file is missing, call `build_synthetic(coinbase, path_count)`. If a required file is still missing, or either builder raises, return 1 and do not create `results`.
3. Call `smoke_skills()`. If it raises, return 1 and do not create `results`.
4. Load the pool. If `members` is empty, score `locked_crashgate()` on the Coinbase file and on every stress file, append the seed ledger row with `trial_count` 0, `parent_id` null, `cycle` -1, and `insert_member(..., seed=True)` even when stress or fragility fails. If `baseline_is_usable` is false, return 1. This return happens after the seed directories may have been created only when step 4 started; a baseline failure may write nothing if it is detected before `append_jsonl`. Check usability after the Coinbase score and before any results write. The 200 stress paths for the seed still run only after the baseline is usable, because the seed is inserted either way and its means must be stored. Order: Coinbase score, usability check (return 1 with no results write if unusable), stress means, then write the seed row and pool.
5. For each cycle in `range(cycles)`, pick a parent with `numpy.random.Generator(numpy.random.PCG64(numpy.random.SeedSequence([run_seed, cycle, 1])))` and `integers(0, len(members))`. If `stall >= 50`, call `pivot_runner` once, translate the returned draft, and set `stall` to 0 after the attempt whether or not it maps. An `Unmapped` error appends a side-pile line and does not append a ledger row. A mapped draft is scored as a child whose parent id is the champion id. Otherwise mutate with `run_seed` and `cycle`, score the child, and append one ledger row at the end of the cycle. A simulation exception appends `status: "error"` with the current `trial_count` and does not increment it. An `ok` row increments `trial_count` by one before it is stored. Recompute the champion. If its breeding number is not strictly greater than the previous champion breeding number, increment `stall`. If it is strictly greater, set `stall` to 0. Save the pool at the end of the cycle, including `champion_id` and `trial_count`.

`path_count` in production is 100. Tests pass `--path-count 2` and point `--coinbase` at a temp CSV so the remix and synthetic dirs are siblings of that CSV.

`build_remix` and `build_synthetic` in production call `python -m price_forecast.datafactory.remix` and `python -m price_forecast.datafactory.synthetic` with `--csv`, `--n-paths`, and `--seed 0` via `subprocess.run(..., check=True)`. Remix does not pass `--mean-block-bars`.

`smoke_skills` imports `evaluate` from the installed `backtest-expert` scripts directory and `review_draft` from the installed `edge-strategy-reviewer` scripts directory (`Path.home() / ".agents" / "skills" / <name> / "scripts"`), then calls `skill_warnings` on a tiny usable `PathMetrics` stand-in built without a backtest: `PathMetrics(total_return=1, edge=1, sharpe=1, max_drawdown=-0.1, win_rate=0.5, profit_factor=2, round_trips=30, end_dollars=20000, start_dollars=10000, trip_pnls=(100.0, -50.0), hodl_return=0)`.

`gate_for(candles)` in production returns a callable that uses `BaseBreakoutGate` only when a spec asks for a switch. Tests pass a `gate_for` that returns `lambda _day: (True, True)`.

`pivot_runner(results, champion_spec)` in production writes `results/pivots/champion_draft.yaml` and `results/pivots/diagnosis.json` with `triggers_fired` set to one object `{"trigger": "plateau", "severity": "medium", "message": "champion breeding number did not rise for 50 cycles"}`, runs `generate_pivots.py --diagnosis <that file> --strategy <draft> --max-pivots 1 --output-dir results/pivots`, and returns the first written YAML mapping. A non-zero exit or a missing YAML raises `Unmapped("pivot script failed")` by the caller catching `subprocess.CalledProcessError` and `StopIteration`.

A child row stores `spec` from `spec_to_mapping`, Coinbase metrics, the five baseline numbers, `breeding_number` when the metrics are usable, `remix_mean_edge`, `synthetic_mean_edge`, `stress_pass`, `fragile`, `round_trips`, and `skill_warnings` for `status: "ok"`. Unusable Coinbase metrics (undefined Sharpe, undefined profit factor, or zero trips) are `status: "error"` and do not enter the pool.

`--cycles` omitted loops until `KeyboardInterrupt`, then returns 0. The interrupt is caught outside the cycle body, after a completed cycle has already saved.

Do not open `price_forecast/strategies/crashgate_v1.py` for writing. The test compares its bytes before and after `main`.

- [ ] **Step 1: Write the failing test**

`tests/search/test_preflight.py`:

```python
import json
from datetime import date, timedelta
from pathlib import Path

from price_forecast.data.candles import Candle, write_candles
from price_forecast.search import __main__ as search_main
from price_forecast.search.score import PathMetrics
from price_forecast.search.spec import locked_crashgate, spec_to_mapping


def _install(monkeypatch, tmp_path: Path):
    coinbase = tmp_path / "data" / "btc-usd-daily.csv"
    coinbase.parent.mkdir(parents=True)
    day = date(2018, 1, 1)
    candles = [
        Candle(day + timedelta(days=i), 100.0, 110.0, 100.0, 105.0, 1.0)
        for i in range(400)
    ]
    write_candles(coinbase, candles)

    def build(kind: str):
        def _build(_csv, count: int) -> None:
            dest = coinbase.parent / kind
            dest.mkdir(parents=True, exist_ok=True)
            for index in range(count):
                write_candles(dest / f"btc-usd-daily-seed0-path{index}.csv", candles)

        return _build

    monkeypatch.setattr(search_main, "build_remix", build("remix"))
    monkeypatch.setattr(search_main, "build_synthetic", build("synthetic"))
    monkeypatch.setattr(search_main, "smoke_skills", lambda: None)
    monkeypatch.setattr(search_main, "gate_for", lambda _candles: (lambda _day: (True, True)))
    monkeypatch.setattr(search_main, "pivot_runner", lambda *_args: {"conditions": ["funding"]})
    monkeypatch.setattr(search_main, "score_file", lambda *_args, **_kwargs: _canned_metrics())
    return coinbase


def _canned_metrics() -> PathMetrics:
    return PathMetrics(
        total_return=1.0,
        edge=0.4,
        sharpe=1.0,
        max_drawdown=-0.2,
        win_rate=0.5,
        profit_factor=2.0,
        round_trips=4,
        end_dollars=20_000.0,
        start_dollars=10_000.0,
        trip_pnls=(2_500.0, 2_500.0, 2_500.0, 2_500.0),
        hodl_return=0.6,
    )


def test_missing_coinbase_writes_nothing(monkeypatch, tmp_path):
    results = tmp_path / "results" / "search"
    monkeypatch.setattr(search_main, "smoke_skills", lambda: (_ for _ in ()).throw(RuntimeError("skill")))
    code = search_main.main(
        ["--cycles", "1", "--coinbase", str(tmp_path / "missing.csv"), "--results", str(results), "--path-count", "2"]
    )
    assert code == 1
    assert not results.exists()


def test_skill_failure_writes_nothing(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"

    def boom():
        raise RuntimeError("skill")

    monkeypatch.setattr(search_main, "smoke_skills", boom)
    code = search_main.main(
        ["--cycles", "1", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 1
    assert not results.exists()


def test_seed_reloads_and_does_not_touch_the_locked_file(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    locked = Path("price_forecast/strategies/crashgate_v1.py").read_bytes()
    code = search_main.main(
        ["--cycles", "0", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 0
    assert Path("price_forecast/strategies/crashgate_v1.py").read_bytes() == locked
    pool = json.loads((results / "pool.json").read_text(encoding="utf-8"))
    assert pool["members"][0]["spec"] == spec_to_mapping(locked_crashgate())
    assert pool["members"][0]["trial_count"] == 0


def test_stall_calls_the_pivot_once(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    calls = {"n": 0}

    def pivot(*_args):
        calls["n"] += 1
        return {"id": "fund", "conditions": ["funding"]}

    monkeypatch.setattr(search_main, "pivot_runner", pivot)
    monkeypatch.setattr(search_main, "mutate", lambda parent, **_kwargs: parent)
    code = search_main.main(
        ["--cycles", "51", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 0
    assert calls["n"] == 1
    side = (results / "side_pile.jsonl").read_text(encoding="utf-8")
    assert "funding" in side
```

Stall starts at 0 and increments at the end of a quiet cycle. The pivot check is at the start of a cycle. Cycles 0 through 49 leave stall at 50. Cycle 50, the 51st cycle, calls the pivot once and resets stall to 0. `score_file` is patched to canned metrics because a flat candle file does not produce a usable CrashGate baseline. `Candle` field order is `day, low, high, open, close, volume`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/search/test_preflight.py -q`

Expected: FAIL with `ModuleNotFoundError` for `price_forecast.search.__main__` or an `ImportError` on `main`.

- [ ] **Step 3: Write minimal implementation**

`price_forecast/search/__main__.py` is the whole loop. Tests patch the module-level names `build_remix`, `build_synthetic`, `smoke_skills`, `gate_for`, `pivot_runner`, `score_file`, and `mutate`. Do not write `price_forecast/strategies/crashgate_v1.py`. `weekly_sessions` is only read from that module inside `score_file`.

```python
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml

from price_forecast.data.candles import BTC_USD_DAILY_CSV, read_candles
from price_forecast.search.ledger import (
    append_jsonl,
    champion_of,
    insert_member,
    load_pool,
    save_pool,
)
from price_forecast.search.mutate import mutate
from price_forecast.search.runner import FILL_COST, simulate_spec
from price_forecast.search.score import (
    PathMetrics,
    baseline_is_usable,
    breeding_number,
    is_fragile,
    metrics_from_path,
    skill_warnings,
    stress_result,
)
from price_forecast.search.spec import locked_crashgate, spec_to_mapping
from price_forecast.search.translate import Unmapped, append_side_pile, translate
from price_forecast.strategies.crashgate_entry import BaseBreakoutGate
from price_forecast.strategies.crashgate_v1 import weekly_sessions

REPO = Path(__file__).resolve().parents[2]


def _skill_module(skill: str, module: str):
    scripts = Path.home() / ".agents" / "skills" / skill / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return importlib.import_module(module)


def _warning_tools():
    evaluate = _skill_module("backtest-expert", "evaluate_backtest").evaluate
    review = _skill_module("edge-strategy-reviewer", "review_strategy_drafts").review_draft
    return evaluate, review


def smoke_skills() -> None:
    evaluate, review = _warning_tools()
    skill_warnings(
        PathMetrics(
            total_return=1.0,
            edge=1.0,
            sharpe=1.0,
            max_drawdown=-0.1,
            win_rate=0.5,
            profit_factor=2.0,
            round_trips=30,
            end_dollars=20_000.0,
            start_dollars=10_000.0,
            trip_pnls=(100.0, -50.0),
            hodl_return=0.0,
        ),
        evaluate=evaluate,
        review=review,
    )


def build_remix(coinbase: Path, count: int) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "price_forecast.datafactory.remix",
            "--csv",
            str(coinbase),
            "--n-paths",
            str(count),
            "--seed",
            "0",
        ],
        check=True,
    )


def build_synthetic(coinbase: Path, count: int) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "price_forecast.datafactory.synthetic",
            "--csv",
            str(coinbase),
            "--n-paths",
            str(count),
            "--seed",
            "0",
        ],
        check=True,
    )


def gate_for(candles):
    cached = {}

    def _gate(day):
        box = cached.get("gate")
        if box is None:
            box = BaseBreakoutGate(candles)
            cached["gate"] = box
        return box.parts(day)

    return _gate


def score_file(candles, spec, gate) -> PathMetrics:
    weeks = weekly_sessions(candles)
    path = simulate_spec(weeks, spec, gate, cost=FILL_COST)
    return metrics_from_path(
        path, first_price=path.start_price, last_price=path.end_price, cost=FILL_COST
    )


def _family_paths(directory: Path, count: int) -> list[Path]:
    return [directory / f"btc-usd-daily-seed0-path{index}.csv" for index in range(count)]


def _ensure_family(directory: Path, coinbase: Path, count: int, builder) -> None:
    paths = _family_paths(directory, count)
    if any(not path.is_file() for path in paths):
        builder(coinbase, count)
    if any(not path.is_file() for path in paths):
        raise FileNotFoundError(directory)


def pivot_runner(results: Path, champion_spec) -> dict:
    dest = results / "pivots"
    dest.mkdir(parents=True, exist_ok=True)
    draft_path = dest / "champion_draft.yaml"
    diagnosis_path = dest / "diagnosis.json"
    draft_path.write_text(
        yaml.safe_dump(spec_to_mapping(champion_spec), sort_keys=True),
        encoding="utf-8",
    )
    diagnosis_path.write_text(
        json.dumps(
            {
                "strategy_id": "crashgate_search",
                "recommendation": "pivot",
                "score_trajectory": [],
                "triggers_fired": [
                    {
                        "trigger": "plateau",
                        "severity": "medium",
                        "message": "champion breeding number did not rise for 50 cycles",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    script = Path.home() / ".agents" / "skills" / "strategy-pivot-designer" / "scripts" / "generate_pivots.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--diagnosis",
            str(diagnosis_path),
            "--strategy",
            str(draft_path),
            "--max-pivots",
            "1",
            "--output-dir",
            str(dest),
        ],
        check=True,
    )
    written = sorted(dest.glob("*.yaml"))
    written = [path for path in written if path.name != "champion_draft.yaml"]
    if not written:
        raise Unmapped("pivot script failed")
    loaded = yaml.safe_load(written[0].read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise Unmapped("pivot script failed")
    return loaded


def _metrics_dict(metrics: PathMetrics) -> dict:
    return {
        "total_return": metrics.total_return,
        "edge": metrics.edge,
        "sharpe": metrics.sharpe,
        "max_drawdown": metrics.max_drawdown,
        "win_rate": metrics.win_rate,
        "profit_factor": metrics.profit_factor,
        "round_trips": metrics.round_trips,
    }


def _score_child(coinbase_candles, stress_candles, spec, gate, baseline: PathMetrics) -> dict:
    try:
        coinbase = score_file(coinbase_candles, spec, gate)
    except Exception as exc:
        return {"status": "error", "error": str(exc), "stress_pass": False, "fragile": False, "round_trips": 0}
    if not baseline_is_usable(coinbase) or coinbase.round_trips == 0 or coinbase.sharpe is None or coinbase.profit_factor is None:
        return {
            "status": "error",
            "error": "unusable coinbase metrics",
            "stress_pass": False,
            "fragile": False,
            "round_trips": coinbase.round_trips,
            "coinbase": _metrics_dict(coinbase),
        }
    fragile = is_fragile(coinbase)
    if coinbase.edge <= 0.0:
        return {
            "status": "ok",
            "coinbase": _metrics_dict(coinbase),
            "baseline": _metrics_dict(baseline),
            "breeding_number": breeding_number(coinbase, baseline),
            "remix_mean_edge": None,
            "synthetic_mean_edge": None,
            "stress_pass": False,
            "fragile": fragile,
            "round_trips": coinbase.round_trips,
            "coinbase_edge": coinbase.edge,
        }
    remix_edges = []
    synthetic_edges = []
    try:
        for candles in stress_candles["remix"]:
            remix_edges.append(score_file(candles, spec, gate).edge)
        for candles in stress_candles["synthetic"]:
            synthetic_edges.append(score_file(candles, spec, gate).edge)
    except Exception as exc:
        return {"status": "error", "error": str(exc), "stress_pass": False, "fragile": fragile, "round_trips": coinbase.round_trips}
    passed, remix_mean, synthetic_mean = stress_result(coinbase.edge, remix_edges, synthetic_edges)
    warnings = {}
    try:
        evaluate, review = _warning_tools()
        warnings = skill_warnings(coinbase, evaluate=evaluate, review=review)
    except Exception as exc:
        warnings = {"skill_error": str(exc)}
    return {
        "status": "ok",
        "coinbase": _metrics_dict(coinbase),
        "baseline": _metrics_dict(baseline),
        "breeding_number": breeding_number(coinbase, baseline),
        "remix_mean_edge": remix_mean,
        "synthetic_mean_edge": synthetic_mean,
        "stress_pass": passed,
        "fragile": fragile,
        "round_trips": coinbase.round_trips,
        "coinbase_edge": coinbase.edge,
        "skill_warnings": warnings,
    }


def _member_from_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "spec": row["spec"],
        "breeding_number": row["breeding_number"],
        "inserted_cycle": row["cycle"],
        "trial_count": row["trial_count"],
        "coinbase_edge": row["coinbase_edge"],
        "stress_pass": row["stress_pass"],
        "fragile": row["fragile"],
    }


def _load_stress(remix_dir: Path, synthetic_dir: Path, count: int) -> dict:
    return {
        "remix": [read_candles(path) for path in _family_paths(remix_dir, count)],
        "synthetic": [read_candles(path) for path in _family_paths(synthetic_dir, count)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Breed CrashGate specs into a ledger.")
    parser.add_argument("--cycles", type=int, default=None)
    parser.add_argument("--run-seed", type=int, default=0)
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--coinbase", type=Path, default=None)
    parser.add_argument("--path-count", type=int, default=100)
    args = parser.parse_args(argv)
    coinbase_path = args.coinbase or BTC_USD_DAILY_CSV
    results = args.results or (REPO / "results" / "search")
    if not coinbase_path.is_file():
        return 1
    remix_dir = coinbase_path.parent / "remix"
    synthetic_dir = coinbase_path.parent / "synthetic"
    try:
        _ensure_family(remix_dir, coinbase_path, args.path_count, build_remix)
        _ensure_family(synthetic_dir, coinbase_path, args.path_count, build_synthetic)
        smoke_skills()
    except Exception:
        return 1

    coinbase_candles = read_candles(coinbase_path)
    gate = gate_for(coinbase_candles)
    pool_path = results / "pool.json"
    ledger_path = results / "ledger.jsonl"
    side_path = results / "side_pile.jsonl"
    pool = load_pool(pool_path)
    if not pool["members"]:
        baseline = score_file(coinbase_candles, locked_crashgate(), gate)
        if not baseline_is_usable(baseline):
            return 1
        stress = _load_stress(remix_dir, synthetic_dir, args.path_count)
        scored = _score_child(coinbase_candles, stress, locked_crashgate(), gate, baseline)
        scored.update(
            {
                "id": "seed",
                "parent_id": None,
                "cycle": -1,
                "spec": spec_to_mapping(locked_crashgate()),
                "trial_count": 0,
                "status": "ok",
            }
        )
        append_jsonl(ledger_path, scored)
        member = _member_from_row(scored)
        pool = {
            "members": insert_member([], member, seed=True),
            "champion_id": "seed",
            "stall": 0,
            "trial_count": 0,
        }
        save_pool(pool_path, pool)
        baseline_metrics = baseline
    else:
        baseline_metrics = PathMetrics(
            total_return=pool["baseline"]["total_return"],
            edge=pool["baseline"]["edge"],
            sharpe=pool["baseline"]["sharpe"],
            max_drawdown=pool["baseline"]["max_drawdown"],
            win_rate=pool["baseline"]["win_rate"],
            profit_factor=pool["baseline"]["profit_factor"],
            round_trips=pool["baseline"]["round_trips"],
            end_dollars=pool["baseline"]["end_dollars"],
            start_dollars=pool["baseline"]["start_dollars"],
            trip_pnls=tuple(pool["baseline"]["trip_pnls"]),
            hodl_return=pool["baseline"]["hodl_return"],
        )
    pool["baseline"] = _metrics_dict(baseline_metrics) | {
        "end_dollars": baseline_metrics.end_dollars,
        "start_dollars": baseline_metrics.start_dollars,
        "trip_pnls": list(baseline_metrics.trip_pnls),
        "hodl_return": baseline_metrics.hodl_return,
    }
    save_pool(pool_path, pool)

    def run_cycle(cycle: int) -> None:
        nonlocal pool
        members = pool["members"]
        champion = champion_of(members)
        previous = champion["breeding_number"]
        trial = pool["trial_count"]
        stall = pool["stall"]
        parent_id = champion["id"]
        child_spec = None
        if stall >= 50:
            try:
                draft = pivot_runner(results, parent_spec(champion))
                child_spec = translate(draft)
            except Unmapped as exc:
                append_side_pile(side_path, draft_id=str(champion["id"]), phrase=exc.phrase)
                pool["stall"] = 0
                save_pool(pool_path, pool)
                return
            pool["stall"] = 0
            stall = 0
        if child_spec is None:
            picker = np.random.Generator(np.random.PCG64(np.random.SeedSequence([args.run_seed, cycle, 1])))
            parent = members[int(picker.integers(0, len(members)))]
            parent_id = parent["id"]
            child_spec = mutate(parent_spec(parent), run_seed=args.run_seed, cycle=cycle)
        stress = _load_stress(remix_dir, synthetic_dir, args.path_count)
        scored = _score_child(coinbase_candles, stress, child_spec, gate, baseline_metrics)
        status = scored["status"]
        if status == "ok":
            trial += 1
            pool["trial_count"] = trial
        row = {
            "id": f"c{cycle}",
            "parent_id": parent_id,
            "cycle": cycle,
            "spec": spec_to_mapping(child_spec),
            "trial_count": trial,
        }
        row.update(scored)
        append_jsonl(ledger_path, row)
        if status == "ok":
            members = insert_member(members, _member_from_row(row))
            pool["members"] = members
            current = champion_of(members)
            pool["champion_id"] = current["id"]
            pool["stall"] = 0 if current["breeding_number"] > previous else stall + 1
        else:
            pool["stall"] = stall + 1
        save_pool(pool_path, pool)

    cycles = args.cycles
    try:
        if cycles is None:
            cycle = 0
            while True:
                run_cycle(cycle)
                cycle += 1
        else:
            for cycle in range(cycles):
                run_cycle(cycle)
    except KeyboardInterrupt:
        return 0
    return 0


def parent_spec(member: dict):
    from price_forecast.search.spec import spec_from_mapping

    return spec_from_mapping(member["spec"])


if __name__ == "__main__":
    raise SystemExit(main())
```

`parent_spec` is called for the pivot champion and for the mutated parent. Do not add a second wrapper.

`_score_child` for the seed must leave `coinbase_edge` on the row. The seed update in `main` forces `status` ok after `_score_child`. If the seed Coinbase edge is positive, `_score_child` already ran stress. The seed is then inserted with `seed=True`.

A flat canned `score_file` returns usable metrics, so the seed test writes the pool. Do not let `_score_child`'s seed path require `skill_warnings` to succeed in tests: `smoke_skills` is patched, but `_warning_tools` is not. Guard the seed row so a warning-tool failure becomes `skill_warnings: {"skill_error": ...}` and still writes `status: ok`. That guard is already in `_score_child`.

`gate_for` returns `BaseBreakoutGate.parts(day)`, a pair `(base_or_breakout, above_long_averages)`. Add `parts` on `BaseBreakoutGate` in `price_forecast/strategies/crashgate_entry.py`. `base_or_breakout` is true when `execution_state` is `Pre-breakout` or `Breakout`. `above_long_averages` is the existing `c1_price_above_sma150_200` pass. `__call__` returns `base and long` from `parts`, so the locked CrashGate rule still requires both. Do not edit `price_forecast/strategies/crashgate_v1.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/search/test_preflight.py tests/search -q`

Expected: PASS for every test under `tests/search/`.

- [ ] **Step 5: Commit**

```bash
git add price_forecast/search/__main__.py tests/search/test_preflight.py
git commit -m "$(cat <<'EOF'
Run the CrashGate search after the files and skills are present.

EOF
)"
```

---

## Self-review

Spec coverage:

- Grammar, locked spec, and rejection of unknown fields: Task 1.
- One edit, seeded mutator, mode reset: Task 2.
- Translator, side pile, no score for unmapped drafts: Task 3 and the pivot branch in Task 7.
- Next-week fill and 0.15% fee: Task 4.
- Breeding number, positive-edge rule, fragility, half-edge means: Task 5.
- Pool of 20, tie rule, atomic ledger, gitignore: Task 6.
- Preflight order, seed insertion despite stress failure, 50-cycle pivot, trial count, locked file untouched: Task 7.
- `residual-edge-analyzer` stays out of the loop. No task calls it.
- The 30-trade skill flags are stored by `skill_warnings` and are not read by `insert_member`.

Placeholder scan: none.

Type names used in later tasks match Task 1 through Task 6: `Spec`, `locked_crashgate`, `spec_to_mapping`, `mutate`, `translate`, `Unmapped`, `append_side_pile`, `simulate_spec`, `FILL_COST`, `PathMetrics`, `metrics_from_path`, `breeding_number`, `baseline_is_usable`, `is_fragile`, `stress_result`, `skill_warnings`, `append_jsonl`, `insert_member`, `champion_of`, `load_pool`, `save_pool`.
