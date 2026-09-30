# Synthetic regime factory

**Date:** 2026-09-30  
**Status:** Draft for review  
**Scope:** Move the stationary-bootstrap remixer under `price_forecast/datafactory/`, and add a second history factory that writes fully synthetic BTC-USD daily candles from six regimes fit on the real Coinbase tape.

This spec records the design agreed in chat. The factory emits movies. It does not score a strategy.

## Goal

Give Prism many Bitcoin-like daily histories that are not rearrangements of the real return tape. Each history is a chain of chapters. A chapter is one of six regimes. The regime's daily moves, streak lengths, successors, and bar shapes are measured on the real Coinbase file. The closes are new Student-t draws. The open, high, low, and volume are a real bar of that same regime, scaled onto the new close.

SMAGateV1, CrashGateV1, and later rules can be pointed at these files in a later job. A cloud of scores on these files is a stress result. It is not out-of-sample proof. The regimes were fit on the same tape those rules were designed on.

## Non-goals

- Running SMAGateV1, CrashGateV1, or any other rule on the generated files
- Retuning a strategy, or designing CrashGateV1
- Replacing remix. Remix still reshuffles real returns
- Replacing `synthetic_daily` in `price_forecast/data/series.py`. That helper stays the deterministic unit-test stub
- Training forecast models on these paths
- Changing weekly sampling, fill rules, costs, or KPI definitions
- Adding CLI flags that change the 365-bar window, the ±25% band, or the 30-bar volatility window

## Layout

```
price_forecast/datafactory/__init__.py
price_forecast/datafactory/remix.py          # moved from price_forecast/remix/remix.py
price_forecast/datafactory/synthetic/__init__.py
price_forecast/datafactory/synthetic/__main__.py
price_forecast/datafactory/synthetic/label.py
price_forecast/datafactory/synthetic/fit.py
price_forecast/datafactory/synthetic/paths.py
price_forecast/datafactory/synthetic/report.py
tests/datafactory/__init__.py
tests/datafactory/test_remix.py              # moved from tests/remix/
tests/datafactory/test_remix_csv.py
tests/datafactory/test_label.py
tests/datafactory/test_fit.py
tests/datafactory/test_paths.py
tests/datafactory/test_report.py
```

Delete `price_forecast/remix/` and `tests/remix/` after the imports move. No compatibility shim. `python -m price_forecast.remix` and `python -m price_forecast.remix.remix` are gone.

`price_forecast/data/candles.py` keeps `REMIX_DIR` (`data/remix`) and gains `SYNTHETIC_DIR` (`data/synthetic`).

Add `data/synthetic/` to `.gitignore`, next to `data/remix/`.

Update the live command and layout lines in `README.md`. Update the code path in `docs/research/2026-09-20-synthetic-btc-paths.md` to `python -m price_forecast.datafactory.remix`. Leave that note's argument as it is. Add `from price_forecast.remix.remix import` and `python -m price_forecast.remix.remix` to the forbidden strings in `tests/layout/test_no_old_modules.py`. Extend the gitignore assertion in `tests/data/test_candles.py` with `data/synthetic/`.

## Commands

| Command | Network | Reads | Writes |
| --- | --- | --- | --- |
| `python -m price_forecast.datafactory.remix` | no | the Coinbase CSV | one CSV and PNG per path under `data/remix/` |
| `python -m price_forecast.datafactory.synthetic` | no | the Coinbase CSV | one CSV and PNG per path under `data/synthetic/`, plus a regime sidecar |

Synthetic flags: `--csv` (default `data/btc-usd-daily.csv`), `--n-paths` (default 1), `--seed` (default 0). `--n-paths` below 1 raises `ValueError` and writes nothing.

A missing `--csv` uses the existing `require_closes` exit: status 1, the message names `python -m price_forecast.data.candles`, and nothing is written.

Remix's behavior stays the behavior it has today, including its sanity report and its `--mean-block-bars` flag. Only its import path and command change. Its output directory stays `data/remix/`.

## Files written

For seed `S` and path index `i` starting at 0:

| Path | Contents |
| --- | --- |
| `data/synthetic/btc-usd-daily-seed{S}-path{i}.csv` | One synthetic candle path |
| `data/synthetic/btc-usd-daily-seed{S}-path{i}.png` | Candlestick chart from the existing `write_candles` |
| `data/synthetic/btc-usd-daily-seed{S}-path{i}-regimes.csv` | One regime name per candle row |

The same seed and path index overwrite those three files. The candle CSV uses the existing header `time,low,high,open,close,volume` and the existing writer, so the PNG is part of that write. The sidecar is a separate CSV. It has no PNG.

Sidecar header:

```
time,regime
```

`time` is the candle row's `YYYY-MM-DD`. `regime` is one of:

`bull_quiet`, `bull_volatile`, `bear_quiet`, `bear_volatile`, `sideways_quiet`, `sideways_volatile`

Generate every path in memory, then write. A fit or generation failure writes nothing.

## How a row is labeled

Labels use bar index, in file order. A missing calendar day does not shift the window.

A row `t` needs 365 rows behind it. Let `R = P_t / P_{t-365} - 1`, using closes.

- Bull when `R > 0.25`
- Bear when `R < -0.25`
- Sideways when `-0.25 <= R <= 0.25`

Rows `0` through `364` have no trend label and are left out of the fit.

Volatility on a labeled row is the sample standard deviation (`ddof=1`) of the 30 daily log-returns that end on that row. Log-return into row `t` is `log(P_t / P_{t-1})`. The threshold is the median of those volatilities on the labeled rows, computed once with `numpy.median` and then frozen. A row at or below the median is quiet. A row above it is volatile.

The regime is the pair of those two answers. Consecutive labeled rows with the same regime are one run. The unlabeled prefix is not a run.

`label.py` exposes the windows and the band as arguments. The defaults are 365, 30, and 0.25. The CLI always uses the defaults. Tests pass smaller windows.

## What the fit saves

`fit.py` takes the labeled candles and returns one record used for every path:

- Per regime, a Student-t on that regime's daily log-returns: `df`, `loc`, and `scale` from `scipy.stats.t.fit`.
- Per regime, the list of run lengths. Each length is at least 1.
- Transition counts at run boundaries only. A run of 40 rows is one vote. The next regime is always a different regime. The last run in the file has no successor.
- Per regime, the bar shapes of its labeled rows: `open/close`, `high/close`, `low/close`, and `volume`.

The fit raises `ValueError`, names the regime, and writes nothing when any regime has fewer than 30 labeled rows, fewer than 2 runs, a sample volatility of 0, a blank volume, a non-finite Student-t parameter, or `df <= 2`. `df <= 2` means the fitted volatility is not a finite number. A regime that always ended in one particular next regime keeps that single successor. That is a real count, not a failure.

## How one path is built

The path has the same dates and the same number of rows as the source file. Row 0 is the source's first candle, unchanged. Every later close is invented.

The random stream for path `k` is:

```python
numpy.random.Generator(numpy.random.PCG64(numpy.random.SeedSequence([seed, k, 0])))
```

Draws happen in this order:

1. Pick a starting run with `rng.integers` over the full list of real runs. Each run is one ticket, whatever its length.
2. Draw a length with `rng.integers` over that regime's length list.
3. For each invented row in the chapter, draw one Student-t log-return with `scipy.stats.t.rvs(df, loc=loc, scale=scale, random_state=rng)`, set `close = previous_close * exp(return)`, then draw a bar shape with `rng.integers` over that regime's shapes.
4. Scale the shape onto the new close: `open`, `high`, and `low` are the close times the stored ratios, and `volume` is the stored volume.
5. When the chapter ends and rows remain, draw the next regime from that regime's successor list (one entry per observed vote, then `rng.integers`), draw a new length, and repeat.
6. A chapter that would pass the last row is cut to fit.

The length counts invented rows only. Row 0 does not consume length. The sidecar still has one regime per row, including row 0. Row 0 records the starting regime and does not change row 0's candle.

A non-finite return or a non-positive close raises `ValueError`. Paths are built in memory first. If any path fails, the command writes nothing, including paths that were already built in that run.

Path `k` depends on `SeedSequence([seed, k, 0])` only. Raising `--n-paths` does not change paths already produced for that seed. The same seed and path index produce the same candles and the same sidecar.

## Report

The command prints a report and exits 0 whenever the files were written. A weak report does not delete files and does not change the exit status.

Three columns, same facts remix already prints: `daily_vol`, `weekly_vol`, `excess_kurtosis`, `daily_p01`, `hodl_max_dd`, `acf_daily_1`, `acf_weekly_1`, `acf_weekly_4`, `acf_weekly_8`. The columns are the real series, the median across synthetic paths, and the median across a control. Weeks come from the existing `weekly_closes`.

The control uses the same dates and the same bar machinery, with one regime. Its Student-t and its bar shapes are fit on every labeled row pooled together. Its stream is `SeedSequence([seed, k, 1])`. Control paths are not written.

Under the table, print day counts for the six regimes and two checks, pooled across every invented row of every written path. Row 0 is excluded, because it has no invented return.

- Mean log-return of rows labeled `bull_quiet` or `bull_volatile` is greater than the mean log-return of rows labeled `bear_quiet` or `bear_volatile`.
- Sample volatility of rows labeled with `volatile` is greater than the sample volatility of rows labeled with `quiet`.

Either check prints `n/a` when either side has fewer than 2 rows. `n/a` is not a failure of the command.

The report does not re-apply the 365-bar / ±25% rule to the fake closes. A short bull chapter inside a down year will not flip that year. The labels that count are the sidecar labels.

## Tests

Tests build a small candle file in memory. They do not read `data/btc-usd-daily.csv`.

- Label cutoffs: over the trend window the test passes in, a crafted return above, below, and inside ±25% gets bull, bear, and sideways. Volatility at the frozen median is quiet. Volatility above it is volatile.
- A tape that leaves one regime under 30 rows, or with a single run, makes the fit raise, and the command writes no file.
- The same seed and path index rewrite the same candle CSV and the same sidecar. `--n-paths 2` leaves path 0 byte-for-byte the same as `--n-paths 1`.
- On a fixture whose bull labeled-days step up and whose bear labeled-days step down, path 0's invented bull rows have a higher mean log-return than its invented bear rows, and its volatile rows have a wider sample volatility than its quiet rows.
- Every invented candle has a finite price above 0, `low <= min(open, close) <= max(open, close) <= high`, and `volume >= 0`.
- Moved remix tests still pass against `price_forecast.datafactory.remix`.

## Success

One command, `python -m price_forecast.datafactory.synthetic`, reads the Coinbase candle CSV and writes seeded candle files under `data/synthetic/` whose closes are new, whose chapters follow the six fitted regimes, and whose bars stay valid candles. Remix still runs from `python -m price_forecast.datafactory.remix` and still writes `data/remix/`. Neither command scores a strategy.
