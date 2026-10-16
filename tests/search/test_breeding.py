import json
from dataclasses import replace
from datetime import date, timedelta

from price_forecast.search import __main__ as search_main
from price_forecast.search.mutate import legal_edits, sell_edits
from price_forecast.search.runner import simulate_spec
from price_forecast.search.score import beats_best
from price_forecast.search.spec import Condition, Spec, locked_crashgate, spec_from_mapping, spec_to_mapping
from tests.search.test_preflight import _install


def _weeks(closes: list[float]):
    start = date(2018, 1, 7)
    return [(start + timedelta(days=7 * index), close) for index, close in enumerate(closes)]


def _rsi_added(parent: Spec) -> list[Spec]:
    return [
        edit
        for edit in legal_edits(parent)
        if len(edit.conditions) == len(parent.conditions) + 1
        and edit.conditions[-1] == Condition("rsi", (14,), "<", 30)
    ]


def test_locked_edits_stay_on_crashgate_and_can_add_one_menu_row():
    parent = locked_crashgate()
    edits = legal_edits(parent)
    assert {edit.mode for edit in edits} == {"threshold"}
    added = _rsi_added(parent)
    assert len(added) == 1
    child = added[0]
    assert child.close_below_sma_weeks == 16
    assert child.down_week == 0.10
    assert len(child.conditions) == 1
    assert spec_from_mapping(spec_to_mapping(child)) == child


def test_one_try_adds_only_one_comparison():
    parent = locked_crashgate()
    assert all(len(edit.conditions) <= 1 for edit in legal_edits(parent))


def test_sell_only_edits_freeze_the_buy():
    parent = replace(
        locked_crashgate(),
        conditions=(Condition("macd", (11, 26), ">", right_series="macd_signal", right_args=(12, 25, 9)),),
    )
    edits = sell_edits(parent)
    exits = [edit.exit_conditions[0] for edit in edits]
    assert Condition("rsi", (14,), ">", 70) in exits
    assert Condition("rsi", (14,), ">", 69) in exits
    assert Condition("rsi", (13,), ">", 70) in exits
    assert all(len(edit.exit_conditions) == 1 for edit in edits)
    for edit in edits:
        assert edit.conditions == parent.conditions
        assert edit.close_above_sma_weeks == parent.close_above_sma_weeks
        assert edit.close_below_sma_weeks == parent.close_below_sma_weeks
        assert edit.down_week == parent.down_week
        assert edit.base_or_breakout == parent.base_or_breakout
        assert edit.above_long_averages == parent.above_long_averages


def test_a_sell_indicator_can_be_added_and_varied():
    parent = locked_crashgate()
    sells = [edit for edit in legal_edits(parent) if edit.exit_conditions]
    added = [edit.exit_conditions[0] for edit in sells if len(edit.exit_conditions) == 1]
    assert Condition("rsi", (14,), ">", 70) in added
    assert Condition("rsi", (14,), ">", 69) in added
    assert Condition("rsi", (13,), ">", 70) in added
    for edit in sells:
        assert edit.conditions == ()
        assert edit.close_below_sma_weeks == 16
        assert edit.down_week == 0.10
        assert len(edit.exit_conditions) == 1


def test_sell_indicator_exits_while_the_crashgate_sell_is_quiet():
    spec = Spec(
        mode="threshold",
        close_above_sma_weeks=4,
        base_or_breakout=False,
        above_long_averages=False,
        close_below_sma_weeks=12,
        down_week=None,
        exit_conditions=(Condition("close", (), ">", 150),),
    )
    closes = [100.0] * 16 + [120.0] * 8 + [200.0] * 6
    path = simulate_spec(_weeks(closes), spec, lambda _day: (True, True))
    sells = [fill for fill in path.fills if fill.side == "SELL"]
    assert sells
    assert sells[0].price == 200.0
    quiet = replace(spec, exit_conditions=())
    assert [fill for fill in simulate_spec(_weeks(closes), quiet, lambda _day: (True, True)).fills if fill.side == "SELL"] == []


def test_menu_variations_are_legal_from_crashgate():
    edits = legal_edits(locked_crashgate())
    added = [edit.conditions[0] for edit in edits if len(edit.conditions) == 1]
    assert Condition("rsi", (13,), "<", 30) in added
    assert Condition("rsi", (15,), "<", 30) in added
    assert Condition("rsi", (14,), "<", 29) in added
    assert Condition("rsi", (14,), "<", 31) in added
    assert Condition("rsi", (12,), "<", 30) not in added


def test_second_try_steps_rsi_or_adds_one_more_comparison():
    parent = _rsi_added(locked_crashgate())[0]
    edits = legal_edits(parent)
    stepped = [edit for edit in edits if len(edit.conditions) == 1]
    periods = {edit.conditions[0].args[0] for edit in stepped}
    levels = {edit.conditions[0].right_value for edit in stepped}
    assert 13 in periods and 15 in periods
    assert 29 in levels and 31 in levels
    assert any(len(edit.conditions) == 2 for edit in edits)
    assert all(len(edit.conditions) <= 2 for edit in edits)


def test_added_check_gates_the_buy_and_not_the_sell():
    spec = Spec(
        mode="threshold",
        close_above_sma_weeks=None,
        base_or_breakout=True,
        above_long_averages=False,
        close_below_sma_weeks=4,
        down_week=None,
        conditions=(Condition("close", (), "<", 50),),
    )
    closes = [100.0] * 8 + [40.0, 40.0, 10.0, 10.0, 10.0]
    path = simulate_spec(_weeks(closes), spec, lambda _day: (True, True))
    buys = [fill for fill in path.fills if fill.side == "BUY"]
    sells = [fill for fill in path.fills if fill.side == "SELL"]
    assert buys
    assert buys[0].price == 40.0
    assert sells
    assert sells[0].price == 10.0


def test_path_check_uses_the_current_best_not_half_the_coinbase_edge():
    best = dict(breeding=5.0, edge=17.0, remix=-32.0, synthetic=-40.0, fragile=False)
    better = dict(breeding=5.1, edge=1.0, remix=-10.0, synthetic=-15.0, fragile=False)
    worse_synth = dict(breeding=5.1, edge=1.0, remix=-10.0, synthetic=-50.0, fragile=False)
    worse_remix = dict(breeding=6.0, edge=1.0, remix=-33.0, synthetic=-15.0, fragile=False)
    fragile = dict(breeding=6.0, edge=1.0, remix=-10.0, synthetic=-15.0, fragile=True)
    no_edge = dict(breeding=6.0, edge=0.0, remix=-10.0, synthetic=-15.0, fragile=False)
    assert beats_best(better, best)
    assert not beats_best(worse_synth, best)
    assert not beats_best(worse_remix, best)
    assert not beats_best(fragile, best)
    assert not beats_best(no_edge, best)


def test_a_winner_becomes_the_only_parent(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    search_main.main(
        ["--cycles", "0", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    pool_path = results / "pool.json"
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    pool["members"][0]["remix_mean_edge"] = -32.0
    pool["members"][0]["synthetic_mean_edge"] = -40.0
    pool_path.write_text(json.dumps(pool), encoding="utf-8")
    child = replace(
        locked_crashgate(),
        conditions=(Condition("rsi", (14,), "<", 30),),
    )

    def scored(_candles, _stress, spec, _gate, _baseline):
        won = spec.conditions != ()
        return {
            "status": "ok",
            "breeding_number": 6.0 if won else 5.0,
            "coinbase_edge": 1.0,
            "remix_mean_edge": -10.0 if won else -32.0,
            "synthetic_mean_edge": -15.0 if won else -40.0,
            "stress_pass": True,
            "fragile": False,
            "round_trips": 4,
            "coinbase": {},
            "baseline": {},
            "skill_warnings": {},
        }

    monkeypatch.setattr(search_main, "_score_child", scored)
    monkeypatch.setattr(search_main, "mutate_sell", lambda _parent, **_kwargs: child)
    code = search_main.main(
        ["--cycles", "1", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 0
    pool = json.loads((results / "pool.json").read_text(encoding="utf-8"))
    assert len(pool["members"]) == 1
    assert pool["champion_id"] == "c0"
    assert pool["members"][0]["remix_mean_edge"] == -10.0
    assert pool["members"][0]["synthetic_mean_edge"] == -15.0


def test_a_failed_try_leaves_the_current_best_as_parent(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    search_main.main(
        ["--cycles", "0", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )

    def scored(*_args):
        return {
            "status": "ok",
            "breeding_number": 4.0,
            "coinbase_edge": 1.0,
            "remix_mean_edge": -10.0,
            "synthetic_mean_edge": -15.0,
            "stress_pass": True,
            "fragile": False,
            "round_trips": 4,
            "coinbase": {},
            "baseline": {},
            "skill_warnings": {},
        }

    monkeypatch.setattr(search_main, "_score_child", scored)
    code = search_main.main(
        ["--cycles", "1", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 0
    pool = json.loads((results / "pool.json").read_text(encoding="utf-8"))
    assert pool["champion_id"] == "seed"
    assert len(pool["members"]) == 1


def test_fifty_quiet_tries_do_not_call_the_pivot(monkeypatch, tmp_path):
    coinbase = _install(monkeypatch, tmp_path)
    results = tmp_path / "results" / "search"
    calls = {"n": 0}

    def pivot(*_args):
        calls["n"] += 1
        return {"conditions": ["funding"]}

    monkeypatch.setattr(search_main, "pivot_runner", pivot)
    monkeypatch.setattr(search_main, "mutate_sell", lambda parent, **_kwargs: parent)
    code = search_main.main(
        ["--cycles", "51", "--coinbase", str(coinbase), "--results", str(results), "--path-count", "2"]
    )
    assert code == 0
    assert calls["n"] == 0
