# SMAGateV1 — weekly BTC SMA-8 in / SMA-16 out vs buy-and-hold

**SMAGateV1** (user-named freeze of the locked best-so-far, 2026-09-18). Not investment advice.
This is a historical backtest of one execution design, not a product rule. V1 is this freeze, not a new rule.

KPI snapshot: start $10,000.00; 2018-04-22 → 2026-09-27 (441 comparable weeks after SMA-16 warmup); strategy end $45,425.09 vs HODL $16,796.92; total return 354.25% vs HODL 67.97%; max DD -62.29% vs HODL -82.74%; alpha +286.28 pp; exposure 48.75%.

Caveats:
- Same-bar weekly close fill: SMA at week t includes close t and the fill is close t. That is contemporaneous fill, not future lookahead. It is more optimistic than the frozen t+1 bakeoff.
- Start in cash (FLAT) until the first close > SMA-8 after SMA-16 exists. The frozen $10k crash-window tables start in BTC.
- 0.15% of notional on each fill. Frozen bakeoff uses 10 bps; this runner now also uses strict > / < (on the line is HOLD).
- Not the frozen t+1 bakeoff (archived at `archive/frozen_t1_bakeoff/`).
- Full-sample KPIs in this table. Monthly rows and the 2022 / Oct 2025–Jun 2026 chapters are in `sma8_16_kpis_monthly.md` (also `.csv`). A full-sample dollar figure can still hide a bad crash window; SMAGateV1 still takes ~30-40% crash chapters. Read those months.

Same-bar fill at the weekly close (more optimistic than the frozen t+1 bakeoff).
Cost is 0.15% per fill vs the frozen bakeoff's 10 bps. Entry uses close > SMA-8;
exit uses close < SMA-16 (on the line is HOLD). Do not compare these
dollars to `archive/frozen_t1_bakeoff/sma_asymmetric_10k_results.md` as if the rules were the same.

Date range: 2018-04-22 → 2026-09-27 (441 comparable weekly bars after SMA-16 warmup).
Start $: $10,000.00
End $ strategy: $45,425.09    End $ buy & hold: $16,796.92
Start BTC price: $8,429.34    End BTC price: $14,179.97
Series: weekly close from daily BTC-USD coinbase (UTC).

Whipsaw = completed round trip with holding period <= 2 weekly bars (holding period = sell bar index − buy bar index).
Open trades are marked to the last close in total return and max DD; profit factor also includes that MTM as a virtual close (no extra 0.15% exit fee).
Win rate / trade count / whipsaws count completed buy→sell round trips only.
HODL pays 0.15% once at entry.

Strategy alpha is excess total return (strategy TR − HODL TR), not CAPM alpha.

KPI                                                  Strategy       Buy & Hold
-------------------------------------------- ---------------- ----------------
Absolute Total Return (%)                             354.25%           67.97%
Strategy Alpha (excess total return)               +286.28 pp              n/a
Profit Factor                                          2.0670              n/a
Max DD %                                              -62.29%          -82.74%
Sortino Ratio (ann., rf=0%)                            0.8542           0.6239
MAR Ratio                                              0.3156           0.0767
Market Exposure Time %                                 48.75%              n/a
Completed round trips                                      38              n/a
Win Rate                                               39.47%              n/a
Whipsaws (<=2 weekly bars)                                 23              n/a
Total fees $                                        $2,574.21           $15.00
Fees % of start $                                      25.74%            0.15%
No-fee total return                                   409.91%           68.22%
Fee drag on total return                            +55.66 pp         +0.25 pp

How to re-run:

```
.venv/bin/python -m price_forecast.strategies.smagate_v1
.venv/bin/python -m price_forecast.strategies.smagate_v1 --starting-dollars 10000
```

Monthly + cumulative-to-date grid: `sma8_16_kpis_monthly.md` / `sma8_16_kpis_monthly.csv`.
