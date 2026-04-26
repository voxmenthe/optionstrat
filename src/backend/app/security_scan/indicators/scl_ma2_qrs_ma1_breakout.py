from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.security_scan.criteria import SeriesPoint
from app.security_scan.indicators import qrs_consist_excess as qrs_module
from app.security_scan.indicators import scl_v4_x5 as scl_module
from app.security_scan.signals import IndicatorSignal

INDICATOR_ID = "scl_ma2_qrs_ma1_breakout"


@dataclass(frozen=True)
class SclMa2QrsMa1BreakoutComputation:
    resolved_settings: dict[str, int | float]
    benchmark_tickers: list[str]
    scl_ma2_series: list[SeriesPoint]
    qrs_ma1_series: list[SeriesPoint]
    signals: list[IndicatorSignal]
    usable_ohlc_points: int
    scl_skipped_price_rows: int
    qrs_aligned_price_points: int
    qrs_dropped_price_points: int
    common_aligned_points: int


def _is_nan(value: float) -> bool:
    return value != value


def _to_int_setting(settings: dict[str, Any], key: str, default: int) -> int:
    value = settings.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc


def _series_value_map(series: Sequence[SeriesPoint]) -> dict[str, float]:
    return {point.date: float(point.value) for point in series}


def _series_points_from_common_dates(
    dates: Sequence[str],
    values_by_date: dict[str, float],
) -> list[SeriesPoint]:
    return [SeriesPoint(date=date, value=float(values_by_date[date])) for date in dates]


def _resolve_benchmark_context(
    settings: dict[str, Any] | None,
) -> tuple[dict[str, list[dict[str, Any]]], Sequence[str] | None]:
    normalized_settings = settings or {}
    context = normalized_settings.get("_context")
    if not isinstance(context, dict):
        raise ValueError("missing _context for qrs benchmarks")

    benchmark_prices_by_ticker = context.get("benchmark_prices_by_ticker") or {}
    if (
        not isinstance(benchmark_prices_by_ticker, dict)
        or not benchmark_prices_by_ticker
    ):
        raise ValueError("missing benchmark_prices_by_ticker context")

    benchmark_tickers = normalized_settings.get("benchmark_tickers")
    if not benchmark_tickers:
        benchmark_tickers = context.get("benchmark_tickers")
    return benchmark_prices_by_ticker, benchmark_tickers


def _compute_prior_extremes(
    values: Sequence[float],
    index: int,
    lookback: int,
) -> tuple[float, float] | None:
    if lookback <= 0 or index < lookback:
        return None

    window = values[index - lookback : index]
    valid: list[float] = []
    for value in window:
        if _is_nan(float(value)):
            return None
        valid.append(float(value))
    if len(valid) != lookback:
        return None
    return max(valid), min(valid)


def _build_dual_breakout_signals(
    scl_ma2_series: Sequence[SeriesPoint],
    qrs_ma1_series: Sequence[SeriesPoint],
    *,
    scl_lookback: int,
    qrs_lookback: int,
) -> list[IndicatorSignal]:
    if len(scl_ma2_series) != len(qrs_ma1_series):
        return []

    common_dates = [point.date for point in scl_ma2_series]
    scl_ma2_values = [float(point.value) for point in scl_ma2_series]
    qrs_ma1_values = [float(point.value) for point in qrs_ma1_series]

    signals: list[IndicatorSignal] = []
    for index, signal_date in enumerate(common_dates):
        scl_extremes = _compute_prior_extremes(scl_ma2_values, index, scl_lookback)
        qrs_extremes = _compute_prior_extremes(qrs_ma1_values, index, qrs_lookback)
        if scl_extremes is None or qrs_extremes is None:
            continue

        scl_prior_high, scl_prior_low = scl_extremes
        qrs_prior_high, qrs_prior_low = qrs_extremes
        scl_current = scl_ma2_values[index]
        qrs_current = qrs_ma1_values[index]

        if scl_current > scl_prior_high and qrs_current > qrs_prior_high:
            signals.append(
                IndicatorSignal(
                    signal_date=signal_date,
                    signal_type="dual_breakout_up",
                    metadata={
                        "label": "scl_ma2_qrs_ma1_dual_breakout_up",
                        "scl_series": "MA2",
                        "scl_lookback": scl_lookback,
                        "scl_current": scl_current,
                        "scl_prior_high": scl_prior_high,
                        "qrs_series": "MA1",
                        "qrs_lookback": qrs_lookback,
                        "qrs_current": qrs_current,
                        "qrs_prior_high": qrs_prior_high,
                    },
                )
            )

        if scl_current < scl_prior_low and qrs_current < qrs_prior_low:
            signals.append(
                IndicatorSignal(
                    signal_date=signal_date,
                    signal_type="dual_breakout_down",
                    metadata={
                        "label": "scl_ma2_qrs_ma1_dual_breakout_down",
                        "scl_series": "MA2",
                        "scl_lookback": scl_lookback,
                        "scl_current": scl_current,
                        "scl_prior_low": scl_prior_low,
                        "qrs_series": "MA1",
                        "qrs_lookback": qrs_lookback,
                        "qrs_current": qrs_current,
                        "qrs_prior_low": qrs_prior_low,
                    },
                )
            )

    return signals


def compute_scl_ma2_qrs_ma1_breakout_computation(
    prices: list[dict[str, Any]],
    settings: dict[str, Any] | None = None,
    *,
    benchmark_prices_by_ticker: dict[str, list[dict[str, Any]]] | None = None,
    benchmark_tickers: Sequence[str] | None = None,
) -> SclMa2QrsMa1BreakoutComputation:
    normalized_settings = settings or {}

    if benchmark_prices_by_ticker is None:
        benchmark_prices_by_ticker, benchmark_tickers = _resolve_benchmark_context(
            normalized_settings
        )

    scl_computation = scl_module.compute_scl_v4_x5_computation(
        prices,
        normalized_settings,
    )
    aligned_inputs = qrs_module.align_qrs_consist_excess_inputs(
        prices=prices,
        benchmark_prices_by_ticker=benchmark_prices_by_ticker,
        benchmark_tickers=benchmark_tickers,
    )
    qrs_computation = qrs_module.compute_qrs_consist_excess_computation(
        aligned_inputs=aligned_inputs,
        settings=normalized_settings,
    )

    resolved_settings: dict[str, int | float] = {
        **scl_computation.resolved_settings,
        **qrs_computation.resolved_settings,
        "scl_ma2_window": _to_int_setting(normalized_settings, "scl_ma2_window", 12),
        "qrs_ma1_window": _to_int_setting(normalized_settings, "qrs_ma1_window", 5),
    }

    if not scl_computation.ma2_series or not qrs_computation.ma1_series:
        return SclMa2QrsMa1BreakoutComputation(
            resolved_settings=resolved_settings,
            benchmark_tickers=list(aligned_inputs.benchmark_tickers),
            scl_ma2_series=[],
            qrs_ma1_series=[],
            signals=[],
            usable_ohlc_points=scl_computation.usable_ohlc_points,
            scl_skipped_price_rows=scl_computation.skipped_price_rows,
            qrs_aligned_price_points=aligned_inputs.aligned_price_points,
            qrs_dropped_price_points=aligned_inputs.dropped_price_points,
            common_aligned_points=0,
        )

    scl_ma2_by_date = _series_value_map(scl_computation.ma2_series)
    qrs_ma1_by_date = _series_value_map(qrs_computation.ma1_series)
    common_dates = sorted(set(scl_ma2_by_date).intersection(qrs_ma1_by_date))
    if not common_dates:
        return SclMa2QrsMa1BreakoutComputation(
            resolved_settings=resolved_settings,
            benchmark_tickers=list(aligned_inputs.benchmark_tickers),
            scl_ma2_series=[],
            qrs_ma1_series=[],
            signals=[],
            usable_ohlc_points=scl_computation.usable_ohlc_points,
            scl_skipped_price_rows=scl_computation.skipped_price_rows,
            qrs_aligned_price_points=aligned_inputs.aligned_price_points,
            qrs_dropped_price_points=aligned_inputs.dropped_price_points,
            common_aligned_points=0,
        )

    scl_ma2_series = _series_points_from_common_dates(common_dates, scl_ma2_by_date)
    qrs_ma1_series = _series_points_from_common_dates(common_dates, qrs_ma1_by_date)

    return SclMa2QrsMa1BreakoutComputation(
        resolved_settings=resolved_settings,
        benchmark_tickers=list(aligned_inputs.benchmark_tickers),
        scl_ma2_series=scl_ma2_series,
        qrs_ma1_series=qrs_ma1_series,
        signals=_build_dual_breakout_signals(
            scl_ma2_series,
            qrs_ma1_series,
            scl_lookback=int(resolved_settings["scl_ma2_window"]),
            qrs_lookback=int(resolved_settings["qrs_ma1_window"]),
        ),
        usable_ohlc_points=scl_computation.usable_ohlc_points,
        scl_skipped_price_rows=scl_computation.skipped_price_rows,
        qrs_aligned_price_points=aligned_inputs.aligned_price_points,
        qrs_dropped_price_points=aligned_inputs.dropped_price_points,
        common_aligned_points=len(common_dates),
    )


def evaluate(
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[IndicatorSignal]:
    benchmark_prices_by_ticker, benchmark_tickers = _resolve_benchmark_context(settings)
    return compute_scl_ma2_qrs_ma1_breakout_computation(
        prices,
        settings,
        benchmark_prices_by_ticker=benchmark_prices_by_ticker,
        benchmark_tickers=benchmark_tickers,
    ).signals


__all__ = [
    "SclMa2QrsMa1BreakoutComputation",
    "compute_scl_ma2_qrs_ma1_breakout_computation",
    "evaluate",
]
