# Synthetic regime factory

**Date:** 2026-09-30  
**Status:** Draft for review  
**Scope:** Move the stationary-bootstrap remixer under `price_forecast/datafactory/`, and add a second history factory that writes fully synthetic BTC-USD daily candles from six regimes fit on the real Coinbase tape.

This spec records the design agreed in chat. The factory emits movies. It does not score a strategy.

## Goal

Give Prism many Bitcoin-like daily histories in a new regime order. Each history is a chain of chapters. A chapter is one of six regimes. The regime's streak lengths and successors are measured on the real Coinbase file. A chapter's days are consecutive real days of that regime: each day keeps its own log-return, wick ratios, and volume, scaled onto the new close.

**Revision 2026-10-15.** The first version drew closes from a per-regime Student-t and attached a random bar of the regime. Measured against the real tape it lost what stress tests need: fitted `df` near 2 forced a 20% daily cap that split the real −49% day into a staircase of equal days, wick range and volume were unrelated to the day's move (volume vs |return| correlation 0.07 against 0.58 real), and volatility clustering inside a regime was gone. Real-day blocks keep all three. The cost: no day is worse than the worst real day, the same limit remix has.

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

A run shorter than `MIN_RUN_BARS = 7` rows joins the run before it. A short first run joins the run after it. Without this, rows flicking across the volatility median gave 186 runs with 2–6 day medians on the real tape, so chapters were chatter, not regimes. With it the real tape has 58 runs, at least 7 per regime. The volatility median is still the raw median.

`label.py` exposes the windows, the band, and the minimum run as arguments. The defaults are 365, 30, 0.25, and 7. The CLI always uses the defaults. Tests pass smaller windows.

## What the fit saves

`fit.py` takes the labeled candles and returns one record used for every path:

- Per regime, its real runs as chapters. Each chapter is the run's rows in order, each row a `RealDay`: `log(P_t / P_{t-1})`, `high/close`, `low/close`, and `volume`.
- Transition counts at run boundaries only. A run of 40 rows is one vote. The next regime is always a different regime. The last run in the file has no successor.

The fit raises `ValueError`, names the regime, and writes nothing when any regime has fewer than 30 labeled rows, fewer than 2 runs, a sample volatility below `1e-12`, or a blank volume. A regime that always ended in one particular next regime keeps that single successor. That is a real count, not a failure.

## How one path is built

The path has the same dates and the same number of rows as the source file. Row 0 is the source's first candle, unchanged.

The random stream for path `k` is:

```python
numpy.random.Generator(numpy.random.PCG64(numpy.random.SeedSequence([seed, k, 0])))
```

Draws happen in this order:

1. Pick a starting run with `rng.integers` over the full list of real runs. Each run is one ticket, whatever its length.
2. Draw a length: the length of a chapter picked with `rng.integers` over that regime's chapters.
3. Pick a source chapter of the regime with `rng.integers`, then a start offset inside it with `rng.integers`. Copy consecutive days from there. When the source chapter runs out, pick another chapter of the regime and continue from its first day.
4. Each copied day sets `close = previous_close * exp(log_return - shift)`, `open = previous_close`, `high = max(close * high_ratio, open, close)`, `low = min(close * low_ratio, open, close)`, and keeps its volume.
5. When the chapter ends and rows remain, draw the next regime from that regime's successor list (one entry per observed vote, then `rng.integers`), draw a new length, and repeat.
6. A chapter that would pass the last row is cut to fit.

`shift` is the mean log-return of every labeled day minus the source's average daily log-return. The labeled days skip the unlabeled prefix, so without it the paths would drift at a different rate than the source.

The length counts invented rows only. Row 0 does not consume length. The sidecar still has one regime per row, including row 0. Row 0 records the starting regime and does not change row 0's candle.

A non-finite or non-positive close raises `ValueError`. Paths are built in memory first. If any path fails, the command writes nothing, including paths that were already built in that run.

Path `k` depends on `SeedSequence([seed, k, 0])` only. Raising `--n-paths` does not change paths already produced for that seed. The same seed and path index produce the same candles and the same sidecar.

## Report

The command prints a report and exits 0 whenever the files were written. A weak report does not delete files and does not change the exit status.

Three columns. The facts remix prints: `daily_vol`, `weekly_vol`, `excess_kurtosis`, `daily_p01`, `worst_day`, `hodl_max_dd`, `acf_daily_1`, `acf_weekly_1`, `acf_weekly_4`, `acf_weekly_8`, `momentum_8w` (correlation of the past 8 weeks' summed return with the next week), `variance_ratio_13w` (variance of 13-week sums over 13 times the weekly variance), `acf_abs_1`, `acf_abs_10`, `acf_abs_30` (volatility clustering), and `leverage` (correlation of a day's return with the next day's absolute return). Then two candle facts: `range_abs_corr` (log high/low range vs absolute return) and `volume_abs_corr` (volume vs absolute return). The columns are the real series, the median across synthetic paths, and the median across a control. `weekly_vol` uses the Sunday weeks of `weekly_closes`. The weekly autocorrelations, momentum, and variance ratio average all seven week-end days, because one end day alone swings real lag 1 from −0.02 to +0.09.

The control uses the same dates and the same bar machinery, with one regime and no order: each row is one labeled real day drawn independently with `rng.integers`, with the same drift shift. Its stream is `SeedSequence([seed, k, 1])`. Control paths are not written.

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
- A real crash day stays one day. A chapter copies consecutive real days. Each day's wicks and volume travel with its return.
- A run shorter than the minimum joins the run before it; a short first run joins the run after it.
- Moved remix tests still pass against `price_forecast.datafactory.remix`.

## Success

One command, `python -m price_forecast.datafactory.synthetic`, reads the Coinbase candle CSV and writes seeded candle files under `data/synthetic/` whose closes are new, whose chapters follow the six fitted regimes, and whose bars stay valid candles. Remix still runs from `python -m price_forecast.datafactory.remix` and still writes `data/remix/`. Neither command scores a strategy.
