"""Univariate Chronos-2 predictor. History ≤ origin only; no extra features."""

from __future__ import annotations

from datetime import date
from typing import Sequence, TYPE_CHECKING

import numpy as np

from price_forecast.predictors import Forecast

if TYPE_CHECKING:
    from price_forecast.series import PriceSeries

CHRONOS_CHECKPOINT = "amazon/chronos-2"
_QUANTILE_LEVELS: tuple[float, ...] = (0.05, 0.1, 0.5, 0.9, 0.95)


class ChronosPredictor:
    """Zero-shot Chronos-2 on the univariate close series."""

    def __init__(self, pipeline=None, *, device_map: str | None = None) -> None:
        self.checkpoint = CHRONOS_CHECKPOINT
        self._pipeline = pipeline
        self.device_map = device_map
        if pipeline is not None and device_map is None:
            self.device_map = "injected"

    def forecast(
        self,
        history: PriceSeries,
        origin: date,
        horizons: Sequence[int],
    ) -> list[Forecast]:
        prices = np.array(
            [history.close_at(day) for day in history.dates()], dtype=float
        )
        max_horizon = max(horizons)
        pipeline = self._ensure_pipeline()
        context = _context_window(prices, pipeline)
        quantiles, _mean = pipeline.predict_quantiles(
            context.reshape(1, 1, -1),
            prediction_length=max_horizon,
            quantile_levels=list(_QUANTILE_LEVELS),
        )
        q = _quantile_paths(quantiles, max_horizon, len(_QUANTILE_LEVELS))
        by_level = {
            level: q[:, i] for i, level in enumerate(_QUANTILE_LEVELS)
        }
        median = by_level[0.5]
        forecasts: list[Forecast] = []
        for horizon in horizons:
            step = horizon - 1
            forecasts.append(
                Forecast(
                    origin=origin,
                    horizon_days=horizon,
                    point=float(median[step]),
                    lower_80=float(by_level[0.1][step]),
                    upper_80=float(by_level[0.9][step]),
                    lower_90=float(by_level[0.05][step]),
                    upper_90=float(by_level[0.95][step]),
                )
            )
        return forecasts

    def _ensure_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        self.device_map = self.device_map or detect_device_map()
        self._pipeline = load_chronos_pipeline(
            self.checkpoint, device_map=self.device_map
        )
        return self._pipeline


def detect_device_map() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def load_chronos_pipeline(checkpoint: str, device_map: str):
    try:
        from chronos import BaseChronosPipeline
    except ImportError as exc:
        raise ImportError(
            "chronos-forecasting is required for ChronosPredictor; "
            "install with: pip install 'chronos-forecasting>=2.2'"
        ) from exc
    return BaseChronosPipeline.from_pretrained(checkpoint, device_map=device_map)


def _context_window(prices: np.ndarray, pipeline) -> np.ndarray:
    max_len = getattr(pipeline, "model_context_length", None)
    if max_len is None:
        return prices
    max_len = int(max_len)
    if max_len <= 0 or prices.size <= max_len:
        return prices
    return prices[-max_len:]


def _quantile_paths(quantiles, prediction_length: int, n_levels: int) -> np.ndarray:
    q = _to_numpy(quantiles)
    if q.ndim == 3:
        q = q[0]
    elif q.ndim == 4:
        q = q[0, 0]
    if q.ndim != 2:
        raise ValueError(f"unexpected Chronos quantile shape {q.shape}")
    if q.shape == (prediction_length, n_levels):
        return q
    if q.shape == (n_levels, prediction_length):
        return q.T
    raise ValueError(f"unexpected Chronos quantile shape {q.shape}")


def _to_numpy(value) -> np.ndarray:
    if isinstance(value, (list, tuple)):
        value = value[0]
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value, dtype=float)
