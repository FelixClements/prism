# SMA-8 vs buy-and-hold, $10k start

Not investment advice. This is a backtest of a frozen weekly rule.

## Exact rules

- Starting capital: $10,000 converted to 100% BTC at the first fill bar of each window (no fee on that opening buy).
- Each window is its own $10k start. SMA-8 does not inherit a pre-window position.
- Series: weekly close from daily BTC-USD coinbase (UTC).
- Daily history: 2018-01-01 to 2026-09-17 (3182 days).
- Weeks: UTC Monday–Sunday. Bar date is Sunday. Weekly close = last UTC daily close in that week. Incomplete trailing weeks dropped.
- Weekly bars: 2018-01-07 to 2026-09-13 (454 weeks).
- SMA-8: 100% BTC iff weekly close > 8-week SMA (SMA includes this week); else cash. Warmup is 8 weeks; first fill bar is week 9.
- Fill: signal at week t close executes at week t+1 close. Cash return = 0.
- Costs: 10 bps of wealth each way on SMA-8 flips. No liquidation cost at window end.
- Buy-and-hold stays in the opening BTC. Window start = last weekly close on or before the calendar start; end = last weekly close on or before the calendar end.
- CAGR uses 365.25 days/year over the Sunday-to-Sunday span.

As of 2026-09-13: latest SMA-8 signal is **in BTC** (weekly close $76,799.85 vs SMA-8 $71,132.42). That signal fills at the next weekly close. Filled SMA-8 position on the full-sample window is **in BTC**; last flip 2026-08-30.

## Results

### full-after-sma8-warmup

Anchors: 2018-03-04 → 2026-09-13 (445 weekly returns). Start BTC price $11,469.90; end $76,799.85.

| | SMA-8 | Buy-and-hold |
| --- | ---: | ---: |
| Start $ | $10,000.00 | $10,000.00 |
| Start BTC (coins) | 0.87184718 | 0.87184718 |
| End $ | $43,392.33 | $66,957.73 |
| End holding | 0.56500545 BTC | 0.87184718 BTC |
| Max drawdown $ | $32,463.22 | $55,839.00 |
| Max drawdown % | -63.2% | -75.2% |
| Total return | 333.9% | 569.6% |
| CAGR | 18.8% | 25.0% |
| Time in BTC | 51.9% | 100.0% |
| Round trips | 41 | 0 |
| Flips | 82 | 0 |
| Est. fees paid | $2,265.05 | $0.00 |
| Last flip | 2026-08-30 | — |
| Window-end filled position | BTC | BTC |
| Latest signal (fills next week) | BTC | BTC |

Inherited-position bakeoff (scaled to $10k of starting wealth, started in cash): SMA-8 ends $52,151.70, max DD -63.2% / $39,016.39. This report's fresh $10k BTC buy ends $43,392.33, max DD -63.2% / $32,463.22. The existing weekly bakeoff inherits the pre-window fill; this run does not.

### 2022

Anchors: 2021-12-26 → 2022-12-25 (52 weekly returns). Start BTC price $50,801.79; end $16,829.02.

| | SMA-8 | Buy-and-hold |
| --- | ---: | ---: |
| Start $ | $10,000.00 | $10,000.00 |
| Start BTC (coins) | 0.19684346 | 0.19684346 |
| End $ | $5,107.23 | $3,312.68 |
| End holding | $5,107.23 cash | 0.19684346 BTC |
| Max drawdown $ | $4,892.77 | $6,800.80 |
| Max drawdown % | -48.9% | -68.0% |
| Total return | -48.9% | -66.9% |
| CAGR | -49.0% | -67.0% |
| Time in BTC | 19.2% | 100.0% |
| Round trips | 4 | 0 |
| Flips | 7 | 0 |
| Est. fees paid | $52.54 | $0.00 |
| Last flip | 2022-11-20 | — |
| Window-end filled position | cash | BTC |
| Latest signal (fills next week) | cash | BTC |

Inherited-position bakeoff (scaled to $10k of starting wealth, started in cash): SMA-8 ends $5,490.94, max DD -45.1% / $4,509.06. This report's fresh $10k BTC buy ends $5,107.23, max DD -48.9% / $4,892.77. The existing weekly bakeoff inherits the pre-window fill; this run does not.

### 2025-10-06..2026-06-30

Anchors: 2025-10-05 → 2026-06-28 (38 weekly returns). Start BTC price $123,520.79; end $59,474.01.

| | SMA-8 | Buy-and-hold |
| --- | ---: | ---: |
| Start $ | $10,000.00 | $10,000.00 |
| Start BTC (coins) | 0.08095803 | 0.08095803 |
| End $ | $6,406.73 | $4,814.90 |
| End holding | $6,406.73 cash | 0.08095803 BTC |
| Max drawdown $ | $3,593.27 | $5,185.10 |
| Max drawdown % | -35.9% | -51.9% |
| Total return | -35.9% | -51.9% |
| CAGR | -45.7% | -63.3% |
| Time in BTC | 42.1% | 100.0% |
| Round trips | 5 | 0 |
| Flips | 9 | 0 |
| Est. fees paid | $71.63 | $0.00 |
| Last flip | 2026-06-07 | — |
| Window-end filled position | cash | BTC |
| Latest signal (fills next week) | cash | BTC |

Inherited-position bakeoff (scaled to $10k of starting wealth, started in cash): SMA-8 ends $6,870.48, max DD -31.3% / $3,129.52. This report's fresh $10k BTC buy ends $6,406.73, max DD -35.9% / $3,593.27. The existing weekly bakeoff inherits the pre-window fill; this run does not.

### 2024-01-01..latest

Anchors: 2023-12-31 → 2026-09-13 (141 weekly returns). Start BTC price $42,288.06; end $76,799.85.

| | SMA-8 | Buy-and-hold |
| --- | ---: | ---: |
| Start $ | $10,000.00 | $10,000.00 |
| Start BTC (coins) | 0.23647337 | 0.23647337 |
| End $ | $14,751.30 | $18,161.12 |
| End holding | 0.19207454 BTC | 0.23647337 BTC |
| Max drawdown $ | $6,507.17 | $15,145.36 |
| Max drawdown % | -36.6% | -51.9% |
| Total return | 47.5% | 81.6% |
| CAGR | 15.5% | 24.7% |
| Time in BTC | 56.0% | 100.0% |
| Round trips | 18 | 0 |
| Flips | 36 | 0 |
| Est. fees paid | $503.71 | $0.00 |
| Last flip | 2026-08-30 | — |
| Window-end filled position | BTC | BTC |
| Latest signal (fills next week) | BTC | BTC |

Inherited-position bakeoff (scaled to $10k of starting wealth): $14,751.30 end, max DD -36.6%. Same path as this fresh $10k BTC buy (already in BTC at the first fill bar).

## How to re-run

```
.venv/bin/python -m price_forecast.sma8_10k
```

Writes `price_forecast/sma8_10k_results.md`. Frozen SMA-8 is `sma_signal(..., lookback=8)` in `price_forecast/weekly_regime.py`.
