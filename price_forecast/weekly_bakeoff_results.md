# Weekly in/out bakeoff

Not investment advice. Frozen rules; no lookback or F&G-threshold search after seeing results.

## Exact rules

- Series: weekly close from daily BTC-USD coinbase (UTC).
- Daily history: 2018-01-01 to 2026-09-17 (3182 days).
- Weeks: UTC Monday–Sunday. Bar date is Sunday. Weekly close = last UTC daily close in that week. Incomplete trailing weeks dropped.
- Weekly bars: 2018-01-07 to 2026-09-13 (454 weeks).
- Fill: signal at week t close executes at week t+1 close. Start inherited 100% BTC. Cash return = 0.
- Costs: 10 bps of wealth each way on every flip (20 bps round trip). No liquidation cost at window end. No fee on the inherited opening long.
- SMA 8 / SMA 12: 100% BTC iff weekly close > SMA including this week; else 100% cash.
- Dual SMA: classic crossover, 100% BTC iff 12-week SMA > 26-week SMA (both include this week); else cash.
- Donchian 12: 100% BTC iff close >= max of the prior 12 weeks excluding this week; else cash. Channel is leakage-safe (this week is not inside its own high).
- F&G source: Alternative.me Crypto Fear & Greed Index. Endpoint `https://api.alternative.me/fng/?limit=0`.
- F&G align: last index with UTC date <= that week's Sunday. No interpolation.
- F&G overlay (one overlay, not a grid): if F&G > 75, force cash (cannot re-enter; if in, exit). F&G does not force a buy. Missing F&G leaves the base signal.
- F&G-only: F&G > 75 cash; F&G < 25 BTC; else keep previous (start BTC).
- C pass: max DD at least 10 percentage points better than buy-and-hold AND terminal wealth >= 90% of buy-and-hold.
- A pass: max DD at least 10 percentage points better than buy-and-hold.
- Product C also needs long-run (2024-01-01 through latest) terminal wealth within 10% of buy-and-hold.
- Full-after-warmup starts at the weekly close that can fill a 26-week dual SMA (common start for every strategy).
- Window start = last weekly close on or before the window's start date; end = last weekly close on or before the window's end date.

- F&G history: 2018-02-01 to 2026-09-17 (450 of 454 weekly bars have an index).

## Scoreboard

### 2022

Anchors: 2021-12-26 → 2022-12-25 (52 weekly returns). F&G coverage: 53/53 weekly bars in this span.

| Strategy | Terminal $1 | vs B&H | Max DD | B&H DD | Time in BTC | Round trips | C? | A? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| buy-hold | 0.331 | 1.000 | -68.0% | -68.0% | 100.0% | 0 | — | — |
| sma-8 | 0.549 | 1.658 | -45.1% | -68.0% | 17.3% | 3 | yes | yes |
| sma-12 | 0.572 | 1.726 | -42.8% | -68.0% | 15.4% | 4 | yes | yes |
| dual-sma-12-26 | 0.834 | 2.518 | -28.6% | -68.0% | 11.5% | 1 | yes | yes |
| donchian-12 | 1.000 | 3.019 | 0.0% | -68.0% | 0.0% | 0 | yes | yes |
| sma-8+fng | 0.549 | 1.658 | -45.1% | -68.0% | 17.3% | 3 | yes | yes |
| sma-12+fng | 0.572 | 1.726 | -42.8% | -68.0% | 15.4% | 4 | yes | yes |
| dual-sma-12-26+fng | 0.834 | 2.518 | -28.6% | -68.0% | 11.5% | 1 | yes | yes |
| donchian-12+fng | 1.000 | 3.019 | 0.0% | -68.0% | 0.0% | 0 | yes | yes |
| fng-only | 0.331 | 1.000 | -68.0% | -68.0% | 100.0% | 0 | no | no |

### 2025-10-06..2026-06-30

Anchors: 2025-10-05 → 2026-06-28 (38 weekly returns). F&G coverage: 39/39 weekly bars in this span.

| Strategy | Terminal $1 | vs B&H | Max DD | B&H DD | Time in BTC | Round trips | C? | A? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| buy-hold | 0.481 | 1.000 | -51.9% | -51.9% | 100.0% | 0 | — | — |
| sma-8 | 0.687 | 1.427 | -31.3% | -51.9% | 39.5% | 5 | yes | yes |
| sma-12 | 0.676 | 1.404 | -32.4% | -51.9% | 26.3% | 4 | yes | yes |
| dual-sma-12-26 | 0.702 | 1.458 | -29.8% | -51.9% | 18.4% | 1 | yes | yes |
| donchian-12 | 0.977 | 2.029 | -5.7% | -51.9% | 7.9% | 3 | yes | yes |
| sma-8+fng | 0.687 | 1.427 | -31.3% | -51.9% | 39.5% | 5 | yes | yes |
| sma-12+fng | 0.676 | 1.404 | -32.4% | -51.9% | 26.3% | 4 | yes | yes |
| dual-sma-12-26+fng | 0.702 | 1.458 | -29.8% | -51.9% | 18.4% | 1 | yes | yes |
| donchian-12+fng | 0.977 | 2.029 | -5.7% | -51.9% | 7.9% | 3 | yes | yes |
| fng-only | 0.547 | 1.135 | -48.1% | -51.9% | 94.7% | 0 | no | no |

### 2024-01-01..latest

Anchors: 2023-12-31 → 2026-09-13 (141 weekly returns). F&G coverage: 142/142 weekly bars in this span.

| Strategy | Terminal $1 | vs B&H | Max DD | B&H DD | Time in BTC | Round trips | C? | A? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| buy-hold | 1.816 | 1.000 | -51.9% | -51.9% | 100.0% | 0 | — | — |
| sma-8 | 1.475 | 0.812 | -36.6% | -51.9% | 56.0% | 18 | no | yes |
| sma-12 | 1.342 | 0.739 | -38.2% | -51.9% | 55.3% | 11 | no | yes |
| dual-sma-12-26 | 1.120 | 0.617 | -33.6% | -51.9% | 54.6% | 3 | no | yes |
| donchian-12 | 1.169 | 0.644 | -12.9% | -51.9% | 15.6% | 14 | no | yes |
| sma-8+fng | 1.451 | 0.799 | -36.0% | -51.9% | 48.2% | 21 | no | yes |
| sma-12+fng | 1.317 | 0.725 | -37.7% | -51.9% | 47.5% | 15 | no | yes |
| dual-sma-12-26+fng | 1.101 | 0.606 | -32.5% | -51.9% | 46.8% | 6 | no | yes |
| donchian-12+fng | 1.198 | 0.660 | -6.9% | -51.9% | 10.6% | 11 | no | yes |
| fng-only | 1.151 | 0.634 | -48.1% | -51.9% | 40.4% | 1 | no | no |

### full-after-warmup

Anchors: 2018-07-08 → 2026-09-13 (427 weekly returns). F&G coverage: 428/428 weekly bars in this span.

| Strategy | Terminal $1 | vs B&H | Max DD | B&H DD | Time in BTC | Round trips | C? | A? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| buy-hold | 11.459 | 1.000 | -75.2% | -75.2% | 100.0% | 0 | — | — |
| sma-8 | 7.424 | 0.648 | -63.2% | -75.2% | 52.5% | 39 | no | yes |
| sma-12 | 6.364 | 0.555 | -70.1% | -75.2% | 53.4% | 30 | no | no |
| dual-sma-12-26 | 9.248 | 0.807 | -61.1% | -75.2% | 50.8% | 8 | no | yes |
| donchian-12 | 3.584 | 0.313 | -40.7% | -75.2% | 18.7% | 39 | no | yes |
| sma-8+fng | 2.795 | 0.244 | -65.9% | -75.2% | 43.1% | 50 | no | no |
| sma-12+fng | 2.391 | 0.209 | -72.4% | -75.2% | 44.0% | 42 | no | no |
| dual-sma-12-26+fng | 3.694 | 0.322 | -61.8% | -75.2% | 41.7% | 19 | no | yes |
| donchian-12+fng | 1.792 | 0.156 | -26.7% | -75.2% | 12.2% | 30 | no | yes |
| fng-only | 2.335 | 0.204 | -68.0% | -75.2% | 65.8% | 4 | no | no |

## Verdict

Winner (C on both crash windows): sma-8, sma-12, dual-sma-12-26, donchian-12, sma-8+fng, sma-12+fng, dual-sma-12-26+fng, donchian-12+fng.
Product C (C on both crash windows and long-run wealth not much worse): none.

F&G overlay: nothing on the two crash windows (DD and wealth identical to the un-overlaid sibling). sma-8+fng vs sma-8 on 2022: same DD (-45.1% → -45.1%, wealth 0.549 → 0.549, Δwealth +0.000). sma-12+fng vs sma-12 on 2022: same DD (-42.8% → -42.8%, wealth 0.572 → 0.572, Δwealth +0.000). dual-sma-12-26+fng vs dual-sma-12-26 on 2022: same DD (-28.6% → -28.6%, wealth 0.834 → 0.834, Δwealth +0.000). donchian-12+fng vs donchian-12 on 2022: same DD (0.0% → 0.0%, wealth 1.000 → 1.000, Δwealth +0.000). sma-8+fng vs sma-8 on 2025-10-06..2026-06-30: same DD (-31.3% → -31.3%, wealth 0.687 → 0.687, Δwealth +0.000). sma-12+fng vs sma-12 on 2025-10-06..2026-06-30: same DD (-32.4% → -32.4%, wealth 0.676 → 0.676, Δwealth +0.000). dual-sma-12-26+fng vs dual-sma-12-26 on 2025-10-06..2026-06-30: same DD (-29.8% → -29.8%, wealth 0.702 → 0.702, Δwealth +0.000). donchian-12+fng vs donchian-12 on 2025-10-06..2026-06-30: same DD (-5.7% → -5.7%, wealth 0.977 → 0.977, Δwealth +0.000). 2024-01-01..latest: overlay helped crash/path DD. sma-8+fng vs sma-8 on 2024-01-01..latest: helped DD (-36.6% → -36.0%, wealth 1.475 → 1.451, Δwealth -0.025). sma-12+fng vs sma-12 on 2024-01-01..latest: helped DD (-38.2% → -37.7%, wealth 1.342 → 1.317, Δwealth -0.025). dual-sma-12-26+fng vs dual-sma-12-26 on 2024-01-01..latest: helped DD (-33.6% → -32.5%, wealth 1.120 → 1.101, Δwealth -0.019). donchian-12+fng vs donchian-12 on 2024-01-01..latest: helped DD (-12.9% → -6.9%, wealth 1.169 → 1.198, Δwealth +0.029). full-after-warmup: overlay mixed on DD. sma-8+fng vs sma-8 on full-after-warmup: hurt DD (-63.2% → -65.9%, wealth 7.424 → 2.795, Δwealth -4.629). sma-12+fng vs sma-12 on full-after-warmup: hurt DD (-70.1% → -72.4%, wealth 6.364 → 2.391, Δwealth -3.973). dual-sma-12-26+fng vs dual-sma-12-26 on full-after-warmup: hurt DD (-61.1% → -61.8%, wealth 9.248 → 3.694, Δwealth -5.554). donchian-12+fng vs donchian-12 on full-after-warmup: helped DD (-40.7% → -26.7%, wealth 3.584 → 1.792, Δwealth -1.792).

Command: `.venv/bin/python -m price_forecast.weekly_bakeoff`
