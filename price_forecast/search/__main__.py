from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from price_forecast.data.candles import BTC_USD_DAILY_CSV, read_candles
from price_forecast.search.ledger import (
    _replace,
    append_jsonl,
    champion_of,
    insert_member,
    load_pool,
    save_pool,
)
from price_forecast.search.mutate import mutate
from price_forecast.search.runner import FILL_COST, simulate_spec
from price_forecast.search.score import (
    PathMetrics,
    baseline_is_usable,
    breeding_number,
    is_fragile,
    metrics_from_path,
    skill_warnings,
    stress_result,
)
from price_forecast.search.spec import locked_crashgate, spec_to_mapping
from price_forecast.search.translate import Unmapped, append_side_pile, translate
from price_forecast.strategies.crashgate_entry import BaseBreakoutGate
from price_forecast.strategies.crashgate_v1 import weekly_sessions

REPO = Path(__file__).resolve().parents[2]


def _skill_module(skill: str, module: str):
    scripts = Path.home() / ".agents" / "skills" / skill / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return importlib.import_module(module)


def _warning_tools():
    evaluate = _skill_module("backtest-expert", "evaluate_backtest").evaluate
    review = _skill_module("edge-strategy-reviewer", "review_strategy_drafts").review_draft
    return evaluate, review


def smoke_skills() -> None:
    evaluate, review = _warning_tools()
    skill_warnings(
        PathMetrics(
            total_return=1.0,
            edge=1.0,
            sharpe=1.0,
            max_drawdown=-0.1,
            win_rate=0.5,
            profit_factor=2.0,
            round_trips=30,
            end_dollars=20_000.0,
            start_dollars=10_000.0,
            trip_pnls=(100.0, -50.0),
            hodl_return=0.0,
        ),
        evaluate=evaluate,
        review=review,
    )


def build_remix(coinbase: Path, count: int) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "price_forecast.datafactory.remix",
            "--csv",
            str(coinbase),
            "--n-paths",
            str(count),
            "--seed",
            "0",
        ],
        check=True,
    )


def build_synthetic(coinbase: Path, count: int) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "price_forecast.datafactory.synthetic",
            "--csv",
            str(coinbase),
            "--n-paths",
            str(count),
            "--seed",
            "0",
        ],
        check=True,
    )


_gate_checkers: dict[int, object] = {}


def gate_for(candles):
    key = id(candles)
    remembered = _gate_checkers.get(key)
    if remembered is not None:
        return remembered
    cached = {}

    def _gate(day):
        box = cached.get("gate")
        if box is None:
            box = BaseBreakoutGate(candles)
            cached["gate"] = box
        return box.parts(day)

    _gate_checkers[key] = _gate
    return _gate


def score_file(candles, spec, gate) -> PathMetrics:
    weeks = weekly_sessions(candles)
    path = simulate_spec(weeks, spec, gate, cost=FILL_COST)
    return metrics_from_path(
        path, first_price=path.start_price, last_price=path.end_price, cost=FILL_COST
    )


def _family_paths(directory: Path, count: int) -> list[Path]:
    return [directory / f"btc-usd-daily-seed0-path{index}.csv" for index in range(count)]


def _ensure_family(directory: Path, coinbase: Path, count: int, builder) -> None:
    paths = _family_paths(directory, count)
    if any(not path.is_file() for path in paths):
        builder(coinbase, count)
    if any(not path.is_file() for path in paths):
        raise FileNotFoundError(directory)


def _load_yaml(path: Path):
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _dump_yaml(mapping: dict) -> str:
    import yaml

    return yaml.safe_dump(mapping, sort_keys=True)


def pivot_runner(results: Path, champion_spec) -> dict:
    dest = results / "pivots"
    dest.mkdir(parents=True, exist_ok=True)
    draft_path = dest / "champion_draft.yaml"
    diagnosis_path = dest / "diagnosis.json"
    draft_path.write_text(_dump_yaml(spec_to_mapping(champion_spec)), encoding="utf-8")
    diagnosis_path.write_text(
        json.dumps(
            {
                "strategy_id": "crashgate_search",
                "recommendation": "pivot",
                "score_trajectory": [],
                "triggers_fired": [
                    {
                        "trigger": "plateau",
                        "severity": "medium",
                        "message": "champion breeding number did not rise for 50 cycles",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    script = Path.home() / ".agents" / "skills" / "strategy-pivot-designer" / "scripts" / "generate_pivots.py"
    before = {path.name for path in dest.glob("pivot_manifest_*.json")}
    try:
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--diagnosis",
                str(diagnosis_path),
                "--strategy",
                str(draft_path),
                "--max-pivots",
                "1",
                "--output-dir",
                str(dest),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise Unmapped("pivot script failed") from exc
    new_names = sorted(
        path.name for path in dest.glob("pivot_manifest_*.json") if path.name not in before
    )
    if not new_names:
        raise Unmapped("pivot script failed")
    try:
        manifest = json.loads((dest / new_names[-1]).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Unmapped("pivot script failed") from exc
    drafts = manifest.get("drafts") if isinstance(manifest, dict) else None
    if not isinstance(drafts, list) or not drafts or not isinstance(drafts[0], dict):
        raise Unmapped("pivot script failed")
    chosen = dest / str(drafts[0].get("path", ""))
    if not chosen.is_file():
        raise Unmapped("pivot script failed")
    loaded = _load_yaml(chosen)
    if not isinstance(loaded, dict):
        raise Unmapped("pivot script failed")
    return loaded


def _metrics_dict(metrics: PathMetrics) -> dict:
    return {
        "total_return": metrics.total_return,
        "edge": metrics.edge,
        "sharpe": metrics.sharpe,
        "max_drawdown": metrics.max_drawdown,
        "win_rate": metrics.win_rate,
        "profit_factor": metrics.profit_factor,
        "round_trips": metrics.round_trips,
    }


def _safe_warnings(metrics: PathMetrics) -> dict:
    try:
        evaluate, review = _warning_tools()
        return skill_warnings(metrics, evaluate=evaluate, review=review)
    except Exception as exc:
        return {"skill_error": str(exc)}


def _score_child(coinbase_candles, stress_candles, spec, _gate, baseline: PathMetrics) -> dict:
    try:
        coinbase = score_file(coinbase_candles, spec, gate_for(coinbase_candles))
    except Exception as exc:
        return {"status": "error", "error": str(exc), "stress_pass": False, "fragile": False, "round_trips": 0}
    if coinbase.round_trips == 0 or coinbase.sharpe is None or coinbase.profit_factor is None:
        return {
            "status": "error",
            "error": "unusable coinbase metrics",
            "stress_pass": False,
            "fragile": False,
            "round_trips": coinbase.round_trips,
            "coinbase": _metrics_dict(coinbase),
        }
    fragile = is_fragile(coinbase)
    if coinbase.edge <= 0.0:
        return {
            "status": "ok",
            "coinbase": _metrics_dict(coinbase),
            "baseline": _metrics_dict(baseline),
            "breeding_number": breeding_number(coinbase, baseline),
            "remix_mean_edge": None,
            "synthetic_mean_edge": None,
            "stress_pass": False,
            "fragile": fragile,
            "round_trips": coinbase.round_trips,
            "coinbase_edge": coinbase.edge,
            "skill_warnings": _safe_warnings(coinbase),
        }
    remix_edges = []
    synthetic_edges = []
    try:
        for candles in stress_candles["remix"]:
            remix_edges.append(score_file(candles, spec, gate_for(candles)).edge)
        for candles in stress_candles["synthetic"]:
            synthetic_edges.append(score_file(candles, spec, gate_for(candles)).edge)
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "stress_pass": False,
            "fragile": fragile,
            "round_trips": coinbase.round_trips,
        }
    passed, remix_mean, synthetic_mean = stress_result(coinbase.edge, remix_edges, synthetic_edges)
    return {
        "status": "ok",
        "coinbase": _metrics_dict(coinbase),
        "baseline": _metrics_dict(baseline),
        "breeding_number": breeding_number(coinbase, baseline),
        "remix_mean_edge": remix_mean,
        "synthetic_mean_edge": synthetic_mean,
        "stress_pass": passed,
        "fragile": fragile,
        "round_trips": coinbase.round_trips,
        "coinbase_edge": coinbase.edge,
        "skill_warnings": _safe_warnings(coinbase),
    }


def _complete_seed_row(baseline: PathMetrics) -> dict:
    return {
        "status": "ok",
        "id": "seed",
        "parent_id": None,
        "cycle": -1,
        "trial_count": 0,
        "spec": spec_to_mapping(locked_crashgate()),
        "breeding_number": breeding_number(baseline, baseline),
        "coinbase_edge": baseline.edge,
        "remix_mean_edge": None,
        "synthetic_mean_edge": None,
        "stress_pass": False,
        "fragile": is_fragile(baseline),
        "round_trips": baseline.round_trips,
        "coinbase": _metrics_dict(baseline),
        "baseline": _metrics_dict(baseline),
        "skill_warnings": _safe_warnings(baseline),
    }


def _ledger_seed(path: Path) -> dict | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("id") == "seed":
            return row
    return None


def _seed_is_reusable(row: dict) -> bool:
    return row.get("breeding_number") is not None and row.get("coinbase_edge") is not None


def _replace_seed_line(path: Path, row: dict) -> None:
    original = path.read_text(encoding="utf-8")
    replaced = False
    out = []
    for line in original.splitlines():
        if not replaced and line.strip() and json.loads(line).get("id") == "seed":
            out.append(json.dumps(row, sort_keys=True))
            replaced = True
            continue
        out.append(line)
    text = "\n".join(out)
    if text:
        text += "\n"
    _replace(path, text)


def _member_from_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "spec": row["spec"],
        "breeding_number": row["breeding_number"],
        "inserted_cycle": row["cycle"],
        "trial_count": row["trial_count"],
        "coinbase_edge": row["coinbase_edge"],
        "stress_pass": row["stress_pass"],
        "fragile": row["fragile"],
    }


def _load_stress(remix_dir: Path, synthetic_dir: Path, count: int) -> dict:
    return {
        "remix": [read_candles(path) for path in _family_paths(remix_dir, count)],
        "synthetic": [read_candles(path) for path in _family_paths(synthetic_dir, count)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Breed CrashGate specs into a ledger.")
    parser.add_argument("--cycles", type=int, default=None)
    parser.add_argument("--run-seed", type=int, default=0)
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--coinbase", type=Path, default=None)
    parser.add_argument("--path-count", type=int, default=100)
    args = parser.parse_args(argv)
    coinbase_path = args.coinbase or BTC_USD_DAILY_CSV
    results = args.results or (REPO / "results" / "search")
    if not coinbase_path.is_file():
        return 1
    remix_dir = coinbase_path.parent / "remix"
    synthetic_dir = coinbase_path.parent / "synthetic"
    try:
        _ensure_family(remix_dir, coinbase_path, args.path_count, build_remix)
        _ensure_family(synthetic_dir, coinbase_path, args.path_count, build_synthetic)
        smoke_skills()
    except Exception:
        return 1

    coinbase_candles = read_candles(coinbase_path)
    gate = gate_for(coinbase_candles)
    stress = _load_stress(remix_dir, synthetic_dir, args.path_count)
    pool_path = results / "pool.json"
    ledger_path = results / "ledger.jsonl"
    side_path = results / "side_pile.jsonl"
    pool = load_pool(pool_path)
    if not pool["members"]:
        baseline = score_file(coinbase_candles, locked_crashgate(), gate)
        if not baseline_is_usable(baseline):
            return 1
        existing_seed = _ledger_seed(ledger_path)
        if existing_seed is not None:
            if _seed_is_reusable(existing_seed):
                member = _member_from_row(existing_seed)
            else:
                row = _complete_seed_row(baseline)
                _replace_seed_line(ledger_path, row)
                member = _member_from_row(row)
        else:
            scored = _score_child(coinbase_candles, stress, locked_crashgate(), gate, baseline)
            if scored.get("status") != "ok" or "breeding_number" not in scored:
                row = _complete_seed_row(baseline)
            else:
                scored.update(
                    {
                        "id": "seed",
                        "parent_id": None,
                        "cycle": -1,
                        "spec": spec_to_mapping(locked_crashgate()),
                        "trial_count": 0,
                        "status": "ok",
                    }
                )
                row = scored
            append_jsonl(ledger_path, row)
            member = _member_from_row(row)
        pool = {
            "members": insert_member([], member, seed=True),
            "champion_id": "seed",
            "stall": 0,
            "trial_count": 0,
            "next_cycle": 0,
        }
        save_pool(pool_path, pool)
        baseline_metrics = baseline
    else:
        baseline_metrics = PathMetrics(
            total_return=pool["baseline"]["total_return"],
            edge=pool["baseline"]["edge"],
            sharpe=pool["baseline"]["sharpe"],
            max_drawdown=pool["baseline"]["max_drawdown"],
            win_rate=pool["baseline"]["win_rate"],
            profit_factor=pool["baseline"]["profit_factor"],
            round_trips=pool["baseline"]["round_trips"],
            end_dollars=pool["baseline"]["end_dollars"],
            start_dollars=pool["baseline"]["start_dollars"],
            trip_pnls=tuple(pool["baseline"]["trip_pnls"]),
            hodl_return=pool["baseline"]["hodl_return"],
        )
    pool["baseline"] = _metrics_dict(baseline_metrics) | {
        "end_dollars": baseline_metrics.end_dollars,
        "start_dollars": baseline_metrics.start_dollars,
        "trip_pnls": list(baseline_metrics.trip_pnls),
        "hodl_return": baseline_metrics.hodl_return,
    }
    save_pool(pool_path, pool)

    def run_cycle(cycle: int) -> None:
        nonlocal pool

        def save_cycle() -> None:
            pool["next_cycle"] = cycle + 1
            save_pool(pool_path, pool)

        members = pool["members"]
        champion = champion_of(members)
        previous = champion["breeding_number"]
        trial = pool["trial_count"]
        stall = pool["stall"]
        parent_id = champion["id"]
        child_spec = None
        if stall >= 50:
            try:
                draft = pivot_runner(results, parent_spec(champion))
                child_spec = translate(draft)
            except Unmapped as exc:
                append_side_pile(side_path, draft_id=str(champion["id"]), phrase=exc.phrase)
                pool["stall"] = 0
                save_cycle()
                return
            pool["stall"] = 0
            stall = 0
        if child_spec is None:
            picker = np.random.Generator(np.random.PCG64(np.random.SeedSequence([args.run_seed, cycle, 1])))
            parent = members[int(picker.integers(0, len(members)))]
            parent_id = parent["id"]
            child_spec = mutate(parent_spec(parent), run_seed=args.run_seed, cycle=cycle)
        scored = _score_child(coinbase_candles, stress, child_spec, gate, baseline_metrics)
        status = scored["status"]
        if status == "ok":
            trial += 1
            pool["trial_count"] = trial
        row = {
            "id": f"c{cycle}",
            "parent_id": parent_id,
            "cycle": cycle,
            "spec": spec_to_mapping(child_spec),
            "trial_count": trial,
        }
        row.update(scored)
        append_jsonl(ledger_path, row)
        if status == "ok":
            members = insert_member(members, _member_from_row(row))
            pool["members"] = members
            current = champion_of(members)
            pool["champion_id"] = current["id"]
            pool["stall"] = 0 if current["breeding_number"] > previous else stall + 1
        else:
            pool["stall"] = stall + 1
        save_cycle()

    cycles = args.cycles
    start = int(pool.get("next_cycle", 0))
    try:
        if cycles is None:
            cycle = start
            while True:
                run_cycle(cycle)
                cycle += 1
        else:
            for cycle in range(start, start + cycles):
                run_cycle(cycle)
    except KeyboardInterrupt:
        return 0
    return 0


def parent_spec(member: dict):
    from price_forecast.search.spec import spec_from_mapping

    return spec_from_mapping(member["spec"])


if __name__ == "__main__":
    raise SystemExit(main())
