"""Selection-bias checks: deflated Sharpe ratio and CSCV probability of backtest overfitting.

References:
- Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio"
- Bailey, Borwein, Lopez de Prado & Zhu (2016), "The Probability of Backtest Overfitting"

All Sharpe ratios here are per week unless the name ends in ``_ann``.
"""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from scipy import stats

from price_forecast.replay.engine import WEEKS_PER_YEAR

EULER_GAMMA = 0.5772156649015329


@dataclass(frozen=True)
class DeflatedSharpe:
    n_trials: int
    weeks: int
    sharpe_ann: float
    expected_max_null_ann: float
    psr: float
    dsr: float


def expected_max_sharpe(n_trials: int, sharpe_variance: float) -> float:
    """Expected best Sharpe among ``n_trials`` skill-less trials (per-period units)."""
    if n_trials <= 1:
        return 0.0
    sd = math.sqrt(sharpe_variance)
    a = stats.norm.ppf(1.0 - 1.0 / n_trials)
    b = stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return sd * ((1.0 - EULER_GAMMA) * a + EULER_GAMMA * b)


def probabilistic_sharpe(returns: Sequence[float], benchmark: float) -> tuple[float, float]:
    """``(sharpe, P[true Sharpe > benchmark])`` with skew and kurtosis correction."""
    values = np.asarray(returns, dtype=float)
    if values.size < 3:
        raise ValueError("need at least 3 returns")
    sd = values.std(ddof=1)
    if sd == 0.0:
        raise ValueError("returns have zero variance")
    sr = values.mean() / sd
    skew = float(stats.skew(values))
    kurt = float(stats.kurtosis(values, fisher=False))
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    z = (sr - benchmark) * math.sqrt(values.size - 1) / math.sqrt(max(denom, 1e-12))
    return sr, float(stats.norm.cdf(z))


def deflated_sharpe(returns: Sequence[float], *, n_trials: int, sharpe_variance: float) -> DeflatedSharpe:
    """DSR of the chosen strategy, given how many trials it was picked from.

    ``sharpe_variance`` is the cross-trial variance of per-week Sharpe ratios.
    """
    sr, psr = probabilistic_sharpe(returns, 0.0)
    threshold = expected_max_sharpe(n_trials, sharpe_variance)
    _sr, dsr = probabilistic_sharpe(returns, threshold)
    root = math.sqrt(WEEKS_PER_YEAR)
    return DeflatedSharpe(
        n_trials=n_trials,
        weeks=len(returns),
        sharpe_ann=sr * root,
        expected_max_null_ann=threshold * root,
        psr=psr,
        dsr=dsr,
    )


@dataclass(frozen=True)
class Pbo:
    strategies: int
    weeks: int
    blocks: int
    splits: int
    pbo: float
    median_logit: float
    oos_loss_rate: float
    is_sharpe_median_ann: float
    oos_sharpe_median_ann: float


def _sharpe_columns(total: np.ndarray, squares: np.ndarray, count: float) -> np.ndarray:
    mean = total / count
    var = squares / count - mean * mean
    out = np.zeros_like(mean)
    ok = var > 1e-18
    out[ok] = mean[ok] / np.sqrt(var[ok])
    return out


def cscv_pbo(matrix: np.ndarray, *, blocks: int = 16, batch: int = 256) -> Pbo:
    """CSCV PBO on a ``weeks x strategies`` return matrix.

    The weeks are cut into ``blocks`` contiguous blocks. Every half/half split of the
    blocks is one trial: pick the best in-sample Sharpe, then see where it ranks out
    of sample. PBO is the share of splits where it ranks at or below the median.
    """
    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2 or values.shape[1] < 2:
        raise ValueError("need a weeks x strategies matrix with at least 2 strategies")
    if blocks % 2 or blocks < 2:
        raise ValueError("blocks must be even")
    weeks, strategies = values.shape
    usable = weeks - weeks % blocks
    values = values[weeks - usable :]
    size = usable // blocks
    shaped = values.reshape(blocks, size, strategies)
    sums = shaped.sum(axis=1)
    squares = (shaped * shaped).sum(axis=1)
    half = blocks // 2
    combos = np.array(list(itertools.combinations(range(blocks), half)), dtype=int)
    member = np.zeros((len(combos), blocks))
    member[np.arange(len(combos))[:, None], combos] = 1.0
    logits: list[float] = []
    oos_selected: list[float] = []
    is_selected: list[float] = []
    count = float(size * half)
    for start in range(0, len(member), batch):
        chunk = member[start : start + batch]
        inside = _sharpe_columns(chunk @ sums, chunk @ squares, count)
        outside = _sharpe_columns((1.0 - chunk) @ sums, (1.0 - chunk) @ squares, count)
        best = inside.argmax(axis=1)
        rows = np.arange(len(chunk))
        chosen_oos = outside[rows, best]
        ranks = (outside < chosen_oos[:, None]).sum(axis=1) + 0.5 * (
            (outside == chosen_oos[:, None]).sum(axis=1) - 1
        ) + 1.0
        omega = ranks / (strategies + 1.0)
        logits.extend(np.log(omega / (1.0 - omega)).tolist())
        oos_selected.extend(chosen_oos.tolist())
        is_selected.extend(inside[rows, best].tolist())
    logit_array = np.array(logits)
    root = math.sqrt(WEEKS_PER_YEAR)
    return Pbo(
        strategies=strategies,
        weeks=usable,
        blocks=blocks,
        splits=len(combos),
        pbo=float((logit_array <= 0.0).mean()),
        median_logit=float(np.median(logit_array)),
        oos_loss_rate=float((np.array(oos_selected) < 0.0).mean()),
        is_sharpe_median_ann=float(np.median(is_selected)) * root,
        oos_sharpe_median_ann=float(np.median(oos_selected)) * root,
    )


@dataclass(frozen=True)
class LedgerTrials:
    rows: int
    scored: int
    unique_specs: list[dict]
    sharpes_ann: list[float]
    pool_trial_count: int | None


def _rows(path: Path) -> Iterable[dict]:
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_ledger(path: Path, pool_path: Path | None = None) -> LedgerTrials:
    """Distinct scored specs in the search ledger, each with its Coinbase Sharpe.

    The ledger re-scores the same spec many times, so ``scored`` overstates the
    number of independent trials; ``unique_specs`` is the honest count.
    """
    rows = 0
    scored = 0
    seen: dict[str, tuple[dict, float]] = {}
    for row in _rows(path):
        rows += 1
        coinbase = row.get("coinbase") or {}
        value = coinbase.get("sharpe")
        spec = row.get("spec")
        if row.get("status") != "ok" or value is None or not math.isfinite(value) or spec is None:
            continue
        scored += 1
        seen.setdefault(json.dumps(spec, sort_keys=True), (spec, float(value)))
    pool_trials = None
    if pool_path is not None and Path(pool_path).is_file():
        pool_trials = json.loads(Path(pool_path).read_text(encoding="utf-8")).get("trial_count")
    return LedgerTrials(
        rows=rows,
        scored=scored,
        unique_specs=[spec for spec, _value in seen.values()],
        sharpes_ann=[value for _spec, value in seen.values()],
        pool_trial_count=pool_trials,
    )


def sharpe_variance_per_week(sharpes_ann: Sequence[float]) -> float:
    values = np.asarray(sharpes_ann, dtype=float) / math.sqrt(WEEKS_PER_YEAR)
    return float(values.var(ddof=1))
