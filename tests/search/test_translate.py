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
