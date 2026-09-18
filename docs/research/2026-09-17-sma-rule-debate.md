# Which SMA rule to freeze in Prism v1

**Date:** 2026-09-17  
**Scope:** Product/research note for Prism. Not investment advice. No recommendation to buy, sell, hedge, or size a Bitcoin position. This is which *already-backtested* weekly in/out rule to freeze as the v1 product action.  
**Question:** Symmetric SMA-8, buy6/sell40, or a mid pair (buy8/sell16 if the tables support it) — which one matches the user’s stated dump and the “~80% of buy-and-hold is good enough” bar?  
**No new grid search. No product code.** Numbers below are copied from the existing result files. Full-sample dollars from `sma8_10k` and from the asymmetric 40-week-warmup window are **not** the same window.

---

## The answer in one paragraph

Freeze **buy 8 / sell 16** as Prism v1. It is the only candidate that (1) matches the dump the user named, (2) clears the 80% long-run bar without being the max cell, and (3) actually delivers the original “C” wish that SMA-8 missed. On the Oct 2025–Jun 2026 grind, buy8/sell16’s hole is **−35.2%** vs SMA-8 **−35.9%** and buy6/sell40 **−42.2%**. On 2024–latest it ends at **104.3%** of buy-and-hold vs SMA-8’s **81.2%**. SMA-8 is the honest runner-up: close on the named dump, simpler, frozen first. It lost because 81% of buy-and-hold was “good enough,” not best, once a mid pair kept the crash. buy6/sell40 lost on criterion (a): all-time max DD of −55.4% is the wrong hole. On the 2025–26 path it is *worse* than SMA-8, and it is not even in the “10pp vs buy-and-hold on both crashes” list.

---

## What these rules actually do

All three are weekly, 100% BTC or 100% cash, no shorts. Signal at this Sunday’s close fills at next week’s close. Cash earns 0. Each flip costs 10 bps of wealth. Same Coinbase BTC-USD weekly closes (UTC Monday–Sunday) as the rest of `price_forecast/`.

**Symmetric SMA-8:** in BTC iff this week’s close is strictly above the 8-week SMA (SMA includes this close). One number. Can flip every week. Defined in `sma_signal(..., lookback=8)` in `price_forecast/weekly_regime.py`.

**Asymmetric buy N / sell M:** while in BTC, sell to cash iff close is strictly below the *longer* SMA; while in cash, buy iff close is strictly above the *shorter* SMA. Hysteresis: the exit is slower than the entry. Defined in `asymmetric_sma_signal` in the same file. The frozen 24-cell grid was `buy ∈ {4,6,8,10,12}` × `sell ∈ {12,16,20,26,40}` with sell > buy (`price_forecast/sma_asymmetric_10k.py`).

**Mid pair used here:** **buy8/sell16**. It is on the “at least as shallow as SMA-8 on both crash windows” list in `sma_asymmetric_10k_results.md`. That is why it is the mid pair, not buy6/sell16 (better-looking cell, not pre-named) and not buy8/sell26 (fails the 80% 2024 bar).

**buy4/sell40** is the full-sample max cell ($235,261.44). Already rejected as a lock. Mentioned only so nobody “discovers” it again.

---

## What the user actually asked for

From `docs/research/2026-09-17-btc-protection-after-point-forecast.md` and the later SMA scoreboards:

- Hold BTC for long-horizon wealth, with some protection against a ~50% drop.
- The cited drop is the **Oct 2025 → Jun 2026 grind**, close-to-close **−53.08%** over 267 days on this Coinbase series — not a 10-day crash, and not calendar-2026’s −39.64% (`docs/research/2026-09-17-btc-protection-after-point-forecast.md` §2). 2022 is the other named stress: calendar 2022 close-to-close **−66.98%** in that note; the weekly $10k windows measure **−68.0%** buy-and-hold max DD.
- Product action: weekly trend, mostly cash when out, full BTC when back in.
- Frozen weekly bakeoff labels (`price_forecast/weekly_bakeoff_results.md`): **C** = max DD at least 10pp better than buy-and-hold *and* terminal wealth ≥ 90% of buy-and-hold; **A** = the drawdown cut alone; **product C** also needs 2024–latest wealth within 10% of buy-and-hold. C on both crashes: several rules including SMA-8. Product C: **none**. Then the user said **~80% of buy-and-hold is good enough**; SMA-8 was **81.2%** of buy-and-hold on 2024–latest (`sma8_10k_results.md` and `sma_asymmetric_10k_results.md`, same window).
- Live challenge: why not **buy6/sell40**, which prints more full-sample dollars and **−55.4%** all-time max DD vs SMA-8’s **−63.2%** on the 40-week-warmup sample.

---

## Comparison (same $10k fresh start, same weeks)

Do **not** compare `sma8_10k`’s full-sample $43,392.33 (starts 2018-03-04 at $11,469.90 after 8-week warmup) to the asymmetric full-sample $94,554.32 (starts 2018-10-14 at $6,183.49 after 40-week warmup). Calendar windows 2022, 2025-10-06..2026-06-30, and 2024–latest use the **same anchors** in both reports.

Weekly bakeoff SMA-8 crash DDs (−45.1% in 2022, −31.3% in 2025–26) inherit a pre-window fill and start in cash. The table below uses the **fresh $10k BTC** path so SMA-8 and the asymmetric cells share a start. Those crash/2024 SMA-8 dollars match `sma8_10k_results.md` exactly.

| Window | Rule | End $ | Max DD | vs B&H end | vs SMA-8 end $ | vs SMA-8 max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| **Full sample (40w warmup)** 2018-10-14→2026-09-13, start $6,183.49 | buy-and-hold | $124,201.46 | −75.2% | 100.0% | +$29,647.15 | −12.0pp |
| | SMA-8 | $94,554.32 | −63.2% | 76.1% | — | — |
| | buy6/sell40 | $187,998.30 | −55.4% | 151.4% | +$93,443.98 | +7.8pp |
| | **buy8/sell16** | $125,320.53 | −58.2% | 100.9% | +$30,766.21 | +5.0pp |
| **Full sample (8w warmup)** 2018-03-04→2026-09-13, start $11,469.90 — SMA-8 report only | buy-and-hold | $66,957.73 | −75.2% | 100.0% | — | — |
| | SMA-8 | $43,392.33 | −63.2% | 64.8% | — | — |
| **2022** 2021-12-26→2022-12-25, start $50,801.79 | buy-and-hold | $3,312.68 | −68.0% | 100.0% | −$1,794.55 | −19.1pp |
| | SMA-8 | $5,107.23 | −48.9% | 154.2% | — | — |
| | buy6/sell40 | $6,438.41 | −36.0% | 194.4% | +$1,331.18 | +12.9pp |
| | **buy8/sell16** | $5,759.79 | −42.4% | 173.9% | +$652.56 | +6.5pp |
| **2025-10-06..2026-06-30** 2025-10-05→2026-06-28, start $123,520.79 | buy-and-hold | $4,814.90 | −51.9% | 100.0% | −$1,591.83 | −15.9pp |
| | SMA-8 | $6,406.73 | −35.9% | 133.1% | — | — |
| | buy6/sell40 | $5,777.07 | −42.2% | 120.0% | **−$629.65** | **−6.3pp** |
| | **buy8/sell16** | $6,722.82 | −35.2% | 139.6% | +$316.09 | +0.8pp |
| **2024-01-01..latest** 2023-12-31→2026-09-13, start $42,288.06 | buy-and-hold | $18,161.12 | −51.9% | 100.0% | +$3,409.82 | −15.3pp |
| | SMA-8 | $14,751.30 | −36.6% | **81.2%** | — | — |
| | buy6/sell40 | $17,872.42 | −42.2% | 98.4% | +$3,121.12 | −5.7pp |
| | **buy8/sell16** | $18,945.27 | −30.9% | **104.3%** | +$4,193.97 | +5.7pp |

Sources: `price_forecast/sma_asymmetric_10k_results.md` (all four windows for SMA-8, buy6/sell40, buy8/sell16, buy-and-hold); `price_forecast/sma8_10k_results.md` (8-week-warmup full sample, and the three calendar windows which match the asymmetric SMA-8 rows).

buy4/sell40 (rejected max cell), same file, for the record only: full-sample $235,261.44 / −56.6%; 2025–26 −39.4% (worse than SMA-8); 2024–latest $17,909.89 / 98.6% of B&H / −40.5% DD.

---

## Debate

### Case for SMA-8

It was frozen before anyone opened the 24-cell grid. That is the strongest anti-overfit story in this repo. The user already said ~80% of buy-and-hold long-run is good enough; SMA-8 is **81.2%** of buy-and-hold on 2024–latest (`sma8_10k_results.md`). On the named dump it cuts the weekly $10k hole from **−51.9%** to **−35.9%** and finishes $6,407 vs hold $4,815. On 2022 it cuts **−68.0%** to **−48.9%** and finishes $5,107 vs hold $3,313. The weekly bakeoff, with inherited fills, still gives SMA-8 a **C** on both crash windows and an **A** on 2024–latest, and names it among the crash-window C winners (`weekly_bakeoff_results.md`). One lookback. No pair to retune next week. Product action is already “weekly trend, cash when out, full BTC when in.” If the job is “ship the rule we already trusted before looking,” this is it.

### Case for buy6/sell40

On the 40-week-warmup full sample it more than doubles SMA-8’s ending dollars ($187,998 vs $94,554) and prints a shallower all-time max DD (**−55.4%** vs **−63.2%**). 2022 is a clear win: **−36.0%** vs SMA-8 **−48.9%**, end $6,438 vs $5,107. 2024–latest wealth is **98.4%** of buy-and-hold — closer to hold than SMA-8’s 81.2%, and well above the 80% concession. Time in BTC on the full sample is 71.2% vs SMA-8’s 53.3%, so more of the bull is kept. If you believe “more money and a smaller all-time hole” is the spec, this cell answers the user’s challenge on its own terms.

### Case for buy8/sell16

Buy = 8 is the lookback Prism already froze; sell = 16 is one mid step on the pre-declared sell grid, not 40 and not the max cell. It is in the “kept both crashes vs SMA-8” list (`sma_asymmetric_10k_results.md`: buy4/sell16, buy4/sell20, buy4/sell26, buy6/sell16, buy6/sell26, buy8/sell12, **buy8/sell16**, buy8/sell26, buy10/sell16, buy10/sell26). On the named dump it is at least as shallow as SMA-8 (**−35.2%** vs **−35.9%**, +$316). On 2022 it is clearly better (**−42.4%** vs **−48.9%**). On 2024–latest it ends at **104.3%** of buy-and-hold with max DD **−30.9%** vs SMA-8 **−36.6%**. That is the original product-C shape (crash cut *and* long-run not worse than hold) that SMA-8 failed at the 90% wealth bar. Full-sample wealth is 100.9% of buy-and-hold vs SMA-8’s 76.1% on the same 40-week window. Among other buy=8 cells: sell26 fails the 80% 2024 bar (74.4% of B&H); sell12 keeps both crashes but 2024 max DD is *worse* than SMA-8 (−38.2% vs −36.6%); sell40 fails the named dump the same way buy6/sell40 does (−42.2%). So 16 is the buy=8 exit that is mid, crash-safe vs SMA-8, and above 80% on 2024–now.

### What kills each case

**SMA-8.** The 80% bar was a concession after product C failed, not a preference for leaving ~19pp of 2024–latest buy-and-hold on the table. On the *same* fresh-$10k windows, buy8/sell16 keeps the named dump (0.8pp better, not worse) and finishes above buy-and-hold on 2024–latest. “Frozen first” is a real overfitting defense. It is not a reason to ignore a mid pair that was also on the table *before* this debate, whose buy leg is the same 8-week SMA, and that passes the user’s ordered criteria. SMA-8 also only reaches 76.1% of buy-and-hold on the 40-week full sample — the 81.2% figure is the 2024–latest window, not all-time.

**buy6/sell40.** Criterion (a) kills it. The user named the 2025–26 grind, not all-time max DD. On that window buy6/sell40 is **worse** than SMA-8: max DD **−42.2%** vs **−35.9%** (−6.3pp), end **$5,777** vs **$6,407**. It is **not** in the pre-declared “beat SMA-8 on full-sample end $ AND 10pp better than buy-and-hold on both crashes” list — on the published 0.1% figures the 2025–26 hole is 9.7pp shallower than hold (−42.2% vs −51.9%), under the 10pp C bar that SMA-8 itself clears (16.0pp). The results file already flags the pattern: cells that miss SMA-8’s own crash cut are “typically sell=12 in 2022, **sell=40 in 2025–26**.” 2024–latest max DD is also worse than SMA-8 (−42.2% vs −36.6%) because that window *contains* the grind. The −55.4% all-time figure is a different hole on a sample that includes 2018. Eight round trips in 38 weeks vs SMA-8’s five: this is not a clean “stay out longer” exit; it is a slow SMA that still chops. If full-sample dollars were the lock, buy4/sell40 is richer ($235k). That cell was already rejected.

**buy8/sell16.** It is still an in-sample grid cell. The asymmetric report says so in so many words: “Those cells are still in-sample grid picks, not a new frozen product rule.” The 2025–26 edge vs SMA-8 is **tiny** (0.8pp, $316). If the only test were the named dump, SMA-8 and 8/16 are nearly tied. Two integers are more retune surface than one. buy6/sell16 looks better on every window in the same table; refusing it is a discipline choice, not a scoreboard choice. Anyone who wants “the best cell that kept both crashes” would not stop at 8/16. The defense is the naming reason: keep the already-frozen buy=8, take a mid sell that is on the kept-both-crashes list and that does not fail 2024’s 80% bar — not “scan the 10 survivors and crown the max.”

---

## The pick, against the ordered criteria

**a) Matches the stated dump (2025–26 grind + 2022), not just all-time max DD.**  
buy6/sell40 fails. SMA-8 and buy8/sell16 both pass; 8/16 is slightly better on both crash windows.

**b) Long-run wealth at least ~80% of B&H on 2024–latest.**  
All three pass: SMA-8 81.2%, buy6/sell40 98.4%, buy8/sell16 104.3%. Only 8/16 is above buy-and-hold. That is the original product-C wealth bar (within 10% of hold) that the weekly bakeoff said **none** of the frozen symmetric/dual/Donchian rules hit.

**c) Named with a reason that is not “it was the max cell on the 24-grid.”**  
buy4/sell40 is the max cell; out. buy6/sell40 is the user’s wealth/all-time-DD challenge, adjacent to that ridge (buy8/sell40 is the next cell down). SMA-8 was frozen before the grid. buy8/sell16: buy leg is that frozen 8; sell leg is a mid grid step that survived the crash-vs-SMA-8 list and the 80% 2024 bar. That is a naming reason.

**d) Simple enough to not retune next week.**  
SMA-8 is simpler. buy8/sell16 is still two frozen integers and the state machine already in `asymmetric_sma_signal`. Freeze it; do not reopen `{12,16,20,26,40}`.

Two rules are close on the dump the user named: SMA-8 and buy8/sell16. Still pick one. **buy8/sell16**, because the ordered criteria do not say “prefer the rule that was frozen first.” They say match the dump, then keep ~80% of the bull, then don’t lock the max cell, then don’t retune. SMA-8 is the runner-up. buy6/sell40 is the rejected challenger.

---

## Why the runner-up lost

**SMA-8** lost as v1 because “81% of buy-and-hold is good enough” was the floor after C failed, not the target. On the same 2024–latest window, buy8/sell16 is 104.3% of hold and a shallower hole (−30.9% vs −36.6%) without giving back the 2025–26 cut. Shipping SMA-8 would be choosing simplicity and freeze-order over the user’s original C wish, once a mid pair that uses SMA-8’s own buy lookback already shows that C-shaped outcome on these windows.

**buy6/sell40** lost harder. The −55.4% vs −63.2% all-time comparison answers a question the user did not ask. On the question they did ask — the 2025–26 grind — it is the worst of the three.

---

## What to do, in order

1. Freeze **buy8/sell16** as the Prism v1 weekly in/out rule (`asymmetric_sma_signal(buy_weeks=8, sell_weeks=16)`). Do not retune after this note.
2. Keep SMA-8 as the published one-parameter baseline, not as the product rule.
3. Leave buy6/sell40 and buy4/sell40 as map cells. Do not promote them because full-sample dollars or all-time DD look better.
4. Skip a new grid, a new lookback, and any “just try buy6/sell16 because the table is prettier” pass. That would be the search this note refused.

**Skip for now:** implementing the product switch, fees other than the 10 bp assumption, and treating these dollars as a live allocation.

---

## Sources

- `docs/research/2026-09-17-btc-protection-after-point-forecast.md` — user goal; Coinbase −53.08% path 2025-10-06→2026-06-30; 2022 calendar −66.98%; C vs A language in the later bakeoff.
- `price_forecast/sma_asymmetric_10k_results.md` — 40-week-warmup full sample and the three calendar windows; 24-cell grid; “kept both crashes vs SMA-8” list; buy4/sell40 as max cell; sell=40 pattern on 2025–26.
- `price_forecast/sma8_10k_results.md` — 8-week-warmup full sample; SMA-8 vs hold on 2022 / 2025–26 / 2024–latest (matches the asymmetric SMA-8 calendar rows).
- `price_forecast/weekly_bakeoff_results.md` — C / A / product C definitions and SMA-8’s C-on-crashes / fail-product-C result (inherited-fill wealth, not the $10k table).
- `price_forecast/weekly_regime.py` — `sma_signal`, `asymmetric_sma_signal`, 10 bp cost, weekly close convention.
- `price_forecast/sma_asymmetric_10k.py` — frozen `BUY_WEEKS` / `SELL_WEEKS`; 40-week warmup; pre-declared callout vs SMA-8.
- `price_forecast/sma8_10k.py` — frozen SMA-8 dollar windows.
- `price_forecast/weekly_bakeoff.py` — `WINDOWS`, `CRASH_WINDOWS`, `LONG_RUN_WINDOW`, `WEALTH_FLOOR = 0.9`, `DD_IMPROVEMENT = 0.10`.
