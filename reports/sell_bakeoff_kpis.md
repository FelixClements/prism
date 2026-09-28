# Sell 1: 16-week average, or a week that falls 10%

Not investment advice. Next-week fill: the signal is the weekly close, and the fill is the next weekly close. Cost is 0.15% per fill. Start in cash.

Buy: weekly close above the 8-week average, pre-breakout or breakout, and price above both the 150-day and 200-day averages.
Sell: weekly close under the 16-week average, or a week that falls 10% or more.

Date range: 2018-04-29 → 2026-09-27 (440 comparable weekly bars after SMA-16 warmup).
Start $: $10,000.00
End $ strategy: $232,088.82    End $ buy & hold: $89,823.58
Start BTC price: $9,389.01    End BTC price: $84,462.14
Series: weekly close from daily BTC-USD coinbase (UTC).

Whipsaw = completed round trip with holding period <= 2 weekly bars (holding period = sell bar index − buy bar index).
Open trades are marked to the last close in total return and max DD; profit factor also includes that MTM as a virtual close (no extra 0.15% exit fee).
Win rate / trade count / whipsaws count completed buy→sell round trips only.
HODL pays 0.15% once at entry.

Strategy alpha is excess total return (strategy TR − HODL TR), not CAPM alpha.

KPI                                                  Strategy       Buy & Hold
-------------------------------------------- ---------------- ----------------
Absolute Total Return (%)                            2220.89%          798.24%
Strategy Alpha (excess total return)              +1422.65 pp              n/a
Profit Factor                                          4.6448              n/a
Max DD %                                              -25.54%          -75.19%
Sortino Ratio (ann., rf=0%)                            1.4993           1.0815
MAR Ratio                                              1.7745           0.3965
Market Exposure Time %                                 37.73%              n/a
Completed round trips                                      15              n/a
Win Rate                                               60.00%              n/a
Whipsaws (<=2 weekly bars)                                  6              n/a
Total fees $                                        $5,543.06           $15.00
Fees % of start $                                      55.43%            0.15%
No-fee total return                                  2331.44%          799.59%
Fee drag on total return                           +110.55 pp         +1.35 pp

How to re-run:

```
.venv/bin/python -m price_forecast.strategies.smagate_v1
.venv/bin/python -m price_forecast.strategies.smagate_v1 --starting-dollars 10000
```

Monthly + cumulative-to-date grid: `sma8_16_kpis_monthly.md` / `sma8_16_kpis_monthly.csv`.


Chapter window 2022-01-02 → 2022-12-25 (52 weekly bars). Start $ is the prior bar's equity (continuing path, not a fresh $10k). Max DD is peak-to-trough inside the chapter.
  Strategy: $87,423.93 → $87,423.93 (0.00%); max DD 0.00%
  HODL:     $54,026.56 → $17,897.28 (-66.87%); max DD -65.64%

Chapter window 2025-10-05 → 2026-06-28 (39 weekly bars). Start $ is the prior bar's equity (continuing path, not a fresh $10k). Max DD is peak-to-trough inside the chapter.
  Strategy: $207,452.33 → $213,732.32 (3.03%); max DD -6.28%
  HODL:     $119,319.69 → $63,249.27 (-46.99%); max DD -51.85%

# Sell 2: 16-week average, or a 10% week that is also under the 8-week average

Not investment advice. Next-week fill: the signal is the weekly close, and the fill is the next weekly close. Cost is 0.15% per fill. Start in cash.

Buy: weekly close above the 8-week average, pre-breakout or breakout, and price above both the 150-day and 200-day averages.
Sell: weekly close under the 16-week average, or a week that falls 10% and is also under the 8-week average.

Date range: 2018-04-29 → 2026-09-27 (440 comparable weekly bars after SMA-16 warmup).
Start $: $10,000.00
End $ strategy: $266,891.67    End $ buy & hold: $89,823.58
Start BTC price: $9,389.01    End BTC price: $84,462.14
Series: weekly close from daily BTC-USD coinbase (UTC).

Whipsaw = completed round trip with holding period <= 2 weekly bars (holding period = sell bar index − buy bar index).
Open trades are marked to the last close in total return and max DD; profit factor also includes that MTM as a virtual close (no extra 0.15% exit fee).
Win rate / trade count / whipsaws count completed buy→sell round trips only.
HODL pays 0.15% once at entry.

Strategy alpha is excess total return (strategy TR − HODL TR), not CAPM alpha.

KPI                                                  Strategy       Buy & Hold
-------------------------------------------- ---------------- ----------------
Absolute Total Return (%)                            2568.92%          798.24%
Strategy Alpha (excess total return)              +1770.68 pp              n/a
Profit Factor                                          5.1126              n/a
Max DD %                                              -29.68%          -75.19%
Sortino Ratio (ann., rf=0%)                            1.5407           1.0815
MAR Ratio                                              1.6090           0.3965
Market Exposure Time %                                 42.05%              n/a
Completed round trips                                      14              n/a
Win Rate                                               64.29%              n/a
Whipsaws (<=2 weekly bars)                                  5              n/a
Total fees $                                        $6,163.91           $15.00
Fees % of start $                                      61.64%            0.15%
No-fee total return                                  2687.67%          799.59%
Fee drag on total return                           +118.75 pp         +1.35 pp

How to re-run:

```
.venv/bin/python -m price_forecast.strategies.smagate_v1
.venv/bin/python -m price_forecast.strategies.smagate_v1 --starting-dollars 10000
```

Monthly + cumulative-to-date grid: `sma8_16_kpis_monthly.md` / `sma8_16_kpis_monthly.csv`.


Chapter window 2022-01-02 → 2022-12-25 (52 weekly bars). Start $ is the prior bar's equity (continuing path, not a fresh $10k). Max DD is peak-to-trough inside the chapter.
  Strategy: $100,533.57 → $100,533.57 (0.00%); max DD 0.00%
  HODL:     $54,026.56 → $17,897.28 (-66.87%); max DD -65.64%

Chapter window 2025-10-05 → 2026-06-28 (39 weekly bars). Start $ is the prior bar's equity (continuing path, not a fresh $10k). Max DD is peak-to-trough inside the chapter.
  Strategy: $238,560.82 → $245,782.52 (3.03%); max DD -6.28%
  HODL:     $119,319.69 → $63,249.27 (-46.99%); max DD -51.85%
