"""Old flat modules must be gone from live code, tests, and research notes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = (
    "from price_forecast.weekly_regime import",
    "from price_forecast.sma8_16_kpis import",
    "from price_forecast.series import",
    "from price_forecast.harness import",
    "from price_forecast.predictors import",
    "from price_forecast.chronos import",
    "from price_forecast.bakeoff import",
    "from price_forecast.remix import",
    "from price_forecast.archive",
    "python -m price_forecast.sma8_16_kpis",
    "python -m price_forecast.bakeoff",
    "python -m price_forecast.remix\n",
    "python -m price_forecast.remix ",
)
SCAN_GLOBS = (
    "price_forecast/**/*.py",
    "tests/**/*.py",
    "archive/**/*.py",
    "docs/research/*.md",
    "README.md",
    "pyproject.toml",
)
SKIP_PARTS = {"superpowers"}


def test_forbidden_import_strings_are_gone():
    hits: list[str] = []
    for glob in SCAN_GLOBS:
        for path in ROOT.glob(glob):
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN:
                if needle in text:
                    hits.append(f"{path.relative_to(ROOT)}: {needle}")
    assert hits == []
