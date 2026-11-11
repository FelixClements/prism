# prism

Walk-forward scoreboard for short-horizon Bitcoin forecasts, plus the weekly SMAGateV1 and CrashGateV1 rules and a search that breeds CrashGate variants.

## Layout

- `price_forecast/data/` — Coinbase candle CSV (`candles.py`), daily `PriceSeries`, Sunday weekly bars
- `price_forecast/forecast/` — walk-forward harness, predictors, Chronos, bakeoff CLI
- `price_forecast/strategies/` — SMAGateV1, CrashGateV1 and its VCP buy gate, weekly indicators
- `price_forecast/backtest/` — SMAGate simulator, KPIs, and report formatters
- `price_forecast/datafactory/` — stationary-bootstrap remix and the synthetic regime factory
- `price_forecast/search/` — CrashGate search: mutate, score on Coinbase + remix + synthetic paths, ledger
- `price_forecast/replay/` — frozen replay harness: next-day fills, weekday anchors, parameter neighbours, exposure-matched and random-timing benchmarks, deflated Sharpe and CSCV PBO over the search ledger
- `price_forecast/replay/book.py`, `portfolio.py` — fractional-exposure replay (0..1 BTC, fees on traded notional): 7-anchor ensembles of the locked rules and the pre-registered no-tuning baselines in `sizing.py` (vol target, TSMOM average, both), with a head-to-head against CrashGate
- `results/` — live scoreboards (markdown/CSV); `results/search/` is local-only
- `data/` — local candle CSV and generated paths (git-ignored)
- `docs/` — architecture blueprint and research notes
- `tests/` — mirrors the live packages

## Run

Download or extend `data/btc-usd-daily.csv`:

```
python -m price_forecast.data.candles
```

Weekly SMAGateV1 rule:

```
python -m price_forecast.strategies.smagate_v1
```

Weekly CrashGateV1 rule:

```
python -m price_forecast.strategies.crashgate_v1
```

Walk-forward forecast bakeoff:

```
python -m price_forecast.forecast.bakeoff
```

Stationary-bootstrap path factory:

```
python -m price_forecast.datafactory.remix
```

Synthetic regime path factory:

```
python -m price_forecast.datafactory.synthetic
```

CrashGate search:

```
python -m price_forecast.search
```

Frozen replay of a locked rule (writes `results/replay/<strategy>.md`; DSR and PBO need `results/search/ledger.jsonl`):

```
python -m price_forecast.replay --strategy crashgate_v1
python -m price_forecast.replay --strategy smagate_v1
```

Fractional replay: anchor ensembles and sizing baselines (writes one scorecard per candidate plus `results/replay/baselines_vs_crashgate.md`):

```
python -m price_forecast.replay.portfolio --strategy all
```

The VCP gate imports `requests`, so the venv needs it installed.

These scripts are not in this repo; they come from agent skills under `~/.agents/skills/`:

- CrashGate's buy gate loads `vcp-screener/scripts`. Set `$CRASHGATE_VCP_SCRIPTS` to point it somewhere else.
- The search also loads `backtest-expert` and `edge-strategy-reviewer`.

Architecture blueprint: `docs/architecture.md`.

Not investment advice.
