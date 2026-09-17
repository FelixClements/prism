"""Predictors share one forecast API. ARIMA+GARCH is the first non-naive model."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from datetime import date
from typing import Protocol, Sequence, TYPE_CHECKING

import numpy as np
from arch import arch_model
from scipy.stats import norm
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

if TYPE_CHECKING:
    from price_forecast.series import PriceSeries


@dataclass(frozen=True)
class Forecast:
    origin: date
    horizon_days: int
    point: float
    lower_80: float | None = None
    upper_80: float | None = None
    lower_90: float | None = None
    upper_90: float | None = None


class Predictor(Protocol):
    def forecast(
        self,
        history: PriceSeries,
        origin: date,
        horizons: Sequence[int],
    ) -> Sequence[Forecast]:
        """Return one price forecast per horizon using only history ≤ origin."""


class LastValuePredictor:
    """Tomorrow's price is today's close, at every horizon."""

    def forecast(
        self,
        history: PriceSeries,
        origin: date,
        horizons: Sequence[int],
    ) -> list[Forecast]:
        last = history.last_close()
        return [
            Forecast(origin=origin, horizon_days=horizon, point=last)
            for horizon in horizons
        ]


class ZeroReturnPredictor:
    """Zero log-return from today's close. Same point as last-value for now."""

    def forecast(
        self,
        history: PriceSeries,
        origin: date,
        horizons: Sequence[int],
    ) -> list[Forecast]:
        last = history.last_close()
        return [
            Forecast(
                origin=origin,
                horizon_days=horizon,
                point=last * math.exp(0.0 * horizon),
            )
            for horizon in horizons
        ]


_Z80 = float(norm.ppf(0.9))
_Z90 = float(norm.ppf(0.95))
_ARIMA_ORDERS: tuple[tuple[int, int, int], ...] = ((1, 0, 1), (1, 0, 0), (0, 0, 0))
_MIN_RETURNS = 30
_PCT = 100.0


class ArimaGarchPredictor:
    """ARIMA on log-returns, invert to price, GARCH/EGARCH bands. History ≤ origin only."""

    def __init__(self) -> None:
        self.last_adf_pvalue: float | None = None

    def forecast(
        self,
        history: PriceSeries,
        origin: date,
        horizons: Sequence[int],
    ) -> list[Forecast]:
        prices = np.array(
            [history.close_at(day) for day in history.dates()], dtype=float
        )
        last = float(prices[-1])
        max_horizon = max(horizons)
        means, variances = self._mean_and_variance(prices, max_horizon)
        cum_mean = np.cumsum(means)
        cum_var = np.cumsum(np.maximum(variances, 0.0))
        forecasts: list[Forecast] = []
        for horizon in horizons:
            mu = float(cum_mean[horizon - 1])
            sd = math.sqrt(float(cum_var[horizon - 1]))
            point = last * math.exp(mu)
            forecasts.append(
                Forecast(
                    origin=origin,
                    horizon_days=horizon,
                    point=point,
                    lower_80=last * math.exp(mu - _Z80 * sd),
                    upper_80=last * math.exp(mu + _Z80 * sd),
                    lower_90=last * math.exp(mu - _Z90 * sd),
                    upper_90=last * math.exp(mu + _Z90 * sd),
                )
            )
        return forecasts

    def _mean_and_variance(
        self, prices: np.ndarray, max_horizon: int
    ) -> tuple[np.ndarray, np.ndarray]:
        if prices.size < 2:
            return np.zeros(max_horizon), np.zeros(max_horizon)
        log_returns = np.diff(np.log(prices))
        self.last_adf_pvalue = _adf_pvalue(log_returns)
        fitted = _arima_mean(log_returns, max_horizon)
        if fitted is None:
            drift = float(np.mean(log_returns)) if log_returns.size else 0.0
            resid = log_returns - drift
            return np.full(max_horizon, drift), _garch_variance(resid, max_horizon)
        means, resid = fitted
        return means, _garch_variance(resid, max_horizon)


def _adf_pvalue(log_returns: np.ndarray) -> float | None:
    if log_returns.size < _MIN_RETURNS:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            result = adfuller(log_returns, autolag="AIC", result_object=True)
            return float(result.pvalue)
        except (TypeError, ValueError, np.linalg.LinAlgError):
            try:
                return float(adfuller(log_returns, autolag="AIC")[1])
            except (ValueError, np.linalg.LinAlgError):
                return None


def _arima_mean(
    log_returns: np.ndarray, max_horizon: int
) -> tuple[np.ndarray, np.ndarray] | None:
    if log_returns.size < _MIN_RETURNS:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for order in _ARIMA_ORDERS:
            try:
                fitted = ARIMA(log_returns, order=order, trend="c").fit()
                forecast = fitted.get_forecast(steps=max_horizon)
                means = np.asarray(forecast.predicted_mean, dtype=float)
                resid = np.asarray(fitted.resid, dtype=float)
                resid = resid[np.isfinite(resid)]
                if (
                    means.size != max_horizon
                    or resid.size < 8
                    or not np.all(np.isfinite(means))
                ):
                    continue
                return means, resid
            except (ValueError, np.linalg.LinAlgError, RuntimeError):
                continue
    return None


def _garch_variance(resid: np.ndarray, max_horizon: int) -> np.ndarray:
    sample = _sample_variance(resid, max_horizon)
    scaled = np.asarray(resid, dtype=float) * _PCT
    if scaled.size < 20 or float(np.std(scaled)) <= 1e-12:
        return sample
    for vol in ("GARCH", "EGARCH"):
        kwargs: dict = {"mean": "Zero", "vol": vol, "p": 1, "q": 1, "rescale": False}
        if vol == "EGARCH":
            kwargs["o"] = 1
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted = arch_model(scaled, **kwargs).fit(
                    disp="off", show_warning=False, options={"maxiter": 200}
                )
                forecast = fitted.forecast(horizon=max_horizon)
                var_pct = np.asarray(forecast.variance, dtype=float)[-1]
                var_log = var_pct / (_PCT ** 2)
                if var_log.size != max_horizon or not np.all(np.isfinite(var_log)):
                    continue
                return np.maximum(var_log, 0.0)
        except (ValueError, RuntimeError, np.linalg.LinAlgError, OverflowError):
            continue
    return sample


def _sample_variance(resid: np.ndarray, max_horizon: int) -> np.ndarray:
    if resid.size < 2:
        return np.zeros(max_horizon)
    sigma2 = float(np.var(resid, ddof=1))
    if not math.isfinite(sigma2) or sigma2 < 0:
        sigma2 = 0.0
    return np.full(max_horizon, sigma2)
