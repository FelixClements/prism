# What protection problem is still real after the dollar-close bakeoff failed

**Date:** 2026-09-17  
**Scope:** Product/research notes for Prism. Not investment advice. No recommendation to buy, sell, hedge, or size a Bitcoin position.  
**Question:** The intended user goal is to hold BTC for long-horizon wealth, with some protection against a ~50% drop (cited as happening “this year”). Point-forecasting the dollar close already failed. What protection problem is real, what Prism already claimed, and what is actually knowable?

**Sources of truth used:** this repo (README, `price_forecast/`, PRs), Coinbase Exchange public daily candles (same loader as the bakeoff), first-party exchange/product docs, Chronos-2 and Adaptive Conformal Inference papers. Secondary write-ups were not used as evidence.

**Where this lives:** the repo had no research-notes folder. The only existing measured note is `price_forecast/bakeoff_results.md` (a scoreboard, not a brief). This file is therefore under `docs/research/`. It was not committed.

**No implementation was done.** Drawdown numbers below were computed from Coinbase candles on 2026-09-17 with the existing loader; the computation scripts were not added to the repo.

---

## 1. Prism context: claimed vs measured

### What the README said the product was

`README.md` (commit `be22a81`, 2026-09-15, “added research”) is a blueprint, not running code. The title claims a “Production-grade Bitcoin (BTC) 3–14d swing forecasting engine” that “Combines foundation models (Chronos-2, TimesFM), MODWT wavelet denoising, on-chain fundamentals, and adaptive conformal safety floors” ([README.md](../../README.md) lines 3–5). The GitHub repo description on PRs #1 and #2 repeats that sentence ([PR #1](https://github.com/FelixClements/prism/pull/1), [PR #2](https://github.com/FelixClements/prism/pull/2)).

The pipeline diagram ends in **Execution & Dynamic Safety Floor**: “Volatility-Adjusted Stop-Loss (q0.1)”, “ATR & Chaikin Volatility Scaling”, “Alpha Sizing via Expected Shortfall” ([README.md](../../README.md) lines 73–78).

The **Dynamic Safety Floor** section is explicit about *automated selling*, not a warning:

- Translate the ensemble 0.1 quantile into a “volatility-adjusted stop-loss execution strategy” ([README.md](../../README.md) lines 566–568).
- Statistical floor: `DD_stat(t,h) = (P_t − ŷ_{t,h}^{ens}(0.1)) / P_t` over a 3-to-14-day horizon ([README.md](../../README.md) lines 618–621).
- Buffer with ATR and expected shortfall; snap to a liquidity cluster; **monotonic trailing** `StopLoss_final(t) = max(StopLoss_final(t−1), Floor_exec(t))` ([README.md](../../README.md) lines 623–640).
- If price ≤ stop: “Immediate Market-De-Risk”, cancel bids, execute IOC ([README.md](../../README.md) lines 609–611).
- Half-Kelly size from the quantile spread; abort the order if `DD_stat > RiskMax` ([README.md](../../README.md) lines 642–647).

The **Minimum Viable Pipeline** keeps one foundation model (Amazon Chronos-2), conformal calibration on the 0.1 quantile, an ATR-buffered safety-floor stop-loss, and half-Kelly sizing ([README.md](../../README.md) lines 714–766). The stated rationale: “Retain the automated safety floor. Running adaptive conformal prediction on the 0.1 quantile from Chronos-2 creates a mathematically grounded stop-loss” ([README.md](../../README.md) lines 765–766).

Adaptive conformal inference is cited as Gibbs & Candès (2021), with the README update `α_{t+1} = α_t + γ(β − err_t)` targeting a 90% interval (`β = 0.1`) ([README.md](../../README.md) lines 557–562, bibliography item 7). That formula matches the paper ([arXiv:2106.00170](https://arxiv.org/abs/2106.00170), eq. 2).

The README’s own critique already flags a failure mode that later showed up on the scoreboard: foundation models “regress to the conditional mean” and “predict horizontal lines during regime consolidations, missing violent volatility expansions” ([README.md](../../README.md) lines 655–657).

**Dump / drawdown language in the repo:** the word “dump” does not appear in code. “Drawdown” appears in the README floor formula above. PR #2’s body states the work “does not implement the README ensemble, Chronos, RL, or dump/drawdown logic” ([PR #2](https://github.com/FelixClements/prism/pull/2)). The matching commit message: “No Chronos, RL, or dump logic” (`13b955a`).

### What was actually built

| Artifact | What it is | What it is not |
| --- | --- | --- |
| `price_forecast/harness.py` | Walk-forward loop: at day `t`, forecast `t+1/3/7/10` from data ≤ `t`. Score MAE, MAPE, hit rate, 80%/90% coverage of the later *close*. Windows: 2022 and 2024–2026. | Not 3–14d swing P&L. Not a safety floor. Not dump classification. |
| `price_forecast/predictors.py` | Last-value, zero-return, ARIMA+GARCH (log-returns → price; GARCH/EGARCH Gaussian bands). | Last-value has no bands. No conformal. |
| `price_forecast/chronos.py` (uncommitted as of this note) | Zero-shot `amazon/chronos-2`; point = 0.5 quantile; 80% band = 0.1–0.9; 90% band = 0.05–0.95. Univariate close only. | No covariates, no conformal floor. |
| `price_forecast/series.py` | Coinbase Exchange public daily candles, product `BTC-USD`, granularity 86400, UTC. | Loader stores **close only**; high/low exist on the wire but are discarded. |
| `price_forecast/__init__.py` | “Walk-forward scoreboard for short-horizon Bitcoin price forecasts. **Not the README ensemble.**” | — |
| `pyproject.toml` | Package name `price-forecast`; description “Walk-forward harness for short-horizon Bitcoin price forecasts.” | — |

[PR #1](https://github.com/FelixClements/prism/pull/1) (merged 2026-09-17): “the scoreboard for a short-horizon Bitcoin **price** forecast. It does not fit ARIMA yet, and it does not implement the README ensemble.” Pass/fail frozen: beat last-value **and** zero-return on MAE in **both** windows.

[PR #2](https://github.com/FelixClements/prism/pull/2) (merged 2026-09-17): Coinbase series + ARIMA+GARCH + bakeoff table. Explicitly no ensemble, Chronos, RL, or dump/drawdown. “No trading P&L.”

Recent git log on `main` (through this note): `d50d5b9` Initial commit → `be22a81` added research → `8d6a1af` / PR #1 harness → `13b955a`+`6e3706c` / PR #2 ARIMA+GARCH. Chronos files exist in the working tree and are not on `main`.

### What the bakeoff actually measured

Both models were scored on **dollar MAE of the point forecast** against last-value and zero-return. Those two naive predictors are the same point (“price does not move”), so their MAE matches (`price_forecast/predictors.py` `LastValuePredictor` / `ZeroReturnPredictor`; [PR #2](https://github.com/FelixClements/prism/pull/2)).

Coverage is a *secondary* column: fraction of later closes that fell inside the 80%/90% band (`price_forecast/harness.py` `_coverage`). Pass/fail ignored coverage.

Numbers from [`price_forecast/bakeoff_results.md`](../../price_forecast/bakeoff_results.md) (series: Coinbase BTC-USD daily close UTC, history 2018-01-01 to 2026-09-17, 3182 days — same count this note re-downloaded):

**ARIMA+GARCH lost the frozen MAE spec.** 2022: MAE worse than last-value at every horizon (e.g. 1d 660.93 vs 657.47). 2024–2026: won 1d and 3d by a few dollars, lost 7d and 10d. Hit rate 46–53%. **Verdict: FAIL.**

**GARCH bands were slightly wide, not empty.** 80% coverage 86.6–90.9%; 90% coverage 91.8–95.1%. That is *over*-coverage relative to the nominal 80/90 labels (Gaussian log-return intervals from `norm.ppf` in `price_forecast/predictors.py`).

**Chronos-2 also lost the frozen MAE spec at every horizon in both windows.** 2022 1d: 766.34 vs last-value 657.47. 2024–2026 1d: 1,472.55 vs 1,379.18. Hit rate 43–52%. The bakeoff entry point states “Point forecast is the 0.5 quantile. No extra features. No conformal floor.” (`price_forecast/bakeoff.py`). **Verdict: FAIL.** “The dollar-close prediction idea is dead.”

**Chronos bands were not well calibrated on this series.** 2022 Cov80 75.6–82.2% (near or under 80%); 2024–2026 Cov80 69.8–83.1%, Cov90 82.5–90.3% — *under*-coverage, worse at 7d/10d. Official Chronos-2 emits 21 trained quantiles including 0.01 and 0.99 and is trained with pinball loss ([arXiv:2510.15821](https://arxiv.org/abs/2510.15821) §architecture: “The inclusion of extreme quantiles (0.01 and 0.99) improves coverage of rare events”). Prism asked for 0.05/0.1/0.5/0.9/0.95 via `predict_quantiles` (`price_forecast/chronos.py`). Uncalibrated quantiles are not a coverage guarantee; that is exactly the gap ACI is designed to wrap ([arXiv:2106.00170](https://arxiv.org/abs/2106.00170) abstract).

**Claimed vs measured (one line):** README promised a conformal 0.1-quantile *stop that sells*; the harness measured whether a *median dollar guess* beat “tomorrow equals today.” Coverage of bands was recorded and never used as the pass rule. Dump/floor/conformal/P&L were never scored.

---

## 2. 50% drops in BTC (Coinbase BTC-USD, this loader)

**Data.** Same primary source as the bakeoff: Coinbase Exchange `GET /products/BTC-USD/candles` with `granularity=86400` ([Coinbase: Get product candles](https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles); wired in `price_forecast/series.py`). Official candle schema is `[timestamp, price_low, price_high, price_open, price_close]` plus volume. Unix `time` is UTC. Prism’s `bars_from_coinbase_candles` keeps **close only**. High/low figures below were taken from the same endpoint without changing the loader.

Series as of 2026-09-17 UTC: **3182** daily closes, **2018-01-01** close **13,480.01** through **2026-09-17** close **76,808.57**. That matches `bakeoff_results.md` (3182 days, 2018-01-01 to 2026-09-17).

Drawdown = peak-to-subsequent-trough on the running maximum. Close-to-close uses daily closes. High-to-low uses that window’s running daily **high** vs later daily **low** (a slightly deeper hole; still not tick data).

### The ~50% “this year” claim

**Calendar 2026 (2026-01-01 through 2026-09-17) does not contain a ~50% close-to-close drawdown.**

| Window | Peak | Trough | Drop | Duration |
| --- | --- | --- | ---: | ---: |
| 2026 YTD, close-to-close | 2026-01-14 close 96,955.16 | 2026-06-30 close 58,523.93 | **−39.64%** | 167 days |
| 2026 YTD, high-to-low | 2026-01-14 high 97,963.62 | 2026-07-01 low 57,717.55 | **−41.08%** | 168 days |

Worst 10-day close-to-close hole *ending* in 2026 YTD: **−28.85%** (2026-01-26 88,250.01 → 2026-02-05 62,791.00). Worst 1-day close in 2026: **−13.98%** on 2026-02-05. That is the only ≤ −10% daily close in 2025–2026 YTD in this series.

**A ~50% drop *does* appear if “this year” is read as the trailing year / the 2025–2026 path, not calendar 2026:**

| Window | Peak | Trough | Drop | Duration |
| --- | --- | --- | ---: | ---: |
| 2025-10-06 → 2026-06-30, close-to-close | 2025-10-06 close 124,720.09 | 2026-06-30 close 58,523.93 | **−53.08%** | 267 days |
| Same path, high-to-low | 2025-10-06 high 126,296.00 | 2026-07-01 low 57,717.55 | **−54.30%** | 268 days |
| Trailing 365d from 2026-09-17 | same peak/trough | same | **−53.08%** close | 267 days |

Calendar **2025** alone: max close-to-close drawdown **−32.10%** (2025-10-06 124,720.09 → 2025-11-22 84,684.00, 47 days). That is a steep autumn leg *inside* the longer 53% path; it is not itself 50%.

**Plain statement:** in this Coinbase series, “~50% this year” is false for calendar 2026 (~40%) and true for the Oct 2025 → Jun 2026 peak-to-trough (~53% over ~9 months). The user-cited example is a **multi-month path**, not a 10-day crash.

### 2022 (and the 2021–2022 cycle)

2022 as a *calendar year* starts already off the 2021 high. The bakeoff window 2022 is 2022-01-01..2022-12-31 (`price_forecast/harness.py` `WINDOWS`).

| Window | Peak | Trough | Drop | Duration |
| --- | --- | --- | ---: | ---: |
| 2022 calendar, close-to-close | 2022-01-01 close 47,733.43 | 2022-11-21 close 15,760.14 | **−66.98%** | 324 days |
| 2021-11-08 ATH through 2022 trough, close-to-close | 2021-11-08 close 67,554.84 | 2022-11-21 close 15,760.14 | **−76.67%** | 378 days |
| Same, high-to-low | 2021-11-10 high 69,000.00 | 2022-11-21 low 15,460.00 | **−77.59%** | 376 days |

That 2021 peak was not recovered until **2024-03-04** on this close series (first later close ≥ 67,554.84).

2022 had several ≤ −10% daily closes (still not 50% days): 2022-01-21 −10.36%; 2022-05-09 −11.61%; 2022-06-13 −15.42%; 2022-08-19 −10.15%; 2022-11-09 −14.33%. Worst 10-day close hole in the full sample that sits in 2022: **−37.21%** (2022-06-08 30,177.00 → 2022-06-18 18,948.89).

### Other notable close-to-close drawdowns (2018–now)

| Window | Peak | Trough | Drop | Duration |
| --- | --- | --- | ---: | ---: |
| Full sample max | 2018-01-06 17,098.99 | 2018-12-15 3,183.00 | **−81.38%** | 343 days |
| 2020 (COVID) | 2020-02-14 10,371.33 | 2020-03-12 4,857.10 | **−53.17%** | 27 days |
| 2021 (mid-year) | 2021-04-13 63,588.22 | 2021-07-20 29,796.16 | **−53.14%** | 98 days |
| 2023 | 2023-07-13 31,471.83 | 2023-09-11 25,152.14 | −20.08% | 60 days |
| 2024 | 2024-03-13 73,135.04 | 2024-09-06 53,950.01 | −26.23% | 177 days |

Worst 1-day close in the sample: **−38.81%** on 2020-03-12 (7,938.05 → 4,857.10). Worst 10-day close hole: **−45.52%** (2020-03-02 → 2020-03-12). **Every 10-day close hole of −40% or worse in 2018–2026-09-17 is in March 2020.** There is no −40% 10-day close hole in 2022 or in 2025–2026.

That matters for product language. “Don’t be surprised by a 40% 10-day hole” is a statement about March 2020 (and, slightly weaker, June 2022 at ~37%). The 2022 and 2025–2026 ~50%+ events are **slow**. A 10-day q0.1 floor, even if calibrated, is a different object from “protect a 9-month 53% path.”

---

## 3. What “protection” can mean (tied to things that are not beating last-value)

None of the following requires a better dollar-close point forecast than last-value. Each is framed as a *product problem*, not a portfolio instruction.

### A. Volatility / prediction bands / conformal floor

**What it is.** A statement of the form: “given history ≤ t, a 10-day close of X is outside the usual set.” GARCH already emits 80/90% price bands; Chronos-2 already emits quantile paths; ACI is a wrapper that adjusts the quantile level online so that, over long intervals, the *next label* falls in the set about 1−α of the time, even under distribution shift ([arXiv:2106.00170](https://arxiv.org/abs/2106.00170) abstract and eq. 2). Chronos-2’s own API is `predict_quantiles(..., quantile_levels=...)` ([amazon-science/chronos-forecasting](https://github.com/amazon-science/chronos-forecasting) README; Context7 `/amazon-science/chronos-forecasting` `predict_quantiles` docs).

**Prism hook.** Yes, partial. `Forecast.lower_80/90` exists. Harness already scores coverage. README MVP is exactly “conformal on Chronos 0.1 + ATR buffer.” **Not built:** ACI, ATR buffer, stop, monotonic trail.

**Point-forecast failure relevant?** Only weakly. Median MAE can fail while interval coverage is still a real question. GARCH already demonstrates the split: lost MAE, kept (slightly wide) coverage. Chronos lost both the median *and* under-covered in 2024–2026, so a raw Chronos 0.1 quantile is **not** currently a trustworthy floor on this series.

**Honest limit.** Coverage is “the close at t+h fell inside the band h days ago” (`harness.py` `_coverage`). It is **not** “the position will not drop 50%.” A calibrated 90% 10-day band can be ~tens of percent wide (last-value 10d MAPE is 7.9% in 2022 and 5.7% in 2024–2026 per `bakeoff_results.md`) and still miss a 50% *multi-month* path, because that path is many 10-day steps, each maybe inside the band.

### B. Drawdown / regime / path classifiers

**What it is.** Detect that a peak-to-trough process is underway (or that the market has changed regime), without naming tomorrow’s dollar close. The 2025-10-06 → 2026-06-30 −53% path spent 267 days below the peak. A classifier that only fires on the dump *day* is the thing this research is not claiming is knowable.

**Prism hook.** Named, not built. PR #2: “does not implement … dump/drawdown logic.” README Part 3 lists changepoint detection (BOCPD) as a missing mitigation for non-stationary regime shifts ([README.md](../../README.md) line 660). On-chain NUPL/SOPR/MVRV are specified for the MVP and not wired (`series.py` has no on-chain client).

**Point-forecast failure relevant?** No. Last-value being the best *price* guess does not decide whether a drawdown state is detectable from the same close path (or from features the bakeoff never used).

**Honest limit.** A path detector that waits for −20% from a peak will, by construction, already have lost 20% before it speaks. That can still be a *warning* product. It is not a predictor of the first down day.

### C. Trend / time-under-peak filters

**What it is.** Rules on “close vs N-day high” or “days since peak,” used to change *whether Prism talks* (warning) or *whether a floor is armed* (execution), not to guess t+7 dollars.

**Prism hook.** None in code. README trailing floor is monotonic once a trade exists; it is not a regime filter for entering a long-term hold.

**Point-forecast failure relevant?** No.

### D. Position sizing from interval width

**What it is.** README half-Kelly: `f_t* = ½ · (ŷ(0.5) − P_t) / [ŷ(0.9) − ŷ(0.1)]²` ([README.md](../../README.md) lines 642–645). The **denominator** is an uncertainty width. The **numerator** is an assumed edge vs spot.

**Prism hook.** Specified, not built.

**Point-forecast failure relevant?** **Yes, for the numerator.** If ŷ(0.5) cannot beat last-value, then (ŷ(0.5) − P_t) is not a measured edge; using it as Kelly “alpha” would be dressing the failed point-forecast as a size. The denominator (band width) can still be a *risk* input without claiming edge. Those are different product questions.

### E. Venue-native stops (automated selling of spot)

**What it is.** Coinbase Exchange stop orders trigger on last trade price: `stop: 'loss'` when last trade ≤ `stop_price`, then execute as a **limit** ([Coinbase Exchange: Create a new order — Stop Orders](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/orders/create-new-order)). Advanced Trade documents `stop_limit_stop_limit_gtc/gtd` and bracket/TP-SL orders, and states “Execution of downside protection is not guaranteed during high market volatility” ([Advanced API Order Management](https://docs.cdp.coinbase.com/coinbase-business/advanced-trade-apis/guides/orders)). Coinbase Global Derivatives (Deribit-powered gateway) lists `stop_market`, `stop_limit`, and `trailing_stop` ([Global Derivatives Overview](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/derivatives/overview)).

**Prism hook.** README execution engine assumes IOC de-risk at a computed floor. No order client exists in this repo.

**Point-forecast failure relevant?** Only if the stop *price* is set from a failed median. A stop set from a calibrated lower quantile, a trailing % from a peak, or a user-chosen dollar floor does not need to beat last-value.

**Honest limit.** A stop *sells the coins*. Gaps and “not guaranteed” execution mean the fill can be worse than the stop. That is a different failure mode from “the model missed the dump day.”

### F. Listed options (a hedge that is not a price guess)

**What exists in first-party product docs (not strategy blogs):**

- **Deribit** instruments include BTC options named `BTC-DMMMYY-STRIKE-C/P` (call/put, USD strike). `public/get_instruments` returns `kind=option`, `option_type` ∈ {call, put}, `strike` ([Deribit JSON-RPC overview — Instrument Naming](https://docs.deribit.com/articles/json-rpc-overview); [public/get_instruments](https://docs.deribit.com/api-reference/market-data/public-get_instruments)).
- **CME** “Options on Bitcoin futures”: European-style; one option is on one BTC futures contract (5 bitcoin); exercise into cash-settled futures vs the CME CF Bitcoin Reference Rate; not physical bitcoin ([CME FAQ: Options on Bitcoin Futures](https://www.cmegroup.com/trading/cryptocurrency-indices/cme-options-bitcoin-futures-frequently-asked-questions.html)).
- **Coinbase Global Derivatives:** “Options trading — Coming soon for eligible users”; options and dated futures are a “fast-follow” after the perpetuals cutover. Technical guide shows option symbology `{BASE}-{DDMMMYY}-{STRIKE}-{C/P}` ([Global Derivatives Overview](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/derivatives/overview); [Technical Migration Guide](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/derivatives/technical)). That is a product *existence* claim, not a live retail options book for this note to assume.

**Prism hook.** None. README does not mention options. A put is a purchased payoff, not a Chronos quantile.

**Point-forecast failure relevant?** No. Whether a listed put exists is a venue fact. Whether Prism should *select* a strike from a 10-day q0.1 is a later design question; it is not implied by the bakeoff.

**This note does not recommend buying puts, selling futures, or using leverage.** Those instruments are listed here only so a later design can distinguish “warning,” “sell spot,” and “pay for a listed payoff” as three different products.

---

## 4. Honest limits: what a model cannot do vs what a band/floor might still do

### Cannot (on present evidence)

- **Predict the dump day, or tomorrow’s dollar close better than last-value**, on this harness, with ARIMA+GARCH or univariate Chronos-2 (`bakeoff_results.md`). Direction was a coin flip.
- **Guarantee a 50% multi-month path will be “caught” by a 10-day 0.1 quantile.** 2022’s −67% calendar drop and the 2025–2026 −53% path are hundreds of days. March 2020 is the only −40% 10-day close hole in the sample.
- **Turn uncalibrated Chronos quantiles into a safety floor.** 2024–2026 Chronos Cov80 at 7d/10d was ~70% against an 80% label.
- **Treat ACI coverage as portfolio insurance.** Gibbs & Candès guarantee a long-run frequency that the *next label* falls in the prediction set, with no assumptions on the data-generating process ([arXiv:2106.00170](https://arxiv.org/abs/2106.00170) abstract). That is not a cap on peak-to-trough loss, and it is silent on fill quality if someone sells when the set is breached.

### Might still do (unmeasured in Prism)

- **Describe typical hole size:** “a 10-day close 30% below today has been rare except in identifiable stress windows.” The sample’s worst 10-day 2026 hole was −29%; 2022’s worst was −37%; only March 2020 broke −40%. That is a *historical* statement from Coinbase closes, not a forecast.
- **Warn that a slow drawdown is in progress** once price is already X% below a peak (the Oct 2025 peak was visible in the same series for months while the path ran to June 2026).
- **Calibrate a band** so that “don’t be surprised by a ~Y% 10-day move” has a stated miss rate. GARCH’s slightly wide bands are a weak existence proof that volatility structure can be scored when the median cannot.

### Three product verbs that must not be collapsed

| Verb | What the user gets | What has to be true | Prism status |
| --- | --- | --- | --- |
| **Warning** | A message that a hole or drawdown path is plausible / underway | Calibration or a transparent rule; user still decides | Not built. Closest: unused coverage columns. |
| **Automated selling** | Spot (or perp) is sold when a floor prints | A stop/IOC that can fail in a gap; selling itself *is* the protection and also the source of fake-alarm regret | README designed this. No order code. Coinbase documents stops and that bracket “downside protection is not guaranteed” in high volatility. |
| **Options / listed hedge** | A separate contract whose payoff depends on a strike and expiry | Venue listing, eligibility, premium, cash vs physical settlement (CME options settle to futures/BRR, not coins) | Not in Prism. First-party listings exist at Deribit and CME; Coinbase options described as coming soon for eligible users. |

A conformal 0.1 quantile that is then wired to a Coinbase `stop: 'loss'` is **automated selling**, even if the README calls it a “safety floor.” A conformal 0.1 quantile that is only displayed is a **warning**. Those two products have opposite error costs (whipsaw vs sitting through a 50% path).

---

## 5. Brainstorming step 1 only (project context)

Explored, per brainstorming skill: README, `price_forecast/` (harness, predictors, chronos, series, bakeoff, bakeoff_results), tests, `pyproject.toml`, git log, PRs #1 and #2. No spec, no implementation, no user questions in this file.

**Facts that constrain any later design:**

1. The running package is a **leakage-safe scoreboard**, not the README ensemble (`price_forecast/__init__.py`).
2. The frozen pass rule is **dollar MAE vs last-value and zero-return** in 2022 and 2024–2026. Both non-naive models failed. Retuning that bar is out of scope for “protection.”
3. Bands exist and were measured; conformal, dump logic, P&L, and execution do not exist.
4. The user-facing 50% example, in this series, is a **267-day path from a 2025-10-06 peak**, not a 2026 calendar-year 50% crash and not a 10-day 50% hole.

---

## 6. Problem statements still alive after the point-forecast failure

1. **Band/floor calibration:** Can Prism emit an honest 1/3/7/10-day lower tail (coverage of the later close, width in percent) so a holder is not surprised by a ~30% 10-day hole, without claiming to beat last-value on the median?
2. **Slow-drawdown warning:** Can Prism detect that price is in a multi-month peak-to-trough path of the 2022 or Oct-2025–Jun-2026 kind, early enough to be a warning, without predicting the first down day?
3. **Execution mapping (design only):** If a floor is ever shown, is it a warning, a Coinbase/Deribit stop that sells spot, or a listed option payoff — three different products with three different failure modes, none of which is “guess tomorrow’s dollar close”?

---

## Source list

- Repo: `README.md`; `price_forecast/harness.py`, `predictors.py`, `chronos.py`, `series.py`, `bakeoff.py`, `bakeoff_results.md`, `__init__.py`; `pyproject.toml`; `tests/test_harness.py`, `test_arima_garch.py`, `test_chronos.py`, `test_loader.py`; git log; commits `be22a81`, `8d6a1af`, `13b955a`, `6e3706c`.
- GitHub: [PR #1](https://github.com/FelixClements/prism/pull/1), [PR #2](https://github.com/FelixClements/prism/pull/2).
- Coinbase candles: [Get product candles](https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles); live download 2026-09-17 via `load_daily_closes(source="coinbase")`.
- Coinbase orders: [Create a new order (stops)](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/orders/create-new-order); [Advanced API Order Management](https://docs.cdp.coinbase.com/coinbase-business/advanced-trade-apis/guides/orders); [Global Derivatives Overview](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/derivatives/overview); [Technical Migration Guide](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/derivatives/technical).
- Deribit: [JSON-RPC overview / instrument naming](https://docs.deribit.com/articles/json-rpc-overview); [public/get_instruments](https://docs.deribit.com/api-reference/market-data/public-get_instruments).
- CME: [FAQ: Options on Bitcoin Futures](https://www.cmegroup.com/trading/cryptocurrency-indices/cme-options-bitcoin-futures-frequently-asked-questions.html).
- Chronos-2: [amazon-science/chronos-forecasting README](https://github.com/amazon-science/chronos-forecasting); [arXiv:2510.15821](https://arxiv.org/abs/2510.15821); Context7 library `/amazon-science/chronos-forecasting` (`predict_quantiles`).
- Conformal: Gibbs & Candès, *Adaptive Conformal Inference Under Distribution Shift*, NeurIPS 2021, [arXiv:2106.00170](https://arxiv.org/abs/2106.00170).
