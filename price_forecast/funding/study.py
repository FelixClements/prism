"""Funding-rate event study (measurement only, no strategy backtest).

The design is pre-registered in ``results/funding/preregistration.md``; the
constants below implement it and must not be changed after results exist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Mapping, Sequence

import numpy as np

from price_forecast.funding.stats import (
    BucketResult,
    SlopeResult,
    benjamini_hochberg,
    bucket_test,
    deciles,
    expanding_deciles,
    holm,
    slope_test,
    zscore,
)

VENUE_FEATURES = ("bybit_btcusd_f7", "binance_btcusdt_f7")
AVG_FEATURE = "venue_avg_f7"
PRIMARY_FEATURES = (*VENUE_FEATURES, AVG_FEATURE)
HORIZONS = (7, 14, 21, 28)
SPLIT = date(2021, 1, 1)
MOM_DAYS = 28
EXPANDING_MIN = 365
ALPHA = 0.05
RHO_MIN = 0.6


def hac_lags(horizon: int) -> int:
    return 2 * horizon


def forward_returns(closes: Mapping[date, float], days: Sequence[date], horizon: int) -> np.ndarray:
    """close(D+h)/close(D) - 1: enter at the signal day's close, first return day is D+1."""
    out = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        end = closes.get(d + timedelta(days=horizon))
        if end is not None and d in closes:
            out[i] = end / closes[d] - 1.0
    return out


def trailing_returns(closes: Mapping[date, float], days: Sequence[date], lookback: int) -> np.ndarray:
    """close(D)/close(D-k) - 1, known at the signal day's close."""
    out = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        start = closes.get(d - timedelta(days=lookback))
        if start is not None and d in closes:
            out[i] = closes[d] / start - 1.0
    return out


@dataclass(frozen=True)
class Subperiod:
    name: str
    n: int
    buckets: BucketResult
    slope: SlopeResult


@dataclass(frozen=True)
class Cell:
    feature: str
    horizon: int
    n: int
    start: date
    end: date
    uncond_mean: float
    edges: np.ndarray  # min and max feature value per bucket, shape (10, 2)
    buckets: BucketResult  # primary: full-sample deciles, L = 2h
    buckets_lag_h: BucketResult  # sensitivity: L = h
    expanding: BucketResult  # deciles from past values only
    slope: SlopeResult  # r on z(feature)
    incremental: SlopeResult  # r on z(feature) + z(trailing 28d return)
    subperiods: tuple[Subperiod, ...] = field(default=())


def run_cell(closes: Mapping[date, float], feature: Mapping[date, float], name: str, horizon: int) -> Cell:
    days = [d for d in sorted(feature) if d in closes]
    vals = np.array([feature[d] for d in days])
    dec = deciles(vals)
    exp_dec = expanding_deciles(vals, EXPANDING_MIN)
    fwd = forward_returns(closes, days, horizon)
    mom = trailing_returns(closes, days, MOM_DAYS)
    ok = ~np.isnan(fwd)
    lags = hac_lags(horizon)
    edges = np.full((10, 2), np.nan)
    for k in range(1, 11):
        sel = vals[dec == k]
        if len(sel):
            edges[k - 1] = (sel.min(), sel.max())
    ok_mom = ok & ~np.isnan(mom)
    day_arr = np.array(days)
    subs = []
    for sub_name, mask in (("pre-2021", day_arr < SPLIT), ("2021+", day_arr >= SPLIT)):
        m = ok & mask
        if m.sum() < 50:
            continue
        subs.append(
            Subperiod(
                sub_name,
                int(m.sum()),
                bucket_test(fwd[m], deciles(vals[m]), lags),
                slope_test(fwd[m], [zscore(vals[m])], lags),
            )
        )
    used = day_arr[ok]
    return Cell(
        feature=name,
        horizon=horizon,
        n=int(ok.sum()),
        start=used[0],
        end=used[-1],
        uncond_mean=float(fwd[ok].mean()),
        edges=edges,
        buckets=bucket_test(fwd[ok], dec[ok], lags),
        buckets_lag_h=bucket_test(fwd[ok], dec[ok], horizon),
        expanding=bucket_test(fwd[ok], exp_dec[ok], lags),
        slope=slope_test(fwd[ok], [zscore(vals[ok])], lags),
        incremental=slope_test(fwd[ok_mom], [zscore(vals[ok_mom]), zscore(mom[ok_mom])], lags),
        subperiods=tuple(subs),
    )


@dataclass(frozen=True)
class Check:
    cell: Cell
    holm_p: float
    checks: dict[str, bool]

    @property
    def robust(self) -> bool:
        return all(self.checks.values())


@dataclass(frozen=True)
class StudyResult:
    cells: dict[tuple[str, int], Cell]
    common: dict[tuple[str, int], Cell]  # venue features on the venue-average window
    spread_holm: dict[tuple[str, int], float]
    spread_bh: dict[tuple[str, int], float]
    slope_holm: dict[tuple[str, int], float]
    survivors: tuple[Check, ...]
    verdict: str
    incremental: bool


def _same_sign(a: float, b: float) -> bool:
    return a != 0 and b != 0 and math.copysign(1, a) == math.copysign(1, b)


def survivor_checks(key: tuple[str, int], res_cells: Mapping[tuple[str, int], Cell], holm_p: float) -> Check:
    cell = res_cells[key]
    sign = cell.buckets.spread
    feat, h = key
    others = [f for f in VENUE_FEATURES if f != feat] if feat in VENUE_FEATURES else list(VENUE_FEATURES)
    checks = {
        "a_slope_same_sign_p<0.05": _same_sign(cell.slope.slope, sign) and cell.slope.p < ALPHA,
        "b_both_subperiods_same_sign": len(cell.subperiods) == 2
        and all(_same_sign(s.buckets.spread, sign) for s in cell.subperiods),
        "c_other_venue_same_sign": all(_same_sign(res_cells[(o, h)].buckets.spread, sign) for o in others),
        "d_monotone_rho>=0.6": _same_sign(cell.buckets.spearman, sign) and abs(cell.buckets.spearman) >= RHO_MIN,
        "e_expanding_deciles_same_sign": _same_sign(cell.expanding.spread, sign),
    }
    return Check(cell, holm_p, checks)


def run_study(closes: Mapping[date, float], features: Mapping[str, Mapping[date, float]]) -> StudyResult:
    cells = {(f, h): run_cell(closes, features[f], f, h) for f in PRIMARY_FEATURES for h in HORIZONS}
    common_days = set(features[AVG_FEATURE])
    common = {
        (f, h): run_cell(closes, {d: v for d, v in features[f].items() if d in common_days}, f, h)
        for f in VENUE_FEATURES
        for h in HORIZONS
    }
    keys = list(cells)
    spread_p = [cells[k].buckets.spread_p for k in keys]
    slope_p = [cells[k].slope.p for k in keys]
    spread_holm = dict(zip(keys, holm(spread_p)))
    spread_bh = dict(zip(keys, benjamini_hochberg(spread_p)))
    slope_holm = dict(zip(keys, holm(slope_p)))
    survivors = tuple(
        survivor_checks(k, cells, spread_holm[k]) for k in keys if spread_holm[k] < ALPHA
    )
    if not survivors:
        verdict = "FAIL"
    elif any(s.robust for s in survivors):
        verdict = "PASS"
    else:
        verdict = "FRAGILE"
    incremental = any(
        s.robust and _same_sign(s.cell.incremental.slope, s.cell.buckets.spread) and s.cell.incremental.p < ALPHA
        for s in survivors
    )
    return StudyResult(cells, common, spread_holm, spread_bh, slope_holm, survivors, verdict, incremental)


# ---------------------------------------------------------------- report


def _pct(x: float, digits: int = 2) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:+.{digits}f}%"


def _ann(daily_rate: float) -> str:
    return "—" if math.isnan(daily_rate) else f"{100 * 365 * daily_rate:+.1f}"


def _f(x: float, digits: int = 2) -> str:
    return "—" if math.isnan(x) else f"{x:+.{digits}f}"


def _p(x: float) -> str:
    return "—" if math.isnan(x) else (f"{x:.3f}" if x >= 0.001 else "<0.001")


def render_report(res: StudyResult, *, header: str) -> str:
    out = [header.rstrip(), ""]
    out += ["## Verdict", ""]
    n_cells = len(res.cells)
    out.append(
        f"- **{res.verdict}**. Primary family: {n_cells} cells (3 features × 4 horizons), "
        f"top-minus-bottom decile spread, Holm-adjusted at α = {ALPHA}."
    )
    if res.survivors:
        for s in res.survivors:
            c = s.cell
            ticks = ", ".join(f"{k} {'✓' if v else '✗'}" for k, v in s.checks.items())
            out.append(
                f"- Survivor `{c.feature}` {c.horizon}d: spread {_pct(c.buckets.spread)}, "
                f"t = {c.buckets.spread_t:+.2f}, Holm p = {_p(s.holm_p)}. Checks: {ticks}."
            )
    else:
        best = min(res.cells, key=lambda k: res.cells[k].buckets.spread_p)
        c = res.cells[best]
        out.append(
            f"- No cell survives Holm. Smallest raw p: `{c.feature}` {c.horizon}d, spread "
            f"{_pct(c.buckets.spread)}, t = {c.buckets.spread_t:+.2f}, raw p = {_p(c.buckets.spread_p)}, "
            f"Holm p = {_p(res.spread_holm[best])}."
        )
    n_raw = sum(c.buckets.spread_p < ALPHA for c in res.cells.values())
    out.append(f"- Spread cells with raw p < {ALPHA}: {n_raw} of {n_cells} (≈{ALPHA * n_cells:.1f} expected by chance).")
    n_slope = sum(p < ALPHA for p in res.slope_holm.values())
    out.append(f"- Secondary family (z-score slope): {n_slope} of {n_cells} cells Holm p < {ALPHA}.")
    out.append(
        f"- Adds information beyond trailing {MOM_DAYS}d return (needed for a strategy step): "
        f"**{'yes' if res.incremental else 'no'}**."
    )
    out.append("")

    out += ["## Primary family", ""]
    out.append(
        "Spread = mean forward return in the top funding decile minus the bottom decile. "
        "t-stats are Newey-West (Bartlett, L = 2h days). ρ = Spearman rank correlation of decile "
        "index vs decile mean. Slope = return per 1 s.d. of funding; incr. t = funding slope t-stat "
        f"with the trailing {MOM_DAYS}d return as a control."
    )
    out.append("")
    out.append(
        "| Feature | h | n | Window | Uncond. mean | Spread | t | raw p | Holm p | BH q | ρ | Slope | Slope t | Slope Holm p | Incr. t |"
    )
    out.append("|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k, c in res.cells.items():
        b = c.buckets
        out.append(
            f"| `{c.feature}` | {c.horizon}d | {c.n} | {c.start} → {c.end} | {_pct(c.uncond_mean)} | "
            f"{_pct(b.spread)} | {b.spread_t:+.2f} | {_p(b.spread_p)} | {_p(res.spread_holm[k])} | "
            f"{_p(res.spread_bh[k])} | {_f(b.spearman)} | {_pct(c.slope.slope)} | {c.slope.t:+.2f} | "
            f"{_p(res.slope_holm[k])} | {c.incremental.t:+.2f} |"
        )
    out.append("")

    out += ["## Forward return by funding decile", ""]
    out.append(
        "Decile 1 = lowest funding. Funding range is the 7-day mean daily rate, annualised in % "
        "(daily × 365). Cells show mean / median forward return."
    )
    for f in PRIMARY_FEATURES:
        out += ["", f"### `{f}`", ""]
        head = "| Decile | Funding range (%/yr) | n (h=7) | " + " | ".join(f"{h}d mean / median" for h in HORIZONS) + " |"
        out.append(head)
        out.append("|---:|---|---:|" + "---:|" * len(HORIZONS))
        first = res.cells[(f, HORIZONS[0])]
        for k in range(10):
            lo, hi = first.edges[k]
            rng = "—" if math.isnan(lo) else f"{_ann(lo)} … {_ann(hi)}"
            row = f"| {k + 1} | {rng} | {first.buckets.counts[k]} |"
            for h in HORIZONS:
                b = res.cells[(f, h)].buckets
                row += f" {_pct(b.means[k], 1)} / {_pct(b.medians[k], 1)} |"
            out.append(row)
        row = "| all | | |"
        for h in HORIZONS:
            row += f" {_pct(res.cells[(f, h)].uncond_mean, 1)} |"
        out.append(row)
    out.append("")

    out += ["## Robustness (descriptive, not part of the tested family)", ""]
    out += ["### Subperiods (deciles and z-scores re-ranked within each period)", ""]
    out.append("| Feature | h | Period | n | Spread | t | ρ | Slope t |")
    out.append("|---|---:|---|---:|---:|---:|---:|---:|")
    for c in res.cells.values():
        for s in c.subperiods:
            out.append(
                f"| `{c.feature}` | {c.horizon}d | {s.name} | {s.n} | {_pct(s.buckets.spread)} | "
                f"{s.buckets.spread_t:+.2f} | {_f(s.buckets.spearman)} | {s.slope.t:+.2f} |"
            )
    out.append("")
    out += ["### Per venue on the common window (days where both venues exist)", ""]
    out.append("| Feature | h | n | Window | Spread | t | ρ | Slope t |")
    out.append("|---|---:|---:|---|---:|---:|---:|---:|")
    for c in res.common.values():
        out.append(
            f"| `{c.feature}` | {c.horizon}d | {c.n} | {c.start} → {c.end} | {_pct(c.buckets.spread)} | "
            f"{c.buckets.spread_t:+.2f} | {_f(c.buckets.spearman)} | {c.slope.t:+.2f} |"
        )
    out.append("")
    out += [f"### No-lookahead deciles (rank among past values only, first {EXPANDING_MIN} days skipped) and L = h", ""]
    out.append("| Feature | h | Expanding spread | t | ρ | Spread t with L = h |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for c in res.cells.values():
        out.append(
            f"| `{c.feature}` | {c.horizon}d | {_pct(c.expanding.spread)} | {c.expanding.spread_t:+.2f} | "
            f"{_f(c.expanding.spearman)} | {c.buckets_lag_h.spread_t:+.2f} |"
        )
    out.append("")
    n_rob = len(res.cells) * 2 * 2 + len(res.common) + len(res.cells) * 2
    out += ["## Tests counted", ""]
    out.append(
        f"- Tested family: {n_cells} spread tests (Holm + BH reported). Secondary family: {n_cells} slope tests (Holm). "
        f"Incremental slope: {n_cells} tests, reported raw."
    )
    out.append(
        f"- Robustness rows: about {n_rob} further t-stats (subperiod spread + slope, common window, expanding "
        "deciles, L = h). Not corrected; read them for sign consistency only, not for significance."
    )
    out.append("")
    return "\n".join(out)
