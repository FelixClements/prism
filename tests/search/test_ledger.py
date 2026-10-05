import json

from price_forecast.search.ledger import append_jsonl, champion_of, insert_member, load_pool


def _member(id_: str, number: float, cycle: int, *, edge: float = 1.0, stress: bool = True, fragile: bool = False):
    return {
        "id": id_,
        "spec": {"mode": "threshold"},
        "breeding_number": number,
        "inserted_cycle": cycle,
        "trial_count": cycle,
        "coinbase_edge": edge,
        "stress_pass": stress,
        "fragile": fragile,
    }


def test_seed_is_kept_when_stress_fails():
    failed = _member("seed", 5.0, 0, stress=False)
    assert [item["id"] for item in insert_member([], failed, seed=True)] == ["seed"]


def test_failed_stress_does_not_enter():
    pool = insert_member([], _member("seed", 5.0, 0), seed=True)
    child = _member("c1", 9.0, 1, stress=False)
    assert [item["id"] for item in insert_member(pool, child)] == ["seed"]


def test_tied_weakest_keeps_the_older_member():
    members = [
        _member("seed", 4, -1),
        _member("cycle5", 4, 5),
        _member("strong", 6, 1),
    ]
    candidate = _member("child", 4.1, 6)
    ids = [item["id"] for item in insert_member(members, candidate, cap=3)]
    assert "seed" in ids
    assert "cycle5" not in ids


def test_tie_keeps_the_older_member_and_the_higher_number_replaces_the_weakest():
    members = [_member("a", 5.0, 0), _member("b", 4.0, 1)]
    tied = _member("c", 4.0, 2)
    assert [item["id"] for item in insert_member(members, tied, cap=2)] == ["a", "b"]
    stronger = _member("d", 4.1, 3)
    assert [item["id"] for item in insert_member(members, stronger, cap=2)] == ["a", "d"]


def test_champion_tie_keeps_the_older_member():
    members = [_member("old", 5.0, 0), _member("new", 5.0, 1)]
    assert champion_of(members)["id"] == "old"


def test_temp_replace_leaves_the_previous_line_when_replace_is_the_commit(tmp_path):
    path = tmp_path / "ledger.jsonl"
    append_jsonl(path, {"id": "seed", "status": "ok"})
    append_jsonl(path, {"id": "c1", "status": "ok"})
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in rows] == ["seed", "c1"]
    assert load_pool(tmp_path / "missing.json")["members"] == []
