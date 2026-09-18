"""Walk-forward bakeoff: Chronos-2 vs last-value vs zero-return.

Usage:
    python3 -m price_forecast.bakeoff
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from price_forecast.chronos import ChronosPredictor
from price_forecast.harness import HORIZONS, WINDOWS, HorizonResult, evaluate
from price_forecast.predictors import LastValuePredictor, ZeroReturnPredictor
from price_forecast.series import (
    BTC_CLOSE_PRODUCT,
    BTC_CLOSE_SOURCE,
    BTC_CLOSE_TIMEZONE,
    load_daily_closes,
)


def main() -> None:
    series = load_daily_closes(
        source="coinbase",
        start=date(2018, 1, 1),
        end=datetime.now(timezone.utc).date(),
    )
    chronos = ChronosPredictor()
    models = {
        "last-value": LastValuePredictor(),
        "zero-return": ZeroReturnPredictor(),
        "chronos": _Progress(chronos),
    }
    tables = {}
    for name, predictor in models.items():
        print(f"scoring {name}...", flush=True)
        tables[name] = evaluate(series, predictor, windows=WINDOWS, horizons=HORIZONS)
    print(
        _format_report(
            series,
            tables,
            checkpoint=chronos.checkpoint,
            device_map=chronos.device_map or "unloaded",
            library_version=_chronos_version(),
        )
    )


class _Progress:
    def __init__(self, inner: ChronosPredictor) -> None:
        self.inner = inner
        self.n = 0

    def forecast(self, history, origin, horizons):
        self.n += 1
        if self.n == 1 or self.n % 100 == 0:
            print(f"  origin {origin.isoformat()} ({self.n} forecasts)", flush=True)
        return self.inner.forecast(history, origin, horizons)


def _format_report(
    series,
    tables: dict[str, list[HorizonResult]],
    *,
    checkpoint: str,
    device_map: str,
    library_version: str,
) -> str:
    first, last = series.dates()[0], series.dates()[-1]
    lines = [
        "# Chronos-2 bakeoff",
        "",
        f"- Series: daily {BTC_CLOSE_PRODUCT} close from {BTC_CLOSE_SOURCE} ({BTC_CLOSE_TIMEZONE}).",
        f"- History: {first.isoformat()} to {last.isoformat()} ({len(series.dates())} days).",
        f"- Model: zero-shot {checkpoint} via chronos-forecasting {library_version} "
        "on the univariate close series.",
        f"- Device: {device_map}.",
        "- Point forecast is the 0.5 quantile. No extra features. No conformal floor.",
        "- Command: `python3 -m price_forecast.bakeoff`",
        "- No hyperparameter search against the bakeoff table. No trading P&L.",
        "",
    ]
    by_key = {
        name: {(row.window, row.horizon_days): row for row in rows}
        for name, rows in tables.items()
    }
    window_pass: dict[str, bool] = {}
    for window in WINDOWS:
        lines.append(f"## {window}")
        lines.append("")
        lines.append(
            "| Horizon | Chronos MAE | LV MAE | ZR MAE | Chronos MAPE | LV MAPE | "
            "Hit | Cov80 | Cov90 | Beat LV | Beat ZR |"
        )
        lines.append(
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"
        )
        wins_all = True
        for horizon in HORIZONS:
            chronos = by_key["chronos"][(window, horizon)]
            last_value = by_key["last-value"][(window, horizon)]
            zero = by_key["zero-return"][(window, horizon)]
            beat_lv = chronos.mae < last_value.mae
            beat_zr = chronos.mae < zero.mae
            wins_all = wins_all and beat_lv and beat_zr
            lines.append(
                "| {h}d | {cmae} | {lmae} | {zmae} | {cmape} | {lmape} | {hit} | "
                "{c80} | {c90} | {blv} | {bzr} |".format(
                    h=horizon,
                    cmae=_fmt_num(chronos.mae),
                    lmae=_fmt_num(last_value.mae),
                    zmae=_fmt_num(zero.mae),
                    cmape=_fmt_pct(chronos.mape),
                    lmape=_fmt_pct(last_value.mape),
                    hit=_fmt_pct(chronos.hit_rate),
                    c80=_fmt_pct(chronos.coverage_80),
                    c90=_fmt_pct(chronos.coverage_90),
                    blv="yes" if beat_lv else "no",
                    bzr="yes" if beat_zr else "no",
                )
            )
        window_pass[window] = wins_all
        lines.append("")
        lines.append(
            f"Window {window}: Chronos-2 "
            f"{'beats' if wins_all else 'does not beat'} last-value and zero-return "
            "on MAE at every horizon."
        )
        lines.append("")
    spec_pass = all(window_pass.values())
    lines.append("## Frozen spec")
    lines.append("")
    lines.append(
        "**Pass** requires Chronos-2 MAE below last-value and zero-return "
        "at every horizon in both windows."
    )
    lines.append("")
    lines.append(f"**Verdict: {'PASS' if spec_pass else 'FAIL'}.**")
    if not spec_pass:
        lines.append("")
        lines.append(
            "It lost. No tuning was applied to chase a win. "
            "The dollar-close prediction idea is dead."
        )
    lines.append("")
    return "\n".join(lines)


def _chronos_version() -> str:
    try:
        import chronos

        return str(getattr(chronos, "__version__", "unknown"))
    except ImportError:
        return "not-installed"


def _fmt_num(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{100.0 * value:.1f}%"


if __name__ == "__main__":
    main()
