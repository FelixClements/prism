"""Dollar SMA-8 vs buy-and-hold. Frozen SMA-8; $10k fresh BTC start per window.

Usage:
    .venv/bin/python -m price_forecast.sma8_10k
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from price_forecast.series import (
    BTC_CLOSE_PRODUCT,
    BTC_CLOSE_SOURCE,
    BTC_CLOSE_TIMEZONE,
    load_daily_closes,
)
from price_forecast.weekly_bakeoff import LONG_RUN_WINDOW, WINDOWS
from price_forecast.weekly_regime import (
    COST_BPS,
    SMA8_LOOKBACK,
    DollarBacktestResult,
    dollar_backtest,
    sma8_first_fill_date,
    sma_signal,
    weekly_closes,
)

STARTING_DOLLARS = 10_000.0


def dollar_window_specs(
    weeks: list[tuple[date, float]],
) -> dict[str, tuple[date, date]]:
    latest = weeks[-1][0]
    specs: dict[str, tuple[date, date]] = {
        "full-after-sma8-warmup": (sma8_first_fill_date(weeks), latest),
    }
    for name, (start, end) in WINDOWS.items():
        specs[name] = (start, end or latest)
    return specs


@dataclass(frozen=True)
class DollarWindowRow:
    window: str
    sma8: DollarBacktestResult
    buy_hold: DollarBacktestResult
    inherited: DollarBacktestResult


def score_dollar_windows(
    weeks: list[tuple[date, float]],
) -> list[DollarWindowRow]:
    specs = dollar_window_specs(weeks)
    hold = [1] * len(weeks)
    sma8 = sma_signal(weeks, lookback=SMA8_LOOKBACK)
    rows = []
    for window, (start, end) in specs.items():
        rows.append(
            DollarWindowRow(
                window=window,
                sma8=dollar_backtest(
                    weeks,
                    sma8,
                    start=start,
                    end=end,
                    starting_dollars=STARTING_DOLLARS,
                ),
                buy_hold=dollar_backtest(
                    weeks,
                    hold,
                    start=start,
                    end=end,
                    starting_dollars=STARTING_DOLLARS,
                ),
                inherited=dollar_backtest(
                    weeks,
                    sma8,
                    start=start,
                    end=end,
                    starting_dollars=STARTING_DOLLARS,
                    inherit_position=True,
                ),
            )
        )
    return rows


def format_report(
    weeks: list[tuple[date, float]],
    rows: list[DollarWindowRow],
    *,
    daily_first: date,
    daily_last: date,
    n_daily: int,
) -> str:
    latest = weeks[-1]
    signals = sma_signal(weeks, lookback=SMA8_LOOKBACK)
    last_signal = signals[-1]
    sma8_now = _sma_at_index(weeks, len(weeks) - 1)
    signal_word = "in BTC" if last_signal == 1 else "in cash"
    full = next(row for row in rows if row.window == "full-after-sma8-warmup")
    held = "in BTC" if full.sma8.end_in_btc else "in cash"
    lines = [
        "# SMA-8 vs buy-and-hold, $10k start",
        "",
        "Not investment advice. This is a backtest of a frozen weekly rule.",
        "",
        "## Exact rules",
        "",
        f"- Starting capital: ${STARTING_DOLLARS:,.0f} converted to 100% BTC at the first fill bar of each window (no fee on that opening buy).",
        "- Each window is its own $10k start. SMA-8 does not inherit a pre-window position.",
        f"- Series: weekly close from daily {BTC_CLOSE_PRODUCT} {BTC_CLOSE_SOURCE} ({BTC_CLOSE_TIMEZONE}).",
        f"- Daily history: {daily_first.isoformat()} to {daily_last.isoformat()} ({n_daily} days).",
        f"- Weeks: UTC Monday–Sunday. Bar date is Sunday. Weekly close = last UTC daily close in that week. Incomplete trailing weeks dropped.",
        f"- Weekly bars: {weeks[0][0].isoformat()} to {weeks[-1][0].isoformat()} ({len(weeks)} weeks).",
        f"- SMA-8: 100% BTC iff weekly close > 8-week SMA (SMA includes this week); else cash. Warmup is {SMA8_LOOKBACK} weeks; first fill bar is week {SMA8_LOOKBACK + 1}.",
        "- Fill: signal at week t close executes at week t+1 close. Cash return = 0.",
        f"- Costs: {COST_BPS} bps of wealth each way on SMA-8 flips. No liquidation cost at window end.",
        "- Buy-and-hold stays in the opening BTC. Window start = last weekly close on or before the calendar start; end = last weekly close on or before the calendar end.",
        "- CAGR uses 365.25 days/year over the Sunday-to-Sunday span.",
        "",
        f"As of {latest[0].isoformat()}: latest SMA-8 signal is **{signal_word}** "
        f"(weekly close ${latest[1]:,.2f} vs SMA-8 ${sma8_now:,.2f}). "
        f"That signal fills at the next weekly close. Filled SMA-8 position on the full-sample window is **{held}**"
        + (
            f"; last flip {full.sma8.last_flip.isoformat()}."
            if full.sma8.last_flip is not None
            else "."
        ),
        "",
        "## Results",
        "",
    ]
    for row in rows:
        lines.extend(_format_window(row))
    lines.extend(
        [
            "## How to re-run",
            "",
            "```",
            ".venv/bin/python -m price_forecast.sma8_10k",
            "```",
            "",
            "Writes `price_forecast/sma8_10k_results.md`. Frozen SMA-8 is `sma_signal(..., lookback=8)` in `price_forecast/weekly_regime.py`.",
            "",
        ]
    )
    return "\n".join(lines)


def _sma_at_index(weeks: list[tuple[date, float]], index: int) -> float:
    closes = [close for _week_end, close in weeks]
    return sum(closes[index + 1 - SMA8_LOOKBACK : index + 1]) / SMA8_LOOKBACK


def _format_window(row: DollarWindowRow) -> list[str]:
    sma8, hold = row.sma8, row.buy_hold
    lines = [
        f"### {row.window}",
        "",
        f"Anchors: {sma8.start.isoformat()} → {sma8.end.isoformat()} "
        f"({sma8.n_intervals} weekly returns). "
        f"Start BTC price ${sma8.start_price:,.2f}; end ${sma8.end_price:,.2f}.",
        "",
        "| | SMA-8 | Buy-and-hold |",
        "| --- | ---: | ---: |",
        f"| Start $ | {_usd(sma8.start_dollars)} | {_usd(hold.start_dollars)} |",
        f"| Start BTC (coins) | {_btc(sma8.start_btc)} | {_btc(hold.start_btc)} |",
        f"| End $ | {_usd(sma8.end_dollars)} | {_usd(hold.end_dollars)} |",
        f"| End holding | {_holding(sma8)} | {_holding(hold)} |",
        f"| Max drawdown $ | {_usd(sma8.max_drawdown_dollars)} | {_usd(hold.max_drawdown_dollars)} |",
        f"| Max drawdown % | {_pct(sma8.max_drawdown)} | {_pct(hold.max_drawdown)} |",
        f"| Total return | {_pct(sma8.total_return)} | {_pct(hold.total_return)} |",
        f"| CAGR | {_cagr(sma8)} | {_cagr(hold)} |",
        f"| Time in BTC | {_pct(sma8.time_in_btc)} | {_pct(hold.time_in_btc)} |",
        f"| Round trips | {sma8.round_trips} | {hold.round_trips} |",
        f"| Flips | {sma8.flips} | {hold.flips} |",
        f"| Est. fees paid | {_usd(sma8.fees_paid)} | {_usd(hold.fees_paid)} |",
        f"| Last flip | {_date(sma8.last_flip)} | {_date(hold.last_flip)} |",
        f"| Window-end filled position | {_side(sma8.end_in_btc)} | {_side(hold.end_in_btc)} |",
        f"| Latest signal (fills next week) | {_signal(sma8.last_signal)} | {_signal(hold.last_signal)} |",
        "",
        _inherit_note(row),
        "",
    ]
    return lines


def _inherit_note(row: DollarWindowRow) -> str:
    inherited, fresh = row.inherited, row.sma8
    inherited_side = "BTC" if inherited.start_btc > 0 else "cash"
    if abs(inherited.end_dollars - fresh.end_dollars) < 0.005:
        return (
            f"Inherited-position bakeoff (scaled to $10k of starting wealth): "
            f"{_usd(inherited.end_dollars)} end, max DD {_pct(inherited.max_drawdown)}. "
            f"Same path as this fresh $10k BTC buy (already in {inherited_side} at the first fill bar)."
        )
    return (
        f"Inherited-position bakeoff (scaled to $10k of starting wealth, started in {inherited_side}): "
        f"SMA-8 ends {_usd(inherited.end_dollars)}, max DD {_pct(inherited.max_drawdown)} / "
        f"{_usd(inherited.max_drawdown_dollars)}. "
        f"This report's fresh $10k BTC buy ends {_usd(fresh.end_dollars)}, max DD {_pct(fresh.max_drawdown)} / "
        f"{_usd(fresh.max_drawdown_dollars)}. "
        "The existing weekly bakeoff inherits the pre-window fill; this run does not."
    )


def _usd(value: float) -> str:
    return f"${value:,.2f}"


def _btc(value: float) -> str:
    return f"{value:.8f}"


def _pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def _cagr(result: DollarBacktestResult) -> str:
    if result.cagr is None:
        return "n/a"
    return _pct(result.cagr)


def _holding(result: DollarBacktestResult) -> str:
    if result.end_in_btc:
        assert result.end_btc is not None
        return f"{_btc(result.end_btc)} BTC"
    assert result.end_cash is not None
    return f"{_usd(result.end_cash)} cash"


def _side(in_btc: bool) -> str:
    return "BTC" if in_btc else "cash"


def _signal(value: int | None) -> str:
    if value == 1:
        return "BTC"
    if value == 0:
        return "cash"
    return "undefined"


def _date(day: date | None) -> str:
    return "—" if day is None else day.isoformat()


def main() -> None:
    daily = load_daily_closes(
        source="coinbase",
        start=date(2018, 1, 1),
        end=datetime.now(timezone.utc).date(),
    )
    weeks = weekly_closes(daily)
    rows = score_dollar_windows(weeks)
    report = format_report(
        weeks,
        rows,
        daily_first=daily.dates()[0],
        daily_last=daily.dates()[-1],
        n_daily=len(daily.dates()),
    )
    out_path = Path(__file__).with_name("sma8_10k_results.md")
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
