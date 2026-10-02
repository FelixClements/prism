# CrashGate search loop

**Date:** 2026-10-02
**Status:** Draft for review
**Scope:** Add an unattended search that breeds CrashGate-style rules, scores them, and stores a ledger. The locked CrashGateV1 file stays unchanged until a person promotes a row by hand.

This spec records the design agreed in chat.

## Goal

Run a contest that starts from the locked CrashGateV1 rule and tries nearby rules made from the blocks this repo already knows how to trade. Each round keeps a small pool of the best specs, mutates one of them, and writes every result to a ledger. Remix and synthetic paths are a stress check. A rule that looks strong on Coinbase and weak on those paths does not become a parent.

The champion is a ledger row. Promoting it means a person chooses to build it into a strategy file later. This loop never does that.

## Non-goals

- Editing `price_forecast/strategies/crashgate_v1.py`, its fill, its fee, or its locked 2026-09-28 behavior
- Changing `routing-crypto-strategy-skills` so that one skill calls the next
- Changing `backtest-expert` or `edge-strategy-reviewer`, including their 30-trade warnings
- Treating fewer than 30 Coinbase round trips as a failure, or rewarding a rule for trading more often
- Adding remix or synthetic round trips into the Coinbase trade count
- Adding a new indicator block in this job. Unknown ideas go to a side pile
- Using another exchange. No second tape is in this repo
- Holding out a calendar tail. A rule like CrashGate has too few trades in a short tail for that tail to accept or reject a spec
- Training a forecast model, or rewriting the data factories

## What already exists

CrashGateV1 buys on the weekly close when the close is above the 8-week average, the daily path is a pre-breakout or a breakout, and price is above the 150-day and 200-day averages. It sells when the close is below the 16-week average, or the week fell 10% and the close is below the 8-week average. The fill is the next weekly close. The fee is 0.15% per fill. It starts in cash. On the Coinbase file it has 14 completed round trips.

`price_forecast/strategies/signals.py` already has close-versus-average, average-versus-average, the asymmetric average state machine, and a prior-high breakout. `price_forecast/strategies/crashgate_entry.py` already answers the daily base-or-breakout question and the combined 150-day and 200-day check.

`python -m price_forecast.datafactory.remix` and `python -m price_forecast.datafactory.synthetic` already write candle files. A cloud of scores on those files is a stress result. The synthetic regimes were fit on the same Coinbase tape. That cloud is not a second Bitcoin history.

`backtest-expert` gives the sample-size category 0 points below 30 trades and raises `small_sample`. `edge-strategy-reviewer` warns when a draft looks like fewer than 30 opportunities per year. `residual-edge-analyzer` is not part of this loop. It reads a weekly return series and can be run by hand before a person promotes a row.

## Layout

```
price_forecast/search/__init__.py
price_forecast/search/spec.py
price_forecast/search/mutate.py
price_forecast/search/translate.py
price_forecast/search/runner.py
price_forecast/search/score.py
price_forecast/search/ledger.py
price_forecast/search/__main__.py
tests/search/__init__.py
tests/search/test_spec.py
tests/search/test_mutate.py
tests/search/test_translate.py
tests/search/test_runner.py
tests/search/test_score.py
tests/search/test_ledger.py
tests/search/test_preflight.py
```

Command: `python -m price_forecast.search`.

Outputs, gitignored:

```
results/search/ledger.jsonl
results/search/pool.json
results/search/side_pile.jsonl
```

Add `results/search/` to `.gitignore`.

The loop reads `data/btc-usd-daily.csv`, `data/remix/btc-usd-daily-seed0-path{0..99}.csv`, and `data/synthetic/btc-usd-daily-seed0-path{0..99}.csv`. It does not write the locked strategy file.

## Spec

A spec is data. It cannot set the fill, the fee, or the starting cash. Those stay next-week close, 0.15% per fill, and cash.

One spec has a mode and the fields for that mode.

**Threshold mode.** This is the CrashGate shape. Entry is the conjunction of the entry fields that are on. Exit is the disjunction of the exit fields that are on. At least one entry field and one exit field must be on.

Entry fields:

- `close_above_sma_weeks`: one of 4, 6, 8, 10, 12, 20, or off
- `base_or_breakout`: on or off. On uses the existing pre-breakout or breakout state
- `above_long_averages`: on or off. On uses the existing combined 150-day and 200-day pass

Exit fields:

- `close_below_sma_weeks`: one of 12, 16, 20, 26, 30, 40, or off
- `down_week`: off, or one of 0.05, 0.08, 0.10, 0.12. When on, the week fell by at least that fraction and the close is below a reference average. The reference is `close_above_sma_weeks` when that field is on, otherwise `close_below_sma_weeks`. A spec with `down_week` on and both averages off is rejected

The locked rule as a threshold spec:

- `close_above_sma_weeks` 8
- `base_or_breakout` on
- `above_long_averages` on
- `close_below_sma_weeks` 16
- `down_week` 0.10

**Dual-average mode.** In while the fast average is above the slow average. Fast and slow are a pair from (4, 12), (8, 16), (8, 20), (10, 30), (12, 26). Optional `base_or_breakout` and `above_long_averages` filters use the same meaning as in threshold mode.

**Prior-high mode.** In on a week whose close is at or above the highest close of the prior N weeks, excluding this week. N is 8, 12, 20, or 26. Out on every other week. The same two optional filters apply.

`spec.py` rejects a document that names any other field, any other number, or a mode whose required fields are off. Rejection raises before a ledger row is scored.

## Mutator

Each child differs from its parent by one edit:

- the mode changes to another mode, and the new mode's fields are that mode's first listed values, with both optional filters off
- or one numeric field moves to the next or previous allowed value
- or one on/off field flips

The edit is chosen with `numpy.random.Generator(numpy.random.PCG64(numpy.random.SeedSequence([run_seed, cycle])))`. The default `run_seed` is 0. The same seed and cycle produce the same child from the same parent.

## Translator

A pivot is requested only after 50 completed cycles in which the champion's breeding number did not strictly increase. Error cycles and stress-check failures count toward those 50. The loop then writes the champion as a draft YAML and writes a diagnosis JSON whose `triggers_fired` list has one entry, and runs `strategy-pivot-designer`'s `generate_pivots.py` once with `--max-pivots 1`. That script's built-in ideas include phrases this grammar does not have, such as RSI. The translator does not change the script.

A draft whose every condition maps onto the fields in this spec becomes one child, with the champion as its parent. Any unmatched phrase appends one JSON object to the side pile. The object stores the draft id and the unmatched phrase. The side-pile count is that file's line count. That draft gets no score and is not a parent. The loop then returns to mutation. Another pivot is not requested until 50 further cycles pass with no new champion. The pivot outputs are written under `results/search/pivots/` and are gitignored with the rest of that directory.

## Runner

The runner turns a spec into a position on each weekly close and simulates it with the CrashGate clock: signal on this weekly close, fill on the next weekly close, 0.15% of wealth per fill, start in cash, start flat. Weekly bars come from the existing week builder.

The base-or-breakout and long-average answers come from `BaseBreakoutGate`'s existing inputs, read as two separate switches. A spec with both switches off does not call that gate. A file-and-date pair is cached, because a child that turns a switch on calls the gate on every stress path.

A spec that raises during simulation appends an error row and is not scored. The loop continues.

## Coinbase metrics

On the real Coinbase file the scorer records:

- total return
- edge, defined as strategy total return minus buy-and-hold total return on that same file
- Sharpe of weekly equity returns, risk-free rate 0, annualized with `sqrt(52)`. A zero standard deviation makes Sharpe undefined
- max drawdown, using the existing peak-to-trough function
- win rate of completed round trips
- profit factor of completed round trips
- completed round-trip count

Undefined Sharpe, undefined profit factor, or zero completed round trips makes the child an error row. It is stored and kept out of the pool. Trade count is stored. It does not decide pool membership.

The locked CrashGate spec is scored once on Coinbase before breeding. Those five numbers are the baseline stored on every later row: total return, Sharpe, max drawdown, win rate, and profit factor. If that baseline Sharpe is undefined, or if total return, Sharpe, absolute max drawdown, win rate, or profit factor is 0, the process exits 1 and writes nothing under `results/search/`. The locked rule's published result is positive on each of these, so this exit is a broken score rather than a trading outcome.

## Breeding number

Each of the five Coinbase metrics becomes a ratio against that locked baseline. Drawdown uses absolute values, so a shallower child drawdown produces a ratio above 1. Each ratio is clipped to the range 0 through 3. The breeding number is the sum of the five clipped ratios. The locked spec's own breeding number is 5.

A child whose Coinbase edge is not strictly positive stays out of the pool. Its stress means are left null and the 200 paths are not run.

## Stress check

Before breeding, these files must exist:

- `data/btc-usd-daily.csv`
- `data/remix/btc-usd-daily-seed0-path0.csv` through `path99.csv`
- `data/synthetic/btc-usd-daily-seed0-path0.csv` through `path99.csv`

If the Coinbase file is missing, the process exits 1 and writes nothing under `results/search/`. If any remix or synthetic path is missing, the loop runs the existing factory command with `--n-paths 100 --seed 0` for that factory only. Remix keeps its current default mean block length. Breeding does not start until all 200 files exist. A factory failure exits 1 and writes nothing under `results/search/`.

A child with a strictly positive Coinbase edge is then run on those same 200 files. For each file the edge is strategy total return minus buy-and-hold total return on that file. The remix score is the arithmetic mean of the 100 remix edges. The synthetic score is the arithmetic mean of the 100 synthetic edges.

The child fails the stress check when either mean is under half of that child's own Coinbase edge. Both means, and each mean minus the Coinbase edge, are stored on the row. A failed child is kept in the ledger and kept out of the pool. The half-edge comparison is not applied to a non-positive Coinbase edge. That child has already failed the pool rule above.

Raw terminal wealth is not averaged. A synthetic path can end at a different price, so a large profit there mostly says that path went up.

## Fragility

For a child with strictly positive Coinbase net profit, subtract each completed round trip's pnl from strategy end dollars once. Buy-and-hold return stays the full-sample number. Recompute edge from that lower end wealth. The row is fragile if any single omission cuts that edge to half or less of the full-sample edge, or turns it non-positive. A fragile row stays out of the pool. This check uses Coinbase trips only. It does not resimulate the path.

## Skill warnings

`backtest-expert`'s `evaluate` and `edge-strategy-reviewer`'s `review_draft` are imported and called on a tiny fixed fixture during startup. If either import or call raises, the process exits 1 and writes nothing under `results/search/`.

On each scored row the loop runs both tools with the real trade count and stores their verdict, the `small_sample` flag when present, and the reviewer sample warning when present. Those fields do not add or remove pool members. The tools are not modified.

## Pool

The pool holds at most 20 specs. It starts with one member: the locked CrashGate threshold spec, scored on Coinbase and on the 200 paths. That seed member is inserted even if it would fail the stress check or the fragility check, so the contest has a parent. Its stress means and fragility mark are still stored.

Each cycle:

1. Choose a parent uniformly from the pool with `SeedSequence([run_seed, cycle, 1])`.
2. Mutate one child.
3. Score it.
4. Insert it when it has a breeding number, its Coinbase edge is positive, it passes the stress check, it is not fragile, and either the pool has fewer than 20 members or its breeding number is strictly greater than the lowest breeding number in the pool.
5. When the pool is already full and the child is inserted, drop the member with the lowest breeding number. A tie does not displace the older member.

The champion is the pool member with the highest breeding number. A tie keeps the older member. The champion id is stored in `pool.json`. Fifty cycles with no strict increase of that number cause one translator pass, as specified above.

`--cycles N` runs N cycles and exits 0. Omitting `--cycles` runs until the process is interrupted. A finished cycle's ledger line is durable. An interrupted cycle writes no partial line.

If `pool.json` is missing or its member list is empty at startup, after preflight, the pool is refilled with the locked spec and that spec is scored again.

## Ledger line

One JSON object per line, written by creating a temp file and renaming it over the target only after the new line is complete. Fields:

- `id`, `parent_id`, `cycle`, `spec`
- `status`: `ok` or `error`. Unmapped drafts are not ledger rows. They go only to the side pile
- `error` when status is `error`
- Coinbase metrics, baseline metrics, and `breeding_number` when status is `ok`
- `remix_mean_edge`, `synthetic_mean_edge`, `stress_pass` when the 200 paths were run. Otherwise the means are null and `stress_pass` is false
- `fragile`, `round_trips`
- `skill_warnings` when status is `ok`
- `trial_count`: the seed row is 0. Each later `ok` row increments it by one. Error rows store the current count and do not increment it. The same count is copied onto the champion in `pool.json`

## Tests

Tests live under `tests/search/` and use small candle fixtures. They do not generate 200 paths and they do not call the VCP screener. The gate is a fake that returns a fixed boolean.

- An unknown field or an unknown number is rejected.
- One mutation changes exactly one mode, one number, or one switch.
- A draft that only uses allowed fields becomes a spec. A draft that says "funding" adds one side-pile line and produces no score.
- The runner fills on the next weekly close and charges 0.15%. A spec has no field that changes either one.
- A child fails when either path-family mean edge is under half its Coinbase edge, and passes when both means are at least half. The fixture uses two paths per family, not 100. The production cutoff stays 100.
- Omitting one trip and cutting the Coinbase edge to half or less marks the row fragile and keeps it out of the pool.
- A missing Coinbase file, a factory failure, or a failed skill fixture writes nothing under `results/search/`.
- A crash after a temp write leaves the previous ledger intact. An empty pool reloads the locked spec.
- A search run does not modify `price_forecast/strategies/crashgate_v1.py`.

## Startup order

1. Confirm the Coinbase CSV exists.
2. Confirm or build the 200 stress files.
3. Run the two skill fixtures.
4. Load or reseed the pool.
5. Breed.

Any failure in steps 1 through 3 exits before step 4 and leaves `results/search/` unchanged. Step 4 may write the reseeded pool and the locked spec's ledger line.
