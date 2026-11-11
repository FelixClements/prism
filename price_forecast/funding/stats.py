"""Event-study statistics: Newey-West OLS, decile buckets, spread test, corrections."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import stats

N_BUCKETS = 10


@dataclass(frozen=True)
class HacFit:
    beta: np.ndarray
    cov: np.ndarray

    def t(self, i: int) -> float:
        return float(self.beta[i] / math.sqrt(self.cov[i, i]))


def newey_west_ols(y: np.ndarray, x: np.ndarray, lags: int) -> HacFit:
    """OLS with Bartlett-kernel Newey-West covariance, no small-sample correction.

    Rows must be in time order. ``lags`` is the truncation lag L; weights are
    1 - l/(L+1) for l = 1..L.
    """
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    xtx_inv = np.linalg.inv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    u = x * (y - x @ beta)[:, None]
    s = u.T @ u
    for lag in range(1, min(lags, len(y) - 1) + 1):
        w = 1.0 - lag / (lags + 1.0)
        g = u[lag:].T @ u[:-lag]
        s += w * (g + g.T)
    return HacFit(beta=beta, cov=xtx_inv @ s @ xtx_inv)


def two_sided_p(t: float) -> float:
    return float(2.0 * stats.norm.sf(abs(t)))


def deciles(values: Sequence[float]) -> np.ndarray:
    """Bucket 1..10 by average rank, so tied values always share a bucket."""
    v = np.asarray(values, dtype=float)
    ranks = stats.rankdata(v, method="average")
    return np.minimum(N_BUCKETS, np.floor(N_BUCKETS * (ranks - 0.5) / len(v)).astype(int) + 1)


def expanding_deciles(values: Sequence[float], min_history: int) -> np.ndarray:
    """Bucket of each value among itself and all earlier values (0 = too little history)."""
    v = np.asarray(values, dtype=float)
    out = np.zeros(len(v), dtype=int)
    for i in range(min_history, len(v)):
        out[i] = deciles(v[: i + 1])[-1]
    return out


@dataclass(frozen=True)
class BucketResult:
    counts: np.ndarray  # per bucket 1..10
    means: np.ndarray  # NaN when empty
    medians: np.ndarray
    spread: float  # top minus bottom mean
    spread_t: float
    spread_p: float
    spearman: float  # rank corr of bucket index vs bucket mean (non-empty buckets)


def bucket_test(returns: Sequence[float], buckets: Sequence[int], lags: int) -> BucketResult:
    """Regress returns on bucket dummies (no intercept) with Newey-West covariance.

    Top-minus-bottom spread = beta_top - beta_bottom over the highest and lowest
    non-empty buckets. Rows with bucket 0 are excluded.
    """
    r = np.asarray(returns, dtype=float)
    b = np.asarray(buckets, dtype=int)
    keep = b > 0
    r, b = r[keep], b[keep]
    present = sorted(set(b.tolist()))
    x = np.column_stack([(b == k).astype(float) for k in present])
    fit = newey_west_ols(r, x, lags)
    counts = np.array([np.sum(b == k) for k in range(1, N_BUCKETS + 1)])
    means = np.full(N_BUCKETS, np.nan)
    medians = np.full(N_BUCKETS, np.nan)
    for j, k in enumerate(present):
        means[k - 1] = fit.beta[j]
        medians[k - 1] = float(np.median(r[b == k]))
    lo, hi = 0, len(present) - 1
    spread = float(fit.beta[hi] - fit.beta[lo])
    var = fit.cov[hi, hi] + fit.cov[lo, lo] - 2.0 * fit.cov[hi, lo]
    t = spread / math.sqrt(var)
    rho = float(stats.spearmanr(present, fit.beta).statistic) if len(present) > 2 else float("nan")
    return BucketResult(counts, means, medians, spread, t, two_sided_p(t), rho)


@dataclass(frozen=True)
class SlopeResult:
    slope: float
    t: float
    p: float


def slope_test(returns: Sequence[float], regressors: Sequence[Sequence[float]], lags: int) -> SlopeResult:
    """r = a + b*z1 [+ c*z2 ...]; returns b with its Newey-West t-stat."""
    r = np.asarray(returns, dtype=float)
    x = np.column_stack([np.ones(len(r)), *[np.asarray(z, dtype=float) for z in regressors]])
    fit = newey_west_ols(r, x, lags)
    t = fit.t(1)
    return SlopeResult(float(fit.beta[1]), t, two_sided_p(t))


def zscore(values: Sequence[float]) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    return (v - v.mean()) / v.std(ddof=1)


def holm(pvalues: Sequence[float]) -> np.ndarray:
    """Holm step-down adjusted p-values (family-wise error control)."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for i, idx in enumerate(order):
        running = max(running, (m - i) * p[idx])
        adj[idx] = min(1.0, running)
    return adj


def benjamini_hochberg(pvalues: Sequence[float]) -> np.ndarray:
    """BH step-up adjusted p-values (q-values, false-discovery-rate control)."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    order = np.argsort(p)[::-1]
    adj = np.empty(m)
    running = 1.0
    for i, idx in enumerate(order):
        rank = m - i
        running = min(running, p[idx] * m / rank)
        adj[idx] = running
    return adj
