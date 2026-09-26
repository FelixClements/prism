# prism

Walk-forward Bitcoin forecast scoreboard plus the frozen weekly SMAGateV1 rule.

Not investment advice.

## Layout

- `price_forecast/data/` — daily `PriceSeries`, Coinbase loader, Sunday weekly bars
- `price_forecast/forecast/` — walk-forward harness, predictors, Chronos, bakeoff CLI
- `price_forecast/strategies/` — SMA signals and SMAGateV1
- `price_forecast/backtest/` — SMAGate simulator/KPIs and the archived t+1 engine
- `price_forecast/remix/` — stationary-bootstrap path factory
- `results/` — live scoreboards (markdown/CSV)
- `docs/` — architecture blueprint and research notes
- `archive/frozen_t1_bakeoff/` — frozen t+1 SMA bakeoff (do not use for new work)
- `tests/` — mirrors the live packages

## Run

```
python -m price_forecast.strategies.smagate_v1
python -m price_forecast.forecast.bakeoff
python -m price_forecast.remix.remix
```

Architecture blueprint: `docs/architecture.md`.
