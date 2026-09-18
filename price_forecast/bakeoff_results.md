# Bakeoff results

ARIMA+GARCH was the classical baseline (PR #2). Chronos-2 is the univariate foundation-model follow-up. Same Coinbase BTC-USD daily close (UTC), same windows, same 1/3/7/10-day dollar MAE vs last-value and zero-return. Neither model is retuned against this table.

---

# ARIMA+GARCH bakeoff

- Series: daily BTC-USD close from coinbase (UTC).
- History: 2018-01-01 to 2026-09-17 (3182 days).
- ADF p-value on full-sample log-returns (FPP2 hygiene): 0.
- Model: ARIMA(1,0,1) on log-returns (fallback AR(1), then mean); GARCH(1,1) on residuals (fallback EGARCH, then sample variance); invert cumulative log-returns to price.
- Command: `python3 -m price_forecast.bakeoff` (historical; the entry point now runs Chronos-2)
- No order search against the bakeoff table. No trading P&L.

## 2022

| Horizon | ARIMA MAE | LV MAE | ZR MAE | ARIMA MAPE | LV MAPE | Hit | Cov80 | Cov90 | Beat LV | Beat ZR |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1d | 660.93 | 657.47 | 657.47 | 2.3% | 2.3% | 48.5% | 88.5% | 93.4% | no | no |
| 3d | 1,219.48 | 1,214.66 | 1,214.66 | 4.3% | 4.2% | 48.8% | 87.4% | 91.8% | no | no |
| 7d | 1,824.13 | 1,800.59 | 1,800.59 | 6.5% | 6.4% | 46.3% | 86.6% | 92.1% | no | no |
| 10d | 2,254.04 | 2,222.72 | 2,222.72 | 8.0% | 7.9% | 48.5% | 87.9% | 93.2% | no | no |

Window 2022: ARIMA+GARCH does not beat last-value and zero-return on MAE at every horizon.

## 2024-2026

| Horizon | ARIMA MAE | LV MAE | ZR MAE | ARIMA MAPE | LV MAPE | Hit | Cov80 | Cov90 | Beat LV | Beat ZR |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1d | 1,377.61 | 1,379.30 | 1,379.30 | 1.8% | 1.8% | 51.6% | 88.5% | 93.4% | yes | yes |
| 3d | 2,443.73 | 2,448.40 | 2,448.40 | 3.1% | 3.1% | 52.5% | 89.2% | 94.6% | yes | yes |
| 7d | 3,732.91 | 3,721.73 | 3,721.73 | 4.8% | 4.7% | 52.4% | 90.9% | 95.1% | no | no |
| 10d | 4,507.20 | 4,471.75 | 4,471.75 | 5.7% | 5.7% | 52.4% | 90.9% | 94.5% | no | no |

Window 2024-2026: ARIMA+GARCH does not beat last-value and zero-return on MAE at every horizon.

## Frozen spec

**Pass** requires ARIMA+GARCH MAE below last-value and zero-return at every horizon in both windows.

**Verdict: FAIL.**

It lost. No tuning was applied to chase a win.

---

# Chronos-2 bakeoff

- Series: daily BTC-USD close from coinbase (UTC).
- History: 2018-01-01 to 2026-09-17 (3182 days).
- Model: zero-shot `amazon/chronos-2` via chronos-forecasting 2.3.2 on the univariate close series.
- Device: mps (Apple GPU). CUDA was not available. Point forecast is the 0.5 quantile.
- No extra features. No conformal floor. No hyperparameter search.
- Command: `python3 -m price_forecast.bakeoff`
- Last-value MAE in 2024–2026 differs by a few cents from the ARIMA table because today's Coinbase candle moved between runs.

## 2022

| Horizon | Chronos MAE | LV MAE | ZR MAE | Chronos MAPE | LV MAPE | Hit | Cov80 | Cov90 | Beat LV | Beat ZR |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1d | 766.34 | 657.47 | 657.47 | 2.7% | 2.3% | 47.1% | 75.6% | 86.8% | no | no |
| 3d | 1,330.47 | 1,214.66 | 1,214.66 | 4.7% | 4.2% | 42.7% | 75.9% | 87.9% | no | no |
| 7d | 1,929.51 | 1,800.59 | 1,800.59 | 6.9% | 6.4% | 50.1% | 80.5% | 89.0% | no | no |
| 10d | 2,385.70 | 2,222.72 | 2,222.72 | 8.5% | 7.9% | 51.0% | 82.2% | 91.8% | no | no |

Window 2022: Chronos-2 does not beat last-value and zero-return on MAE at every horizon.

## 2024-2026

| Horizon | Chronos MAE | LV MAE | ZR MAE | Chronos MAPE | LV MAPE | Hit | Cov80 | Cov90 | Beat LV | Beat ZR |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1d | 1,472.55 | 1,379.18 | 1,379.18 | 1.9% | 1.8% | 52.2% | 83.1% | 90.3% | no | no |
| 3d | 2,508.94 | 2,448.52 | 2,448.52 | 3.2% | 3.1% | 52.0% | 73.1% | 83.5% | no | no |
| 7d | 3,831.63 | 3,721.61 | 3,721.61 | 4.9% | 4.7% | 49.7% | 69.8% | 82.6% | no | no |
| 10d | 4,624.47 | 4,471.87 | 4,471.87 | 5.9% | 5.7% | 50.6% | 70.1% | 82.5% | no | no |

Window 2024-2026: Chronos-2 does not beat last-value and zero-return on MAE at every horizon.

| Window | Horizon | Chronos MAE | Last-value MAE | Beat both? |
| --- | ---: | ---: | ---: | --- |
| 2022 | 1d | 766.34 | 657.47 | no |
| 2022 | 3d | 1,330.47 | 1,214.66 | no |
| 2022 | 7d | 1,929.51 | 1,800.59 | no |
| 2022 | 10d | 2,385.70 | 2,222.72 | no |
| 2024-2026 | 1d | 1,472.55 | 1,379.18 | no |
| 2024-2026 | 3d | 2,508.94 | 2,448.52 | no |
| 2024-2026 | 7d | 3,831.63 | 3,721.61 | no |
| 2024-2026 | 10d | 4,624.47 | 4,471.87 | no |

## Frozen spec

**Pass** requires Chronos-2 MAE below last-value and zero-return at every horizon in both windows.

**Verdict: FAIL.**

It lost. No tuning was applied to chase a win. The dollar-close prediction idea is dead.
