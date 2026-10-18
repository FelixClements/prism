from dataclasses import replace

from price_forecast.search.mutate import mutate_sell, sell_edits
from price_forecast.search.spec import Condition, Spec, locked_crashgate


def _selling(condition: Condition) -> Spec:
    return replace(locked_crashgate(), exit_conditions=(condition,))


def _stepped(parent: Spec) -> list[Condition]:
    return [edit.exit_conditions[0] for edit in sell_edits(parent) if len(edit.exit_conditions) == 1]


def test_rsi_sell_steps_exactly_one_number():
    steps = _stepped(_selling(Condition("rsi", (21,), "<", 25)))
    assert len(steps) == 4
    for step in steps:
        period_changed = step.args != (21,)
        level_changed = step.right_value != 25
        assert period_changed != level_changed
    assert {step.args[0] for step in steps} == {20, 21, 22}
    assert {step.right_value for step in steps} == {24, 25, 26}


def test_seven_week_sell_steps_to_six_or_eight():
    steps = _stepped(_selling(Condition("close", (), ">", right_series="sma", right_args=(7,))))
    assert sorted(step.right_args[0] for step in steps) == [6, 8]


def test_bollinger_width_and_relative_volume_use_their_steps():
    width = _selling(Condition("close", (), ">", right_series="bb_upper", right_args=(20, 2.2)))
    widths = sorted(step.right_args[1] for step in _stepped(width) if step.right_args[1] != 2.2)
    assert widths == [1.7, 2.7]
    volume = _selling(Condition("rel_volume", (20,), ">=", 1.55))
    multiples = sorted(step.right_value for step in _stepped(volume) if step.right_value != 1.55)
    assert multiples == [1.45, 1.65]


def test_same_seed_and_cycle_match_and_the_next_cycle_does_not():
    parent = locked_crashgate()
    assert mutate_sell(parent, run_seed=0, cycle=3) == mutate_sell(parent, run_seed=0, cycle=3)
    assert mutate_sell(parent, run_seed=0, cycle=3) != mutate_sell(parent, run_seed=0, cycle=4)
