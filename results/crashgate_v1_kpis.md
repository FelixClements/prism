# CrashGateV1 — base-or-breakout buy, 16-week sell, 10% week under the 8-week average

Not investment advice. This is the locked 2026-09-28 rule, not SMAGateV1.
Signal on the weekly close. Fill on the next weekly close. Cost is 0.15% per fill.
Start in cash.

Buy when the weekly close is above the 8-week average, the daily path is a
pre-breakout or a breakout, and price is above both the 150-day and 200-day averages.
Sell when the weekly close is below the 16-week average, or when the week falls
10% or more and that close is below the 8-week average.

Date range: 2018-04-29 → 2026-09-27 (440 weekly bars).
Start $: $10,000.00
End $ strategy: $266,891.67    End $ buy & hold: $89,823.58
Start BTC price: $9,389.01    End BTC price: $84,462.14

Strategy alpha is excess total return (strategy total return − buy-and-hold total return).
HODL pays 0.15% once at the first bar of this window.

KPI                                                  Strategy       Buy & Hold
-------------------------------------------- ---------------- ----------------
Absolute Total Return (%)                            2568.92%          798.24%
Strategy Alpha (excess total return)              +1770.68 pp              n/a
Profit Factor                                          5.1126              n/a
Max DD %                                              -29.68%          -75.19%
Sortino Ratio (ann., rf=0%)                            1.5407           1.0815
CAGR                                                   47.75%           29.81%
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
python -m price_forecast.strategies.crashgate_v1
```

Chapter window 2022-01-02 → 2022-12-25 (52 weekly bars). Start $ is the prior bar's equity (continuing path, not a fresh $10k). Max DD is peak-to-trough inside the chapter.
  Strategy: $100,533.57 → $100,533.57 (0.00%); max DD 0.00%
  HODL:     $54,026.56 → $17,897.28 (-66.87%); max DD -65.64%
Chapter window 2025-10-05 → 2026-06-28 (39 weekly bars). Start $ is the prior bar's equity (continuing path, not a fresh $10k). Max DD is peak-to-trough inside the chapter.
  Strategy: $238,560.82 → $245,782.52 (3.03%); max DD -6.28%
  HODL:     $119,319.69 → $63,249.27 (-46.99%); max DD -51.85%
