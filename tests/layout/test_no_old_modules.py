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
    "import price_forecast.weekly_regime",
    "import price_forecast.sma8_16_kpis",
    "import price_forecast.series",
    "import price_forecast.harness",
    "import price_forecast.predictors",
    "import price_forecast.chronos",
    "import price_forecast.bakeoff",
    "python -m price_forecast.sma8_16_kpis",
    "python -m price_forecast.bakeoff",
    "python -m price_forecast.remix\n",
    "python -m price_forecast.remix ",
    "python -m price_forecast.archive",
    "python3 -m price_forecast.sma8_16_kpis",
    "python3 -m price_forecast.bakeoff",
    "python3 -m price_forecast.remix\n",
    "python3 -m price_forecast.remix ",
    "python3 -m price_forecast.archive",
)
SCAN_GLOBS = (
    "price_forecast/**/*.py",
    "tests/**/*.py",
    "archive/**/*.py",
    "archive/**/*.md",
    "docs/research/*.md",
    "docs/*.md",
    "results/*.md",
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


def test_test_packages_have_init():
    tests_root = ROOT / "tests"
    missing: list[str] = []
    for path in tests_root.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        for parent in path.parents:
            if parent == tests_root:
                break
            if not (parent / "__init__.py").is_file():
                rel = str(parent.relative_to(ROOT))
                if rel not in missing:
                    missing.append(rel)
    assert missing == []
