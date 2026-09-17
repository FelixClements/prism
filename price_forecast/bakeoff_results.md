# ARIMA+GARCH bakeoff

- Series: daily BTC-USD close from coinbase (UTC).
- History: 2018-01-01 to 2026-09-17 (3182 days).
- ADF p-value on full-sample log-returns (FPP2 hygiene): 0.
- Model: ARIMA(1,0,1) on log-returns (fallback AR(1), then mean); GARCH(1,1) on residuals (fallback EGARCH, then sample variance); invert cumulative log-returns to price.
- Command: `python3 -m price_forecast.bakeoff`
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
