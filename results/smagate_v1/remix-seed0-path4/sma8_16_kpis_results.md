# SMAGateV1 — weekly BTC SMA-8 in / SMA-16 out vs buy-and-hold

**SMAGateV1** (user-named freeze of the locked best-so-far, 2026-09-18). Not investment advice.
This is a historical backtest of one execution design, not a product rule. V1 is this freeze, not a new rule.

KPI snapshot: start $10,000.00; 2018-04-22 → 2026-09-27 (441 comparable weeks after SMA-16 warmup); strategy end $4,823.23 vs HODL $2,545.35; total return -51.77% vs HODL -74.55%; max DD -89.25% vs HODL -97.31%; alpha +22.78 pp; exposure 50.57%.

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
End $ strategy: $4,823.23    End $ buy & hold: $2,545.35
Start BTC price: $18,604.05    End BTC price: $4,742.49
Series: weekly close from daily BTC-USD coinbase (UTC).

Whipsaw = completed round trip with holding period <= 2 weekly bars (holding period = sell bar index − buy bar index).
Open trades are marked to the last close in total return and max DD; profit factor also includes that MTM as a virtual close (no extra 0.15% exit fee).
Win rate / trade count / whipsaws count completed buy→sell round trips only.
HODL pays 0.15% once at entry.

Strategy alpha is excess total return (strategy TR − HODL TR), not CAPM alpha.

KPI                                                  Strategy       Buy & Hold
-------------------------------------------- ---------------- ----------------
Absolute Total Return (%)                             -51.77%          -74.55%
Strategy Alpha (excess total return)                +22.78 pp              n/a
Profit Factor                                          0.6539              n/a
Max DD %                                              -89.25%          -97.31%
Sortino Ratio (ann., rf=0%)                            0.0027           0.0764
MAR Ratio                                             -0.0928          -0.1539
Market Exposure Time %                                 50.57%              n/a
Completed round trips                                      47              n/a
Win Rate                                               23.40%              n/a
Whipsaws (<=2 weekly bars)                                 37              n/a
Total fees $                                          $531.60           $15.00
Fees % of start $                                       5.32%            0.15%
No-fee total return                                   -44.46%          -74.51%
Fee drag on total return                             +7.31 pp         +0.04 pp

How to re-run:

```
.venv/bin/python -m price_forecast.strategies.smagate_v1
.venv/bin/python -m price_forecast.strategies.smagate_v1 --starting-dollars 10000
```

Monthly + cumulative-to-date grid: `sma8_16_kpis_monthly.md` / `sma8_16_kpis_monthly.csv`.
