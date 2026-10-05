from __future__ import annotations

import math
from dataclasses import dataclass

from price_forecast.backtest.engine import EquityPath
from price_forecast.backtest.kpis import max_drawdown, profit_factor


@dataclass(frozen=True)
class PathMetrics:
    total_return: float
    edge: float
    sharpe: float | None
    max_drawdown: float
    win_rate: float | None
    profit_factor: float | None
    round_trips: int
    end_dollars: float
    start_dollars: float
    trip_pnls: tuple[float, ...]
    hodl_return: float


def hodl_return(first_price: float, last_price: float, cost: float) -> float:
    return (1.0 - cost) * (last_price / first_price) - 1.0


def _sharpe(equity: list[float]) -> float | None:
    returns = [
        equity[i] / equity[i - 1] - 1.0
        for i in range(1, len(equity))
        if equity[i - 1] > 0.0
    ]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    if var == 0.0:
        return None
    return (mean / math.sqrt(var)) * math.sqrt(52.0)


def metrics_from_path(
    path: EquityPath, *, first_price: float, last_price: float, cost: float
) -> PathMetrics:
    total = path.end_dollars / path.start_dollars - 1.0
    hold = hodl_return(first_price, last_price, cost)
    wins = sum(1 for value in path.completed_pnls if value > 0.0)
    rate = (wins / len(path.completed_pnls)) if path.completed_pnls else None
    factor = profit_factor(path.completed_pnls)
    if factor is not None and not math.isfinite(factor):
        factor = None
    return PathMetrics(
        total_return=total,
        edge=total - hold,
        sharpe=_sharpe(list(path.equity)),
        max_drawdown=max_drawdown(path.equity),
        win_rate=rate,
        profit_factor=factor,
        round_trips=path.completed_round_trips,
        end_dollars=path.end_dollars,
        start_dollars=path.start_dollars,
        trip_pnls=tuple(path.completed_pnls),
        hodl_return=hold,
    )


def _clip(value: float) -> float:
    return min(3.0, max(0.0, value))


def breeding_number(child: PathMetrics, baseline: PathMetrics) -> float:
    drawdown = 3.0 if child.max_drawdown == 0.0 else abs(baseline.max_drawdown) / abs(child.max_drawdown)
    parts = [
        child.total_return / baseline.total_return,
        child.sharpe / baseline.sharpe,
        drawdown,
        child.win_rate / baseline.win_rate,
        child.profit_factor / baseline.profit_factor,
    ]
    return sum(_clip(part) for part in parts)


def baseline_is_usable(baseline: PathMetrics) -> bool:
    values = [
        baseline.total_return,
        baseline.sharpe,
        abs(baseline.max_drawdown),
        baseline.win_rate,
        baseline.profit_factor,
    ]
    return all(value is not None and math.isfinite(value) and value != 0.0 for value in values)


def is_fragile(metrics: PathMetrics) -> bool:
    if metrics.end_dollars - metrics.start_dollars <= 0.0 or metrics.edge <= 0.0:
        return False
    for pnl in metrics.trip_pnls:
        end = metrics.end_dollars - pnl
        total = end / metrics.start_dollars - 1.0
        edge = total - metrics.hodl_return
        if edge <= 0.5 * metrics.edge or edge <= 0.0:
            return True
    return False


def stress_result(
    coinbase_edge: float,
    remix_edges: list[float],
    synthetic_edges: list[float],
    *,
    require_remix: bool = True,
) -> tuple[bool, float | None, float]:
    synthetic_mean = sum(synthetic_edges) / len(synthetic_edges)
    if not require_remix:
        passed = coinbase_edge > 0.0 and synthetic_mean >= 0.5 * coinbase_edge
        return passed, None, synthetic_mean
    remix_mean = sum(remix_edges) / len(remix_edges)
    passed = coinbase_edge > 0.0 and remix_mean >= 0.5 * coinbase_edge and synthetic_mean >= 0.5 * coinbase_edge
    return passed, remix_mean, synthetic_mean


def skill_warnings(metrics: PathMetrics, *, evaluate, review) -> dict:
    wins = [value for value in metrics.trip_pnls if value > 0.0]
    losses = [value for value in metrics.trip_pnls if value < 0.0]
    avg_win = (sum(wins) / len(wins) / metrics.start_dollars * 100.0) if wins else 0.0
    avg_loss = (sum(abs(value) for value in losses) / len(losses) / metrics.start_dollars * 100.0) if losses else 0.0
    rate = 0.0 if metrics.win_rate is None else metrics.win_rate * 100.0
    result = evaluate(
        total_trades=metrics.round_trips,
        win_rate=rate,
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        max_drawdown_pct=abs(metrics.max_drawdown) * 100.0,
        years_tested=1,
        num_parameters=1,
        slippage_tested=True,
    )
    reviewed = review(
        {
            "id": "search",
            "thesis": "Weekly Bitcoin close versus a moving average.",
            "regime": "Neutral",
            "entry": {"conditions": ["weekly_close > sma_8"]},
            "exit": {"stop_loss_pct": 0.08, "take_profit_rr": 1.5},
            "risk": {"risk_per_trade": 0.01, "max_positions": 1},
        }
    )
    warning = None
    for finding in reviewed.findings:
        if finding.criterion == "C3_sample_adequacy" and finding.severity != "pass":
            warning = finding.reason
    return {
        "backtest_expert_verdict": result["verdict"],
        "small_sample": any(flag["id"] == "small_sample" for flag in result["red_flags"]),
        "reviewer_verdict": reviewed.verdict,
        "reviewer_sample_warning": warning,
    }
