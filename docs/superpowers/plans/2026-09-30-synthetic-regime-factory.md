# Synthetic Regime Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move remix under `price_forecast/datafactory/` and add a command that writes seeded synthetic BTC-USD candle files from six regimes fit on the real tape.

**Architecture:** `label.py` assigns each source row one of six names. `fit.py` stores a Student-t, run lengths, successors, and bar shapes per name. `paths.py` builds candle paths and an unwritten one-regime control from those records. `report.py` prints the comparison. `__main__.py` writes files only after every path has been built in memory.

**Tech Stack:** Python 3, numpy, scipy.stats.t, the existing `Candle` / `write_candles` helpers, pytest.

**Spec:** `docs/superpowers/specs/2026-09-30-synthetic-regime-factory-design.md`

## Global Constraints

- Trend window default is 365 bars. Band is ±0.25. Volatility window default is 30 daily log-returns. The CLI does not expose flags for these.
- Bull is a simple return strictly above +0.25. Bear is strictly below −0.25. The endpoints ±0.25 are sideways.
- Quiet is trailing realized volatility at or below `numpy.median` of the labeled rows. Above that median is volatile.
- Fit raises `ValueError` and writes nothing when any regime has fewer than 30 labeled rows, fewer than 2 runs, a blank volume, sample volatility 0, a non-finite Student-t parameter, or `df <= 2`.
- Regime names are exactly `bull_quiet`, `bull_volatile`, `bear_quiet`, `bear_volatile`, `sideways_quiet`, `sideways_volatile`.
- Path `k` uses `SeedSequence([seed, k, 0])`. The control uses `SeedSequence([seed, k, 1])`. Control files are not written.
- Row 0 of each path is the source's first candle. Its sidecar cell is the starting regime and does not change that candle.
- Output files are `data/synthetic/btc-usd-daily-seed{seed}-path{index}.csv`, the PNG `write_candles` adds beside it, and `data/synthetic/btc-usd-daily-seed{seed}-path{index}-regimes.csv`.
- Remix's output stays `data/remix/`. There is no compatibility shim at `price_forecast.remix`.
- Do not score SMAGateV1, CrashGateV1, or any other rule. Do not change `synthetic_daily`.

## Review Focus

- A labeled row with a blank `volume` — the fit names that regime and the command writes no file (Task 3 and Task 6).
- `scipy.stats.t.fit` returning `df <= 2` — the fit names that regime and writes nothing (Task 3).
- A non-finite simulated return — the command raises before creating any file from that invocation, including an earlier path already built in memory (Task 4 and Task 6).
- A drawn chapter longer than the rows left — the candle file still has one row per source row, and the tail keeps that chapter's regime (Task 4).
- `--n-paths 2` after `--n-paths 1` with the same seed — path 0's candle CSV and sidecar are byte-for-byte the same (Task 6).

---

### Task 1: Move remix under datafactory

**Files:**
- Create: `price_forecast/datafactory/__init__.py`
- Create: `price_forecast/datafactory/remix.py` (move of `price_forecast/remix/remix.py`)
- Create: `tests/datafactory/__init__.py`
- Create: `tests/datafactory/test_remix.py` (move)
- Create: `tests/datafactory/test_remix_csv.py` (move)
- Modify: `README.md`
- Modify: `docs/research/2026-09-20-synthetic-btc-paths.md`
- Modify: `tests/layout/test_no_old_modules.py`
- Delete: `price_forecast/remix/`
- Delete: `tests/remix/`
- Test: `tests/datafactory/test_remix.py`

**Interfaces:**
- Consumes: existing remix functions `main`, `remix_daily_closes`, `remix_candle_paths`, `remix_sanity`, `stylized_facts`, `MEAN_BLOCK_BARS`.
- Produces: `from price_forecast.datafactory.remix import main, remix_daily_closes, remix_candle_paths, remix_sanity, stylized_facts, MEAN_BLOCK_BARS`. Command: `python -m price_forecast.datafactory.remix`. `REMIX_DIR` stays imported from `price_forecast.data.candles`.

- [ ] **Step 1: Write the failing test**

Move the remix tests first so they import the new module. In `tests/datafactory/test_remix.py` and `tests/datafactory/test_remix_csv.py`, replace every `price_forecast.remix.remix` with `price_forecast.datafactory.remix`. That includes the import lines and both `monkeypatch.setattr("price_forecast.remix.remix.REMIX_DIR", ...)` strings.

Create empty `tests/datafactory/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/datafactory/test_remix.py tests/datafactory/test_remix_csv.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.datafactory'`

- [ ] **Step 3: Write minimal implementation**

```bash
mkdir -p price_forecast/datafactory
git mv price_forecast/remix/remix.py price_forecast/datafactory/remix.py
rm price_forecast/remix/__init__.py
rmdir price_forecast/remix
rm -rf tests/remix
```

`price_forecast/datafactory/__init__.py`:

```python
"""History factories: stationary-bootstrap remix and synthetic regime paths."""
```

In `price_forecast/datafactory/remix.py`, change the usage line in the module docstring from `python -m price_forecast.remix.remix` to `python -m price_forecast.datafactory.remix`. Leave the rest of the file, including `REMIX_DIR` and `data/remix` output, as it is.

`README.md` layout bullet and command:

```markdown
- `price_forecast/datafactory/` — stationary-bootstrap path factory
```

```markdown
python -m price_forecast.datafactory.remix
```

In `docs/research/2026-09-20-synthetic-btc-paths.md`, replace the code line's command and path with `python -m price_forecast.datafactory.remix` and `price_forecast/datafactory/remix.py`. In the numbered step that names `price_forecast/remix/remix.py`, name `price_forecast/datafactory/remix.py` instead. Do not rewrite the note's argument.

Add these two strings to `FORBIDDEN` in `tests/layout/test_no_old_modules.py`, next to the existing remix entries:

```python
"from price_forecast.remix.remix import",
"python -m price_forecast.remix.remix",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/datafactory/test_remix.py tests/datafactory/test_remix_csv.py tests/layout/test_no_old_modules.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/datafactory tests/datafactory README.md docs/research/2026-09-20-synthetic-btc-paths.md tests/layout/test_no_old_modules.py
git add -u price_forecast/remix tests/remix
git commit -m "$(cat <<'EOF'
Move the remix factory under datafactory.

EOF
)"
```

---

### Task 2: Label each row

**Files:**
- Create: `price_forecast/datafactory/synthetic/__init__.py`
- Create: `price_forecast/datafactory/synthetic/label.py`
- Create: `tests/datafactory/fixture.py`
- Create: `tests/datafactory/test_label.py`
- Test: `tests/datafactory/test_label.py`

**Interfaces:**
- Consumes: `Candle` from `price_forecast.data.candles`.
- Produces:

```python
TREND_BARS = 365
VOL_BARS = 30
TREND_BAND = 0.25
REGIME_NAMES = (
    "bull_quiet",
    "bull_volatile",
    "bear_quiet",
    "bear_volatile",
    "sideways_quiet",
    "sideways_volatile",
)

@dataclass(frozen=True)
class LabelResult:
    labels: tuple[str | None, ...]  # one per candle; None on the unlabeled prefix
    vol_median: float

def label_candles(
    candles: Sequence[Candle],
    *,
    trend_bars: int = TREND_BARS,
    vol_bars: int = VOL_BARS,
    trend_band: float = TREND_BAND,
) -> LabelResult:
    ...
```

A row `t` is labeled only when `t >= trend_bars` and `t >= vol_bars`. `tests/datafactory/fixture.py` produces `balanced_tape()` for later tasks: trend window 4, vol window 2, two 40-row blocks of each regime.

- [ ] **Step 1: Write the failing test**

`tests/datafactory/fixture.py`:

```python
"""Candles whose six regimes each have at least 30 rows and 2 runs."""

from __future__ import annotations

import math
from datetime import date, timedelta

from price_forecast.data.candles import Candle

BLOCK_ORDER = (
    "bull_quiet",
    "bear_quiet",
    "bull_volatile",
    "bear_volatile",
    "sideways_quiet",
    "sideways_volatile",
)
QUIET_SHOCKS = (0.002, -0.001, -0.002, 0.001)
LOUD_SHOCKS = (0.12, -0.06, -0.12, 0.06)
MU = {"bull": 0.08, "bear": -0.09, "sideways": 0.0}


def candles_from_closes(closes: list[float], *, volume: float | None = 1.0) -> tuple[Candle, ...]:
    start = date(2020, 1, 1)
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            Candle(
                start + timedelta(days=index),
                close * 0.99,
                close * 1.01,
                close * 0.995,
                close,
                volume,
            )
        )
    return tuple(rows)


def balanced_tape() -> tuple[Candle, ...]:
    """40-row blocks, each regime twice, after a 4-row prefix."""
    prices = [100.0]
    for index in range(4):
        shock = 0.001 if index % 2 == 0 else -0.001
        prices.append(prices[-1] * math.exp(shock))
    for name in BLOCK_ORDER + BLOCK_ORDER:
        trend, noise = name.split("_")
        shocks = QUIET_SHOCKS if noise == "quiet" else LOUD_SHOCKS
        mu = MU[trend]
        for index in range(40):
            prices.append(prices[-1] * math.exp(mu + shocks[index % 4]))
    return candles_from_closes(prices)
```

`tests/datafactory/test_label.py`:

```python
from __future__ import annotations

import pytest

from price_forecast.datafactory.synthetic.label import (
    TREND_BAND,
    TREND_BARS,
    VOL_BARS,
    label_candles,
)
from tests.datafactory.fixture import candles_from_closes


def test_defaults_are_the_spec_windows():
    assert TREND_BARS == 365
    assert VOL_BARS == 30
    assert TREND_BAND == 0.25


def test_prefix_is_unlabeled_and_cutoffs_name_the_trend():
    bull = label_candles(candles_from_closes([100, 100, 100, 100, 130]), trend_bars=4, vol_bars=2)
    bear = label_candles(candles_from_closes([100, 100, 100, 100, 70]), trend_bars=4, vol_bars=2)
    inside = label_candles(candles_from_closes([100, 100, 100, 100, 110]), trend_bars=4, vol_bars=2)
    up_edge = label_candles(candles_from_closes([100, 100, 100, 100, 125]), trend_bars=4, vol_bars=2)
    down_edge = label_candles(candles_from_closes([100, 100, 100, 100, 75]), trend_bars=4, vol_bars=2)

    assert bull.labels == (None, None, None, None, "bull_quiet")
    assert bear.labels == (None, None, None, None, "bear_quiet")
    assert inside.labels[-1] == "sideways_quiet"
    assert up_edge.labels[-1] == "sideways_quiet"
    assert down_edge.labels[-1] == "sideways_quiet"


def test_row_at_the_vol_median_is_quiet_and_a_wilder_row_is_volatile():
    labeled = label_candles(
        candles_from_closes([100, 100, 100, 100, 130, 80]),
        trend_bars=4,
        vol_bars=2,
    )
    assert labeled.labels[4] == "bull_quiet"
    assert labeled.labels[5] == "sideways_volatile"
    assert labeled.vol_median == pytest.approx(0.35717248497513854)


def test_equal_volatility_is_quiet():
    closes = [100.0]
    for _ in range(5):
        closes.append(closes[-1] * 1.1)
    labeled = label_candles(candles_from_closes(closes), trend_bars=4, vol_bars=2)
    assert labeled.labels[4] == "bull_quiet"
    assert labeled.labels[5] == "bull_quiet"


def test_no_labeled_row_raises():
    with pytest.raises(ValueError, match="no labeled rows"):
        label_candles(candles_from_closes([100, 101, 102]), trend_bars=4, vol_bars=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/datafactory/test_label.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.datafactory.synthetic'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/datafactory/synthetic/__init__.py`:

```python
"""Synthetic regime candle factory."""
```

`price_forecast/datafactory/synthetic/label.py`:

```python
"""Label each candle row as one of the six trend-by-volatility regimes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from price_forecast.data.candles import Candle

TREND_BARS = 365
VOL_BARS = 30
TREND_BAND = 0.25
REGIME_NAMES = (
    "bull_quiet",
    "bull_volatile",
    "bear_quiet",
    "bear_volatile",
    "sideways_quiet",
    "sideways_volatile",
)


@dataclass(frozen=True)
class LabelResult:
    labels: tuple[str | None, ...]
    vol_median: float


def label_candles(
    candles: Sequence[Candle],
    *,
    trend_bars: int = TREND_BARS,
    vol_bars: int = VOL_BARS,
    trend_band: float = TREND_BAND,
) -> LabelResult:
    if trend_bars < 1:
        raise ValueError("trend_bars must be at least 1")
    if vol_bars < 2:
        raise ValueError("vol_bars must be at least 2")
    if trend_band < 0:
        raise ValueError("trend_band must be non-negative")
    closes = [candle.close for candle in candles]
    first = max(trend_bars, vol_bars)
    vols: list[float] = []
    pending: list[tuple[int, str, float]] = []
    for index in range(first, len(closes)):
        simple = closes[index] / closes[index - trend_bars] - 1.0
        if simple > trend_band:
            trend = "bull"
        elif simple < -trend_band:
            trend = "bear"
        else:
            trend = "sideways"
        window = [
            math.log(closes[pos] / closes[pos - 1])
            for pos in range(index - vol_bars + 1, index + 1)
        ]
        vol = float(np.std(window, ddof=1))
        pending.append((index, trend, vol))
        vols.append(vol)
    if not pending:
        raise ValueError("no labeled rows")
    median = float(np.median(vols))
    labels: list[str | None] = [None] * len(closes)
    for index, trend, vol in pending:
        noise = "quiet" if vol <= median else "volatile"
        labels[index] = f"{trend}_{noise}"
    return LabelResult(tuple(labels), median)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/datafactory/test_label.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/datafactory/synthetic/__init__.py price_forecast/datafactory/synthetic/label.py tests/datafactory/fixture.py tests/datafactory/test_label.py
git commit -m "$(cat <<'EOF'
Label daily bars into six trend and volatility regimes.

EOF
)"
```

---

### Task 3: Fit regimes

**Files:**
- Create: `price_forecast/datafactory/synthetic/fit.py`
- Create: `tests/datafactory/test_fit.py`
- Test: `tests/datafactory/test_fit.py`

**Interfaces:**
- Consumes: `LabelResult`, `REGIME_NAMES`, `label_candles` from `price_forecast.datafactory.synthetic.label`. `balanced_tape` and `candles_from_closes` from `tests.datafactory.fixture`.
- Produces:

```python
MIN_ROWS = 30
MIN_RUNS = 2

@dataclass(frozen=True)
class BarShape:
    open_ratio: float
    high_ratio: float
    low_ratio: float
    volume: float

@dataclass(frozen=True)
class RegimeModel:
    df: float
    loc: float
    scale: float
    run_lengths: tuple[int, ...]
    successors: tuple[str, ...]
    shapes: tuple[BarShape, ...]

@dataclass(frozen=True)
class TapeModel:
    runs: tuple[tuple[str, int], ...]  # file order, one ticket per run
    regimes: dict[str, RegimeModel]    # all six names

def fit_tape(candles: Sequence[Candle], labeling: LabelResult) -> TapeModel:
    ...
```

Check order for each name in `REGIME_NAMES`: row count and run count, then blank volume, then zero volatility, then the Student-t. The first failure raises `ValueError` whose message contains the regime name.

- [ ] **Step 1: Write the failing test**

`tests/datafactory/test_fit.py`:

```python
from __future__ import annotations

import math

import pytest

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.fit import fit_tape
from price_forecast.datafactory.synthetic.label import REGIME_NAMES, LabelResult, label_candles
from tests.datafactory.fixture import balanced_tape, candles_from_closes


def _labeled(shock: float) -> tuple[tuple[Candle, ...], LabelResult]:
    """Two runs of 15 rows for every regime. `shock` is the log-return, or 0 to alternate."""
    labels: list[str | None] = [None]
    plan: list[str] = []
    for _ in range(2):
        for name in REGIME_NAMES:
            plan.extend([name] * 15)
    labels.extend(plan)
    closes = [100.0]
    for index in range(len(plan)):
        step = shock if shock != 0.0 else (0.01 if index % 2 == 0 else 0.02)
        closes.append(closes[-1] * math.exp(step))
    return candles_from_closes(closes), LabelResult(tuple(labels), 0.01)


def test_balanced_tape_fits_all_six_and_keeps_a_single_successor():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    model = fit_tape(candles, labeling)

    assert set(model.regimes) == set(REGIME_NAMES)
    bull = model.regimes["bull_quiet"]
    assert set(bull.successors) == {"sideways_volatile"}
    assert sum(len(item.successors) for item in model.regimes.values()) == len(model.runs) - 1
    assert model.regimes["bull_quiet"].loc > 0.05
    assert model.regimes["bear_quiet"].loc < -0.05


def test_thin_regime_names_itself():
    candles, labeling = _labeled(0.0)
    labels = list(labeling.labels)
    seen = 0
    for index, name in enumerate(labels):
        if name == "bull_quiet":
            seen += 1
            if seen > 10:
                labels[index] = "bull_volatile"
    with pytest.raises(ValueError, match="bull_quiet"):
        fit_tape(candles, LabelResult(tuple(labels), labeling.vol_median))


def test_blank_volume_names_the_regime():
    candles, labeling = _labeled(0.0)
    broken = list(candles)
    broken[1] = Candle(
        broken[1].day,
        broken[1].low,
        broken[1].high,
        broken[1].open,
        broken[1].close,
        None,
    )
    with pytest.raises(ValueError, match="bull_quiet"):
        fit_tape(tuple(broken), labeling)


def test_zero_volatility_names_the_regime():
    candles, labeling = _labeled(0.01)
    with pytest.raises(ValueError, match="bull_quiet"):
        fit_tape(candles, labeling)


def test_student_t_df_at_or_below_two_names_the_regime(monkeypatch):
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)

    def _flat_df(_returns):
        return (2.0, 0.0, 0.01)

    monkeypatch.setattr("price_forecast.datafactory.synthetic.fit.t.fit", _flat_df)
    with pytest.raises(ValueError, match="bull_quiet"):
        fit_tape(candles, labeling)
```

`_labeled(0.0)` alternates log-returns 0.01 and 0.02, so volatility is non-zero. `_labeled(0.01)` uses one constant return, so `bull_quiet` fails the zero-volatility check before `t.fit`. The thin test leaves `bull_quiet` with 10 rows, so the count check fires before `t.fit`. The blank-volume test clears row 1, the first `bull_quiet` row. The df test uses the balanced tape, whose volatility is non-zero, and the monkeypatch is what fails.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/datafactory/test_fit.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.datafactory.synthetic.fit'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/datafactory/synthetic/fit.py`:

```python
"""Measure Student-t moves, run lengths, successors, and bar shapes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.stats import t

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.label import REGIME_NAMES, LabelResult

MIN_ROWS = 30
MIN_RUNS = 2


@dataclass(frozen=True)
class BarShape:
    open_ratio: float
    high_ratio: float
    low_ratio: float
    volume: float


@dataclass(frozen=True)
class RegimeModel:
    df: float
    loc: float
    scale: float
    run_lengths: tuple[int, ...]
    successors: tuple[str, ...]
    shapes: tuple[BarShape, ...]


@dataclass(frozen=True)
class TapeModel:
    runs: tuple[tuple[str, int], ...]
    regimes: dict[str, RegimeModel]


def fit_tape(candles: Sequence[Candle], labeling: LabelResult) -> TapeModel:
    if len(labeling.labels) != len(candles):
        raise ValueError("labels must align with candles")
    groups = {name: [] for name in REGIME_NAMES}
    runs: list[tuple[str, int]] = []
    for index, name in enumerate(labeling.labels):
        if name is None:
            continue
        if name not in groups:
            raise ValueError(f"unknown regime {name}")
        groups[name].append(index)
        if not runs or runs[-1][0] != name:
            runs.append((name, 1))
        else:
            runs[-1] = (name, runs[-1][1] + 1)
    run_lengths = {name: [] for name in REGIME_NAMES}
    successors = {name: [] for name in REGIME_NAMES}
    for pos, (name, length) in enumerate(runs):
        run_lengths[name].append(length)
        if pos + 1 < len(runs):
            successors[name].append(runs[pos + 1][0])
    regimes: dict[str, RegimeModel] = {}
    for name in REGIME_NAMES:
        indexes = groups[name]
        lengths = run_lengths[name]
        if len(indexes) < MIN_ROWS or len(lengths) < MIN_RUNS:
            raise ValueError(
                f"{name} has {len(indexes)} labeled rows and {len(lengths)} runs"
            )
        for index in indexes:
            if candles[index].volume is None:
                raise ValueError(f"{name} has a blank volume")
        returns = np.array(
            [
                math.log(candles[index].close / candles[index - 1].close)
                for index in indexes
            ],
            dtype=float,
        )
        if returns.size < 2 or float(np.std(returns, ddof=1)) == 0.0:
            raise ValueError(f"{name} has zero volatility")
        df, loc, scale = t.fit(returns)
        df = float(df)
        loc = float(loc)
        scale = float(scale)
        if df <= 2.0 or not math.isfinite(df) or not math.isfinite(loc) or not math.isfinite(scale):
            raise ValueError(f"{name} student-t df={df}")
        shapes = tuple(
            BarShape(
                candles[index].open / candles[index].close,
                candles[index].high / candles[index].close,
                candles[index].low / candles[index].close,
                float(candles[index].volume),
            )
            for index in indexes
        )
        regimes[name] = RegimeModel(df, loc, scale, tuple(lengths), tuple(successors[name]), shapes)
    return TapeModel(tuple(runs), regimes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/datafactory/test_fit.py tests/datafactory/test_label.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/datafactory/synthetic/fit.py tests/datafactory/test_fit.py
git commit -m "$(cat <<'EOF'
Fit Student-t regimes, run lengths, and bar shapes.

EOF
)"
```

---

### Task 4: Build one candle path

**Files:**
- Create: `price_forecast/datafactory/synthetic/paths.py`
- Create: `tests/datafactory/test_paths.py`
- Test: `tests/datafactory/test_paths.py`

**Interfaces:**
- Consumes: `TapeModel`, `RegimeModel`, `BarShape`, `fit_tape` from `price_forecast.datafactory.synthetic.fit`. `LabelResult` and `label_candles` from `label.py`.
- Produces:

```python
@dataclass(frozen=True)
class PathResult:
    candles: tuple[Candle, ...]
    regimes: tuple[str, ...]

def synthetic_paths(
    candles: Sequence[Candle],
    model: TapeModel,
    *,
    n_paths: int,
    seed: int,
) -> tuple[PathResult, ...]:
    ...

def control_paths(
    candles: Sequence[Candle],
    labeling: LabelResult,
    *,
    n_paths: int,
    seed: int,
) -> tuple[tuple[Candle, ...], ...]:
    ...
```

Draw order inside a path: starting run, then repeating (length, one Student-t and one shape per invented row, next regime when rows remain). `n_paths < 1` raises `ValueError`. A non-finite return or a non-positive close raises `ValueError` and does not return a partial tuple.

- [ ] **Step 1: Write the failing test**

`tests/datafactory/test_paths.py`:

```python
from __future__ import annotations

import math

import pytest

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.fit import (
    BarShape,
    RegimeModel,
    TapeModel,
    fit_tape,
)
from price_forecast.datafactory.synthetic.label import label_candles
from price_forecast.datafactory.synthetic.paths import control_paths, synthetic_paths
from tests.datafactory.fixture import balanced_tape, candles_from_closes


def _cycle_model(source: TapeModel) -> TapeModel:
    order = (
        "bull_quiet",
        "bear_quiet",
        "bull_volatile",
        "bear_volatile",
        "sideways_quiet",
        "sideways_volatile",
    )
    regimes = {}
    for pos, name in enumerate(order):
        current = source.regimes[name]
        nxt = order[(pos + 1) % len(order)]
        regimes[name] = RegimeModel(
            current.df,
            current.loc,
            current.scale,
            (40,),
            (nxt,),
            current.shapes,
        )
    runs = tuple((name, 40) for name in order)
    return TapeModel(runs, regimes)


def _long_chapter() -> tuple[tuple[Candle, ...], TapeModel]:
    candles = candles_from_closes([100.0 + index for index in range(20)])
    shape = BarShape(0.995, 1.01, 0.99, 1.0)
    model = RegimeModel(8.0, 0.0, 0.01, (10_000,), ("bull_quiet",), (shape,))
    tape = TapeModel((("bull_quiet", 10_000),), {"bull_quiet": model})
    return candles, tape


def test_row_zero_is_the_source_and_a_long_chapter_is_cut_to_the_file():
    candles, tape = _long_chapter()
    path = synthetic_paths(candles, tape, n_paths=1, seed=0)[0]
    assert path.candles[0] == candles[0]
    assert len(path.candles) == len(candles)
    assert path.regimes == ("bull_quiet",) * len(candles)
    assert path.regimes[0] == "bull_quiet"


def test_same_seed_repeats_and_extra_paths_do_not_change_path_zero():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    model = _cycle_model(fit_tape(candles, labeling))
    first = synthetic_paths(candles, model, n_paths=1, seed=0)[0]
    second = synthetic_paths(candles, model, n_paths=2, seed=0)[0]
    assert first.candles == second.candles
    assert first.regimes == second.regimes


def test_bull_chapters_drift_up_more_than_bear_and_volatile_jumps_more():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    model = _cycle_model(fit_tape(candles, labeling))
    path = synthetic_paths(candles, model, n_paths=1, seed=0)[0]
    returns = [
        math.log(path.candles[index].close / path.candles[index - 1].close)
        for index in range(1, len(path.candles))
    ]
    bull = [ret for ret, name in zip(returns, path.regimes[1:]) if name.startswith("bull")]
    bear = [ret for ret, name in zip(returns, path.regimes[1:]) if name.startswith("bear")]
    volatile = [ret for ret, name in zip(returns, path.regimes[1:]) if name.endswith("volatile")]
    quiet = [ret for ret, name in zip(returns, path.regimes[1:]) if name.endswith("quiet")]
    assert sum(bull) / len(bull) > sum(bear) / len(bear)
    assert _std(volatile) > _std(quiet)


def test_every_invented_candle_is_a_valid_bar():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    path = synthetic_paths(candles, fit_tape(candles, labeling), n_paths=1, seed=0)[0]
    for candle in path.candles:
        assert math.isfinite(candle.close) and candle.close > 0
        assert candle.low <= min(candle.open, candle.close)
        assert candle.high >= max(candle.open, candle.close)
        assert candle.volume is not None and candle.volume >= 0


def test_non_finite_return_raises(monkeypatch):
    candles, tape = _long_chapter()
    monkeypatch.setattr(
        "price_forecast.datafactory.synthetic.paths.t.rvs",
        lambda *args, **kwargs: float("nan"),
    )
    with pytest.raises(ValueError, match="non-finite"):
        synthetic_paths(candles, tape, n_paths=2, seed=0)


def test_n_paths_below_one_raises():
    candles, tape = _long_chapter()
    with pytest.raises(ValueError, match="n_paths"):
        synthetic_paths(candles, tape, n_paths=0, seed=0)


def test_control_uses_the_other_stream_and_keeps_row_zero():
    candles = balanced_tape()
    labeling = label_candles(candles, trend_bars=4, vol_bars=2)
    control = control_paths(candles, labeling, n_paths=1, seed=0)[0]
    assert control[0] == candles[0]
    assert len(control) == len(candles)
    assert control[1].close != candles[1].close


def _std(values: list[float]) -> float:
    mean = sum(values) / len(values)
    var = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(var)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/datafactory/test_paths.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.datafactory.synthetic.paths'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/datafactory/synthetic/paths.py`:

```python
"""Draw synthetic candle paths and the one-regime control."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.stats import t

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.fit import BarShape, TapeModel
from price_forecast.datafactory.synthetic.label import LabelResult


@dataclass(frozen=True)
class PathResult:
    candles: tuple[Candle, ...]
    regimes: tuple[str, ...]


def synthetic_paths(
    candles: Sequence[Candle],
    model: TapeModel,
    *,
    n_paths: int,
    seed: int,
) -> tuple[PathResult, ...]:
    if n_paths < 1:
        raise ValueError("n_paths must be at least 1")
    return tuple(
        _regime_path(candles, model, _rng(seed, index, 0)) for index in range(n_paths)
    )


def control_paths(
    candles: Sequence[Candle],
    labeling: LabelResult,
    *,
    n_paths: int,
    seed: int,
) -> tuple[tuple[Candle, ...], ...]:
    if n_paths < 1:
        raise ValueError("n_paths must be at least 1")
    pooled = _pooled(candles, labeling)
    return tuple(
        _flat_path(candles, pooled, _rng(seed, index, 1)) for index in range(n_paths)
    )


def _rng(seed: int, path_index: int, stream: int) -> np.random.Generator:
    sequence = np.random.SeedSequence([seed, path_index, stream])
    return np.random.Generator(np.random.PCG64(sequence))


def _regime_path(
    candles: Sequence[Candle],
    model: TapeModel,
    rng: np.random.Generator,
) -> PathResult:
    start = int(rng.integers(0, len(model.runs)))
    regime = model.runs[start][0]
    rows = [candles[0]]
    regimes = [regime]
    remaining = len(candles) - 1
    while remaining > 0:
        params = model.regimes[regime]
        length = int(params.run_lengths[int(rng.integers(0, len(params.run_lengths)))])
        take = min(length, remaining)
        for _ in range(take):
            shock = float(t.rvs(params.df, loc=params.loc, scale=params.scale, random_state=rng))
            close = rows[-1].close * math.exp(shock) if math.isfinite(shock) else float("nan")
            if not math.isfinite(shock) or not math.isfinite(close) or close <= 0.0:
                raise ValueError(f"non-finite return in {regime}")
            shape = params.shapes[int(rng.integers(0, len(params.shapes)))]
            day = candles[len(rows)].day
            rows.append(_scaled(day, close, shape))
            regimes.append(regime)
        remaining -= take
        if remaining > 0:
            regime = params.successors[int(rng.integers(0, len(params.successors)))]
    return PathResult(tuple(rows), tuple(regimes))


def _flat_path(
    candles: Sequence[Candle],
    pooled: tuple[float, float, float, tuple[BarShape, ...]],
    rng: np.random.Generator,
) -> tuple[Candle, ...]:
    df, loc, scale, shapes = pooled
    rows = [candles[0]]
    for index in range(1, len(candles)):
        shock = float(t.rvs(df, loc=loc, scale=scale, random_state=rng))
        close = rows[-1].close * math.exp(shock) if math.isfinite(shock) else float("nan")
        if not math.isfinite(shock) or not math.isfinite(close) or close <= 0.0:
            raise ValueError("non-finite return in control")
        shape = shapes[int(rng.integers(0, len(shapes)))]
        rows.append(_scaled(candles[index].day, close, shape))
    return tuple(rows)


def _pooled(
    candles: Sequence[Candle],
    labeling: LabelResult,
) -> tuple[float, float, float, tuple[BarShape, ...]]:
    indexes = [index for index, name in enumerate(labeling.labels) if name is not None]
    if len(indexes) < 30:
        raise ValueError("pooled regime has fewer than 30 labeled rows")
    returns = [
        math.log(candles[index].close / candles[index - 1].close) for index in indexes
    ]
    vol = float(np.std(returns, ddof=1))
    if vol == 0.0:
        raise ValueError("pooled regime has zero volatility")
    for index in indexes:
        if candles[index].volume is None:
            raise ValueError("pooled regime has a blank volume")
    df, loc, scale = t.fit(returns)
    df, loc, scale = float(df), float(loc), float(scale)
    if df <= 2.0 or not all(math.isfinite(value) for value in (df, loc, scale)):
        raise ValueError(f"pooled student-t df={df}")
    shapes = tuple(
        BarShape(
            candles[index].open / candles[index].close,
            candles[index].high / candles[index].close,
            candles[index].low / candles[index].close,
            float(candles[index].volume),
        )
        for index in indexes
    )
    return df, loc, scale, shapes


def _scaled(day, close: float, shape: BarShape) -> Candle:
    return Candle(
        day,
        close * shape.low_ratio,
        close * shape.high_ratio,
        close * shape.open_ratio,
        close,
        shape.volume,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/datafactory/test_paths.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/datafactory/synthetic/paths.py tests/datafactory/test_paths.py
git commit -m "$(cat <<'EOF'
Draw seeded regime candle paths and a one-regime control.

EOF
)"
```

---

### Task 5: Print the sanity report

**Files:**
- Create: `price_forecast/datafactory/synthetic/report.py`
- Create: `tests/datafactory/test_report.py`
- Test: `tests/datafactory/test_report.py`

**Interfaces:**
- Consumes: `PathResult` from `paths.py`. `stylized_facts` from `price_forecast.datafactory.remix`. `closes_from_candles` from `price_forecast.data.candles`. `weekly_closes` is already used inside `stylized_facts`.
- Produces:

```python
def synthetic_report(
    candles: Sequence[Candle],
    paths: Sequence[PathResult],
    controls: Sequence[Sequence[Candle]],
) -> dict[str, object]:
    ...

def format_synthetic_report(report: Mapping[str, object]) -> str:
    ...
```

Fact keys, in order: `daily_vol`, `weekly_vol`, `excess_kurtosis`, `daily_p01`, `hodl_max_dd`, `acf_daily_1`, `acf_weekly_1`, `acf_weekly_4`, `acf_weekly_8`. The path median is the upper-middle sorted value, matching remix's `_median` (`ordered[len(ordered) // 2]`), not `numpy.median`. Chapter checks pool invented rows only (index 1 onward). Fewer than 2 rows on either side of a check prints `n/a`.

- [ ] **Step 1: Write the failing test**

`tests/datafactory/test_report.py`:

```python
from __future__ import annotations

import math
from datetime import date, timedelta

from price_forecast.data.candles import Candle
from price_forecast.datafactory.synthetic.paths import PathResult
from price_forecast.datafactory.synthetic.report import format_synthetic_report, synthetic_report


def _row(index: int, close: float) -> Candle:
    day = date(2020, 1, 1) + timedelta(days=index)
    return Candle(day, close * 0.99, close * 1.01, close, close, 1.0)


def _path(regimes: tuple[str, ...], closes: list[float]) -> PathResult:
    candles = tuple(_row(index, close) for index, close in enumerate(closes))
    return PathResult(candles, regimes)


def test_report_names_facts_counts_and_na_when_a_side_is_thin():
    regimes = ("bull_quiet",) * 8
    closes = [100.0 * math.exp(0.01 * index) for index in range(8)]
    path = _path(regimes, closes)
    report = synthetic_report(path.candles, (path,), (path.candles,))
    text = format_synthetic_report(report)
    for key in (
        "daily_vol",
        "weekly_vol",
        "excess_kurtosis",
        "daily_p01",
        "hodl_max_dd",
        "acf_daily_1",
        "acf_weekly_1",
        "acf_weekly_4",
        "acf_weekly_8",
    ):
        assert key in text
    assert "synthetic median" in text
    assert "control median" in text
    assert "bull_quiet=7" in text
    assert "bear_quiet=0" in text
    assert "n/a" in text


def test_passing_checks_print_pass():
    regimes = (
        "bull_quiet",
        "bull_quiet",
        "bull_quiet",
        "bear_quiet",
        "bear_quiet",
        "bear_quiet",
        "sideways_volatile",
        "sideways_volatile",
        "sideways_volatile",
        "sideways_quiet",
        "sideways_quiet",
        "sideways_quiet",
    )
    closes = [100.0]
    jumps = {
        "bull_quiet": 0.02,
        "bear_quiet": -0.03,
        "sideways_volatile": 0.05,
        "sideways_quiet": 0.0,
    }
    # Alternate the volatile sign so its sample std is wide, and keep quiet flat.
    signs = [1, -1, 1]
    volatile_seen = 0
    for name in regimes[1:]:
        shock = jumps[name]
        if name.endswith("volatile"):
            shock = 0.05 * signs[volatile_seen]
            volatile_seen += 1
        closes.append(closes[-1] * math.exp(shock))
    path = _path(regimes, closes)
    text = format_synthetic_report(synthetic_report(path.candles, (path,), (path.candles,)))
    assert "bull_vs_bear pass" in text
    assert "quiet_vs_volatile pass" in text
```

Row 0 is excluded, so seven `bull_quiet` invented rows are counted when all eight labels are `bull_quiet`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/datafactory/test_report.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecast.datafactory.synthetic.report'`

- [ ] **Step 3: Write minimal implementation**

`price_forecast/datafactory/synthetic/report.py`:

```python
"""Real versus synthetic versus one-regime control."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from price_forecast.data.candles import Candle, closes_from_candles
from price_forecast.datafactory.remix import stylized_facts
from price_forecast.datafactory.synthetic.label import REGIME_NAMES
from price_forecast.datafactory.synthetic.paths import PathResult

_FACT_KEYS = (
    "daily_vol",
    "weekly_vol",
    "excess_kurtosis",
    "daily_p01",
    "hodl_max_dd",
    "acf_daily_1",
    "acf_weekly_1",
    "acf_weekly_4",
    "acf_weekly_8",
)


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
        "real": stylized_facts(closes_from_candles(candles)),
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


def _summary(paths: Sequence[Sequence[Candle]]) -> dict[str, object]:
    rows = [stylized_facts(closes_from_candles(path)) for path in paths]
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/datafactory/test_report.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/datafactory/synthetic/report.py tests/datafactory/test_report.py
git commit -m "$(cat <<'EOF'
Report synthetic paths against the real tape and a one-regime control.

EOF
)"
```

---

### Task 6: Write the files from the command line

**Files:**
- Create: `price_forecast/datafactory/synthetic/__main__.py`
- Modify: `price_forecast/data/candles.py` (add `SYNTHETIC_DIR` next to `REMIX_DIR`)
- Modify: `.gitignore` (add `data/synthetic/`)
- Modify: `tests/data/test_candles.py` (`test_gitignore_lists_generated_candle_files`)
- Modify: `README.md` (layout bullet and a synthetic command)
- Create: `tests/datafactory/test_command.py`
- Test: `tests/datafactory/test_command.py`

**Interfaces:**
- Consumes: `label_candles`, `fit_tape`, `synthetic_paths`, `control_paths`, `synthetic_report`, `format_synthetic_report`, `require_closes`, `read_candles`, `write_candles`, `SYNTHETIC_DIR`.
- Produces: `python -m price_forecast.datafactory.synthetic` with `--csv`, `--n-paths`, and `--seed`. `main(argv: Sequence[str] | None = None) -> None`.

- [ ] **Step 1: Write the failing test**

`tests/datafactory/test_command.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from price_forecast.data.candles import write_candles
from price_forecast.datafactory.synthetic.__main__ import main
from tests.datafactory.fixture import balanced_tape


def _csv(tmp_path: Path) -> Path:
    path = tmp_path / "source.csv"
    write_candles(path, balanced_tape())
    return path


def _short_windows(monkeypatch) -> None:
    from price_forecast.datafactory.synthetic.label import label_candles

    def _label(candles):
        return label_candles(candles, trend_bars=4, vol_bars=2)

    monkeypatch.setattr(
        "price_forecast.datafactory.synthetic.__main__.label_candles",
        _label,
    )


def test_command_writes_candle_png_and_sidecar(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    _short_windows(monkeypatch)
    main(["--csv", str(source), "--n-paths", "1", "--seed", "3"])
    stem = dest / "btc-usd-daily-seed3-path0"
    assert stem.with_suffix(".csv").is_file()
    assert stem.with_suffix(".png").read_bytes().startswith(b"\x89PNG")
    sidecar = dest / "btc-usd-daily-seed3-path0-regimes.csv"
    text = sidecar.read_text(encoding="utf-8").splitlines()
    assert text[0] == "time,regime"
    assert sidecar.with_suffix(".png").exists() is False
    assert len(text) == len(balanced_tape()) + 1
    assert sorted(path.name for path in dest.iterdir()) == [
        "btc-usd-daily-seed3-path0-regimes.csv",
        "btc-usd-daily-seed3-path0.csv",
        "btc-usd-daily-seed3-path0.png",
    ]


def test_more_paths_keep_path_zero_bytes(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    _short_windows(monkeypatch)
    main(["--csv", str(source), "--n-paths", "1", "--seed", "3"])
    candle = (dest / "btc-usd-daily-seed3-path0.csv").read_bytes()
    sidecar = (dest / "btc-usd-daily-seed3-path0-regimes.csv").read_bytes()
    main(["--csv", str(source), "--n-paths", "2", "--seed", "3"])
    assert (dest / "btc-usd-daily-seed3-path0.csv").read_bytes() == candle
    assert (dest / "btc-usd-daily-seed3-path0-regimes.csv").read_bytes() == sidecar
    assert (dest / "btc-usd-daily-seed3-path1.csv").is_file()


def test_missing_csv_writes_nothing(tmp_path, monkeypatch, capsys):
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    with pytest.raises(SystemExit) as exc:
        main(["--csv", str(tmp_path / "missing.csv")])
    assert exc.value.code == 1
    assert "python -m price_forecast.data.candles" in capsys.readouterr().err
    assert dest.exists() is False


def test_n_paths_below_one_writes_nothing(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    with pytest.raises(ValueError, match="n_paths"):
        main(["--csv", str(source), "--n-paths", "0"])
    assert dest.exists() is False


def test_fit_failure_writes_nothing(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    _short_windows(monkeypatch)
    monkeypatch.setattr(
        "price_forecast.datafactory.synthetic.fit.t.fit",
        lambda _returns: (1.0, 0.0, 0.01),
    )
    with pytest.raises(ValueError, match="bull_quiet"):
        main(["--csv", str(source)])
    assert dest.exists() is False


def test_non_finite_return_writes_nothing(tmp_path, monkeypatch):
    source = _csv(tmp_path)
    dest = tmp_path / "synthetic"
    monkeypatch.setattr("price_forecast.datafactory.synthetic.__main__.SYNTHETIC_DIR", dest)
    _short_windows(monkeypatch)
    monkeypatch.setattr(
        "price_forecast.datafactory.synthetic.paths.t.rvs",
        lambda *args, **kwargs: float("nan"),
    )
    with pytest.raises(ValueError, match="non-finite"):
        main(["--csv", str(source), "--n-paths", "2"])
    assert list(dest.glob("*")) == []
```

Extend `test_gitignore_lists_generated_candle_files` so the tuple of required lines includes `"data/synthetic/"`.

`README.md` layout bullet becomes:

```markdown
- `price_forecast/datafactory/` — remix and the synthetic regime factory
```

Add a run block under the remix command whose heading is `Synthetic regime path factory:` and whose command is `python -m price_forecast.datafactory.synthetic`.

`main` calls `label_candles(candles)` with no window arguments. Do not add window flags. The command tests monkeypatch that name to `trend_bars=4, vol_bars=2` because `balanced_tape()` is built for those windows. Production still uses 365 and 30.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/datafactory/test_command.py tests/data/test_candles.py::test_gitignore_lists_generated_candle_files -q`

Expected: FAIL with `ModuleNotFoundError` for `__main__`, and the gitignore assertion fails until `data/synthetic/` is added.

- [ ] **Step 3: Write minimal implementation**

In `price_forecast/data/candles.py`, next to `REMIX_DIR`:

```python
SYNTHETIC_DIR = BTC_USD_DAILY_CSV.parent / "synthetic"
```

`.gitignore`, under `data/remix/`:

```
data/synthetic/
```

`price_forecast/datafactory/synthetic/__main__.py`:

```python
"""Write synthetic regime candle paths.

Usage:
    python -m price_forecast.datafactory.synthetic
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Sequence

from price_forecast.data.candles import (
    BTC_USD_DAILY_CSV,
    SYNTHETIC_DIR,
    read_candles,
    require_closes,
    write_candles,
)
from price_forecast.datafactory.synthetic.fit import fit_tape
from price_forecast.datafactory.synthetic.label import label_candles
from price_forecast.datafactory.synthetic.paths import control_paths, synthetic_paths
from price_forecast.datafactory.synthetic.report import (
    format_synthetic_report,
    synthetic_report,
)


def write_regimes(path: Path, days: Sequence[str], regimes: Sequence[str]) -> None:
    if len(days) != len(regimes):
        raise ValueError("regime rows must align with candles")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("time", "regime"))
        writer.writerows(zip(days, regimes))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Write synthetic regime candle paths. Does not score a strategy."
    )
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--n-paths", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    source = BTC_USD_DAILY_CSV if args.csv is None else args.csv
    require_closes(source)
    if args.n_paths < 1:
        raise ValueError("n_paths must be at least 1")
    candles = read_candles(source)
    labeling = label_candles(candles)
    model = fit_tape(candles, labeling)
    paths = synthetic_paths(candles, model, n_paths=args.n_paths, seed=args.seed)
    controls = control_paths(candles, labeling, n_paths=args.n_paths, seed=args.seed)
    for index, path in enumerate(paths):
        stem = f"btc-usd-daily-seed{args.seed}-path{index}"
        write_candles(SYNTHETIC_DIR / f"{stem}.csv", path.candles)
        write_regimes(
            SYNTHETIC_DIR / f"{stem}-regimes.csv",
            [candle.day.isoformat() for candle in path.candles],
            path.regimes,
        )
    print(format_synthetic_report(synthetic_report(candles, paths, controls)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/datafactory tests/layout/test_no_old_modules.py tests/data/test_candles.py::test_gitignore_lists_generated_candle_files -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add price_forecast/datafactory/synthetic/__main__.py price_forecast/data/candles.py .gitignore tests/data/test_candles.py tests/datafactory/test_command.py README.md
git commit -m "$(cat <<'EOF'
Write seeded synthetic regime candles from the command line.

EOF
)"
```
