from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


DEFAULT_DISPERSION_WINDOWS = (5, 21, 63)
DEFAULT_WINDOW_WEIGHTS = {5: 0.45, 21: 0.35, 63: 0.20}
DEFAULT_METHOD_WEIGHTS = {
    "corr": 0.40,
    "xs": 0.25,
    "pca": 0.25,
    "sign": 0.10,
}
PRIMARY_COMPONENT_WINDOW = 21
STD_EPSILON = 1e-12


@dataclass(frozen=True)
class DispersionConfig:
    enabled: bool = True
    return_horizons: list[int] = field(default_factory=lambda: [1])
    windows: list[int] = field(default_factory=lambda: [5, 21, 63])
    window_weights: dict[int, float] = field(
        default_factory=lambda: {5: 0.45, 21: 0.35, 63: 0.20}
    )
    method_weights: dict[str, float] = field(
        default_factory=lambda: {
            "corr": 0.40,
            "xs": 0.25,
            "pca": 0.25,
            "sign": 0.10,
        }
    )
    min_tickers: int = 20
    min_observations: int = 15
    min_pair_coverage: float = 0.60
    use_robust_xs_dispersion: bool = True
    xs_lockstep_decay: float = 1.0
    volatility_gate_enabled: bool = False
    volatility_gate_lookback: int = 20
    volatility_gate_percentile: float = 0.60
    segment_up_down: bool = False
    segment_threshold_sigma: float = 0.0
    segment_min_events: int = 8


@dataclass(frozen=True)
class DispersionState:
    ordered_return_dates: list[str]
    returns_by_ticker: dict[str, dict[str, float]]
    universe_ticker_count: int


@dataclass(frozen=True)
class DispersionWindowResult:
    lockstep: float | None
    corr_mean: float | None
    pc1_share: float | None
    sign_consensus: float | None
    xs_mad_z: float | None
    valid_ticker_count: int
    valid_pair_count: int
    observation_count: int
    reliability: float


def build_dispersion_metric_keys(
    windows: Iterable[int] | None = None,
) -> list[str]:
    normalized_windows = _normalize_windows(windows)
    keys = [
        "disp_lockstep_score",
        "disp_dispersion_score",
        "disp_corr_mean_21d",
        "disp_pca_pc1_share_21d",
        "disp_sign_consensus_21d",
        "disp_xs_mad_z_21d",
        "disp_valid_ticker_count",
        "disp_valid_pair_count",
        "disp_observation_count",
    ]
    for window in normalized_windows:
        keys.append(f"disp_lockstep_{window}d")
    for window in normalized_windows:
        keys.append(f"disp_reliability_{window}d")
    return keys


def build_dispersion_state(
    price_series_by_ticker: Mapping[str, Sequence[Mapping[str, Any]]],
    tickers: Iterable[str],
    *,
    return_horizon: int = 1,
) -> DispersionState:
    returns_by_ticker: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()
    universe_ticker_count = 0

    for ticker in _dedupe_tickers(tickers):
        universe_ticker_count += 1
        rows = price_series_by_ticker.get(ticker, [])
        closes = _extract_ordered_close_series(rows)
        returns = _compute_return_series(closes, return_horizon)
        if not returns:
            continue
        returns_map = {date_value: value for date_value, value in returns}
        returns_by_ticker[ticker] = returns_map
        all_dates.update(returns_map.keys())

    return DispersionState(
        ordered_return_dates=sorted(all_dates),
        returns_by_ticker=returns_by_ticker,
        universe_ticker_count=universe_ticker_count,
    )


def compute_dispersion_snapshot(
    state: DispersionState,
    *,
    as_of_date: str,
    config: DispersionConfig,
) -> dict[str, float | int | None]:
    metrics = _empty_dispersion_metrics(config.windows)
    if state.universe_ticker_count <= 0:
        return metrics

    available_dates = [
        date_value
        for date_value in state.ordered_return_dates
        if date_value <= as_of_date
    ]
    if not available_dates:
        return metrics

    window_results: dict[int, DispersionWindowResult] = {}
    for window in _normalize_windows(config.windows):
        window_result = _compute_window_result(
            state,
            available_dates=available_dates,
            window=window,
            config=config,
        )
        window_results[window] = window_result
        metrics[f"disp_lockstep_{window}d"] = (
            _round_to_2dp(window_result.lockstep * 100.0)
            if window_result.lockstep is not None
            else None
        )
        metrics[f"disp_reliability_{window}d"] = _round_to_6dp(
            window_result.reliability
        )

    window_score_numerator = 0.0
    window_score_denominator = 0.0
    for window, result in window_results.items():
        window_weight = config.window_weights.get(window, 0.0)
        if (
            window_weight <= 0.0
            or result.lockstep is None
            or result.reliability <= 0.0
        ):
            continue
        scaled_weight = window_weight * result.reliability
        window_score_numerator += scaled_weight * result.lockstep
        window_score_denominator += scaled_weight

    if window_score_denominator > 0.0:
        lockstep_score = _round_to_2dp(
            (window_score_numerator / window_score_denominator) * 100.0
        )
        metrics["disp_lockstep_score"] = lockstep_score
        metrics["disp_dispersion_score"] = _round_to_2dp(100.0 - lockstep_score)

    component_result = window_results.get(PRIMARY_COMPONENT_WINDOW)
    if component_result is not None:
        metrics["disp_corr_mean_21d"] = _round_to_6dp(component_result.corr_mean)
        metrics["disp_pca_pc1_share_21d"] = _round_to_6dp(component_result.pc1_share)
        metrics["disp_sign_consensus_21d"] = _round_to_6dp(
            component_result.sign_consensus
        )
        metrics["disp_xs_mad_z_21d"] = _round_to_6dp(component_result.xs_mad_z)

    primary_window = (
        PRIMARY_COMPONENT_WINDOW
        if PRIMARY_COMPONENT_WINDOW in window_results
        else _normalize_windows(config.windows)[0]
    )
    primary_result = window_results.get(primary_window)
    if primary_result is not None:
        metrics["disp_valid_ticker_count"] = primary_result.valid_ticker_count
        metrics["disp_valid_pair_count"] = primary_result.valid_pair_count
        metrics["disp_observation_count"] = primary_result.observation_count

    return metrics


def _empty_dispersion_metrics(windows: Iterable[int]) -> dict[str, float | int | None]:
    metrics: dict[str, float | int | None] = {
        "disp_lockstep_score": None,
        "disp_dispersion_score": None,
        "disp_corr_mean_21d": None,
        "disp_pca_pc1_share_21d": None,
        "disp_sign_consensus_21d": None,
        "disp_xs_mad_z_21d": None,
        "disp_valid_ticker_count": None,
        "disp_valid_pair_count": None,
        "disp_observation_count": None,
    }
    for window in _normalize_windows(windows):
        metrics[f"disp_lockstep_{window}d"] = None
        metrics[f"disp_reliability_{window}d"] = None
    return metrics


def _compute_window_result(
    state: DispersionState,
    *,
    available_dates: Sequence[str],
    window: int,
    config: DispersionConfig,
) -> DispersionWindowResult:
    selected_dates = list(available_dates[-window:])
    observation_count = len(selected_dates)
    if observation_count < 2:
        return DispersionWindowResult(
            lockstep=None,
            corr_mean=None,
            pc1_share=None,
            sign_consensus=None,
            xs_mad_z=None,
            valid_ticker_count=0,
            valid_pair_count=0,
            observation_count=observation_count,
            reliability=0.0,
        )

    matrix_columns: list[list[float]] = []
    for returns_by_date in state.returns_by_ticker.values():
        values = []
        missing_data = False
        for date_value in selected_dates:
            value = returns_by_date.get(date_value)
            if value is None or not math.isfinite(value):
                missing_data = True
                break
            values.append(value)
        if missing_data:
            continue
        matrix_columns.append(values)

    if not matrix_columns:
        return DispersionWindowResult(
            lockstep=None,
            corr_mean=None,
            pc1_share=None,
            sign_consensus=None,
            xs_mad_z=None,
            valid_ticker_count=0,
            valid_pair_count=0,
            observation_count=observation_count,
            reliability=0.0,
        )

    returns_matrix = np.asarray(matrix_columns, dtype=float).T
    standardized_matrix = _zscore_columns(returns_matrix)
    valid_ticker_count = int(standardized_matrix.shape[1])
    valid_pair_count = max(0, (valid_ticker_count * (valid_ticker_count - 1)) // 2)
    reliability = _compute_reliability(
        valid_ticker_count=valid_ticker_count,
        valid_pair_count=valid_pair_count,
        observation_count=observation_count,
        universe_ticker_count=state.universe_ticker_count,
        min_tickers=config.min_tickers,
        min_observations=config.min_observations,
        min_pair_coverage=config.min_pair_coverage,
    )
    if standardized_matrix.size == 0 or valid_ticker_count < 2:
        return DispersionWindowResult(
            lockstep=None,
            corr_mean=None,
            pc1_share=None,
            sign_consensus=None,
            xs_mad_z=None,
            valid_ticker_count=valid_ticker_count,
            valid_pair_count=valid_pair_count,
            observation_count=observation_count,
            reliability=reliability,
        )

    corr_mean = _compute_corr_mean(standardized_matrix)
    pc1_share = _compute_pc1_share(standardized_matrix)
    sign_consensus = _compute_sign_consensus(returns_matrix[:, :valid_ticker_count])
    xs_mad_z = _compute_cross_sectional_mad(standardized_matrix)

    lockstep_components = {
        "corr": _normalize_corr(corr_mean),
        "xs": (
            _normalize_cross_sectional_dispersion(
                xs_mad_z,
                decay=max(config.xs_lockstep_decay, 0.0),
            )
            if xs_mad_z is not None
            else None
        ),
        "pca": _clamp(pc1_share, 0.0, 1.0),
        "sign": _clamp(sign_consensus, 0.0, 1.0),
    }
    composite_lockstep = _weighted_mean(lockstep_components, config.method_weights)

    return DispersionWindowResult(
        lockstep=composite_lockstep,
        corr_mean=corr_mean,
        pc1_share=pc1_share,
        sign_consensus=sign_consensus,
        xs_mad_z=xs_mad_z,
        valid_ticker_count=valid_ticker_count,
        valid_pair_count=valid_pair_count,
        observation_count=observation_count,
        reliability=reliability,
    )


def _zscore_columns(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0 or matrix.shape[0] < 2:
        return np.empty((matrix.shape[0], 0))
    column_std = matrix.std(axis=0, ddof=1)
    valid_columns = column_std > STD_EPSILON
    if not np.any(valid_columns):
        return np.empty((matrix.shape[0], 0))
    filtered_matrix = matrix[:, valid_columns]
    filtered_std = column_std[valid_columns]
    filtered_mean = filtered_matrix.mean(axis=0)
    return (filtered_matrix - filtered_mean) / filtered_std


def _compute_corr_mean(standardized_matrix: np.ndarray) -> float | None:
    observations, ticker_count = standardized_matrix.shape
    if observations < 2 or ticker_count < 2:
        return None
    summed_by_row = standardized_matrix.sum(axis=1)
    correlation_sum = float(np.dot(summed_by_row, summed_by_row) / (observations - 1))
    denominator = ticker_count * (ticker_count - 1)
    if denominator <= 0:
        return None
    correlation_mean = (correlation_sum - ticker_count) / denominator
    return _clamp(float(correlation_mean), -1.0, 1.0)


def _compute_pc1_share(standardized_matrix: np.ndarray, max_iters: int = 25) -> float | None:
    observations, ticker_count = standardized_matrix.shape
    if observations < 2 or ticker_count < 2:
        return None
    vector = np.full((ticker_count,), 1.0 / math.sqrt(ticker_count), dtype=float)
    for _ in range(max_iters):
        projected = standardized_matrix @ vector
        covariance_product = (standardized_matrix.T @ projected) / (observations - 1)
        norm_value = float(np.linalg.norm(covariance_product))
        if norm_value <= STD_EPSILON:
            return 0.0
        next_vector = covariance_product / norm_value
        if np.linalg.norm(next_vector - vector) <= 1e-8:
            vector = next_vector
            break
        vector = next_vector
    projected = standardized_matrix @ vector
    covariance_product = (standardized_matrix.T @ projected) / (observations - 1)
    eigenvalue = float(np.dot(vector, covariance_product))
    return _clamp(eigenvalue / ticker_count, 0.0, 1.0)


def _compute_sign_consensus(returns_matrix: np.ndarray) -> float | None:
    if returns_matrix.size == 0:
        return None
    consensus_values: list[float] = []
    for row in returns_matrix:
        positives = int(np.count_nonzero(row > 0))
        negatives = int(np.count_nonzero(row < 0))
        active_count = positives + negatives
        if active_count == 0:
            continue
        up_ratio = positives / active_count
        down_ratio = negatives / active_count
        entropy = 0.0
        if up_ratio > 0.0:
            entropy -= up_ratio * math.log2(up_ratio)
        if down_ratio > 0.0:
            entropy -= down_ratio * math.log2(down_ratio)
        consensus_values.append(1.0 - entropy)
    if not consensus_values:
        return None
    return float(np.median(np.asarray(consensus_values, dtype=float)))


def _compute_cross_sectional_mad(standardized_matrix: np.ndarray) -> float | None:
    if standardized_matrix.size == 0:
        return None
    row_medians = np.median(standardized_matrix, axis=1)
    mad_values = np.median(
        np.abs(standardized_matrix - row_medians[:, np.newaxis]),
        axis=1,
    )
    if mad_values.size == 0:
        return None
    return float(np.median(mad_values))


def _normalize_corr(corr_mean: float | None) -> float | None:
    if corr_mean is None:
        return None
    return _clamp((corr_mean + 1.0) / 2.0, 0.0, 1.0)


def _normalize_cross_sectional_dispersion(
    xs_mad_z: float,
    *,
    decay: float,
) -> float:
    return _clamp(math.exp(-decay * xs_mad_z), 0.0, 1.0)


def _weighted_mean(
    values_by_key: Mapping[str, float | None],
    weights_by_key: Mapping[str, float],
) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for key, value in values_by_key.items():
        if value is None or not math.isfinite(value):
            continue
        weight = float(weights_by_key.get(key, 0.0))
        if weight <= 0.0:
            continue
        numerator += weight * value
        denominator += weight
    if denominator <= 0.0:
        return None
    return _clamp(numerator / denominator, 0.0, 1.0)


def _compute_reliability(
    *,
    valid_ticker_count: int,
    valid_pair_count: int,
    observation_count: int,
    universe_ticker_count: int,
    min_tickers: int,
    min_observations: int,
    min_pair_coverage: float,
) -> float:
    min_ticker_threshold = max(min_tickers, 1)
    min_observation_threshold = max(min_observations, 1)
    ticker_reliability = min(1.0, valid_ticker_count / min_ticker_threshold)
    observation_reliability = min(1.0, observation_count / min_observation_threshold)

    total_possible_pairs = max(
        0,
        (universe_ticker_count * (universe_ticker_count - 1)) // 2,
    )
    if total_possible_pairs == 0 or min_pair_coverage <= 0:
        pair_reliability = 1.0
    else:
        pair_coverage = valid_pair_count / total_possible_pairs
        pair_reliability = min(1.0, pair_coverage / min_pair_coverage)

    return _clamp(
        ticker_reliability * observation_reliability * pair_reliability,
        0.0,
        1.0,
    )


def _compute_return_series(
    close_series: Sequence[tuple[str, float]],
    return_horizon: int,
) -> list[tuple[str, float]]:
    horizon = max(1, int(return_horizon))
    if len(close_series) <= horizon:
        return []
    returns: list[tuple[str, float]] = []
    for index in range(horizon, len(close_series)):
        current_date, current_close = close_series[index]
        prior_close = close_series[index - horizon][1]
        if prior_close == 0:
            continue
        return_value = (current_close / prior_close) - 1.0
        if not math.isfinite(return_value):
            continue
        returns.append((current_date, float(return_value)))
    return returns


def _extract_ordered_close_series(
    price_rows: Sequence[Mapping[str, Any]],
) -> list[tuple[str, float]]:
    parsed_rows: list[tuple[str, float]] = []
    for row in price_rows:
        date_raw = row.get("date")
        close_raw = row.get("close")
        if not isinstance(date_raw, str) or not date_raw:
            continue
        try:
            close_value = float(close_raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(close_value):
            continue
        parsed_rows.append((date_raw, close_value))
    parsed_rows.sort(key=lambda row: row[0])
    return parsed_rows


def _dedupe_tickers(tickers: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for ticker in tickers:
        ticker_value = str(ticker).strip()
        if not ticker_value or ticker_value in seen:
            continue
        seen.add(ticker_value)
        deduped.append(ticker_value)
    return deduped


def _normalize_windows(windows: Iterable[int] | None) -> list[int]:
    raw_windows = list(windows) if windows is not None else list(DEFAULT_DISPERSION_WINDOWS)
    normalized: list[int] = []
    seen: set[int] = set()
    for value in raw_windows:
        try:
            window = int(value)
        except (TypeError, ValueError):
            continue
        if window <= 0 or window in seen:
            continue
        seen.add(window)
        normalized.append(window)
    if not normalized:
        return list(DEFAULT_DISPERSION_WINDOWS)
    normalized.sort()
    return normalized


def _round_to_2dp(value: float) -> float:
    return round(float(value), 2)


def _round_to_6dp(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _clamp(value: float | None, lower: float, upper: float) -> float | None:
    if value is None:
        return None
    return min(upper, max(lower, float(value)))

