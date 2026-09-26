# OLD. Superseded by SMAGateV1.

Do **not** use this package for new work. It is the frozen t+1 SMA bakeoff, kept
only as history. The live freeze is **SMAGateV1**.

```bash
.venv/bin/python -m price_forecast.strategies.smagate_v1
```

## What these rules were

Conservative weekly BTC in/out book, **not** SMAGateV1:

- Signal at week t Sunday close, fill at week **t+1** close
- 10 bps of wealth per flip
- Start in BTC (inherited long / fresh $10k BTC on dollar tables)
- Strict inequalities (`>` / `<`)
- Symmetric SMA-8/12, dual SMA 12/26, Donchian-12, F&G overlay, asymmetric grid

SMAGateV1 is a different execution: SMA-8 in / SMA-16 out, **same-bar** Sunday
close, 0.15%/fill, start cash, inclusive `>=` / `<=`. Do not mix the two
scoreboards.

## What lives here

| File | Role |
| --- | --- |
| `weekly_bakeoff.py` + `weekly_bakeoff_results.md` | Wealth-ratio C/A scoreboard |
| `sma8_10k.py` + `sma8_10k_results.md` | $10k SMA-8 vs hold |
| `sma_asymmetric_10k.py` + `sma_asymmetric_10k_results.md` | Frozen 24-cell buy/sell grid |
| `fng.py` | Alternative.me F&G loader, used only by this bakeoff overlay |

Shared week helper `weekly_closes` stays live in `price_forecast/data/weekly.py`
because SMAGateV1 still imports it.

Historical tests: `tests/archive/frozen_t1_bakeoff/` (collected with pytest; they
are historical, not the live freeze).

Historical re-run (not for new work):

```bash
.venv/bin/python -m archive.frozen_t1_bakeoff.weekly_bakeoff
.venv/bin/python -m archive.frozen_t1_bakeoff.sma8_10k
.venv/bin/python -m archive.frozen_t1_bakeoff.sma_asymmetric_10k
```
