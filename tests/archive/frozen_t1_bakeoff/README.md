# Historical tests for the frozen t+1 SMA bakeoff

OLD. Superseded by SMAGateV1. These tests lock the archived runners under
`price_forecast/archive/frozen_t1_bakeoff/`. They stay collected by default
pytest (`testpaths = ["tests"]`) so the archive does not rot. They are not the
live freeze.

Live tests: `tests/test_sma8_16_kpis.py`.
Live runner: `.venv/bin/python -m price_forecast.sma8_16_kpis`.
