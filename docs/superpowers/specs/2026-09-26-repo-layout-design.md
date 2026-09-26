# Prism repo layout: folders and module split

**Date:** 2026-09-26  
**Status:** Draft for review  
**Scope:** Reorganize the existing `price_forecast` codebase into domain folders and split mixed modules. No new strategy, forecast, or backtest behavior.

This spec records the design agreed in chat: approach A (one package, domain folders, results and docs at the top), plus splitting mixed files rather than only moving them.

## Goal

A reader can tell from the folders where data loading lives, where strategies live, where backtests live, where forecast support lives, and where docs and scoreboard files live. Imports follow that map. Tests still pass. SMAGateV1, the walk-forward harness, Chronos, remix, and the frozen t+1 bakeoff produce the same numbers they do today.

## Non-goals

- Renaming the Python package to `prism` or introducing a `src/` tree
- Compatibility shims at old import paths (`price_forecast.weekly_regime`, `price_forecast.sma8_16_kpis`, …)
- Changing fill rules, costs, KPI definitions, CLI flags, or scoreboard content
- New features, predictors, or strategies
- Moving `.cursor/` or `.agents/`

## Target tree

```
price_forecast/
  __init__.py
  data/
    __init__.py
    series.py              # PriceSeries, Coinbase + synthetic loaders
    weekly.py              # weekly_closes (Sunday bars from dailies)
  forecast/
    __init__.py
    harness.py
    predictors.py
    chronos.py
    bakeoff.py
  strategies/
    __init__.py
    signals.py             # SMA / dual / asymmetric / Donchian
    smagate_v1.py          # live freeze constants + CLI
  backtest/
    __init__.py
    engine.py              # SMAGateV1 same-bar simulator + HODL
    kpis.py
    reports.py
    t1.py                  # archived t+1 / 10 bp engine
  remix/
    __init__.py
    remix.py
results/                   # bakeoff + SMAGate KPI .md/.csv
docs/
  architecture.md          # current README blueprint, moved
  research/                # existing research notes
  superpowers/specs/       # this spec
archive/frozen_t1_bakeoff/ # frozen t+1 code, tests stay under tests/archive/
tests/                     # mirrors live packages
README.md                  # short folder map + python -m commands
pyproject.toml
```

Package name stays `price_forecast`. `pyproject.toml` continues to find `price_forecast*`.

## File split

### `weekly_regime.py` (deleted after split)

| Contents | Destination |
| --- | --- |
| `weekly_closes`, Sunday week-end helper | `price_forecast.data.weekly` |
| `sma_signal`, `dual_sma_signal`, `asymmetric_sma_signal`, `donchian_signal`, SMA helper | `price_forecast.strategies.signals` |
| t+1 `backtest`, `dollar_backtest`, `BacktestResult`, `DollarBacktestResult`, Fear & Greed overlay, pass-A / pass-C, related constants | `price_forecast.backtest.t1` |

Live SMAGateV1 must not import `backtest.t1`.

### `sma8_16_kpis.py` (deleted after split)

| Contents | Destination |
| --- | --- |
| `BUY_WEEKS`, `SELL_WEEKS`, fill cost, starting dollars, `python -m` CLI | `price_forecast.strategies.smagate_v1` |
| `simulate_strategy`, `simulate_hodl`, `Fill`, `EquityPath` | `price_forecast.backtest.engine` |
| KPI math (`compute_kpis`, monthly chapters, Sortino, MAR, …) | `price_forecast.backtest.kpis` |
| Markdown / CSV formatters | `price_forecast.backtest.reports` |

CLI output paths change from files beside the module to files under `results/`. Report *content* does not change.

### Move as whole files

| Today | After |
| --- | --- |
| `price_forecast/series.py` | `price_forecast/data/series.py` |
| `price_forecast/harness.py` | `price_forecast/forecast/harness.py` |
| `price_forecast/predictors.py` | `price_forecast/forecast/predictors.py` |
| `price_forecast/chronos.py` | `price_forecast/forecast/chronos.py` |
| `price_forecast/bakeoff.py` | `price_forecast/forecast/bakeoff.py` |
| `price_forecast/remix.py` | `price_forecast/remix/remix.py` |
| `price_forecast/archive/frozen_t1_bakeoff/` | `archive/frozen_t1_bakeoff/` |
| `price_forecast/bakeoff_results.md` | `results/bakeoff_results.md` |
| `price_forecast/sma8_16_kpis_results.md` | `results/sma8_16_kpis_results.md` |
| `price_forecast/sma8_16_kpis_monthly.md` | `results/sma8_16_kpis_monthly.md` |
| `price_forecast/sma8_16_kpis_monthly.csv` | `results/sma8_16_kpis_monthly.csv` |
| `price_forecast/archive/frozen_t1_bakeoff/*_results.md` | stay with the frozen bakeoff under `archive/frozen_t1_bakeoff/` |
| Root `README.md` (architecture blueprint) | `docs/architecture.md` |

Root `README.md` is replaced by a short map of the folders and the three live `python -m` commands. Research notes stay in `docs/research/`; internal path strings that name old modules are updated.

## Dependency direction

Imports only go downstream. Nothing lower in this list imports anything above it, except the one remix exception.

1. **`data`** — daily series in, weekly bars out. No strategy, backtest, forecast, or remix imports.
2. **`strategies.signals`** — bars in, position/signal out. No backtest, forecast, or remix imports.
3. **`backtest.engine` / `kpis` / `reports`** — signals + bars in, equity path and scoreboard out. Writes under `results/` only.
4. **`forecast`** — daily series in, walk-forward scores out. Does not import strategies or the SMAGate engine.
5. **`remix`** — daily series in, remixed daily paths out. May call `weekly_closes` and `simulate_strategy` to sanity-check a path. That is the only allowed reach from remix into backtest.
6. **`archive/frozen_t1_bakeoff`** — may import `data`, `strategies.signals`, and `backtest.t1`. Live SMAGate and forecast never import archive.

`price_forecast/__init__.py` stays a thin convenience export for the forecast scoreboard (`evaluate`, predictors, `load_daily_closes`, `LeakageError`). Strategy and backtest stay behind their subpackages so `import price_forecast` does not pull in SMAGate.

## Entry points

| Removed | Replacement |
| --- | --- |
| `python -m price_forecast.sma8_16_kpis` | `python -m price_forecast.strategies.smagate_v1` |
| `python -m price_forecast.bakeoff` | `python -m price_forecast.forecast.bakeoff` |
| `python -m price_forecast.remix` | `python -m price_forecast.remix.remix` |

CLI flags and defaults stay the same. No shims for the old module names.

## Errors

`LeakageError` stays on `PriceSeries` in `data.series`. SMAGate still refuses to trade before SMA-16 exists. Coinbase load failures stay as they are today. No new exception types.

## Tests

`tests/` mirrors live packages:

- loader / series → `price_forecast.data`
- harness, Chronos, ARIMA+GARCH → `price_forecast.forecast`
- SMAGate KPI tests → `strategies.smagate_v1` + `backtest.engine` + `backtest.kpis`
- remix → `price_forecast.remix`
- weekly signal and t+1 engine tests → `strategies.signals` + `backtest.t1`

Frozen tests stay under `tests/archive/frozen_t1_bakeoff/` and import `archive.frozen_t1_bakeoff` plus `backtest.t1` / `strategies.signals` / `data` as needed. `pytest` still collects `tests/` including the archive folder (`pyproject.toml` already documents that on purpose). Result files are the same artifacts; only their on-disk home for live scoreboards is `results/`.

`archive/` is a repo-root package (`archive/__init__.py`) so frozen tests can `from archive.frozen_t1_bakeoff ...`. Pytest already sets `pythonpath = ["."]`. Do not add `archive*` to setuptools package discovery; it is not part of the installed `price-forecast` distribution.

## Docs and config

- Update path mentions in `docs/research/*.md` that point at `price_forecast/weekly_regime.py` or `price_forecast/sma8_16_kpis.py`.
- `pyproject.toml` `[tool.setuptools.packages.find] include` stays `["price_forecast*"]`. Do not publish `archive` as an installed package.
- Do not commit `.cursor/` or `.agents/`.

## Done when

1. `pytest` is green, including `tests/archive/frozen_t1_bakeoff/`.
2. The three `python -m` entry points above still run with the same flags.
3. `git grep` finds no `price_forecast.weekly_regime` or `price_forecast.sma8_16_kpis` in live code, tests, or docs (this spec may mention them as the old names).
4. Live scoreboards live under `results/`. The architecture blueprint lives at `docs/architecture.md`. Root `README.md` is a folder map, not the blueprint.

## Risks

- Frozen bakeoff currently imports `price_forecast.weekly_regime`. Those imports must be retargeted to `data.weekly`, `strategies.signals`, and `backtest.t1` in one pass so archive tests do not bit-rot.
- `sma8_16_kpis.py` is large; the split must be mechanical (move functions, keep logic) so KPI numbers do not drift.
- Relative paths in CLI writers must be updated to `results/` relative to the repo root, not the module file.
