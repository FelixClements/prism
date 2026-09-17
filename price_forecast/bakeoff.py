"""Walk-forward bakeoff: ARIMA+GARCH vs last-value vs zero-return.

Usage:
    python3 -m price_forecast.bakeoff
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from statsmodels.tsa.stattools import adfuller

from price_forecast.harness import HORIZONS, WINDOWS, HorizonResult, evaluate
from price_forecast.predictors import (
    ArimaGarchPredictor,
    LastValuePredictor,
    ZeroReturnPredictor,
)
from price_forecast.series import (
    BTC_CLOSE_PRODUCT,
    BTC_CLOSE_SOURCE,
    BTC_CLOSE_TIMEZONE,
    PriceSeries,
    load_daily_closes,
)


def main() -> None:
    series = load_daily_closes(
        source="coinbase",
        start=date(2018, 1, 1),
        end=datetime.now(timezone.utc).date(),
    )
    adf_p = _full_sample_adf(series)
    models = {
        "last-value": LastValuePredictor(),
        "zero-return": ZeroReturnPredictor(),
        "arima-garch": _Progress(ArimaGarchPredictor()),
    }
    tables = {}
    for name, predictor in models.items():
        print(f"scoring {name}...", flush=True)
        tables[name] = evaluate(series, predictor, windows=WINDOWS, horizons=HORIZONS)
    print(_format_report(series, adf_p, tables))


class _Progress:
    def __init__(self, inner: ArimaGarchPredictor) -> None:
        self.inner = inner
        self.n = 0

    def forecast(self, history, origin, horizons):
        self.n += 1
        if self.n == 1 or self.n % 100 == 0:
            print(f"  origin {origin.isoformat()} ({self.n} fits)", flush=True)
        return self.inner.forecast(history, origin, horizons)


def _full_sample_adf(series: PriceSeries) -> float | None:
    prices = [series.close_at(day) for day in series.dates()]
    if len(prices) < 32:
        return None
    import math

    log_returns = [
        math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))
    ]
    try:
        return float(adfuller(log_returns, autolag="AIC", result_object=True).pvalue)
    except (TypeError, ValueError):
        return float(adfuller(log_returns, autolag="AIC")[1])


def _format_report(
    series: PriceSeries,
    adf_p: float | None,
    tables: dict[str, list[HorizonResult]],
) -> str:
    first, last = series.dates()[0], series.dates()[-1]
    lines = [
        "# ARIMA+GARCH bakeoff",
        "",
        f"- Series: daily {BTC_CLOSE_PRODUCT} close from {BTC_CLOSE_SOURCE} ({BTC_CLOSE_TIMEZONE}).",
        f"- History: {first.isoformat()} to {last.isoformat()} ({len(series.dates())} days).",
        f"- ADF p-value on full-sample log-returns (FPP2 hygiene): {_fmt_p(adf_p)}.",
        "- Model: ARIMA(1,0,1) on log-returns (fallback AR(1), then mean); "
        "GARCH(1,1) on residuals (fallback EGARCH, then sample variance); "
        "invert cumulative log-returns to price.",
        "- No order search against the bakeoff table. No trading P&L.",
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
            "| Horizon | ARIMA MAE | LV MAE | ZR MAE | ARIMA MAPE | LV MAPE | "
            "Hit | Cov80 | Cov90 | Beat LV | Beat ZR |"
        )
        lines.append(
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"
        )
        wins_all = True
        for horizon in HORIZONS:
            arima = by_key["arima-garch"][(window, horizon)]
            last_value = by_key["last-value"][(window, horizon)]
            zero = by_key["zero-return"][(window, horizon)]
            beat_lv = arima.mae < last_value.mae
            beat_zr = arima.mae < zero.mae
            wins_all = wins_all and beat_lv and beat_zr
            lines.append(
                "| {h}d | {amae} | {lmae} | {zmae} | {amape} | {lmape} | {hit} | "
                "{c80} | {c90} | {blv} | {bzr} |".format(
                    h=horizon,
                    amae=_fmt_num(arima.mae),
                    lmae=_fmt_num(last_value.mae),
                    zmae=_fmt_num(zero.mae),
                    amape=_fmt_pct(arima.mape),
                    lmape=_fmt_pct(last_value.mape),
                    hit=_fmt_pct(arima.hit_rate),
                    c80=_fmt_pct(arima.coverage_80),
                    c90=_fmt_pct(arima.coverage_90),
                    blv="yes" if beat_lv else "no",
                    bzr="yes" if beat_zr else "no",
                )
            )
        window_pass[window] = wins_all
        lines.append("")
        lines.append(
            f"Window {window}: ARIMA+GARCH "
            f"{'beats' if wins_all else 'does not beat'} last-value and zero-return "
            "on MAE at every horizon."
        )
        lines.append("")
    spec_pass = all(window_pass.values())
    lines.append("## Frozen spec")
    lines.append("")
    lines.append(
        "**Pass** requires ARIMA+GARCH MAE below last-value and zero-return "
        "at every horizon in both windows."
    )
    lines.append("")
    lines.append(f"**Verdict: {'PASS' if spec_pass else 'FAIL'}.**")
    if not spec_pass:
        lines.append("")
        lines.append("It lost. No tuning was applied to chase a win.")
    lines.append("")
    return "\n".join(lines)


def _fmt_num(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{100.0 * value:.1f}%"


def _fmt_p(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4g}"


if __name__ == "__main__":
    main()
