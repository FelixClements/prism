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


def _indicator(**condition) -> Spec:
    return spec_from_mapping(
        {
            "mode": "indicator",
            "conditions": [condition],
            "base_or_breakout": False,
            "above_long_averages": False,
        }
    )


def test_rsi_parent_steps_exactly_one_number():
    parent = _indicator(left="rsi", args=[21], op="<", right={"value": 25})
    edits = legal_edits(parent)
    assert len(edits) == 4
    for edit in edits:
        period_changed = edit.conditions[0].args != (21,)
        level_changed = edit.conditions[0].right_value != 25
        assert period_changed != level_changed
    assert {edit.conditions[0].args[0] for edit in edits} == {20, 21, 22}
    assert {edit.conditions[0].right_value for edit in edits} == {24, 25, 26}


def test_seven_week_indicator_steps_to_six_or_eight():
    parent = _indicator(
        left="close",
        args=[],
        op=">",
        right={"series": "sma", "args": [7]},
    )
    assert sorted(edit.conditions[0].right_args[0] for edit in legal_edits(parent)) == [6, 8]


def test_locked_eight_week_field_stays_on_the_ladder():
    parent = locked_crashgate()
    moved = [
        edit.close_above_sma_weeks
        for edit in legal_edits(parent)
        if edit.mode == "threshold" and edit.close_above_sma_weeks != 8
    ]
    assert set(moved) == {6, 10}


def test_bollinger_width_and_relative_volume_use_their_steps():
    width = _indicator(
        left="close",
        args=[],
        op=">",
        right={"series": "bb_upper", "args": [20, 2.2]},
    )
    widths = sorted(
        edit.conditions[0].right_args[1]
        for edit in legal_edits(width)
        if edit.conditions[0].right_args[1] != 2.2
    )
    assert widths == [1.7, 2.7]
    volume = _indicator(left="rel_volume", args=[20], op=">=", right={"value": 1.55})
    multiples = sorted(
        edit.conditions[0].right_value
        for edit in legal_edits(volume)
        if edit.conditions[0].right_value != 1.55
    )
    assert multiples == [1.45, 1.65]


def test_same_seed_and_cycle_match_and_the_next_cycle_does_not():
    parent = locked_crashgate()
    assert mutate(parent, run_seed=0, cycle=3) == mutate(parent, run_seed=0, cycle=3)
    assert mutate(parent, run_seed=0, cycle=3) != mutate(parent, run_seed=0, cycle=4)
