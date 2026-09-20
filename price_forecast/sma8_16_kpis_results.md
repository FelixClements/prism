# BTC weekly SMA-8 entry / SMA-16 exit vs buy-and-hold

**Current best-so-far (user, 2026-09-18).** Not investment advice.
This is a historical backtest of one execution design, not a product rule.

KPI snapshot: start $10,000.00; 2018-04-22 → 2026-09-13 (439 comparable weeks after SMA-16 warmup); strategy end $156,621.64 vs HODL $87,191.09; total return 1466.22% vs HODL 771.91%; max DD -50.27% vs HODL -75.19%; alpha +694.31 pp; exposure 58.54%.

Caveats:
- Same-bar weekly close fill: SMA at week t includes close t and the fill is close t. That is contemporaneous fill, not future lookahead. It is more optimistic than the frozen t+1 bakeoff.
- Start in cash (FLAT) until the first close >= SMA-8 after SMA-16 exists. The frozen $10k crash-window tables start in BTC.
- 0.15% of notional on each fill. Frozen bakeoff uses 10 bps and strict inequalities.
- Not the frozen t+1 bakeoff (`weekly_bakeoff` / `sma_asymmetric_10k`).
- Full-sample KPIs in this table. Monthly rows and the 2022 / Oct 2025–Jun 2026 chapters are in `sma8_16_kpis_monthly.md` (also `.csv`). A full-sample dollar figure can still hide a bad crash window; read those months.

Same-bar fill at the weekly close (more optimistic than the frozen t+1 bakeoff).
Cost is 0.15% per fill vs the frozen bakeoff's 10 bps. Entry uses close >= SMA-8;
exit uses close <= SMA-16 (frozen bakeoff uses strict > / <). Do not compare these
dollars to `sma_asymmetric_10k_results.md` as if the rules were the same.

Date range: 2018-04-22 → 2026-09-13 (439 comparable weekly bars after SMA-16 warmup).
Start $: $10,000.00
End $ strategy: $156,621.64    End $ buy & hold: $87,191.09
Start BTC price: $8,795.01    End BTC price: $76,799.85
Series: weekly close from daily BTC-USD coinbase (UTC).

Whipsaw = completed round trip with holding period <= 2 weekly bars (holding period = sell bar index − buy bar index).
Open trades are marked to the last close in total return and max DD; profit factor also includes that MTM as a virtual close (no extra 0.15% exit fee).
Win rate / trade count / whipsaws count completed buy→sell round trips only.
HODL pays 0.15% once at entry.

Strategy alpha is excess total return (strategy TR − HODL TR), not CAPM alpha.

KPI                                                  Strategy       Buy & Hold
-------------------------------------------- ---------------- ----------------
Absolute Total Return (%)                            1466.22%          771.91%
Strategy Alpha (excess total return)               +694.31 pp              n/a
Profit Factor                                          1.6869              n/a
Max DD %                                              -50.27%          -75.19%
Sortino Ratio (ann., rf=0%)                            1.2668           1.0753
MAR Ratio                                              0.7716           0.3914
Market Exposure Time %                                 58.54%              n/a
Completed round trips                                      38              n/a
Win Rate                                               34.21%              n/a
Whipsaws (<=2 weekly bars)                                 27              n/a
Total fees $                                       $11,649.70           $15.00
Fees % of start $                                     116.50%            0.15%
No-fee total return                                  1658.13%          773.22%
Fee drag on total return                           +191.91 pp         +1.31 pp

How to re-run:

```
.venv/bin/python -m price_forecast.sma8_16_kpis
.venv/bin/python -m price_forecast.sma8_16_kpis --starting-dollars 10000
```

Monthly + cumulative-to-date grid: `sma8_16_kpis_monthly.md` / `sma8_16_kpis_monthly.csv`.
