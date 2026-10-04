import json
import os
from datetime import date, timedelta
from pathlib import Path

import pytest

from price_forecast.data.candles import Candle, write_candles
from price_forecast.search import __main__ as search_main
from price_forecast.search.ledger import insert_member
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


def test_gate_for_remembers_the_checker_for_one_file():
    candles = [object()]
    other = [object()]
    first = search_main.gate_for(candles)
    second = search_main.gate_for(candles)
    third = search_main.gate_for(other)
    assert first is second
    assert first is not third


def test_zero_drawdown_child_stays_scored(monkeypatch):
    canned = _canned_metrics()
    zero_drawdown = PathMetrics(
        total_return=canned.total_return,
        edge=0.4,
        sharpe=1,
        max_drawdown=0,
        win_rate=canned.win_rate,
        profit_factor=0,
        round_trips=4,
        end_dollars=canned.end_dollars,
        start_dollars=canned.start_dollars,
        trip_pnls=canned.trip_pnls,
        hodl_return=canned.hodl_return,
    )

    def every_file(*_args, **_kwargs):
        return zero_drawdown

    monkeypatch.setattr(search_main, "score_file", every_file)
    result = search_main._score_child(
        [object()],
        {"remix": [[object()]], "synthetic": [[object()]]},
        locked_crashgate(),
        object(),
        canned,
    )
    assert result["status"] == "ok"
    assert isinstance(result["breeding_number"], (int, float))
    assert result["stress_pass"] is True
    child = {
        "id": "child",
        "breeding_number": result["breeding_number"],
        "inserted_cycle": 1,
        "coinbase_edge": result["coinbase_edge"],
        "stress_pass": True,
        "fragile": False,
    }
    assert "child" in [item["id"] for item in insert_member([], child)]


def test_stress_files_use_their_own_gate(monkeypatch):
    coinbase = [object()]
    remix = [object()]
    synthetic = [object()]
    checkers = {}

    def remember(candles):
        key = id(candles)
        if key not in checkers:
            checkers[key] = object()
        return checkers[key]

    passed = []

    def record(candles, _spec, gate):
        passed.append((candles, gate))
        return _canned_metrics()

    monkeypatch.setattr(search_main, "gate_for", remember)
    monkeypatch.setattr(search_main, "score_file", record)
    search_main._score_child(
        coinbase,
        {"remix": [remix], "synthetic": [synthetic]},
        locked_crashgate(),
        object(),
        _canned_metrics(),
    )
    by_list = {id(candles): gate for candles, gate in passed}
    assert by_list[id(remix)] is remember(remix)
    assert by_list[id(synthetic)] is remember(synthetic)
    assert by_list[id(remix)] is not remember(coinbase)


def test_pivot_runner_opens_the_manifest_from_this_run(monkeypatch, tmp_path):
    results = tmp_path / "results"
    pivot = results / "pivots"
    old_dir = pivot / "pivot_drafts" / "research_only"
    old_dir.mkdir(parents=True)
    old_yaml = old_dir / "aaa_old.yaml"
    old_yaml.write_text(
        '{"id": "stale", "conditions": ["weekly_close > sma_20"]}\n',
        encoding="utf-8",
    )
    (pivot / "pivot_manifest_crashgate_search_20000101_000000.json").write_text(
        json.dumps({"drafts": [{"path": "pivot_drafts/research_only/aaa_old.yaml"}]}),
        encoding="utf-8",
    )

    def fake_run(_command, check=True):
        new_yaml = old_dir / "zzz_new.yaml"
        new_yaml.write_text(
            '{"id": "fresh", "conditions": ["weekly_close > sma_8"]}\n',
            encoding="utf-8",
        )
        (pivot / "pivot_manifest_crashgate_search_20261004_000000.json").write_text(
            json.dumps(
                {"drafts": [{"path": "pivot_drafts/research_only/zzz_new.yaml"}]}
            ),
            encoding="utf-8",
        )
        return None

    monkeypatch.setattr(search_main.subprocess, "run", fake_run)
    monkeypatch.setattr(search_main, "_dump_yaml", lambda mapping: json.dumps(mapping))
    monkeypatch.setattr(
        search_main,
        "_load_yaml",
        lambda path: json.loads(Path(path).read_text(encoding="utf-8")),
    )
    loaded = search_main.pivot_runner(results, locked_crashgate())
    assert loaded == {"id": "fresh", "conditions": ["weekly_close > sma_8"]}
    assert old_yaml.is_file()
    assert "stale" in old_yaml.read_text(encoding="utf-8")


def test_restart_continues_the_cycle_count(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    recorded = []

    def recording_mutate(parent, run_seed=0, cycle=0):
        recorded.append(cycle)
        return parent

    monkeypatch.setattr(search_main, "mutate", recording_mutate)
    shared = ["--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    assert search_main.main(["--cycles", "2", *shared]) == 0
    assert search_main.main(["--cycles", "1", *shared]) == 0
    rows = [
        json.loads(line)
        for line in (results / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    ids = [row["id"] for row in rows]
    assert ids == ["seed", "c0", "c1", "c2"]
    assert len(ids) == len(set(ids))
    pool = json.loads((results / "pool.json").read_text(encoding="utf-8"))
    assert pool["next_cycle"] == 3
    assert recorded == [0, 1, 2]


def test_seed_stress_crash_still_saves_one_complete_seed(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    calls = {"n": 0}

    def flaky(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            return _canned_metrics()
        raise RuntimeError("stress blew up")

    monkeypatch.setattr(search_main, "score_file", flaky)
    code = search_main.main(
        ["--cycles", "0", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 0
    lines = [
        line
        for line in (results / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["id"] == "seed"
    assert row["status"] == "ok"
    assert row["stress_pass"] is False
    assert row["remix_mean_edge"] is None
    assert row["synthetic_mean_edge"] is None
    assert "breeding_number" in row
    assert "coinbase_edge" in row
    pool = json.loads((results / "pool.json").read_text(encoding="utf-8"))
    assert len(pool["members"]) == 1
    assert pool["members"][0]["id"] == "seed"


def test_existing_seed_line_is_not_written_twice(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    results.mkdir(parents=True)
    metrics = _canned_metrics()
    row = {
        "baseline": {},
        "breeding_number": 1.5,
        "coinbase": {},
        "coinbase_edge": metrics.edge,
        "cycle": -1,
        "fragile": False,
        "id": "seed",
        "parent_id": None,
        "remix_mean_edge": None,
        "round_trips": metrics.round_trips,
        "skill_warnings": {},
        "spec": spec_to_mapping(locked_crashgate()),
        "status": "ok",
        "stress_pass": False,
        "synthetic_mean_edge": None,
        "trial_count": 0,
    }
    ledger = results / "ledger.jsonl"
    original = json.dumps(row, sort_keys=True) + "\n"
    ledger.write_text(original, encoding="utf-8")
    code = search_main.main(
        ["--cycles", "0", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 0
    assert ledger.read_text(encoding="utf-8") == original
    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == "seed"
    pool = json.loads((results / "pool.json").read_text(encoding="utf-8"))
    assert len(pool["members"]) == 1
    assert pool["members"][0]["id"] == "seed"


def test_seed_rewrite_leaves_the_ledger_intact_when_replace_fails(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    original = b'{"id": "seed"}\n{"id": "c0"}\n'
    ledger.write_bytes(original)
    metrics = _canned_metrics()
    row = {
        "baseline": {},
        "breeding_number": 1.5,
        "coinbase": {},
        "coinbase_edge": metrics.edge,
        "cycle": -1,
        "fragile": False,
        "id": "seed",
        "parent_id": None,
        "remix_mean_edge": None,
        "round_trips": metrics.round_trips,
        "skill_warnings": {},
        "spec": spec_to_mapping(locked_crashgate()),
        "status": "ok",
        "stress_pass": False,
        "synthetic_mean_edge": None,
        "trial_count": 0,
    }

    def fail_replace(*_args, **_kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        search_main._replace_seed_line(ledger, row)
    assert ledger.read_bytes() == original
