import json
from datetime import date, timedelta
from pathlib import Path

from price_forecast.data.candles import Candle, write_candles
from price_forecast.search import __main__ as search_main
from price_forecast.search.score import PathMetrics
from price_forecast.search.spec import locked_crashgate, spec_to_mapping


def _install(monkeypatch, tmp_path: Path):
    coinbase = tmp_path / "data" / "btc-usd-daily.csv"
    coinbase.parent.mkdir(parents=True)
    day = date(2018, 1, 1)
    candles = [
        Candle(day + timedelta(days=i), 100.0, 110.0, 100.0, 105.0, 1.0)
        for i in range(400)
    ]
    write_candles(coinbase, candles)

    def build(kind: str):
        def _build(_csv, count: int) -> None:
            dest = coinbase.parent / kind
            dest.mkdir(parents=True, exist_ok=True)
            for index in range(count):
                write_candles(dest / f"btc-usd-daily-seed0-path{index}.csv", candles)

        return _build

    monkeypatch.setattr(search_main, "build_remix", build("remix"))
    monkeypatch.setattr(search_main, "build_synthetic", build("synthetic"))
    monkeypatch.setattr(search_main, "smoke_skills", lambda: None)
    monkeypatch.setattr(search_main, "gate_for", lambda _candles: (lambda _day: (True, True)))
    monkeypatch.setattr(search_main, "pivot_runner", lambda *_args: {"conditions": ["funding"]})
    monkeypatch.setattr(search_main, "score_file", lambda *_args, **_kwargs: _canned_metrics())
    return coinbase


def _canned_metrics() -> PathMetrics:
    return PathMetrics(
        total_return=1.0,
        edge=0.4,
        sharpe=1.0,
        max_drawdown=-0.2,
        win_rate=0.5,
        profit_factor=2.0,
        round_trips=4,
        end_dollars=20_000.0,
        start_dollars=10_000.0,
        trip_pnls=(2_500.0, 2_500.0, 2_500.0, 2_500.0),
        hodl_return=0.6,
    )


def test_missing_coinbase_writes_nothing(monkeypatch, tmp_path):
    results = tmp_path / "results" / "search"
    monkeypatch.setattr(search_main, "smoke_skills", lambda: (_ for _ in ()).throw(RuntimeError("skill")))
    code = search_main.main(
        ["--cycles", "1", "--coinbase", str(tmp_path / "missing.csv"), "--results", str(results), "--path-count", "2"]
    )
    assert code == 1
    assert not results.exists()


def test_skill_failure_writes_nothing(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"

    def boom():
        raise RuntimeError("skill")

    monkeypatch.setattr(search_main, "smoke_skills", boom)
    code = search_main.main(
        ["--cycles", "1", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 1
    assert not results.exists()


def test_seed_reloads_and_does_not_touch_the_locked_file(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    locked = Path("price_forecast/strategies/crashgate_v1.py").read_bytes()
    code = search_main.main(
        ["--cycles", "0", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 0
    assert Path("price_forecast/strategies/crashgate_v1.py").read_bytes() == locked
    pool = json.loads((results / "pool.json").read_text(encoding="utf-8"))
    assert pool["members"][0]["spec"] == spec_to_mapping(locked_crashgate())
    assert pool["members"][0]["trial_count"] == 0


def test_stall_calls_the_pivot_once(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    calls = {"n": 0}

    def pivot(*_args):
        calls["n"] += 1
        return {"id": "fund", "conditions": ["funding"]}

    monkeypatch.setattr(search_main, "pivot_runner", pivot)
    monkeypatch.setattr(search_main, "mutate", lambda parent, **_kwargs: parent)
    code = search_main.main(
        ["--cycles", "51", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 0
    assert calls["n"] == 1
    side = (results / "side_pile.jsonl").read_text(encoding="utf-8")
    assert "funding" in side
