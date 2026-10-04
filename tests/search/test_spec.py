import pytest

from price_forecast.search.spec import locked_crashgate, spec_from_mapping, spec_to_mapping


def test_locked_rule_fields():
    spec = locked_crashgate()
    assert spec.mode == "threshold"
    assert spec.close_above_sma_weeks == 8
    assert spec.base_or_breakout is True
    assert spec.above_long_averages is True
    assert spec.close_below_sma_weeks == 16
    assert spec.down_week == pytest.approx(0.10)
    assert spec_to_mapping(spec).keys().isdisjoint({"cost", "fill", "starting_dollars"})


def test_round_trip():
    spec = locked_crashgate()
    assert spec_from_mapping(spec_to_mapping(spec)) == spec


def test_unknown_field_is_rejected():
    data = spec_to_mapping(locked_crashgate())
    data["funding"] = "negative"
    with pytest.raises(ValueError, match="funding"):
        spec_from_mapping(data)


def test_unknown_number_is_rejected():
    data = spec_to_mapping(locked_crashgate())
    data["close_above_sma_weeks"] = 7
    with pytest.raises(ValueError, match="close_above_sma_weeks"):
        spec_from_mapping(data)


def test_down_week_without_an_average_is_rejected():
    with pytest.raises(ValueError, match="down_week"):
        spec_from_mapping(
            {
                "mode": "threshold",
                "close_above_sma_weeks": None,
                "base_or_breakout": True,
                "above_long_averages": False,
                "close_below_sma_weeks": None,
                "down_week": 0.10,
            }
        )


def test_threshold_needs_an_entry_and_an_exit():
    with pytest.raises(ValueError, match="entry"):
        spec_from_mapping(
            {
                "mode": "threshold",
                "close_above_sma_weeks": None,
                "base_or_breakout": False,
                "above_long_averages": False,
                "close_below_sma_weeks": 16,
                "down_week": None,
            }
        )
