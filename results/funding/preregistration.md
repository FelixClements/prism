# Funding-rate event study: pre-registration

Committed on 2026-11-11 **before any forward BTC return was computed against funding**. The results
commit (`results/funding/event_study.md`) must come after this one in git history. The code that
produces the results (`price_forecast/funding/`) is committed together with this file. Any later
change to it is listed under "Deviations" in the results file.

This is a measurement step only: no strategy and no backtest. Any later strategy stays long-only
with no leverage.

## What was looked at before this commit

- Funding prints only: coverage, the timing grid, and the distribution of the 7-day feature
  (deciles, and the share of days tied at the 0.01%/8h default rate: 4.4% Bybit, 5.7% Binance).
- No BTC prices were joined to funding. No forward or trailing returns were computed against any
  funding series.

## Question

Does perpetual-swap funding, a positioning and crowding signal that is not derived from BTC's own
price, sort BTC's forward 1–4 week returns? The prior is contrarian: high funding (crowded longs) is
followed by lower returns. **All tests are two-sided.**

## Data

| Series | Source | Coverage |
|---|---|---|
| Bybit inverse BTCUSD perp funding | `api.bybit.com/v5/market/funding/history`, category `inverse` | 2018-11-15 → |
| Binance BTCUSDT perp funding | `fapi.binance.com/fapi/v1/fundingRate` | 2019-09-10 → |
| BTC-USD daily close | Coinbase, `data/btc-usd-daily.csv` (as in the replay work) | 2018-01-01 → 2026-09-27 |

**BitMEX was replaced before any returns were seen.** The brief named BitMEX XBTUSD, from 2016. BitMEX
stopped trading on 2026-09-23 and its API now returns HTTP 403, so no official free source of its
history remains. The user approved Bybit's inverse BTCUSD perp instead: it is also coin-margined,
like XBTUSD, and it is the longest freely fetchable alternative. Because funding now starts in
2018-11, the study needs no BTC prices from before 2018, and the Coinbase CSV covers the whole sample.

Funding caches are written to `data/funding/<venue>.csv` (git-ignored) by
`python -m price_forecast.funding.fetch`. Both venues settle every 8h at 00:00, 08:00 and 16:00
UTC. The candle CSV is used as-is, ending 2026-09-27, and is not extended for this study.

## Features (signal day D)

1. **Day assignment.** A print's timestamp is rounded to the nearest minute and assigned to its UTC
   calendar day. A print at 00:00 UTC on D+1 belongs to D+1, not to D. Day D therefore uses the
   00:00, 08:00 and 16:00 prints of D, all strictly before D's close at 24:00 UTC.
2. **Daily rate** `daily_v(D) = 3 × mean(prints of venue v on D)`. This equals the sum when all 3
   prints exist. A day with at least one print is valid.
3. **`<venue>_f7(D)`** = mean of `daily_v` over D−6 … D. It is defined only if all 7 days are valid.
4. **`venue_avg_f7(D)`** = mean of `bybit_btcusd_f7(D)` and `binance_btcusdt_f7(D)`. It is defined
   only where both venues are defined (from 2019-09-16).

The three primary features are `bybit_btcusd_f7`, `binance_btcusdt_f7` and `venue_avg_f7`.

## Outcomes

`fwd_h(D) = close(D+h) / close(D) − 1` (simple return), for **h ∈ {7, 14, 21, 28} days**. The
position is entered at D's close, so the first return day is D+1. A cell's sample is every D where
the feature and both closes exist.

## Tests

For each feature × horizon cell:

- **Deciles.** Each feature is bucketed into deciles over all of its days with a Coinbase close
  (D ≤ 2026-09-27). Buckets use average ranks, so tied values always share a decile. The same
  assignment is used at every horizon.
- **Decile means.** `fwd_h` is regressed on the 10 decile dummies with no intercept, using
  Newey-West (Bartlett) covariance with **L = 2h days** and no small-sample correction. Rows are in
  date order. Decile means are the coefficients. Medians are reported as descriptive only.
- **Primary statistic.** The top-minus-bottom spread, β₁₀ − β₁, with its HAC t-stat and two-sided
  normal p-value.
- **Monotonicity.** The Spearman ρ between decile index and decile mean.
- **Slope.** `fwd_h = a + b·z(feature)`, with a full-sample z-score and HAC L = 2h. Report b and t.
- **Incremental slope.** `fwd_h = a + b·z(feature) + c·z(ret_28)`, where `ret_28 = close(D)/close(D−28) − 1`.
  Report the t-stat of b. This asks whether funding adds anything beyond price momentum.

### Multiple testing

- **Primary family:** 3 features × 4 horizons = **12 spread tests**, Holm-adjusted at
  family-wise α = 0.05. Benjamini-Hochberg q-values are reported as well.
- **Secondary family:** the 12 z-slope tests, Holm-adjusted separately.
- Everything else is robustness. It is read for sign consistency only and is not corrected.

### Robustness (descriptive)

- **Subperiods.** Signal date before 2021-01-01 vs from 2021-01-01. Deciles and z-scores are
  re-ranked within each period. Report spread, t, ρ and slope t.
- **Per venue on a common window.** The two venue features restricted to days where both exist.
- **No-lookahead deciles.** Each day is ranked among that feature's values up to and including that
  day. The first 365 days are skipped.
- **Lag sensitivity.** The spread t with L = h.

## Pass/fail bar (fixed now)

A **survivor** is a primary cell with Holm-adjusted p < 0.05. A survivor is **robust** if all of
these hold:

- **(a)** The z-slope has the same sign as the spread, with raw p < 0.05.
- **(b)** The within-period spread has the same sign in both subperiods.
- **(c)** The spread at the same horizon has the same sign for the other venue. For `venue_avg_f7`,
  this applies to both venues.
- **(d)** Spearman ρ has the same sign as the spread, and |ρ| ≥ 0.6.
- **(e)** The spread from no-lookahead deciles has the same sign.

The verdict is one of:

- **PASS:** at least one robust survivor.
- **FRAGILE:** survivors exist, but none is robust.
- **FAIL:** no survivors.

**Gate to a later strategy step:** PASS, **and** at least one robust survivor whose incremental
slope (controlling for the 28-day return) has the same sign with raw p < 0.05. Any sign can qualify.
A long-only book can use either sign by cutting exposure in the bad deciles.

## Out of scope

- No trading rule, sizing or backtest.
- No other venues, no open-interest or basis features, and no other lookbacks than 7 days.
- These may be proposed later as new, separately pre-registered tests.
