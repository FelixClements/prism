# Residual Edge Analysis

**Status:** RESIDUAL_FRAGILE
**Decision eligibility:** REVIEW_REQUIRED
**Period:** 2018-06-24 to 2026-09-27 (432 observations)
**Primary model:** hodl

## Primary Model

| Metric | Value |
|---|---:|
| R² | 0.6050 |
| Adjusted R² | 0.6041 |
| Annualized alpha | 17.4518% |
| Alpha HAC t-stat | 1.655 |
| Annualized residual volatility | 29.5888% |
| Residual edge ratio | 0.590 |

## Baseline Loadings

| Baseline | Loading | HAC t-stat | VIF |
|---|---:|---:|---:|
| hodl_return | 0.6076 | 9.109 | 1.000 |

## Model Sensitivity

| Model | Role | R² | Annualized alpha | Residual edge ratio | Status |
|---|---|---:|---:|---:|---|
| hodl | primary | 0.6050 | 17.4518% | 0.590 | RESIDUAL_FRAGILE |
| lagged_momentum | sensitivity | 0.0116 | 43.3619% | 0.926 | RESIDUAL_EDGE |
| hodl_plus_momentum | sensitivity | 0.6054 | 16.7794% | 0.567 | RESIDUAL_FRAGILE |

## Evidence Warnings

- **HIGH — NOT_OUT_OF_SAMPLE:** Treat in-sample residual edge as exploratory until confirmed out of sample.

## Regime Breakdown

### vol_regime

| Regime | N | Evidence | Annualized active return | Active Sharpe |
|---|---:|---|---:|---:|
| high | 50 | ADEQUATE | 22.4602% | 0.660 |
| low | 382 | ADEQUATE | 16.7962% | 0.579 |

## Interpretation

- Residual evidence does not clear all robustness thresholds.
- Diagnostic status changes under alternate declared baselines.
- This report does not authorize a trade or an automatic exposure change.
- Confirm exploratory findings on untouched out-of-sample or live data.
