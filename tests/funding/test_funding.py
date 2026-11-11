from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from price_forecast.funding import fetch
from price_forecast.funding.features import build_features, daily_funding, print_day, trailing_mean, venue_average
from price_forecast.funding.fetch import FundingPrint, merge_prints, read_prints, update_venue, write_prints
from price_forecast.funding.stats import (
    benjamini_hochberg,
    bucket_test,
    deciles,
    expanding_deciles,
    holm,
    newey_west_ols,
    slope_test,
)
from price_forecast.funding.study import forward_returns, render_report, run_study, trailing_returns


def _ms(y, m, d, h=0, minute=0, sec=0, ms=0) -> int:
    t = datetime(y, m, d, h, minute, sec, tzinfo=timezone.utc)
    return int(t.timestamp() * 1000) + ms


# ---------------------------------------------------------------- fetch


def test_binance_pages_forward_until_short_page():
    start = _ms(2019, 9, 10, 8)
    all_rows = [{"fundingTime": start + i * 8 * 3_600_000 + 2, "fundingRate": f"{i * 1e-6:.8f}"} for i in range(2500)]
    calls = []

    def get(url, params):
        calls.append(params["startTime"])
        rows = [r for r in all_rows if r["fundingTime"] >= params["startTime"]]
        return rows[: params["limit"]]

    out = fetch.fetch_binance(start, get=get)
    assert [p.time_ms for p in out] == [r["fundingTime"] for r in all_rows]
    assert len(calls) == 3


def test_bybit_pages_backward_to_start():
    start = _ms(2018, 11, 15)
    times = [start + i * 8 * 3_600_000 for i in range(450)]

    def get(url, params):
        rows = [t for t in reversed(times) if t <= params["endTime"]][: params["limit"]]
        return {"retCode": 0, "result": {"list": [{"fundingRateTimestamp": str(t), "fundingRate": "0.0001"} for t in rows]}}

    out = fetch.fetch_bybit(start - 10, get=get, now_ms=times[-1] + 5)
    assert [p.time_ms for p in out] == times


def test_update_venue_extends_cache(tmp_path, monkeypatch):
    seen = []

    def fake(start, *, get):
        seen.append(start)
        return [FundingPrint(start + 5, 0.0002)]

    monkeypatch.setitem(fetch.VENUES, "fake", (fake, 1000))
    path = update_venue("fake", tmp_path)
    update_venue("fake", tmp_path)
    assert seen == [1000, 1006]
    assert [p.time_ms for p in read_prints(path)] == [1005, 1011]


def test_write_read_round_trip_dedupes(tmp_path):
    path = tmp_path / "x.csv"
    write_prints(path, [FundingPrint(3, 0.1), FundingPrint(1, 0.2), FundingPrint(3, 0.3)])
    assert read_prints(path) == [FundingPrint(1, 0.2), FundingPrint(3, 0.3)]
    assert merge_prints([]) == []


# ---------------------------------------------------------------- features


def test_midnight_print_belongs_to_new_day_and_jitter_rounds():
    assert print_day(_ms(2020, 1, 2, 0)) == date(2020, 1, 2)
    assert print_day(_ms(2020, 1, 2, 0, ms=47)) == date(2020, 1, 2)
    # A print a few ms before midnight rounds forward, never back into the earlier day.
    assert print_day(_ms(2020, 1, 1, 23, 59, 59, 998)) == date(2020, 1, 2)
    assert print_day(_ms(2020, 1, 1, 16)) == date(2020, 1, 1)


def test_daily_is_three_times_mean():
    prints = [
        FundingPrint(_ms(2020, 1, 1, 0), 1e-4),
        FundingPrint(_ms(2020, 1, 1, 8), 2e-4),
        FundingPrint(_ms(2020, 1, 1, 16), 3e-4),
        FundingPrint(_ms(2020, 1, 2, 0), 1e-4),
        FundingPrint(_ms(2020, 1, 2, 16), 3e-4),
    ]
    daily = daily_funding(prints)
    assert daily[date(2020, 1, 1)] == pytest.approx(6e-4)
    assert daily[date(2020, 1, 2)] == pytest.approx(6e-4)


def test_trailing_mean_needs_full_window_and_ignores_future():
    base = date(2020, 1, 1)
    daily = {base + timedelta(days=i): float(i) for i in range(10)}
    del daily[base + timedelta(days=8)]
    f7 = trailing_mean(daily)
    assert min(f7) == base + timedelta(days=6)
    assert f7[base + timedelta(days=6)] == pytest.approx(3.0)
    assert f7[base + timedelta(days=7)] == pytest.approx(4.0)
    assert base + timedelta(days=9) not in f7  # window contains the gap
    # Changing a later day never changes an earlier feature value.
    daily2 = dict(daily)
    daily2[base + timedelta(days=7)] = 1e9
    assert trailing_mean(daily2)[base + timedelta(days=6)] == f7[base + timedelta(days=6)]


def test_venue_average_only_on_common_days():
    a = {date(2020, 1, 1): 1.0, date(2020, 1, 2): 3.0}
    b = {date(2020, 1, 2): 5.0}
    assert venue_average([a, b]) == {date(2020, 1, 2): 4.0}


# ---------------------------------------------------------------- stats


def test_newey_west_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(0)
    n = 400
    x = rng.normal(size=n)
    e = np.convolve(rng.normal(size=n + 9), np.ones(10), "valid")
    y = 0.3 * x + e
    X = np.column_stack([np.ones(n), x])
    ours = newey_west_ols(y, X, 14)
    ref = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 14, "use_correction": False})
    np.testing.assert_allclose(ours.beta, ref.params, rtol=1e-10)
    np.testing.assert_allclose(ours.cov, ref.cov_params(), rtol=1e-8)


def test_deciles_equal_sizes_and_ties_share_bucket():
    d = deciles(np.arange(100.0))
    assert np.bincount(d)[1:].tolist() == [10] * 10
    v = np.concatenate([np.arange(50.0), np.full(20, 50.0), np.arange(51.0, 81.0)])
    d = deciles(v)
    assert len(set(d[v == 50.0])) == 1
    assert d.min() == 1 and d.max() == 10


def test_expanding_deciles_use_only_past():
    v = np.arange(500.0)
    d = expanding_deciles(v, 100)
    assert (d[:100] == 0).all()
    assert (d[100:] == 10).all()  # each new value is the highest so far
    v2 = v.copy()
    v2[300:] = -1.0
    np.testing.assert_array_equal(expanding_deciles(v2, 100)[:300], d[:300])


def test_bucket_test_spread_matches_group_means():
    rng = np.random.default_rng(1)
    b = np.tile(np.arange(1, 11), 50)
    r = rng.normal(size=500)
    res = bucket_test(r, b, 5)
    assert res.spread == pytest.approx(r[b == 10].mean() - r[b == 1].mean())
    assert res.medians[0] == pytest.approx(np.median(r[b == 1]))
    assert res.counts.tolist() == [50] * 10


def test_bucket_test_detects_signal_and_monotonicity():
    rng = np.random.default_rng(2)
    f = rng.normal(size=2000)
    r = -0.5 * f + rng.normal(size=2000)
    res = bucket_test(r, deciles(f), 7)
    assert res.spread < 0 and res.spread_t < -5 and res.spearman < -0.9
    null = bucket_test(rng.normal(size=2000), deciles(f), 7)
    assert abs(null.spread_t) < 4


def test_overlap_inflates_naive_t_but_not_hac():
    # Overlapping 28-day sums of iid noise: naive OLS t-stats are far too big.
    rng = np.random.default_rng(3)
    ts = []
    for _ in range(200):
        daily = rng.normal(size=1200)
        fwd = np.convolve(daily, np.ones(28), "valid")[1:]
        sig = np.convolve(rng.normal(size=1200), np.ones(28), "valid")[:-1]
        ts.append(slope_test(fwd, [sig], 56).t)
    assert np.mean(np.abs(np.array(ts)) > 1.96) < 0.2


def test_holm_and_bh_known_values():
    p = [0.01, 0.04, 0.03, 0.005]
    np.testing.assert_allclose(holm(p), [0.03, 0.06, 0.06, 0.02])
    np.testing.assert_allclose(benjamini_hochberg(p), [0.02, 0.04, 0.04, 0.02])


# ---------------------------------------------------------------- study


def test_forward_and_trailing_returns_align():
    base = date(2020, 1, 1)
    closes = {base + timedelta(days=i): 100.0 + i for i in range(40)}
    days = [base, base + timedelta(days=35)]
    fwd = forward_returns(closes, days, 7)
    assert fwd[0] == pytest.approx(107.0 / 100.0 - 1)
    assert np.isnan(fwd[1])
    back = trailing_returns(closes, days, 28)
    assert np.isnan(back[0])
    assert back[1] == pytest.approx(135.0 / 107.0 - 1)


def _synthetic(seed: int, effect: float):
    """Funding that predicts the next 7 days of returns with a given sign and size."""
    rng = random.Random(seed)
    start = date(2018, 11, 15)
    n = 1800
    f_state = 0.0
    signal = []
    for _ in range(n):
        f_state = 0.97 * f_state + rng.gauss(0, 0.3)
        signal.append(f_state)
    # Day i's return depends on the signal at i-1 (known before the day starts).
    closes = {}
    px = 10_000.0
    for i in range(n):
        drift = effect * signal[i - 1] if i else 0.0
        px *= 1 + drift + rng.gauss(0, 0.03)
        closes[start + timedelta(days=i)] = px
    prints = {"bybit_btcusd": [], "binance_btcusdt": []}
    for i in range(n):
        d = start + timedelta(days=i)
        for venue, lag in (("bybit_btcusd", 0), ("binance_btcusdt", 300)):
            if i < lag:
                continue
            for h in (0, 8, 16):
                t = int(datetime(d.year, d.month, d.day, h, tzinfo=timezone.utc).timestamp() * 1000)
                prints[venue].append(FundingPrint(t, 1e-4 * (1 + signal[i]) + rng.gauss(0, 1e-6)))
    return closes, build_features(prints)


def test_study_finds_planted_negative_effect():
    closes, features = _synthetic(5, effect=-0.004)
    res = run_study(closes, features)
    assert res.verdict in {"PASS", "FRAGILE"}
    assert all(res.cells[(f, 7)].buckets.spread < 0 for f in ("bybit_btcusd_f7", "binance_btcusdt_f7", "venue_avg_f7"))
    text = render_report(res, header="# test")
    assert "## Verdict" in text and "Tests counted" in text


def test_study_null_rarely_passes():
    closes, features = _synthetic(6, effect=0.0)
    res = run_study(closes, features)
    assert res.verdict != "PASS"
