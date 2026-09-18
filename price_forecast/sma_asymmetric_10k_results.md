# Asymmetric SMA grid vs SMA-8 and buy-and-hold, $10k start

Not investment advice. This is a backtest of a frozen weekly grid, not a new product rule.

## The answer in one paragraph

Full sample after 40-week warmup, fresh $10,000 in BTC: buy-and-hold ends $124,201.46 (max DD -75.2%); symmetric SMA-8 ends $94,554.32 (max DD -63.2%); symmetric SMA-12 ends $82,670.82 (max DD -70.1%). Highest full-sample cells: buy4/sell40 $235,261.44 (max DD -56.6%), buy6/sell40 $187,998.30 (max DD -55.4%), buy8/sell40 $165,831.01 (max DD -56.9%). 15 of 24 combos beat SMA-8 on full-sample end $ and still had max DD at least 10pp better than buy-and-hold on both crash windows. That bar is vs buy-and-hold, not vs SMA-8's own crash path. 10 of those were also at least as shallow as SMA-8 on both crashes. On 2024–latest, 19 of 24 combos finished closer to buy-and-hold than SMA-8 (81.2% of B&H end $) without giving back the 2022 10pp-vs-B&H drawdown filter. Do not treat the top cell as a new frozen rule.

## Exact rule

While holding BTC, sell to cash iff weekly close is strictly below the longer SMA; while in cash, buy BTC iff weekly close is strictly above the shorter SMA.

- Starting capital: $10,000 converted to 100% BTC at the first fill bar of each window (no fee on that opening buy).
- Each window is its own $10k start. Signals walk the full weekly series; the dollar path does not inherit a pre-window position.
- Series: weekly close from daily BTC-USD coinbase (UTC).
- Daily history: 2018-01-01 to 2026-09-17 (3182 days).
- Weeks: UTC Monday–Sunday. Bar date is Sunday. Weekly close = last UTC daily close in that week. Incomplete trailing weeks dropped.
- Weekly bars: 2018-01-07 to 2026-09-13 (454 weeks).
- Frozen grid: buy_weeks ∈ [4, 6, 8, 10, 12], sell_weeks ∈ [12, 16, 20, 26, 40], skip sell_weeks <= buy_weeks (24 combos).
- SMA includes this week's close, same as SMA-8. Warmup for the full-sample window is 40 weeks (longest SMA); first fill bar is week 41.
- Fill: signal at week t close executes at week t+1 close. Cash return = 0.
- Costs: 10 bps of wealth each way on flips. No liquidation cost at window end.
- Position is 100% BTC or 100% cash. Do not use the short SMA while in; do not use the long SMA while out.
- Baselines: buy-and-hold, symmetric SMA-8, symmetric SMA-12 (in iff close > SMA).
- Window start = last weekly close on or before the calendar start; end = last weekly close on or before the calendar end.
- Full-sample dollars are not comparable to `sma8_10k`'s 8-week-warmup window. This full sample starts 2018-10-14 at $6,183.49; that report starts after SMA-8 warmup (2018-03-04 at a higher BTC price).
- Calendar windows 2022, 2025-10-06..2026-06-30, and 2024-01-01..latest use the same anchors as sma8_10k / weekly bakeoff.

## This is a map, not a new frozen rule

Picking the best cell after seeing the grid is overfitting. The 24 combos were frozen before looking at results. Do not quietly replace SMA-8 with the max cell.

## Full sample after 40-week warmup

### full-after-sma40-warmup

Anchors: 2018-10-14 → 2026-09-13 (413 weekly returns). Start BTC price $6,183.49; end $76,799.85.

| combo | End $ | Max DD $ | Max DD % | Total return | Time in BTC | Round trips | Fees $ | vs B&H end | vs SMA-8 end $ | vs SMA-8 max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| buy-and-hold | $124,201.46 | $103,577.07 | -75.2% | 1142.0% | 100.0% | 0 | $0.00 | 100.0% | +$29,647.15 | -12.0pp |
| SMA-8 | $94,554.32 | $70,739.17 | -63.2% | 845.5% | 53.3% | 37 | $4,838.10 | 76.1% | +$0.00 | +0.0pp |
| SMA-12 | $82,670.82 | $107,221.86 | -70.1% | 726.7% | 54.7% | 29 | $4,143.45 | 66.6% | -$11,883.50 | -6.9pp |
| buy4/sell12 | $116,494.47 | $115,349.44 | -73.5% | 1064.9% | 62.5% | 51 | $6,771.57 | 93.8% | +$21,940.15 | -10.3pp |
| buy4/sell16 | $134,002.91 | $66,127.99 | -59.2% | 1240.0% | 64.6% | 50 | $6,583.50 | 107.9% | +$39,448.60 | +3.9pp |
| buy4/sell20 | $103,623.93 | $62,375.08 | -59.8% | 936.2% | 65.6% | 49 | $5,271.61 | 83.4% | +$9,069.61 | +3.4pp |
| buy4/sell26 | $147,717.95 | $72,676.04 | -58.8% | 1377.2% | 65.1% | 54 | $7,158.52 | 118.9% | +$53,163.63 | +4.4pp |
| buy4/sell40 | $235,261.44 | $131,382.91 | -56.6% | 2252.6% | 71.9% | 43 | $7,939.84 | 189.4% | +$140,707.12 | +6.6pp |
| buy6/sell12 | $101,506.58 | $89,235.35 | -71.7% | 915.1% | 59.3% | 41 | $4,783.98 | 81.7% | +$6,952.26 | -8.5pp |
| buy6/sell16 | $146,835.24 | $55,596.39 | -56.6% | 1368.4% | 62.0% | 42 | $5,861.82 | 118.2% | +$52,280.93 | +6.6pp |
| buy6/sell20 | $89,177.25 | $40,478.97 | -67.1% | 791.8% | 63.9% | 40 | $3,515.36 | 71.8% | -$5,377.06 | -3.9pp |
| buy6/sell26 | $146,013.48 | $55,933.14 | -56.0% | 1360.1% | 63.2% | 46 | $5,786.59 | 117.6% | +$51,459.17 | +7.1pp |
| buy6/sell40 | $187,998.30 | $109,662.89 | -55.4% | 1780.0% | 71.2% | 39 | $6,331.58 | 151.4% | +$93,443.98 | +7.8pp |
| buy8/sell12 | $125,733.42 | $84,301.34 | -61.7% | 1157.3% | 56.7% | 33 | $5,511.98 | 101.2% | +$31,179.11 | +1.5pp |
| buy8/sell16 | $125,320.53 | $62,843.41 | -58.2% | 1153.2% | 60.3% | 33 | $5,053.31 | 100.9% | +$30,766.21 | +5.0pp |
| buy8/sell20 | $74,837.29 | $45,767.87 | -66.9% | 648.4% | 62.0% | 32 | $3,029.39 | 60.3% | -$19,717.02 | -3.7pp |
| buy8/sell26 | $107,327.42 | $63,122.24 | -57.5% | 973.3% | 61.5% | 38 | $5,155.94 | 86.4% | +$12,773.10 | +5.6pp |
| buy8/sell40 | $165,831.01 | $106,707.23 | -56.9% | 1558.3% | 68.8% | 31 | $5,453.25 | 133.5% | +$71,276.69 | +6.3pp |
| buy10/sell12 | $109,899.27 | $109,993.94 | -70.0% | 999.0% | 55.2% | 30 | $4,504.62 | 88.5% | +$15,344.95 | -6.8pp |
| buy10/sell16 | $119,927.79 | $74,147.29 | -64.1% | 1099.3% | 58.4% | 28 | $3,961.15 | 96.6% | +$25,373.48 | -0.9pp |
| buy10/sell20 | $69,700.68 | $54,047.75 | -63.9% | 597.0% | 60.3% | 27 | $2,356.41 | 56.1% | -$24,853.64 | -0.7pp |
| buy10/sell26 | $111,069.36 | $74,550.83 | -63.4% | 1010.7% | 59.8% | 33 | $4,242.23 | 89.4% | +$16,515.04 | -0.2pp |
| buy10/sell40 | $130,522.66 | $74,648.56 | -62.7% | 1205.2% | 67.8% | 26 | $3,508.28 | 105.1% | +$35,968.35 | +0.5pp |
| buy12/sell16 | $80,211.50 | $71,967.18 | -63.9% | 702.1% | 57.9% | 25 | $3,124.48 | 64.6% | -$14,342.81 | -0.7pp |
| buy12/sell20 | $45,601.98 | $53,890.67 | -65.5% | 356.0% | 59.3% | 25 | $1,905.56 | 36.7% | -$48,952.34 | -2.3pp |
| buy12/sell26 | $72,667.63 | $74,368.68 | -65.0% | 626.7% | 58.8% | 31 | $3,435.36 | 58.5% | -$21,886.69 | -1.8pp |
| buy12/sell40 | $96,053.95 | $73,493.81 | -65.1% | 860.5% | 67.1% | 24 | $2,938.19 | 77.3% | +$1,499.63 | -1.9pp |

## 2024 through latest

### 2024-01-01..latest

Anchors: 2023-12-31 → 2026-09-13 (141 weekly returns). Start BTC price $42,288.06; end $76,799.85.

| combo | End $ | Max DD $ | Max DD % | Total return | Time in BTC | Round trips | Fees $ | vs B&H end | vs SMA-8 end $ | vs SMA-8 max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| buy-and-hold | $18,161.12 | $15,145.36 | -51.9% | 81.6% | 100.0% | 0 | $0.00 | 100.0% | +$3,409.82 | -15.3pp |
| SMA-8 | $14,751.30 | $6,507.17 | -36.6% | 47.5% | 56.0% | 18 | $503.71 | 81.2% | +$0.00 | +0.0pp |
| SMA-12 | $13,420.94 | $6,804.12 | -38.2% | 34.2% | 55.3% | 11 | $342.63 | 73.9% | -$1,330.35 | -1.7pp |
| buy4/sell12 | $19,309.45 | $6,105.20 | -36.2% | 93.1% | 61.7% | 17 | $574.76 | 106.3% | +$4,558.15 | +0.4pp |
| buy4/sell16 | $21,754.94 | $6,837.18 | -28.2% | 117.5% | 65.2% | 17 | $658.47 | 119.8% | +$7,003.64 | +8.4pp |
| buy4/sell20 | $17,669.07 | $7,039.01 | -32.7% | 76.7% | 68.8% | 15 | $487.40 | 97.3% | +$2,917.78 | +3.9pp |
| buy4/sell26 | $18,355.88 | $5,214.31 | -30.9% | 83.6% | 66.7% | 17 | $516.38 | 101.1% | +$3,604.58 | +5.6pp |
| buy4/sell40 | $17,909.89 | $10,001.86 | -40.5% | 79.1% | 75.9% | 12 | $382.34 | 98.6% | +$3,158.59 | -3.9pp |
| buy6/sell12 | $21,256.36 | $6,115.13 | -36.3% | 112.6% | 60.3% | 16 | $568.07 | 117.0% | +$6,505.06 | +0.3pp |
| buy6/sell16 | $23,948.42 | $7,194.70 | -28.3% | 139.5% | 63.8% | 16 | $654.16 | 131.9% | +$9,197.12 | +8.3pp |
| buy6/sell20 | $19,450.59 | $7,131.28 | -31.5% | 94.5% | 67.4% | 14 | $478.49 | 107.1% | +$4,699.30 | +5.1pp |
| buy6/sell26 | $19,892.87 | $5,417.15 | -32.1% | 98.9% | 66.0% | 16 | $505.07 | 109.5% | +$5,141.57 | +4.4pp |
| buy6/sell40 | $17,872.42 | $10,425.31 | -42.2% | 78.7% | 76.6% | 13 | $409.22 | 98.4% | +$3,121.12 | -5.7pp |
| buy8/sell12 | $16,815.62 | $6,542.88 | -38.2% | 68.2% | 59.6% | 15 | $476.31 | 92.6% | +$2,064.32 | -1.7pp |
| buy8/sell16 | $18,945.27 | $6,910.77 | -30.9% | 89.5% | 63.1% | 15 | $545.00 | 104.3% | +$4,193.97 | +5.7pp |
| buy8/sell20 | $15,387.10 | $7,468.17 | -37.2% | 53.9% | 66.7% | 13 | $396.63 | 84.7% | +$635.80 | -0.6pp |
| buy8/sell26 | $13,512.74 | $6,631.31 | -37.4% | 35.1% | 66.0% | 16 | $434.15 | 74.4% | -$1,238.55 | -0.9pp |
| buy8/sell40 | $14,849.54 | $9,555.23 | -44.0% | 48.5% | 74.5% | 12 | $337.79 | 81.8% | +$98.24 | -7.4pp |
| buy10/sell12 | $17,024.12 | $6,711.89 | -38.2% | 70.2% | 55.3% | 12 | $381.87 | 93.7% | +$2,272.82 | -1.7pp |
| buy10/sell16 | $20,470.35 | $6,543.99 | -30.5% | 104.7% | 58.9% | 12 | $442.90 | 112.7% | +$5,719.06 | +6.1pp |
| buy10/sell20 | $16,180.90 | $6,712.46 | -33.6% | 61.8% | 63.1% | 10 | $305.35 | 89.1% | +$1,429.60 | +3.0pp |
| buy10/sell26 | $15,788.98 | $5,769.86 | -34.2% | 57.9% | 62.4% | 13 | $365.00 | 86.9% | +$1,037.68 | +2.3pp |
| buy10/sell40 | $15,531.39 | $8,882.72 | -41.1% | 55.3% | 71.6% | 9 | $261.45 | 85.5% | +$780.10 | -4.5pp |
| buy12/sell16 | $16,137.78 | $6,486.58 | -30.5% | 61.4% | 58.9% | 11 | $394.89 | 88.9% | +$1,386.48 | +6.1pp |
| buy12/sell20 | $13,106.89 | $6,873.40 | -34.4% | 31.1% | 62.4% | 9 | $272.58 | 72.2% | -$1,644.41 | +2.2pp |
| buy12/sell26 | $12,789.43 | $5,769.86 | -34.2% | 27.9% | 61.7% | 12 | $333.01 | 70.4% | -$1,961.87 | +2.3pp |
| buy12/sell40 | $12,580.78 | $9,037.20 | -41.8% | 25.8% | 70.9% | 8 | $229.99 | 69.3% | -$2,170.52 | -5.2pp |

## Crash windows

### 2022

Anchors: 2021-12-26 → 2022-12-25 (52 weekly returns). Start BTC price $50,801.79; end $16,829.02.

| combo | End $ | Max DD $ | Max DD % | Total return | Time in BTC | Round trips | Fees $ | vs B&H end | vs SMA-8 end $ | vs SMA-8 max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| buy-and-hold | $3,312.68 | $6,800.80 | -68.0% | -66.9% | 100.0% | 0 | $0.00 | 100.0% | -$1,794.55 | -19.1pp |
| SMA-8 | $5,107.23 | $4,892.77 | -48.9% | -48.9% | 19.2% | 4 | $52.54 | 154.2% | +$0.00 | +0.0pp |
| SMA-12 | $5,317.74 | $4,682.26 | -46.8% | -46.8% | 17.3% | 5 | $67.49 | 160.5% | +$210.51 | +2.1pp |
| buy4/sell12 | $4,101.46 | $5,898.54 | -59.0% | -59.0% | 32.7% | 10 | $115.93 | 123.8% | -$1,005.77 | -10.1pp |
| buy4/sell16 | $5,777.76 | $4,222.24 | -42.2% | -42.2% | 28.8% | 11 | $136.14 | 174.4% | +$670.53 | +6.7pp |
| buy4/sell20 | $5,809.82 | $4,190.18 | -41.9% | -41.9% | 26.9% | 11 | $136.73 | 175.4% | +$702.59 | +7.0pp |
| buy4/sell26 | $6,383.48 | $3,616.52 | -36.2% | -36.2% | 25.0% | 12 | $161.95 | 192.7% | +$1,276.25 | +12.8pp |
| buy4/sell40 | $6,173.26 | $3,826.74 | -38.3% | -38.3% | 25.0% | 11 | $143.31 | 186.4% | +$1,066.03 | +10.7pp |
| buy6/sell12 | $4,309.97 | $5,690.03 | -56.9% | -56.9% | 25.0% | 7 | $90.58 | 130.1% | -$797.26 | -8.0pp |
| buy6/sell16 | $6,071.50 | $3,967.26 | -39.7% | -39.3% | 21.2% | 8 | $106.79 | 183.3% | +$964.27 | +9.3pp |
| buy6/sell20 | $6,105.19 | $3,933.79 | -39.3% | -38.9% | 19.2% | 8 | $107.19 | 184.3% | +$997.96 | +9.6pp |
| buy6/sell26 | $6,708.01 | $3,334.82 | -33.3% | -32.9% | 17.3% | 9 | $131.02 | 202.5% | +$1,600.78 | +15.6pp |
| buy6/sell40 | $6,438.41 | $3,602.70 | -36.0% | -35.6% | 19.2% | 9 | $126.32 | 194.4% | +$1,331.18 | +12.9pp |
| buy8/sell12 | $5,759.79 | $4,240.21 | -42.4% | -42.4% | 17.3% | 5 | $71.26 | 173.9% | +$652.56 | +6.5pp |
| buy8/sell16 | $5,759.79 | $4,240.21 | -42.4% | -42.4% | 17.3% | 5 | $71.26 | 173.9% | +$652.56 | +6.5pp |
| buy8/sell20 | $5,791.75 | $4,208.25 | -42.1% | -42.1% | 15.4% | 5 | $71.56 | 174.8% | +$684.52 | +6.8pp |
| buy8/sell26 | $6,382.75 | $3,617.25 | -36.2% | -36.2% | 11.5% | 6 | $95.21 | 192.7% | +$1,275.52 | +12.8pp |
| buy8/sell40 | $6,126.23 | $3,873.77 | -38.7% | -38.7% | 13.5% | 6 | $91.18 | 184.9% | +$1,019.00 | +10.2pp |
| buy10/sell12 | $4,705.83 | $5,294.17 | -52.9% | -52.9% | 19.2% | 5 | $63.66 | 142.1% | -$401.40 | -4.0pp |
| buy10/sell16 | $5,178.63 | $4,821.37 | -48.2% | -48.2% | 17.3% | 5 | $66.62 | 156.3% | +$71.40 | +0.7pp |
| buy10/sell20 | $5,207.36 | $4,792.64 | -47.9% | -47.9% | 15.4% | 5 | $66.88 | 157.2% | +$100.13 | +1.0pp |
| buy10/sell26 | $5,738.73 | $4,261.27 | -42.6% | -42.6% | 11.5% | 6 | $90.07 | 173.2% | +$631.50 | +6.3pp |
| buy10/sell40 | $5,508.09 | $4,491.91 | -44.9% | -44.9% | 13.5% | 6 | $86.25 | 166.3% | +$400.86 | +4.0pp |
| buy12/sell16 | $5,317.74 | $4,682.26 | -46.8% | -46.8% | 17.3% | 5 | $67.49 | 160.5% | +$210.51 | +2.1pp |
| buy12/sell20 | $5,347.24 | $4,652.76 | -46.5% | -46.5% | 15.4% | 5 | $67.76 | 161.4% | +$240.01 | +2.4pp |
| buy12/sell26 | $5,892.89 | $4,107.11 | -41.1% | -41.1% | 11.5% | 6 | $91.03 | 177.9% | +$785.65 | +7.9pp |
| buy12/sell40 | $5,656.05 | $4,343.95 | -43.4% | -43.4% | 13.5% | 6 | $87.18 | 170.7% | +$548.82 | +5.5pp |

### 2025-10-06..2026-06-30

Anchors: 2025-10-05 → 2026-06-28 (38 weekly returns). Start BTC price $123,520.79; end $59,474.01.

| combo | End $ | Max DD $ | Max DD % | Total return | Time in BTC | Round trips | Fees $ | vs B&H end | vs SMA-8 end $ | vs SMA-8 max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| buy-and-hold | $4,814.90 | $5,185.10 | -51.9% | -51.9% | 100.0% | 0 | $0.00 | 100.0% | -$1,591.83 | -15.9pp |
| SMA-8 | $6,406.73 | $3,593.27 | -35.9% | -35.9% | 42.1% | 5 | $71.63 | 133.1% | +$0.00 | +0.0pp |
| SMA-12 | $6,303.49 | $3,696.51 | -37.0% | -37.0% | 28.9% | 4 | $55.26 | 130.9% | -$103.24 | -1.0pp |
| buy4/sell12 | $6,941.73 | $3,058.27 | -30.6% | -30.6% | 34.2% | 5 | $74.21 | 144.2% | +$535.00 | +5.4pp |
| buy4/sell16 | $7,112.11 | $3,141.23 | -31.4% | -28.9% | 36.8% | 6 | $95.09 | 147.7% | +$705.38 | +4.5pp |
| buy4/sell20 | $6,851.91 | $3,148.09 | -31.5% | -31.5% | 34.2% | 6 | $94.83 | 142.3% | +$445.19 | +4.5pp |
| buy4/sell26 | $7,946.93 | $2,053.07 | -20.5% | -20.5% | 26.3% | 7 | $112.94 | 165.0% | +$1,540.20 | +15.4pp |
| buy4/sell40 | $6,056.21 | $3,943.79 | -39.4% | -39.4% | 34.2% | 7 | $85.63 | 125.8% | -$350.52 | -3.5pp |
| buy6/sell12 | $6,941.73 | $3,058.27 | -30.6% | -30.6% | 34.2% | 5 | $74.21 | 144.2% | +$535.00 | +5.4pp |
| buy6/sell16 | $7,112.11 | $3,141.23 | -31.4% | -28.9% | 36.8% | 6 | $95.09 | 147.7% | +$705.38 | +4.5pp |
| buy6/sell20 | $6,851.91 | $3,148.09 | -31.5% | -31.5% | 34.2% | 6 | $94.83 | 142.3% | +$445.19 | +4.5pp |
| buy6/sell26 | $7,946.93 | $2,053.07 | -20.5% | -20.5% | 26.3% | 7 | $112.94 | 165.0% | +$1,540.20 | +15.4pp |
| buy6/sell40 | $5,777.07 | $4,222.93 | -42.2% | -42.2% | 36.8% | 8 | $97.46 | 120.0% | -$629.65 | -6.3pp |
| buy8/sell12 | $6,561.76 | $3,438.24 | -34.4% | -34.4% | 36.8% | 6 | $87.74 | 136.3% | +$155.04 | +1.6pp |
| buy8/sell16 | $6,722.82 | $3,516.65 | -35.2% | -32.8% | 39.5% | 7 | $108.42 | 139.6% | +$316.09 | +0.8pp |
| buy8/sell20 | $6,476.87 | $3,523.13 | -35.2% | -35.2% | 36.8% | 7 | $108.18 | 134.5% | +$70.14 | +0.7pp |
| buy8/sell26 | $6,450.22 | $3,549.78 | -35.5% | -35.5% | 31.6% | 9 | $139.27 | 134.0% | +$43.49 | +0.4pp |
| buy8/sell40 | $5,777.07 | $4,222.93 | -42.2% | -42.2% | 36.8% | 8 | $97.46 | 120.0% | -$629.65 | -6.3pp |
| buy10/sell12 | $6,303.49 | $3,696.51 | -37.0% | -37.0% | 28.9% | 4 | $55.26 | 130.9% | -$103.24 | -1.0pp |
| buy10/sell16 | $6,892.63 | $3,352.89 | -33.5% | -31.1% | 31.6% | 5 | $75.02 | 143.2% | +$485.90 | +2.4pp |
| buy10/sell20 | $6,640.46 | $3,359.54 | -33.6% | -33.6% | 28.9% | 5 | $74.77 | 137.9% | +$233.73 | +2.3pp |
| buy10/sell26 | $7,348.05 | $2,651.95 | -26.5% | -26.5% | 23.7% | 7 | $109.85 | 152.6% | +$941.33 | +9.4pp |
| buy10/sell40 | $5,891.05 | $4,108.95 | -41.1% | -41.1% | 31.6% | 6 | $73.21 | 122.4% | -$515.68 | -5.2pp |
| buy12/sell16 | $6,892.63 | $3,352.89 | -33.5% | -31.1% | 31.6% | 5 | $75.02 | 143.2% | +$485.90 | +2.4pp |
| buy12/sell20 | $6,640.46 | $3,359.54 | -33.6% | -33.6% | 28.9% | 5 | $74.77 | 137.9% | +$233.73 | +2.3pp |
| buy12/sell26 | $7,348.05 | $2,651.95 | -26.5% | -26.5% | 23.7% | 7 | $109.85 | 152.6% | +$941.33 | +9.4pp |
| buy12/sell40 | $5,891.05 | $4,108.95 | -41.1% | -41.1% | 31.6% | 6 | $73.21 | 122.4% | -$515.68 | -5.2pp |

## Combos that beat SMA-8 without giving back the crash filter

Pre-declared callout: beat SMA-8 on full-sample end $ AND max DD at least 10pp better than buy-and-hold on both crash windows. Crash dollars below are those window paths, not the full-sample path.

- buy4/sell16: full-sample end $134,002.91 (SMA-8 $94,554.32); 2022 max DD -42.2% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -31.4% (SMA-8 -35.9%, B&H -51.9%).
- buy4/sell20: full-sample end $103,623.93 (SMA-8 $94,554.32); 2022 max DD -41.9% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -31.5% (SMA-8 -35.9%, B&H -51.9%).
- buy4/sell26: full-sample end $147,717.95 (SMA-8 $94,554.32); 2022 max DD -36.2% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -20.5% (SMA-8 -35.9%, B&H -51.9%).
- buy4/sell40: full-sample end $235,261.44 (SMA-8 $94,554.32); 2022 max DD -38.3% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -39.4% (SMA-8 -35.9%, B&H -51.9%).
- buy6/sell12: full-sample end $101,506.58 (SMA-8 $94,554.32); 2022 max DD -56.9% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -30.6% (SMA-8 -35.9%, B&H -51.9%).
- buy6/sell16: full-sample end $146,835.24 (SMA-8 $94,554.32); 2022 max DD -39.7% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -31.4% (SMA-8 -35.9%, B&H -51.9%).
- buy6/sell26: full-sample end $146,013.48 (SMA-8 $94,554.32); 2022 max DD -33.3% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -20.5% (SMA-8 -35.9%, B&H -51.9%).
- buy8/sell12: full-sample end $125,733.42 (SMA-8 $94,554.32); 2022 max DD -42.4% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -34.4% (SMA-8 -35.9%, B&H -51.9%).
- buy8/sell16: full-sample end $125,320.53 (SMA-8 $94,554.32); 2022 max DD -42.4% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -35.2% (SMA-8 -35.9%, B&H -51.9%).
- buy8/sell26: full-sample end $107,327.42 (SMA-8 $94,554.32); 2022 max DD -36.2% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -35.5% (SMA-8 -35.9%, B&H -51.9%).
- buy10/sell12: full-sample end $109,899.27 (SMA-8 $94,554.32); 2022 max DD -52.9% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -37.0% (SMA-8 -35.9%, B&H -51.9%).
- buy10/sell16: full-sample end $119,927.79 (SMA-8 $94,554.32); 2022 max DD -48.2% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -33.5% (SMA-8 -35.9%, B&H -51.9%).
- buy10/sell26: full-sample end $111,069.36 (SMA-8 $94,554.32); 2022 max DD -42.6% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -26.5% (SMA-8 -35.9%, B&H -51.9%).
- buy10/sell40: full-sample end $130,522.66 (SMA-8 $94,554.32); 2022 max DD -44.9% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -41.1% (SMA-8 -35.9%, B&H -51.9%).
- buy12/sell40: full-sample end $96,053.95 (SMA-8 $94,554.32); 2022 max DD -43.4% (SMA-8 -48.9%, B&H -68.0%); 2025–26 max DD -41.1% (SMA-8 -35.9%, B&H -51.9%).

Of those, also at least as shallow as SMA-8 on both crash windows: buy4/sell16, buy4/sell20, buy4/sell26, buy6/sell16, buy6/sell26, buy8/sell12, buy8/sell16, buy8/sell26, buy10/sell16, buy10/sell26. The rest still cleared 10pp vs buy-and-hold but gave back some of SMA-8's own crash cut (typically sell=12 in 2022, sell=40 in 2025–26).
Those cells are still in-sample grid picks, not a new frozen product rule.

## 2024–now vs SMA-8's share of buy-and-hold

SMA-8 ends $14,751.30 vs buy-and-hold $18,161.12 (81.2% of B&H). SMA-8 total return 47.5% vs B&H 81.6%. The 2022 filter here is 10pp vs buy-and-hold, the same bar SMA-8 itself clears.
Combos that did both:
- buy4/sell16: end $21,754.94 (119.8% of B&H); 2022 max DD -42.2% (SMA-8 -48.9%).
- buy4/sell20: end $17,669.07 (97.3% of B&H); 2022 max DD -41.9% (SMA-8 -48.9%).
- buy4/sell26: end $18,355.88 (101.1% of B&H); 2022 max DD -36.2% (SMA-8 -48.9%).
- buy4/sell40: end $17,909.89 (98.6% of B&H); 2022 max DD -38.3% (SMA-8 -48.9%).
- buy6/sell12: end $21,256.36 (117.0% of B&H); 2022 max DD -56.9% (SMA-8 -48.9%).
- buy6/sell16: end $23,948.42 (131.9% of B&H); 2022 max DD -39.7% (SMA-8 -48.9%).
- buy6/sell20: end $19,450.59 (107.1% of B&H); 2022 max DD -39.3% (SMA-8 -48.9%).
- buy6/sell26: end $19,892.87 (109.5% of B&H); 2022 max DD -33.3% (SMA-8 -48.9%).
- buy6/sell40: end $17,872.42 (98.4% of B&H); 2022 max DD -36.0% (SMA-8 -48.9%).
- buy8/sell12: end $16,815.62 (92.6% of B&H); 2022 max DD -42.4% (SMA-8 -48.9%).
- buy8/sell16: end $18,945.27 (104.3% of B&H); 2022 max DD -42.4% (SMA-8 -48.9%).
- buy8/sell20: end $15,387.10 (84.7% of B&H); 2022 max DD -42.1% (SMA-8 -48.9%).
- buy8/sell40: end $14,849.54 (81.8% of B&H); 2022 max DD -38.7% (SMA-8 -48.9%).
- buy10/sell12: end $17,024.12 (93.7% of B&H); 2022 max DD -52.9% (SMA-8 -48.9%).
- buy10/sell16: end $20,470.35 (112.7% of B&H); 2022 max DD -48.2% (SMA-8 -48.9%).
- buy10/sell20: end $16,180.90 (89.1% of B&H); 2022 max DD -47.9% (SMA-8 -48.9%).
- buy10/sell26: end $15,788.98 (86.9% of B&H); 2022 max DD -42.6% (SMA-8 -48.9%).
- buy10/sell40: end $15,531.39 (85.5% of B&H); 2022 max DD -44.9% (SMA-8 -48.9%).
- buy12/sell16: end $16,137.78 (88.9% of B&H); 2022 max DD -46.8% (SMA-8 -48.9%).

Of those, 2022 max DD at least as shallow as SMA-8: buy4/sell16, buy4/sell20, buy4/sell26, buy4/sell40, buy6/sell16, buy6/sell20, buy6/sell26, buy6/sell40, buy8/sell12, buy8/sell16, buy8/sell20, buy8/sell40, buy10/sell16, buy10/sell20, buy10/sell26, buy10/sell40, buy12/sell16.

## What I would not do

I would not replace frozen SMA-8 with whichever cell printed the highest full-sample end dollars. That selection uses the same sample the table is scored on. If a later product rule needs a different SMA pair, freeze it first, then score — do not crown a winner from this map.

## How to re-run

```
.venv/bin/python -m price_forecast.sma_asymmetric_10k
```

Writes `price_forecast/sma_asymmetric_10k_results.md`. State machine is `asymmetric_sma_signal` in `price_forecast/weekly_regime.py`. Dollar fills reuse `dollar_backtest`.
