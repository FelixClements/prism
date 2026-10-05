import json

import pytest

from price_forecast.search.spec import locked_crashgate
from price_forecast.search.translate import Unmapped, append_side_pile, translate


def test_known_conditions_become_the_locked_spec():
    draft = {
        "id": "locked",
        "entry": {"conditions": ["weekly_close > sma_8", "base_or_breakout", "above_long_averages"]},
        "exit": {"conditions": ["weekly_close < sma_16", "down_week 0.10"]},
    }
    assert translate(draft) == locked_crashgate()


def test_seven_week_average_and_rsi_become_indicator_specs():
    average = translate({"conditions": ["weekly_close > sma_7"]})
    assert average.mode == "indicator"
    assert average.conditions[0].left == "close"
    assert average.conditions[0].right_series == "sma"
    assert average.conditions[0].right_args == (7,)
    rsi = translate({"conditions": ["rsi_21 < 25"]})
    assert rsi.mode == "indicator"
    assert rsi.conditions[0].left == "rsi"
    assert rsi.conditions[0].args == (21,)
    assert rsi.conditions[0].op == "<"
    assert rsi.conditions[0].right_value == 25
    assert translate({"conditions": ["price > sma_50", "sma_50 > sma_200"]}).mode == "indicator"
    assert translate({"conditions": ["weekly_close > sma_8"]}).mode == "indicator"


def test_bad_indicator_phrases_are_not_translated():
    for phrase in ("rsi_1 < 25", "rsi_14 < 120", "close > sma_50 > sma_200"):
        with pytest.raises(Unmapped) as caught:
            translate({"conditions": [phrase]})
        assert caught.value.phrase == phrase
    with pytest.raises(Unmapped) as mixed:
        translate({"conditions": ["rsi_14 < 30", "down_week 0.10"]})
    assert mixed.value.phrase == "down_week 0.10"


def test_funding_is_unmapped_and_adds_one_side_pile_line(tmp_path):
    draft = {"id": "fund", "conditions": ["funding"]}
    with pytest.raises(Unmapped) as caught:
        translate(draft)
    assert caught.value.phrase == "funding"
    path = tmp_path / "side_pile.jsonl"
    assert append_side_pile(path, draft_id="fund", phrase=caught.value.phrase) == 1
    line = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert line == {"draft_id": "fund", "phrase": "funding"}
    assert append_side_pile(path, draft_id="fund", phrase="funding") == 2
