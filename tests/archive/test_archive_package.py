"""Frozen t+1 bakeoff stays importable and collected after the move."""

from pathlib import Path


def test_archive_is_not_inside_price_forecast():
    root = Path(__file__).resolve().parents[2]
    assert not (root / "price_forecast/archive").exists()
    assert (root / "archive/frozen_t1_bakeoff/weekly_bakeoff.py").is_file()


def test_frozen_weekly_bakeoff_imports():
    from archive.frozen_t1_bakeoff.weekly_bakeoff import WINDOWS

    assert WINDOWS
