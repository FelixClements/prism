# Indicator Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test an outside search idea that names a known indicator at any in-range setting, and let a later copy of a winning idea change one of those numbers by one step.

**Architecture:** `indicators.py` turns daily candles into Sunday-ending weekly bars and computes each series. `spec.py` gains an `indicator` mode whose comparisons are data. `translate.py` keeps a valid original spec as that spec, and otherwise parses comparisons. `mutate.py` leaves the original three modes on their ladders and steps one number on an indicator parent. `runner.py` is in while every comparison is true. A spec that needs volume skips remix.

**Tech Stack:** Python 3.11, pytest, the existing search package. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-05-indicator-search-design.md`

## Global Constraints

- Do not edit `price_forecast/strategies/crashgate_v1.py`, its fill, its fee, or its locked behavior.
- Fill is the next weekly close. Fee is 0.15% per fill. Start in cash, start flat.
- Original modes stay on their ladders. An 8-week threshold field moves to 6 or 10, not to 7. `close_above_sma_weeks` of 7 is still rejected on a threshold spec.
- A number in a phrase counts weeks. A period is an integer from 2 through 260.
- An indicator position is in only while every comparison is true and every selected filter passes. A week where a required series is undefined is out.
- `down_week` mixed into a draft that is not a valid original threshold spec is not tested.
- One phrase cannot contain two comparisons.
- Remix is not run for `obv`, `obv_sma`, or `rel_volume`. `remix_mean_edge` is null. Synthetic must still be at least half of a positive Coinbase edge.
- A non-positive Coinbase edge still skips every path family.
- Tests use small fixtures. They do not generate 200 paths.

## File map

- Create: `price_forecast/strategies/indicators.py` — `WeekBar`, `weekly_bars`, and one function per series. Produces `series_values(name, args, bars) -> list[float | None]`.
- Modify: `price_forecast/search/spec.py` — `Condition`, indicator mode in `spec_from_mapping` / `spec_to_mapping`, `needs_volume`.
- Modify: `price_forecast/search/translate.py` — original spec first, then indicator phrases.
- Modify: `price_forecast/search/mutate.py` — one-number steps for an indicator parent.
- Modify: `price_forecast/search/runner.py` — evaluate indicator comparisons on the same fill clock.
- Modify: `price_forecast/search/score.py` — `stress_result(..., require_remix=False)`.
- Modify: `price_forecast/search/__main__.py` — skip remix when `needs_volume`.
- Test: `tests/strategies/test_indicators.py`, `tests/search/test_spec.py`, `tests/search/test_translate.py`, `tests/search/test_mutate.py`, `tests/search/test_runner.py`, `tests/search/test_score.py`.

---

### Task 1: Weekly bars and series

Hand-computed values are the ones in the spec. `series_values` returns one value per bar, with `None` before the series exists.

- [x] **Step 1: Write `tests/strategies/test_indicators.py` for SMA, EMA, RSI, ROC, MACD, Bollinger, ATR, Donchian, OBV, relative volume, stochastic, and ADX.**
- [x] **Step 2: Run `pytest tests/strategies/test_indicators.py -q` and confirm the import fails.**
- [x] **Step 3: Implement `price_forecast/strategies/indicators.py`.**
- [x] **Step 4: Re-run that test file and confirm it passes.**

### Task 2: Indicator spec

`Condition` fields: `left: str`, `args: tuple[int | float, ...]`, `op: str`, `right_value: int | float | None = None`, `right_series: str | None = None`, `right_args: tuple[int | float, ...] = ()`.

`Spec.conditions` defaults to an empty tuple so the original three modes stay unchanged.

- [x] **Step 1: Add failing tests for a round trip of `rsi_21 < 25`, rejection of period 1, rejection of RSI level 120, and rejection of a threshold 7.**
- [x] **Step 2: Run `pytest tests/search/test_spec.py -q` and confirm the new tests fail.**
- [x] **Step 3: Implement indicator parsing in `spec.py`, including `needs_volume`.**
- [x] **Step 4: Re-run that test file and confirm it passes.**

### Task 3: Phrases

- [x] **Step 1: Add failing translate tests: locked phrases stay the locked spec; `weekly_close > sma_7` and `rsi_21 < 25` become indicator specs; `funding`, `rsi_1 < 25`, `rsi_14 < 120`, `close > sma_50 > sma_200`, and `down_week` mixed with RSI raise `Unmapped`.**
- [x] **Step 2: Run `pytest tests/search/test_translate.py -q` and confirm the new tests fail.**
- [x] **Step 3: Try the original translator first. On `Unmapped`, parse indicator phrases.**
- [x] **Step 4: Re-run that test file and confirm it passes.**

### Task 4: Breeding steps

- [x] **Step 1: Add failing tests: an indicator parent `rsi_21 < 25` has exactly the four one-number edits; an SMA period of 7 steps to 6 and 8; the locked 8-week field still steps to 6 and 10.**
- [x] **Step 2: Run `pytest tests/search/test_mutate.py -q` and confirm the new tests fail.**
- [x] **Step 3: Implement indicator edits in `mutate.py`. Do not add those edits to the original three modes.**
- [x] **Step 4: Re-run that test file and confirm it passes.**

### Task 5: Runner

- [x] **Step 1: Add a failing test that an indicator spec buys on the next week when the comparison becomes true, and a test that an undefined series does not raise until every week is undefined.**
- [x] **Step 2: Run `pytest tests/search/test_runner.py -q` and confirm the new test fails.**
- [x] **Step 3: Evaluate comparisons in `runner.py`. `score_file` passes weekly bars built from the candles.**
- [x] **Step 4: Re-run that test file and confirm it passes.**

### Task 6: Volume stress

- [x] **Step 1: Add a failing test that `stress_result(..., require_remix=False)` returns a null remix mean and can still pass on synthetic.**
- [x] **Step 2: Run `pytest tests/search/test_score.py -q` and confirm the new test fails.**
- [x] **Step 3: Implement the flag. `__main__._score_child` skips remix when `needs_volume(spec)`.**
- [x] **Step 4: Re-run `pytest tests/search tests/strategies -q` and confirm the suite passes.**
