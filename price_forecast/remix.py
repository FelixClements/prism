"""Stationary-bootstrap remixed daily BTC closes.

History factory for a later SMAGateV1 stress test. Not a new trading rule.
Remixing this Coinbase return process does not undo having picked SMA-8/16
on the real tape, does not invent worse-than-history crashes, and does not
replace combinatorial CV, deflated Sharpe, a holdout, or costs.

Glue points can split a crash chapter. Calendar windows are meaningless on
remixed paths. A thin spike of later KPIs around the historical number means
the bootstrap never left the original movie.

Do not reuse `synthetic_daily`; that stub is deterministic unit-test drift.
"""

from __future__ import annotations

import argparse
import math
from datetime import date, datetime, timezone
from typing import Mapping, Sequence

import numpy as np
from arch.bootstrap import StationaryBootstrap, optimal_block_length
from scipy.stats import kurtosis

from price_forecast.series import PriceSeries, load_daily_closes
from price_forecast.weekly_regime import weekly_closes

MEAN_BLOCK_BARS = 182
_FACT_KEYS: tuple[str, ...] = (
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


def remix_daily_closes(
    series: PriceSeries,
    *,
    n_paths: int,
    mean_block_bars: int = MEAN_BLOCK_BARS,
    seed: int = 0,
) -> tuple[PriceSeries, ...]:
    """Remix daily log-returns with arch StationaryBootstrap; keep original dates."""
    if n_paths < 1:
        raise ValueError("n_paths must be at least 1")
    if mean_block_bars < 1:
        raise ValueError("mean_block_bars must be at least 1")
    dates = list(series.dates())
    prices = _close_array(series)
    if prices.size < 2:
        raise ValueError("need at least two daily closes to remix returns")
    log_returns = np.diff(np.log(prices))
    start = float(prices[0])
    bootstrap = StationaryBootstrap(int(mean_block_bars), log_returns, seed=seed)
    paths: list[PriceSeries] = []
    for pos, _kw in bootstrap.bootstrap(n_paths):
        remixed = np.asarray(pos[0], dtype=float)
        rebuilt = np.concatenate(([start], start * np.exp(np.cumsum(remixed))))
        paths.append(PriceSeries(zip(dates, (float(p) for p in rebuilt))))
    return tuple(paths)


def stylized_facts(series: PriceSeries) -> dict[str, float]:
    """Single-path facts the factory must not silently destroy."""
    daily = _close_array(series)
    daily_r = _log_returns(daily)
    weekly = np.array([close for _day, close in weekly_closes(series)], dtype=float)
    weekly_r = _log_returns(weekly)
    return {
        "daily_vol": _sample_vol(daily_r),
        "weekly_vol": _sample_vol(weekly_r),
        "excess_kurtosis": _excess_kurtosis(daily_r),
        "daily_p01": _percentile(daily_r, 1.0),
        "hodl_max_dd": _max_drawdown(daily),
        "acf_daily_1": _acf(daily_r, 1),
        "acf_weekly_1": _acf(weekly_r, 1),
        "acf_weekly_4": _acf(weekly_r, 4),
        "acf_weekly_8": _acf(weekly_r, 8),
    }


def remix_sanity(
    real: PriceSeries,
    paths: Sequence[PriceSeries],
    *,
    iid_paths: Sequence[PriceSeries] = (),
) -> dict[str, object]:
    """Compare real tape vs remixed cloud vs optional mean-block-1 control."""
    report: dict[str, object] = {
        "real": stylized_facts(real),
        "remixed": _summarize_paths(paths),
        "iid_control": _summarize_paths(iid_paths) if iid_paths else None,
    }
    return report


def format_sanity_report(report: Mapping[str, object]) -> str:
    real = report["real"]
    remixed = report["remixed"]
    iid = report["iid_control"]
    if not isinstance(real, dict) or not isinstance(remixed, dict):
        raise TypeError("sanity report is missing real or remixed facts")
    remixed_median = remixed["median"]
    iid_median: Mapping[str, float] | None
    if iid is None:
        iid_median = None
    else:
        if not isinstance(iid, dict):
            raise TypeError("iid_control must be a summary dict or None")
        iid_median = iid["median"]
    lines = [
        "stylized fact       real            remixed median  iid_control median",
    ]
    for key in _FACT_KEYS:
        iid_cell = _fmt(iid_median[key]) if iid_median is not None else "n/a"
        lines.append(
            f"{key:<18} {_fmt(real[key]):<16} {_fmt(remixed_median[key]):<16} {iid_cell}"
        )
    lines.append(f"n_paths remixed={remixed['n']} iid={iid['n'] if isinstance(iid, dict) else 0}")
    return "\n".join(lines)


def format_optimal_block_diagnostic(series: PriceSeries) -> str:
    """arch optimal_block_length is a diagnostic, not the factory default."""
    log_returns = np.diff(np.log(_close_array(series)))
    table = optimal_block_length(log_returns)
    stationary = float(table["stationary"].iloc[0])
    circular = float(table["circular"].iloc[0])
    return (
        "optimal_block_length (diagnostic only; factory default "
        f"MEAN_BLOCK_BARS={MEAN_BLOCK_BARS}):\n"
        f"  stationary={stationary:.4f}\n"
        f"  circular={circular:.4f}"
    )


def main(
    argv: Sequence[str] | None = None,
    series: PriceSeries | None = None,
) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Remix Coinbase BTC daily log-returns with a stationary bootstrap. "
            "Sanity only; does not score SMAGateV1."
        )
    )
    parser.add_argument("--n-paths", type=int, default=1, help="Number of remixed paths.")
    parser.add_argument("--seed", type=int, default=0, help="Bootstrap seed.")
    parser.add_argument(
        "--mean-block-bars",
        type=int,
        default=MEAN_BLOCK_BARS,
        help=f"Mean stationary-bootstrap block length in bars (default {MEAN_BLOCK_BARS}).",
    )
    args = parser.parse_args(argv)
    if series is None:
        series = load_daily_closes(
            source="coinbase",
            start=date(2018, 1, 1),
            end=datetime.now(timezone.utc).date(),
        )
    paths = remix_daily_closes(
        series,
        n_paths=args.n_paths,
        mean_block_bars=args.mean_block_bars,
        seed=args.seed,
    )
    iid_paths = remix_daily_closes(
        series,
        n_paths=args.n_paths,
        mean_block_bars=1,
        seed=args.seed + 1,
    )
    report = remix_sanity(series, paths, iid_paths=iid_paths)
    print(format_sanity_report(report))
    print(format_optimal_block_diagnostic(series))


def _close_array(series: PriceSeries) -> np.ndarray:
    return np.array([series.close_at(day) for day in series.dates()], dtype=float)


def _log_returns(closes: np.ndarray) -> np.ndarray:
    if closes.size < 2:
        return np.array([], dtype=float)
    return np.diff(np.log(closes))


def _sample_vol(returns: np.ndarray) -> float:
    if returns.size < 2:
        return math.nan
    return float(np.std(returns, ddof=1))


def _excess_kurtosis(returns: np.ndarray) -> float:
    if returns.size < 4:
        return math.nan
    return float(kurtosis(returns, fisher=True, bias=False))


def _percentile(returns: np.ndarray, q: float) -> float:
    if returns.size == 0:
        return math.nan
    return float(np.percentile(returns, q))


def _acf(values: np.ndarray, lag: int) -> float:
    if lag < 1 or values.size <= lag:
        return math.nan
    left = values[:-lag]
    right = values[lag:]
    if np.std(left, ddof=1) == 0.0 or np.std(right, ddof=1) == 0.0:
        return math.nan
    return float(np.corrcoef(left, right)[0, 1])


def _max_drawdown(closes: np.ndarray) -> float:
    if closes.size == 0:
        raise ValueError("closes are empty")
    peak = float(closes[0])
    worst = 0.0
    for value in closes:
        price = float(value)
        peak = max(peak, price)
        worst = min(worst, price / peak - 1.0)
    return worst


def _summarize_paths(paths: Sequence[PriceSeries]) -> dict[str, object]:
    if not paths:
        raise ValueError("need at least one path to summarize")
    rows = [stylized_facts(path) for path in paths]
    median = {key: _median([row[key] for row in rows]) for key in _FACT_KEYS}
    return {"n": len(paths), "median": median}


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return float(ordered[len(ordered) // 2])


def _fmt(value: float) -> str:
    if value != value:  # NaN
        return "nan"
    return f"{value:.6g}"


if __name__ == "__main__":
    main()
