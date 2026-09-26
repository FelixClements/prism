# Repo Layout and Module Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `price_forecast` into domain folders and split mixed modules so data, strategies, backtests, forecast support, results, and docs each have a clear home, with no change to numbers or fill rules.

**Architecture:** Keep the `price_forecast` package name. Add subpackages `data`, `forecast`, `strategies`, `backtest`, and `remix`. Put live scoreboards in top-level `results/`, the architecture blueprint in `docs/architecture.md`, and the frozen t+1 bakeoff in top-level `archive/`. No shims at old import paths. Imports only go downstream except two orchestrators: `strategies.smagate_v1` (CLI) and `remix.remix` (sanity-check), which may import backtest.

**Tech Stack:** Python 3.11+, pytest, existing numpy/scipy/statsmodels/arch stack. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-26-repo-layout-design.md`

## Global Constraints

- Package name stays `price_forecast`. No `src/` tree. No rename to `prism`.
- No compatibility shims at `price_forecast.weekly_regime` or `price_forecast.sma8_16_kpis` (or `price_forecast.series`, `price_forecast.harness`, `price_forecast.bakeoff`, `price_forecast.remix`, `price_forecast.chronos`, `price_forecast.predictors`).
- Do not change fill rules, costs, KPI definitions, CLI flags, or scoreboard *content*. Move function bodies; only rewrite imports and output paths.
- `python -m price_forecast.strategies.smagate_v1` replaces `python -m price_forecast.sma8_16_kpis`. `python -m price_forecast.forecast.bakeoff` replaces `python -m price_forecast.bakeoff`. `python -m price_forecast.remix.remix` replaces `python -m price_forecast.remix`.
- Live SMAGate and forecast never import `archive` or `price_forecast.backtest.t1`.
- `strategies.signals` never imports backtest, forecast, remix, or archive.
- `data` never imports strategy, backtest, forecast, or remix.
- `archive/` is a repo-root package for tests (`pythonpath = ["."]`). Do not add `archive*` to setuptools `include`. Keep `include = ["price_forecast*"]`.
- Do not move `.cursor/` or `.agents/`.
- `LeakageError` stays on `PriceSeries` in `data.series`.

## Review Focus

- CLI writes scoreboards beside the `.py` file instead of `results/` — a rerun would scatter markdown back into the package. Task 4 and Task 5 pin `RESULTS_DIR`.
- `backtest.engine` importing `smagate_v1` at module level while `smagate_v1` imports `engine` at module level — circular import on `python -m`. Task 4 pins lazy imports inside `main()`.
- Live SMAGate accidentally importing `backtest.t1` or `archive` after the split. Task 4 and Task 8 pin source/import checks.
- Frozen bakeoff tests drop out of collection after the archive move. Task 7 pins pytest collection.
- `from price_forecast import evaluate` / `LeakageError` breaks because `__init__.py` still points at deleted flat modules. Task 5 pins the public re-exports.

## File map (lock this)

| Path | Responsibility |
| --- | --- |
| `price_forecast/data/series.py` | `PriceSeries`, `LeakageError`, Coinbase + synthetic loaders. Move of `price_forecast/series.py` unchanged. |
| `price_forecast/data/weekly.py` | `weekly_closes(series: PriceSeries) -> list[tuple[date, float]]` and private `_sunday_week_end`. |
| `price_forecast/strategies/signals.py` | `sma_at`, `sma_signal`, `dual_sma_signal`, `asymmetric_sma_signal`, `donchian_signal`. |
| `price_forecast/strategies/smagate_v1.py` | `BUY_WEEKS`, `SELL_WEEKS`, `FILL_COST`, `STARTING_DOLLARS`, `WHIPSAW_MAX_HOLDING_BARS`, `RESULTS_DIR`, and CLI `main()`. |
| `price_forecast/backtest/engine.py` | `Fill`, `EquityPath`, `simulate_strategy`, `simulate_hodl`, `first_comparable_index`. |
| `price_forecast/backtest/kpis.py` | `SideKpis`, `KpiReport`, `MonthKpis`, `ChapterWindow`, KPI math, monthly chapters. |
| `price_forecast/backtest/reports.py` | Markdown/CSV formatters. |
| `price_forecast/backtest/t1.py` | t+1 / 10 bp engine: `BacktestResult`, `DollarBacktestResult`, `backtest`, `dollar_backtest`, F&G helpers, `pass_a` / `pass_c`. |
| `price_forecast/forecast/{harness,predictors,chronos,bakeoff}.py` | Walk-forward scoreboard. Move as whole files. |
| `price_forecast/remix/remix.py` | Stationary-bootstrap factory. Move as whole file. |
| `price_forecast/__init__.py` | Re-export forecast scoreboard + `load_daily_closes` / `LeakageError` / `synthetic_daily` only. |
| `results/` | Live `bakeoff_results.md` and SMAGate KPI `.md`/`.csv`. |
| `archive/frozen_t1_bakeoff/` | Frozen t+1 code and its result files. |
| `docs/architecture.md` | Current root README blueprint, moved. |
| `README.md` | Short folder map + the three `python -m` commands. |
| `tests/data/`, `tests/forecast/`, `tests/strategies/`, `tests/backtest/`, `tests/remix/` | Mirrors live packages. |
| `tests/archive/frozen_t1_bakeoff/` | Frozen tests (stay here). |

Delete after the last consumer is updated: `price_forecast/series.py`, `price_forecast/weekly_regime.py`, `price_forecast/sma8_16_kpis.py`, `price_forecast/harness.py`, `price_forecast/predictors.py`, `price_forecast/chronos.py`, `price_forecast/bakeoff.py`, `price_forecast/remix.py`, `price_forecast/archive/`.

---

### Task 1: Data package (`series` + `weekly_closes`)

**Files:**
- Create: `price_forecast/data/__init__.py`
- Create: `price_forecast/data/weekly.py`
- Create: `tests/data/test_loader.py` (move of `tests/test_loader.py`)
- Create: `tests/data/test_weekly.py`
- Modify: `price_forecast/__init__.py` (series import only)
- Modify: every current `from price_forecast.series import` site listed in the import step
- Delete: `price_forecast/series.py`, `tests/test_loader.py`

**Interfaces:**
- Consumes: existing `price_forecast/series.py` bodies
- Produces:
  - `price_forecast.data.series.PriceSeries`
  - `price_forecast.data.series.LeakageError`
  - `price_forecast.data.series.load_daily_closes(*, source: str = "synthetic", **kwargs) -> PriceSeries`
  - `price_forecast.data.series.synthetic_daily(...) -> PriceSeries`
  - `price_forecast.data.series.BTC_CLOSE_SOURCE: str` (`"coinbase"`)
  - `price_forecast.data.weekly.weekly_closes(series: PriceSeries) -> list[tuple[date, float]]`

- [ ] **Step 1: Write the failing weekly test at the new path**

Create `tests/data/test_weekly.py`:

```python
"""Sunday weekly bars from daily UTC closes."""

from __future__ import annotations

from datetime import date, timedelta

from price_forecast.data.series import PriceSeries
from price_forecast.data.weekly import weekly_closes


def test_weekly_close_is_last_utc_daily_in_sunday_ending_week():
    daily = []
    price = 100.0
    day = date(2022, 1, 3)
    while day <= date(2022, 1, 9):
        daily.append((day, price))
        price += 1.0
        day += timedelta(days=1)
    series = PriceSeries(daily)

    weeks = weekly_closes(series)

    assert weeks == [(date(2022, 1, 9), 106.0)]


def test_incomplete_trailing_week_is_dropped():
    daily = []
    day = date(2022, 1, 3)
    price = 100.0
    while day <= date(2022, 1, 12):
        daily.append((day, price))
        price += 1.0
        day += timedelta(days=1)
    series = PriceSeries(daily)

    weeks = weekly_closes(series)

    assert [week_end for week_end, _close in weeks] == [date(2022, 1, 9)]
```

Copy `tests/test_loader.py` to `tests/data/test_loader.py` and change only the import:

```python
from price_forecast.data.series import (
    BTC_CLOSE_SOURCE,
    BTC_CLOSE_TIMEZONE,
    bars_from_coinbase_candles,
    load_daily_closes,
)
```

Leave assertions unchanged.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/data/test_loader.py tests/data/test_weekly.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.data'`

- [ ] **Step 3: Create the data package and retarget series imports**

```bash
mkdir -p price_forecast/data tests/data
git mv price_forecast/series.py price_forecast/data/series.py
```

Write `price_forecast/data/__init__.py` as an empty file (or a one-line docstring `"""Daily series and weekly bars."""`).

Write `price_forecast/data/weekly.py` by moving `_sunday_week_end` and `weekly_closes` **unchanged** from `price_forecast/weekly_regime.py` (lines 74–90 today). Change only the series import:

```python
from __future__ import annotations

from datetime import date, timedelta

from price_forecast.data.series import PriceSeries


def _sunday_week_end(day: date) -> date:
    return day + timedelta(days=(6 - day.weekday()))


def weekly_closes(series: PriceSeries) -> list[tuple[date, float]]:
    """Last UTC daily close in each complete Sunday-ending week."""
    last_day = series.dates()[-1]
    buckets: dict[date, tuple[date, float]] = {}
    for day in series.dates():
        week_end = _sunday_week_end(day)
        buckets[week_end] = (day, series.close_at(day))
    weeks = []
    for week_end in sorted(buckets):
        if week_end > last_day:
            continue
        weeks.append((week_end, buckets[week_end][1]))
    return weeks
```

Replace `from price_forecast.series import` with `from price_forecast.data.series import` in:

- `price_forecast/__init__.py`
- `price_forecast/weekly_regime.py`
- `price_forecast/remix.py`
- `price_forecast/bakeoff.py`
- `price_forecast/chronos.py`
- `price_forecast/harness.py`
- `price_forecast/sma8_16_kpis.py`
- `price_forecast/predictors.py`
- `price_forecast/archive/frozen_t1_bakeoff/sma_asymmetric_10k.py`
- `price_forecast/archive/frozen_t1_bakeoff/weekly_bakeoff.py`
- `price_forecast/archive/frozen_t1_bakeoff/sma8_10k.py`
- `tests/test_harness.py` — keep `from price_forecast import ...`; change `from price_forecast.series import PriceSeries` if present (it is not; harness uses package exports)
- `tests/test_arima_garch.py`
- `tests/test_chronos.py`
- `tests/test_weekly_regime.py`
- `tests/test_remix.py`
- `tests/archive/frozen_t1_bakeoff/*.py` if any import `price_forecast.series`

In `weekly_regime.py`, `sma8_16_kpis.py`, `remix.py`, and `tests/test_weekly_regime.py` / `tests/test_remix.py`, change `weekly_closes` imports to:

```python
from price_forecast.data.weekly import weekly_closes
```

Remove `weekly_closes` from `weekly_regime.py` (function body only; leave the rest of that file for Task 3).

Delete `tests/test_loader.py` after the copy exists.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/data/test_loader.py tests/data/test_weekly.py tests/test_harness.py tests/test_weekly_regime.py tests/test_sma8_16_kpis.py tests/test_remix.py tests/archive -q`

Expected: PASS

Then: `.venv/bin/pytest -q`

Expected: PASS (whole suite)

- [ ] **Step 5: Commit**

```bash
git add price_forecast tests
git commit -m "$(cat <<'EOF'
Move daily series and weekly bars into price_forecast.data.

EOF
)"
```

---

### Task 2: Strategy signals

**Files:**
- Create: `price_forecast/strategies/__init__.py`
- Create: `price_forecast/strategies/signals.py`
- Create: `tests/strategies/test_signals.py`
- Modify: `price_forecast/weekly_regime.py` (delete signal functions; import from signals if any t+1 helper still needs them — it should not)
- Modify: `price_forecast/sma8_16_kpis.py` (`sma_at` import)
- Modify: `price_forecast/archive/frozen_t1_bakeoff/weekly_bakeoff.py`
- Modify: `price_forecast/archive/frozen_t1_bakeoff/sma8_10k.py`
- Modify: `price_forecast/archive/frozen_t1_bakeoff/sma_asymmetric_10k.py`
- Modify: `tests/test_weekly_regime.py` (remove signal tests once moved)
- Modify: `tests/test_sma8_16_kpis.py` (`sma_at` import)
- Modify: `tests/archive/frozen_t1_bakeoff/*.py` signal imports

**Interfaces:**
- Consumes: `weekly_closes` is not used here; signals take `weeks: Sequence[tuple[date, float]]`
- Produces:
  - `sma_at(closes: Sequence[float], index: int, lookback: int) -> float`
  - `sma_signal(weeks, *, lookback: int) -> list[int | None]`
  - `dual_sma_signal(weeks, *, fast: int = 12, slow: int = 26) -> list[int | None]`
  - `asymmetric_sma_signal(weeks, *, buy_weeks: int, sell_weeks: int, start_in_btc: bool = True) -> list[int | None]`
  - `donchian_signal(weeks, *, lookback: int = 12) -> list[int | None]`

- [ ] **Step 1: Write the failing signal tests at the new path**

Create `tests/strategies/test_signals.py` by moving these functions from `tests/test_weekly_regime.py` **with assertions unchanged**, new imports only:

```python
from price_forecast.strategies.signals import (
    asymmetric_sma_signal,
    donchian_signal,
    dual_sma_signal,
    sma_at,
    sma_signal,
)
```

Move: `test_sma_is_in_only_when_close_is_strictly_above_sma`, `test_sma_is_out_when_close_equals_or_is_below_sma`, `test_sma_does_not_use_future_weeks`, both `test_dual_sma_*`, three `test_donchian_*`, `test_asymmetric_sma_rejects_sell_weeks_not_longer_than_buy_weeks`, `test_asymmetric_sma_is_undefined_until_the_sell_sma_is_defined`, `test_asymmetric_sma_sells_on_the_long_sma_not_the_short_while_in`, `test_asymmetric_sma_buys_on_the_short_sma_not_the_long_while_out`, `test_asymmetric_sma_does_not_use_future_weeks`, `test_asymmetric_sma_stays_in_when_close_equals_the_sell_sma`, `test_asymmetric_sma_stays_out_when_close_equals_the_buy_sma`.

Also move `test_sma_at_t_uses_closes_through_t_inclusive` from `tests/test_sma8_16_kpis.py` into this file (same assertions). Keep the `_weeks_from_closes` helper in the new file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/strategies/test_signals.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.strategies'`

- [ ] **Step 3: Create `signals.py` and delete the old copies**

`price_forecast/strategies/__init__.py`: docstring `"""Trading rules. Signals have no backtest imports."""`

`price_forecast/strategies/signals.py`:

- Copy `sma_at` **from** `sma8_16_kpis.py` (the validating version, including `ValueError`s). Do not copy `_sma_at` from `weekly_regime.py`.
- Copy `sma_signal`, `dual_sma_signal`, `asymmetric_sma_signal`, `donchian_signal` from `weekly_regime.py`.
- Inside `dual_sma_signal` and `asymmetric_sma_signal`, call `sma_at(...)` instead of `_sma_at(...)`. Those call sites already only run when the lookback is defined, so behavior stays the same.

`signals.py` imports: `date` is only needed in type hints via `tuple[date, float]` — keep `from datetime import date` and `from typing import Sequence`. No `PriceSeries` import. No backtest import.

Delete the copied functions from `weekly_regime.py` and `sma_at` from `sma8_16_kpis.py`. Point remaining callers at the new module:

```python
from price_forecast.strategies.signals import (
    asymmetric_sma_signal,
    donchian_signal,
    dual_sma_signal,
    sma_at,
    sma_signal,
)
```

Callers today: `weekly_regime.py` should no longer need signals after the copy (t+1 `backtest` takes precomputed `signals`). Archive modules currently import signals from `weekly_regime` — switch them now:

- `weekly_bakeoff.py`: `sma_signal`, `dual_sma_signal`, `donchian_signal` from `strategies.signals`; `weekly_closes` already from `data.weekly`
- `sma8_10k.py`: `sma_signal`, `sma_first_fill_date` still from weekly_regime until Task 3; `sma_signal` from signals
- `sma_asymmetric_10k.py`: `asymmetric_sma_signal` from signals

`sma8_16_kpis.py` `simulate_strategy` must import `sma_at` from `price_forecast.strategies.signals`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/strategies/test_signals.py tests/test_weekly_regime.py tests/test_sma8_16_kpis.py tests/archive -q`

Expected: PASS

Then: `.venv/bin/pytest -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast tests
git commit -m "$(cat <<'EOF'
Move SMA and Donchian signals into price_forecast.strategies.

EOF
)"
```

---

### Task 3: t+1 backtest engine; delete `weekly_regime.py`

**Files:**
- Create: `price_forecast/backtest/__init__.py`
- Create: `price_forecast/backtest/t1.py`
- Create: `tests/backtest/test_t1.py`
- Modify: archive modules that still import `price_forecast.weekly_regime`
- Modify: `tests/archive/frozen_t1_bakeoff/*.py`
- Delete: `price_forecast/weekly_regime.py`
- Delete: `tests/test_weekly_regime.py` (after remaining tests moved)

**Interfaces:**
- Consumes: `strategies.signals` (archive callers pass signal lists in). `t1.py` does not need to import signals.
- Produces:
  - `COST_BPS = 10`, `FNG_GREED_EXIT = 75`, `FNG_FEAR_ENTRY = 25`, `WEALTH_FLOOR = 0.9`, `DD_IMPROVEMENT = 0.10`, `SMA8_LOOKBACK = 8`
  - `BacktestResult`, `DollarBacktestResult`
  - `backtest(weeks, signals, *, start=None, end=None, start_in_btc=True) -> BacktestResult`
  - `dollar_backtest(weeks, signals, *, start=None, end=None, starting_dollars=10_000.0, inherit_position=False, start_in_btc=True) -> DollarBacktestResult`
  - `sma_first_fill_date(weeks, lookback: int) -> date`
  - `sma8_first_fill_date(weeks) -> date`
  - `apply_fng_overlay`, `fng_only_signal`, `align_fng_to_weeks`
  - `pass_a`, `pass_c`

- [ ] **Step 1: Write the failing t+1 tests at the new path**

Create `tests/backtest/test_t1.py` by moving every remaining test in `tests/test_weekly_regime.py` (fill, cost, F&G, pass A/C, dollar backtest, first-fill dates). New imports:

```python
from price_forecast.backtest.t1 import (
    COST_BPS,
    SMA8_LOOKBACK,
    BacktestResult,
    align_fng_to_weeks,
    apply_fng_overlay,
    backtest,
    dollar_backtest,
    fng_only_signal,
    pass_a,
    pass_c,
    sma8_first_fill_date,
    sma_first_fill_date,
)
from price_forecast.strategies.signals import (
    asymmetric_sma_signal,
    donchian_signal,
    dual_sma_signal,
    sma_signal,
)
```

Keep `_weeks_from_closes`. Do not import `weekly_closes` unless a remaining test needs it (the weekly-bar tests already left in Task 1).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backtest/test_t1.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.backtest'`

- [ ] **Step 3: Move the t+1 engine and delete `weekly_regime.py`**

`price_forecast/backtest/__init__.py`: docstring `"""Backtests. t1 is archive-only."""`

Create `price_forecast/backtest/t1.py` by moving from `weekly_regime.py`, bodies unchanged:

- Module docstring: keep the frozen t+1 rules text; retarget the live-freeze sentence to `python -m price_forecast.strategies.smagate_v1`.
- Constants: `COST_BPS`, `_COST`, `FNG_GREED_EXIT`, `FNG_FEAR_ENTRY`, `WEALTH_FLOOR`, `DD_IMPROVEMENT`, `SMA8_LOOKBACK`, `_DAYS_PER_YEAR`
- Dataclasses `BacktestResult`, `DollarBacktestResult`
- `backtest`, `dollar_backtest`, `_last_on_or_before`
- `sma_first_fill_date`, `sma8_first_fill_date`
- `apply_fng_overlay`, `fng_only_signal`, `align_fng_to_weeks`
- `pass_a`, `pass_c`

`t1.py` must not import `data.weekly` unless needed (it does not). No `PriceSeries` import.

Replace every remaining `from price_forecast.weekly_regime import` with `from price_forecast.backtest.t1 import` (plus signals/weekly already updated). Sites:

- `price_forecast/archive/frozen_t1_bakeoff/weekly_bakeoff.py`
- `price_forecast/archive/frozen_t1_bakeoff/sma8_10k.py`
- `price_forecast/archive/frozen_t1_bakeoff/sma_asymmetric_10k.py`
- `tests/archive/frozen_t1_bakeoff/test_sma8_10k.py` (`SMA8_LOOKBACK`)
- `tests/archive/frozen_t1_bakeoff/test_weekly_bakeoff.py` (`BacktestResult`)
- `tests/archive/frozen_t1_bakeoff/test_sma_asymmetric_10k.py` (`DD_IMPROVEMENT`, `sma_first_fill_date`)

Delete `price_forecast/weekly_regime.py` and `tests/test_weekly_regime.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backtest/test_t1.py tests/archive tests/data tests/strategies -q`

Expected: PASS

Then: `.venv/bin/pytest -q`

Expected: PASS

Confirm: `.venv/bin/python -c "import price_forecast.weekly_regime"` fails with `ModuleNotFoundError`.

- [ ] **Step 5: Commit**

```bash
git add price_forecast tests
git commit -m "$(cat <<'EOF'
Move the archived t+1 engine into price_forecast.backtest.t1.

EOF
)"
```

---

### Task 4: Split SMAGateV1 (`engine`, `kpis`, `reports`, CLI)

**Files:**
- Create: `price_forecast/backtest/engine.py`
- Create: `price_forecast/backtest/kpis.py`
- Create: `price_forecast/backtest/reports.py`
- Create: `price_forecast/strategies/smagate_v1.py`
- Create: `tests/backtest/test_smagate_kpis.py`
- Create: `tests/strategies/test_smagate_v1.py`
- Create: `results/sma8_16_kpis_results.md` (git mv)
- Create: `results/sma8_16_kpis_monthly.md` (git mv)
- Create: `results/sma8_16_kpis_monthly.csv` (git mv)
- Create: `tests/layout/test_import_direction.py` (or keep in `tests/strategies/test_smagate_v1.py`)
- Modify: `tests/test_remix.py` (`simulate_strategy` import)
- Delete: `price_forecast/sma8_16_kpis.py`
- Delete: `tests/test_sma8_16_kpis.py`

**Interfaces:**
- Consumes:
  - `sma_at` from `price_forecast.strategies.signals`
  - `weekly_closes` from `price_forecast.data.weekly`
  - `load_daily_closes` from `price_forecast.data.series`
- Produces:
  - `BUY_WEEKS = 8`, `SELL_WEEKS = 16`, `FILL_COST = 0.0015`, `STARTING_DOLLARS = 10_000.0`, `WHIPSAW_MAX_HOLDING_BARS = 2`
  - `RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"`
  - `simulate_strategy(weeks, *, starting_dollars: float = STARTING_DOLLARS, cost: float = FILL_COST) -> EquityPath`
  - `simulate_hodl(weeks, *, starting_dollars: float = STARTING_DOLLARS, cost: float = FILL_COST) -> EquityPath`
  - `compute_kpis(weeks, *, starting_dollars: float = STARTING_DOLLARS) -> KpiReport`
  - `format_report(report: KpiReport) -> str` and the other formatters listed below
  - `main(argv: Sequence[str] | None = None) -> None`

- [ ] **Step 1: Write failing tests at the new paths**

Create `tests/strategies/test_smagate_v1.py`:

```python
"""SMAGateV1 freeze constants and CLI wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from price_forecast.strategies.smagate_v1 import (
    BUY_WEEKS,
    FILL_COST,
    RESULTS_DIR,
    SELL_WEEKS,
    STARTING_DOLLARS,
    WHIPSAW_MAX_HOLDING_BARS,
)


def test_defaults_match_the_stated_product_rule():
    assert BUY_WEEKS == 8
    assert SELL_WEEKS == 16
    assert FILL_COST == pytest.approx(0.0015)
    assert STARTING_DOLLARS == 10_000.0
    assert WHIPSAW_MAX_HOLDING_BARS == 2


def test_results_dir_is_repo_results_folder():
    root = Path(__file__).resolve().parents[2]
    assert (root / "pyproject.toml").is_file()
    assert RESULTS_DIR == root / "results"


def test_smagate_source_does_not_import_t1_or_archive():
    text = (
        Path(__file__).resolve().parents[2]
        / "price_forecast/strategies/smagate_v1.py"
    ).read_text(encoding="utf-8")
    assert "backtest.t1" not in text
    assert "archive" not in text


def test_engine_is_imported_only_inside_main():
    source = (
        Path(__file__).resolve().parents[2]
        / "price_forecast/strategies/smagate_v1.py"
    ).read_text(encoding="utf-8")
    header, _, rest = source.partition("def main")
    assert "price_forecast.backtest" not in header
    assert "price_forecast.backtest.engine" in rest
```

Create `tests/backtest/test_smagate_kpis.py` by moving every remaining test from `tests/test_sma8_16_kpis.py` except `test_defaults_match_the_stated_product_rule` and `test_sma_at_t_uses_closes_through_t_inclusive`. New imports:

```python
from price_forecast.backtest.engine import simulate_hodl, simulate_strategy
from price_forecast.backtest.kpis import (
    cagr,
    compute_kpis,
    mar_ratio,
    max_drawdown,
    monthly_kpis,
    profit_factor,
    sortino_ratio,
)
from price_forecast.backtest.reports import (
    format_compact_monthly_table,
    format_monthly_csv,
    format_monthly_markdown,
    format_report,
)
from price_forecast.strategies.smagate_v1 import (
    BUY_WEEKS,
    FILL_COST,
    SELL_WEEKS,
    STARTING_DOLLARS,
    WHIPSAW_MAX_HOLDING_BARS,
)
```

Keep helpers and assertions unchanged. If a test called `sma_at`, it already moved in Task 2.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/strategies/test_smagate_v1.py tests/backtest/test_smagate_kpis.py -v`

Expected: FAIL with `ImportError` / `ModuleNotFoundError` for `smagate_v1` / `backtest.engine`

- [ ] **Step 3: Split `sma8_16_kpis.py` without changing logic**

`price_forecast/strategies/smagate_v1.py` contains **only**:

```python
"""SMAGateV1: weekly BTC SMA-8 in / SMA-16 out. CLI orchestrator."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from price_forecast.data.series import load_daily_closes
from price_forecast.data.weekly import weekly_closes

BUY_WEEKS = 8
SELL_WEEKS = 16
FILL_COST = 0.0015
STARTING_DOLLARS = 10_000.0
WHIPSAW_MAX_HOLDING_BARS = 2
RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"
```

Then `main()` **as a function whose first lines import backtest**:

```python
def main(argv: Sequence[str] | None = None) -> None:
    from price_forecast.backtest.engine import simulate_hodl, simulate_strategy
    from price_forecast.backtest.kpis import (
        CHAPTER_SPECS,
        chapter_window,
        compute_kpis,
    )
    from price_forecast.backtest.kpis import _monthly_from_paths
    from price_forecast.backtest.reports import (
        format_compact_monthly_table,
        format_highlighted_chapters,
        format_monthly_csv,
        format_monthly_markdown,
        format_report,
    )
    # argparse + load + write: same as current main(), except:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "sma8_16_kpis_results.md"
    monthly_md_path = RESULTS_DIR / "sma8_16_kpis_monthly.md"
    monthly_csv_path = RESULTS_DIR / "sma8_16_kpis_monthly.csv"
```

If `_monthly_from_paths` is private, either export `monthly_rows_from_paths` as a public alias in `kpis.py` or keep the name and import it in `main()` as today. Prefer keeping the name `_monthly_from_paths` and importing it in `main()` (same privacy as now).

Copy argparse flags unchanged (`--starting-dollars`, default `STARTING_DOLLARS`).

`if __name__ == "__main__": main()` at the bottom.

**`engine.py`:** move `Fill`, `EquityPath`, `first_comparable_index`, `_require_sma16`, `simulate_strategy`, `simulate_hodl` from `sma8_16_kpis.py` unchanged. Imports:

```python
from price_forecast.strategies.signals import sma_at
from price_forecast.strategies.smagate_v1 import (
    BUY_WEEKS,
    FILL_COST,
    SELL_WEEKS,
    STARTING_DOLLARS,
    WHIPSAW_MAX_HOLDING_BARS,
)
```

`WHIPSAW_MAX_HOLDING_BARS` is used when counting whipsaws inside `simulate_strategy` — keep that use in engine.

**`kpis.py`:** move `SideKpis`, `KpiReport`, `MonthKpis`, `ChapterWindow`, `HIGHLIGHT_MONTH_RANGES`, `CHAPTER_SPECS`, `_MONTHLY_CSV_COLUMNS` (CSV columns may live in reports if only formatters use them — if `format_monthly_csv` is the only user, put `_MONTHLY_CSV_COLUMNS` in `reports.py`). Move `max_drawdown`, `sortino_ratio`, `cagr`, `mar_ratio`, `profit_factor`, `_weekly_returns`, `_win_rate`, `compute_kpis`, `year_month`, `_ym_tuple`, `_is_highlight_month`, `_month_groups`, `_completed_stats`, `_monthly_from_paths`, `monthly_kpis`, `chapter_window`, `_rows_in_range`. Import `simulate_strategy` / `simulate_hodl` from `engine` and constants from `smagate_v1`.

**`reports.py`:** move `format_monthly_csv`, `format_compact_monthly_table`, `format_chapter_window`, `format_highlighted_chapters`, `format_monthly_markdown`, `format_report`, and every `_fmt_*`, `_csv_cell`, `_md_table`, `_row` helper those functions need. Update the “How to re-run” strings **inside `format_report`** from `python -m price_forecast.sma8_16_kpis` to `python -m price_forecast.strategies.smagate_v1`. That is an allowed string change (entry point renamed). Leave KPI numbers and table layout alone.

```bash
mkdir -p results
git mv price_forecast/sma8_16_kpis_results.md results/sma8_16_kpis_results.md
git mv price_forecast/sma8_16_kpis_monthly.md results/sma8_16_kpis_monthly.md
git mv price_forecast/sma8_16_kpis_monthly.csv results/sma8_16_kpis_monthly.csv
```

Do not regenerate those files in this task (would need Coinbase). Path strings inside the committed markdown that name the old module can wait for Task 8 if they are historical quotes; the formatter’s *next* run will use the new how-to-rerun lines.

Update `tests/test_remix.py`:

```python
from price_forecast.backtest.engine import simulate_strategy
from price_forecast.data.series import PriceSeries
from price_forecast.data.weekly import weekly_closes
from price_forecast.remix import ...  # still old path until Task 6
```

Delete `price_forecast/sma8_16_kpis.py` and `tests/test_sma8_16_kpis.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/strategies/test_smagate_v1.py tests/backtest/test_smagate_kpis.py tests/test_remix.py -q`

Expected: PASS, including `test_engine_is_imported_only_inside_main` and `test_results_dir_is_repo_results_folder`.

Then: `.venv/bin/pytest -q`

Expected: PASS

Confirm: `.venv/bin/python -c "import price_forecast.sma8_16_kpis"` fails.

Confirm: `.venv/bin/python -c "import price_forecast.strategies.smagate_v1 as m; import price_forecast.backtest.t1"` — `smagate_v1` import alone must not load `t1`. Check with:

```bash
.venv/bin/python -c "import sys; import price_forecast.strategies.smagate_v1; assert 'price_forecast.backtest.t1' not in sys.modules"
```

Expected: exit 0

- [ ] **Step 5: Commit**

```bash
git add price_forecast tests results
git commit -m "$(cat <<'EOF'
Split SMAGateV1 into strategy CLI, engine, KPIs, and reports.

EOF
)"
```

---

### Task 5: Forecast package and public `__init__`

**Files:**
- Create: `price_forecast/forecast/__init__.py`
- Modify by git mv: `harness.py`, `predictors.py`, `chronos.py`, `bakeoff.py` into `price_forecast/forecast/`
- Modify: `price_forecast/__init__.py`
- Modify: `price_forecast/forecast/bakeoff.py` (imports + `RESULTS_DIR`)
- Create: `results/bakeoff_results.md` (git mv of `price_forecast/bakeoff_results.md`)
- Create: `tests/forecast/test_harness.py`, `test_arima_garch.py`, `test_chronos.py` (git mv)

**Interfaces:**
- Consumes: `price_forecast.data.series.PriceSeries`, `load_daily_closes`, `LeakageError`
- Produces (still re-exported from `price_forecast`):
  - `HORIZONS`, `WINDOWS`, `HorizonResult`, `evaluate`
  - `Forecast`, `Predictor`, `LastValuePredictor`, `ZeroReturnPredictor`, `ArimaGarchPredictor`
  - `ChronosPredictor`
  - `LeakageError`, `load_daily_closes`, `synthetic_daily`

- [ ] **Step 1: Point forecast tests at the new modules (they should still pass via `__init__` until you break it)**

Move tests:

```bash
mkdir -p tests/forecast
git mv tests/test_harness.py tests/forecast/test_harness.py
git mv tests/test_arima_garch.py tests/forecast/test_arima_garch.py
git mv tests/test_chronos.py tests/forecast/test_chronos.py
```

Add `tests/forecast/test_public_api.py`:

```python
"""price_forecast still exports the walk-forward scoreboard."""

from price_forecast import (
    HORIZONS,
    WINDOWS,
    ArimaGarchPredictor,
    ChronosPredictor,
    Forecast,
    LastValuePredictor,
    LeakageError,
    ZeroReturnPredictor,
    evaluate,
    load_daily_closes,
    synthetic_daily,
)
from price_forecast.forecast.bakeoff import RESULTS_DIR
from pathlib import Path


def test_package_exports_forecast_scoreboard():
    assert HORIZONS
    assert WINDOWS
    assert callable(evaluate)
    assert issubclass(LeakageError, Exception)


def test_bakeoff_results_dir_is_repo_results():
    root = Path(__file__).resolve().parents[2]
    assert RESULTS_DIR == root / "results"
```

Keep existing harness/ARIMA/Chronos tests importing `from price_forecast import ...`. Change `from price_forecast.series import PriceSeries` in those files to `from price_forecast.data.series import PriceSeries` if Task 1 did not already (it did).

- [ ] **Step 2: Run the new public-api test before the move**

Run: `.venv/bin/pytest tests/forecast/test_public_api.py -v`

Expected: FAIL (`price_forecast.forecast.bakeoff` missing and/or `RESULTS_DIR` missing)

- [ ] **Step 3: Move forecast modules**

```bash
mkdir -p price_forecast/forecast
git mv price_forecast/harness.py price_forecast/forecast/harness.py
git mv price_forecast/predictors.py price_forecast/forecast/predictors.py
git mv price_forecast/chronos.py price_forecast/forecast/chronos.py
git mv price_forecast/bakeoff.py price_forecast/forecast/bakeoff.py
git mv price_forecast/bakeoff_results.md results/bakeoff_results.md
```

`price_forecast/forecast/__init__.py`: docstring `"""Walk-forward scoreboard. Not SMAGate."""`

Rewrite internal imports to:

```python
from price_forecast.forecast.harness import ...
from price_forecast.forecast.predictors import ...
from price_forecast.forecast.chronos import ...
from price_forecast.data.series import ...
```

`price_forecast/__init__.py` becomes:

```python
"""Walk-forward scoreboard for short-horizon Bitcoin price forecasts.

Not the README ensemble. Not SMAGateV1.
"""

from price_forecast.forecast.harness import HORIZONS, WINDOWS, HorizonResult, evaluate
from price_forecast.forecast.chronos import ChronosPredictor
from price_forecast.forecast.predictors import (
    ArimaGarchPredictor,
    Forecast,
    LastValuePredictor,
    Predictor,
    ZeroReturnPredictor,
)
from price_forecast.data.series import LeakageError, load_daily_closes, synthetic_daily

__all__ = [
    "HORIZONS",
    "WINDOWS",
    "ArimaGarchPredictor",
    "ChronosPredictor",
    "Forecast",
    "HorizonResult",
    "LastValuePredictor",
    "LeakageError",
    "Predictor",
    "ZeroReturnPredictor",
    "evaluate",
    "load_daily_closes",
    "synthetic_daily",
]
```

In `bakeoff.py` add:

```python
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"
```

Update the module docstring usage line to `python -m price_forecast.forecast.bakeoff`. `bakeoff.py` today prints the report and does not write `bakeoff_results.md`; do not add a write unless one already exists. Only expose `RESULTS_DIR` so the destination for the committed scoreboard is obvious and tested.

Forecast must not import `strategies` or `backtest`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/forecast -q`

Expected: PASS

Then: `.venv/bin/pytest -q`

Expected: PASS

Confirm: `.venv/bin/python -c "import price_forecast.harness"` fails.

- [ ] **Step 5: Commit**

```bash
git add price_forecast tests results
git commit -m "$(cat <<'EOF'
Move the walk-forward forecast stack into price_forecast.forecast.

EOF
)"
```

---

### Task 6: Remix package

**Files:**
- Create: `price_forecast/remix/__init__.py`
- Create: `price_forecast/remix/remix.py` (git mv of `price_forecast/remix.py`)
- Create: `tests/remix/test_remix.py` (git mv)

**Interfaces:**
- Consumes: `PriceSeries`, `load_daily_closes` from `data.series`; `weekly_closes` from `data.weekly`; `simulate_strategy` from `backtest.engine` (sanity-check only)
- Produces: `MEAN_BLOCK_BARS`, `remix_daily_closes`, `remix_sanity`, `stylized_facts`, `main`

- [ ] **Step 1: Move the remix test and point it at the new module**

```bash
mkdir -p tests/remix price_forecast/remix
git mv tests/test_remix.py tests/remix/test_remix.py
```

Change imports in that test to:

```python
from price_forecast.remix.remix import (
    MEAN_BLOCK_BARS,
    main,
    remix_daily_closes,
    remix_sanity,
    stylized_facts,
)
from price_forecast.data.series import PriceSeries
from price_forecast.backtest.engine import simulate_strategy
from price_forecast.data.weekly import weekly_closes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/remix/test_remix.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.remix.remix'` (empty package) or import error from the old file if you have not moved it yet.

- [ ] **Step 3: Move `remix.py`**

```bash
git mv price_forecast/remix.py price_forecast/remix/remix.py
```

If `git mv` cannot move a file onto a directory of the same name, sequence it as:

```bash
git mv price_forecast/remix.py /tmp/prism-remix.py
mkdir -p price_forecast/remix
git mv /tmp/prism-remix.py price_forecast/remix/remix.py
```

`price_forecast/remix/__init__.py`: docstring `"""Stationary-bootstrap path factory."""`

Update imports inside `remix.py` to `data.series`, `data.weekly`, `backtest.engine`. Docstring usage: `python -m price_forecast.remix.remix`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/remix/test_remix.py -q`

Expected: PASS

Then: `.venv/bin/pytest -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast tests
git commit -m "$(cat <<'EOF'
Move the remix path factory into price_forecast.remix.

EOF
)"
```

---

### Task 7: Top-level `archive/` package

**Files:**
- Create: `archive/__init__.py`
- Create: `archive/frozen_t1_bakeoff/` (git mv of `price_forecast/archive/frozen_t1_bakeoff/`)
- Modify: `tests/archive/frozen_t1_bakeoff/*.py` imports
- Modify: frozen module docstrings / `python -m` lines
- Delete: `price_forecast/archive/`

**Interfaces:**
- Consumes: `data.series`, `data.weekly`, `strategies.signals`, `backtest.t1`
- Produces: `archive.frozen_t1_bakeoff.{weekly_bakeoff,sma8_10k,sma_asymmetric_10k,fng}`

- [ ] **Step 1: Write a collection test that will fail until the package exists**

Add `tests/archive/test_archive_package.py`:

```python
"""Frozen t+1 bakeoff stays importable and collected after the move."""

from pathlib import Path


def test_archive_is_not_inside_price_forecast():
    root = Path(__file__).resolve().parents[2]
    assert not (root / "price_forecast/archive").exists()
    assert (root / "archive/frozen_t1_bakeoff/weekly_bakeoff.py").is_file()


def test_frozen_weekly_bakeoff_imports():
    from archive.frozen_t1_bakeoff.weekly_bakeoff import WINDOWS

    assert WINDOWS
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/archive/test_archive_package.py -v`

Expected: FAIL (`price_forecast/archive` still exists and/or `archive.frozen_t1_bakeoff` missing)

- [ ] **Step 3: Move the frozen package**

```bash
mkdir -p archive
git mv price_forecast/archive/frozen_t1_bakeoff archive/frozen_t1_bakeoff
# remove leftover price_forecast/archive/__init__.py
```

Write `archive/__init__.py`:

```python
"""Archived experiments. Do not use for new work."""
```

Keep `archive/frozen_t1_bakeoff/__init__.py`. Change its docstring live-freeze line to `python -m price_forecast.strategies.smagate_v1`. Historical re-run lines become:

```
python -m archive.frozen_t1_bakeoff.weekly_bakeoff
```

Rewrite every `from price_forecast.archive.frozen_t1_bakeoff` to `from archive.frozen_t1_bakeoff` in the archive package and in `tests/archive/frozen_t1_bakeoff/`. Data/signals/t1 imports should already be new from Tasks 1–3; keep them.

Do not add `archive*` to `pyproject.toml` setuptools include. Leave `pythonpath = ["."]` as-is.

Result markdown files stay beside the frozen scripts (`archive/frozen_t1_bakeoff/*_results.md`), not in `results/`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/archive -q`

Expected: PASS, including `test_archive_is_not_inside_price_forecast`

Then: `.venv/bin/pytest -q --collect-only`

Expected: collected files include `tests/archive/frozen_t1_bakeoff/test_sma8_10k.py`, `test_fng.py`, `test_weekly_bakeoff.py`, `test_sma_asymmetric_10k.py`

Then: `.venv/bin/pytest -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add archive price_forecast tests pyproject.toml
git commit -m "$(cat <<'EOF'
Move the frozen t+1 bakeoff to the top-level archive package.

EOF
)"
```

---

### Task 8: Docs, README, leftover grep

**Files:**
- Create: `docs/architecture.md` (git mv of current `README.md`)
- Modify: `README.md` (replace with the short map below)
- Modify: `docs/research/2026-09-17-sma-rule-debate.md`
- Modify: `docs/research/2026-09-17-btc-protection-after-point-forecast.md`
- Modify: `docs/research/2026-09-20-synthetic-btc-paths.md`
- Modify: archive README / result markdown path strings that name deleted modules
- Modify: `pyproject.toml` only if a comment still names `price_forecast.sma8_16_kpis` (testpaths comment about `tests/archive/frozen_t1_bakeoff` stays)
- Create: `tests/layout/test_no_old_modules.py`

**Interfaces:**
- Consumes: layout from earlier tasks
- Produces: human-readable map; no Python API

- [ ] **Step 1: Write the leftover-path test**

Create `tests/layout/test_no_old_modules.py`:

```python
"""Old flat modules must be gone from live code, tests, and research notes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = (
    "price_forecast.weekly_regime",
    "price_forecast.sma8_16_kpis",
    "price_forecast.series",
    "price_forecast.harness",
    "python -m price_forecast.bakeoff",
    "python -m price_forecast.remix\n",
    "python -m price_forecast.sma8_16_kpis",
)
SCAN_GLOBS = (
    "price_forecast/**/*.py",
    "tests/**/*.py",
    "archive/**/*.py",
    "docs/research/*.md",
    "README.md",
    "pyproject.toml",
)
# This spec/plan may name old paths on purpose.
SKIP_PARTS = {"superpowers"}


def test_forbidden_import_strings_are_gone():
    hits: list[str] = []
    for glob in SCAN_GLOBS:
        for path in ROOT.glob(glob):
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN:
                if needle in text:
                    hits.append(f"{path.relative_to(ROOT)}: {needle}")
    assert hits == []
```

`price_forecast.series` as a substring can false-positive on `price_forecast.data.series`. Use needles that cannot match the new paths: `from price_forecast.series import` and `import price_forecast.series` instead of `price_forecast.series`.

Replace the `FORBIDDEN` tuple with:

```python
FORBIDDEN = (
    "from price_forecast.weekly_regime import",
    "from price_forecast.sma8_16_kpis import",
    "from price_forecast.series import",
    "from price_forecast.harness import",
    "from price_forecast.predictors import",
    "from price_forecast.chronos import",
    "from price_forecast.bakeoff import",
    "from price_forecast.remix import",
    "from price_forecast.archive",
    "python -m price_forecast.sma8_16_kpis",
    "python -m price_forecast.bakeoff",
    "python -m price_forecast.remix\n",
    "python -m price_forecast.remix ",
)
```

- [ ] **Step 2: Run it to verify it fails on remaining docs**

Run: `.venv/bin/pytest tests/layout/test_no_old_modules.py -v`

Expected: FAIL listing research notes and/or archive markdown still using old imports. If the test already passes, still do the README/docs moves in Step 3.

- [ ] **Step 3: Move the blueprint and write the short README**

```bash
git mv README.md docs/architecture.md
```

Write `README.md`:

```markdown
# prism

Walk-forward Bitcoin forecast scoreboard plus the frozen weekly SMAGateV1 rule.

Not investment advice.

## Layout

- `price_forecast/data/` — daily `PriceSeries`, Coinbase loader, Sunday weekly bars
- `price_forecast/forecast/` — walk-forward harness, predictors, Chronos, bakeoff CLI
- `price_forecast/strategies/` — SMA signals and SMAGateV1
- `price_forecast/backtest/` — SMAGate simulator/KPIs and the archived t+1 engine
- `price_forecast/remix/` — stationary-bootstrap path factory
- `results/` — live scoreboards (markdown/CSV)
- `docs/` — architecture blueprint and research notes
- `archive/frozen_t1_bakeoff/` — frozen t+1 SMA bakeoff (do not use for new work)
- `tests/` — mirrors the live packages

## Run

```
python -m price_forecast.strategies.smagate_v1
python -m price_forecast.forecast.bakeoff
python -m price_forecast.remix.remix
```

Architecture blueprint: `docs/architecture.md`.
```

Update research notes so path strings match the new tree. Keep historical *numbers*. Replace module paths:

- `price_forecast/weekly_regime.py` → `price_forecast/data/weekly.py` / `price_forecast/strategies/signals.py` / `price_forecast/backtest/t1.py` according to which symbol the sentence names
- `price_forecast/sma8_16_kpis.py` → `price_forecast/strategies/smagate_v1.py` (and engine/kpis when the sentence is about simulation or KPIs)
- `python -m price_forecast.sma8_16_kpis` → `python -m price_forecast.strategies.smagate_v1`
- `python -m price_forecast.remix` → `python -m price_forecast.remix.remix`
- `price_forecast/series.py` → `price_forecast/data/series.py`
- `price_forecast/harness.py` → `price_forecast/forecast/harness.py`
- `price_forecast/bakeoff.py` → `price_forecast/forecast/bakeoff.py`
- `price_forecast/bakeoff_results.md` → `results/bakeoff_results.md` (fix relative links)
- `price_forecast/sma8_16_kpis_results.md` → `results/sma8_16_kpis_results.md`
- `price_forecast/archive/frozen_t1_bakeoff/` → `archive/frozen_t1_bakeoff/`

In `docs/research/2026-09-17-btc-protection-after-point-forecast.md` the link `../../price_forecast/bakeoff_results.md` becomes `../../results/bakeoff_results.md`.

In archive `README.md` and `*_results.md`, update “live freeze” commands and `weekly_regime.py` mentions. Frozen *numbers* stay.

Do not edit `docs/superpowers/specs/2026-09-26-repo-layout-design.md` to erase old names; that spec is allowed to name what was deleted.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/layout/test_no_old_modules.py -q`

Expected: PASS

Then: `.venv/bin/pytest -q`

Expected: PASS

Then grep (must print nothing):

```bash
git grep -n "from price_forecast.weekly_regime import" -- ':!docs/superpowers'
git grep -n "from price_forecast.sma8_16_kpis import" -- ':!docs/superpowers'
git grep -n "python -m price_forecast.sma8_16_kpis" -- ':!docs/superpowers'
```

Confirm the three modules exist as runnables (import only; do not download Coinbase in CI unless tests already do):

```bash
.venv/bin/python -c "import price_forecast.strategies.smagate_v1 as m; print(m.RESULTS_DIR)"
.venv/bin/python -c "import price_forecast.forecast.bakeoff as m; print(m.RESULTS_DIR)"
.venv/bin/python -c "import price_forecast.remix.remix"
```

Expected: prints `.../results` twice; remix import succeeds.

- [ ] **Step 5: Commit**

```bash
git add README.md docs archive tests price_forecast results pyproject.toml
git commit -m "$(cat <<'EOF'
Point docs and the root README at the new folder map.

EOF
)"
```

---

## Self-review (author)

**Spec coverage**
- Target tree → Tasks 1–8
- `weekly_regime.py` split → Tasks 1–3
- `sma8_16_kpis.py` split → Task 4
- Whole-file moves (series, forecast, remix, archive, results, README) → Tasks 1, 5, 6, 7, 8
- Dependency direction + CLI exception → Task 4 tests, Task 8 grep test
- Entry points renamed → Tasks 4, 5, 6, 8
- No shims → each task deletes the old module; Task 8 forbids old import strings
- `LeakageError` stays on `PriceSeries` → Task 1 move, Task 5 `__init__` re-export
- Tests mirror packages → `tests/data|forecast|strategies|backtest|remix|archive|layout`
- Archive not in setuptools → Task 7
- Done-when pytest / python -m / git grep → Tasks 4, 5, 7, 8

**Placeholders:** none. `_monthly_from_paths` kept as the existing private name, imported from `main()`.

**Types:** `weekly_closes` → `list[tuple[date, float]]` in Task 1 and later tasks. `simulate_strategy` signature unchanged. `RESULTS_DIR` is `Path`.
