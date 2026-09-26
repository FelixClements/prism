# Candle CSV files for Coinbase and remix

**Date:** 2026-09-26  
**Status:** Draft for review  
**Scope:** Persist BTC-USD daily candles to CSV, refresh them with one command, write one remix CSV per synthetic path, and point SMAGate and the forecast bakeoff at a CSV. Each CSV write also writes a candlestick PNG.

This spec records the design agreed in chat: approach 1 (closes stay in memory; OHLC lives in the file), a separate update command, one file pair per remix path, and scaled source-day wicks on remix rows.

## Goal

Stop downloading the full Coinbase history on every backtest and remix run. Keep a local daily candle file, append only what is new, and give each remixed path the same kind of file so a backtest can score that path. The SMA-8/16 rule, fill cost, and KPI math stay as they are. One backtest run scores one CSV.

## Non-goals

- Scoring SMAGate across every remix file in one run, or searching for a new SMA pair
- Changing `PriceSeries` to store open, high, low, or volume
- Changing weekly sampling, fill rules, costs, or KPI definitions
- Editing `archive/frozen_t1_bakeoff` (those scripts may still download)
- Inventing daily bars for calendar days Coinbase does not return
- Drawing a volume panel

## Files

Repo-root paths:

| Path | Contents |
| --- | --- |
| `data/btc-usd-daily.csv` | Real Coinbase BTC-USD daily candles |
| `data/btc-usd-daily.png` | Candlestick chart of that CSV |
| `data/remix/btc-usd-daily-seed{seed}-path{i}.csv` | One remix path |
| `data/remix/btc-usd-daily-seed{seed}-path{i}.png` | Candlestick chart of that path |

`{seed}` is the remix CLI `--seed`. `{i}` is the path index starting at 0. The same seed and path index overwrite the previous pair.

Add these lines to `.gitignore`:

```
data/btc-usd-daily.csv
data/btc-usd-daily.png
data/remix/
```

## CSV shape

Header, in this order:

```
time,low,high,open,close,volume
```

`time` is the UTC day `YYYY-MM-DD`. The other price fields are decimal numbers. A blank `volume` cell is empty, not `0` and not `nan`.

Coinbase rows store the exchange candle: time, low, high, open, close, volume. Remix rows use the same header. Remix `volume` is always blank. Remix `time` values are the original Coinbase dates copied onto the path, in the same order `remix_daily_closes` already keeps. Those dates label the row. They are not the calendar day the wick came from.

Reading a CSV for a backtest builds a `PriceSeries` from `time` and `close` only.

## Commands

| Command | Network | Reads | Writes |
| --- | --- | --- | --- |
| `python -m price_forecast.data.candles` | Coinbase only | existing CSV if present | `data/btc-usd-daily.csv` and `.png` |
| `python -m price_forecast.remix.remix` | no | the Coinbase CSV | one CSV and PNG per path under `data/remix/` |
| `python -m price_forecast.strategies.smagate_v1` | no | `--csv` | existing KPI files under `results/` |
| `python -m price_forecast.forecast.bakeoff` | no | `--csv` | existing bakeoff scoreboard |

`--csv` defaults to `data/btc-usd-daily.csv`. The remixer, SMAGate, and the bakeoff accept `--csv` so a test can point them at a fixture. SMAGate keeps `--starting-dollars`. The remixer keeps `--n-paths`, `--seed`, and `--mean-block-bars`. The remixer treats `--csv` as the source tape: one close series and the OHLC table aligned on those dates.

If `--csv` is missing, the command exits non-zero, prints `python -m price_forecast.data.candles`, and writes no scoreboard. It does not download.

The candles command calls the existing chunked Coinbase fetch in `price_forecast.data.series` and parses every field of `[time, low, high, open, close, volume]`. It does not call `load_daily_closes(source="coinbase")`, because that helper keeps only the close. That helper stays for existing parser tests and for `archive/frozen_t1_bakeoff`. SMAGate, the remixer, and the bakeoff stop calling it.

## Update rule

The candles command covers 2018-01-01 through today's UTC date.

When `data/btc-usd-daily.csv` is missing, it downloads that range and writes the CSV and PNG.

When the file exists, it fetches from the last stored day through today. Rows dated before that last day stay as they are, including any hole already in the file. The last stored day is replaced by the fetched row for that day. Fetched days after it are appended. A day the response omits stays absent. Earlier history is not downloaded again.

## Remix candles

Closes for a seed, path count, and block length match `remix_daily_closes` for those same arguments. The first close is the real first close.

Each later close comes from one sampled daily log-return. That return belongs to the source day whose close is the end of the return. The remix row's open, high, and low are that source candle scaled onto the remix close:

```
scale = remix_close / source_close
remix_open = source_open * scale
remix_high = source_high * scale
remix_low = source_low * scale
```

Worked example. A source day opens at 41,000, highs at 43,000, lows at 39,000, and closes at 42,000. A remix close of 26,000 on that sampled return stores open 25,381, high 26,619, low 24,143, and close 26,000 (rounded here only for reading; the file stores the full quotients).

The first remix row copies the real first day's open, high, low, and close, and still leaves volume blank.

`price_forecast.data.candles` owns CSV read, CSV write, the PNG, and the update command. It does not import remix, strategies, or backtest. The remixer calls it to write each path. `PriceSeries` stays close-only.

## Chart

Every successful CSV write also writes a PNG whose path is the CSV path with a `.png` suffix. One function draws both Coinbase and remix files. The chart is a matplotlib candlestick of every row, with the UTC day on the x-axis. An up day (close above open) is green. A down day (close below open) is red. A day with close equal to open uses the down color. There is no volume panel. The renderer uses a non-interactive backend so tests do not need a display.

Rows are finished in memory before either file is replaced. The command writes a temporary CSV and a temporary PNG beside the target, then replaces the real paths. If the Coinbase fetch fails, or the PNG fails before replacement, the previous CSV and PNG stay, and the temporary files are removed. A first-run failure leaves no CSV and no PNG.

## Validation

Reject a file before any backtest or remix when any of these is true:

- The header is not `time,low,high,open,close,volume`
- A day is duplicated, out of ascending order, or not `YYYY-MM-DD`
- Open, high, low, or close is missing or not strictly positive
- High is below open or close, or low is above open or close
- Volume is not blank and is not a number greater than or equal to zero

A blank volume is valid. That is what remix files use. Coinbase rows from the update command store the numeric exchange volume, including zero.

## Tests

Tests use CSV fixtures and a stand-in for the Coinbase fetch. No test calls the network.

- Round-trip a candle CSV, including a blank volume cell
- Update against the stand-in: create a file from an empty path; on the second run replace only the last day and append a newer day; a failed fetch leaves the previous CSV and PNG bytes unchanged
- A remix fixture: output closes match `remix_daily_closes`; open, high, and low match the source-day scale above; volume is blank; one CSV and one PNG per path
- SMAGate and the bakeoff read a fixture via `--csv`; a missing path exits with `python -m price_forecast.data.candles` and does not download
- A fixture with a duplicate day, a non-positive price, or a high below the low is rejected

`matplotlib` is a required dependency in `pyproject.toml`.

## Done when

1. `python -m price_forecast.data.candles` creates or extends `data/btc-usd-daily.csv` and writes the PNG beside it.
2. `python -m price_forecast.remix.remix` reads that CSV and writes one CSV and one PNG per path under `data/remix/`, with scaled wicks and blank volume.
3. SMAGate and the bakeoff score `--csv` and do not download. The default file is `data/btc-usd-daily.csv`.
4. `pytest` is green, including the new fixture tests, with no live HTTP.
5. The three generated paths are gitignored.
