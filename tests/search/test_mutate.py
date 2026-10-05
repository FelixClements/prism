from dataclasses import fields

from price_forecast.search.mutate import legal_edits, mutate
from price_forecast.search.spec import Spec, locked_crashgate, spec_from_mapping, spec_to_mapping


class _Pick:
    def __init__(self, index: int):
        self.index = index

    def integers(self, low: int, high: int) -> int:
        assert low == 0
        assert high > self.index
        return self.index


def _differing_names(left: Spec, right: Spec) -> list[str]:
    names = []
    for field in fields(Spec):
        if getattr(left, field.name) != getattr(right, field.name):
            names.append(field.name)
    return names


def test_first_edit_switches_mode_to_the_first_dual_pair():
    child = mutate(locked_crashgate(), cycle=0, rng=_Pick(0))
    assert child == Spec(
        mode="dual_average",
        fast_weeks=4,
        slow_weeks=12,
        base_or_breakout=False,
        above_long_averages=False,
    )


def test_same_mode_edit_changes_one_field():
    parent = locked_crashgate()
    edits = legal_edits(parent)
    same_mode = [edit for edit in edits if edit.mode == parent.mode]
    assert same_mode
    for edit in same_mode:
        changed = _differing_names(parent, edit)
        assert len(changed) == 1
        spec_from_mapping(spec_to_mapping(edit))


def test_same_seed_and_cycle_match_and_the_next_cycle_does_not():
    parent = locked_crashgate()
    assert mutate(parent, run_seed=0, cycle=3) == mutate(parent, run_seed=0, cycle=3)
    assert mutate(parent, run_seed=0, cycle=3) != mutate(parent, run_seed=0, cycle=4)
