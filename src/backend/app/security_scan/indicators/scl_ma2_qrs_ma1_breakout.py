from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

from app.security_scan.indicators import qrs_consist_excess as qrs_module
from app.security_scan.indicators import scl_v4_x5 as scl_module
from app.security_scan.signals import IndicatorSignal

INDICATOR_ID = "scl_ma2_qrs_ma1_breakout"


def _is_nan(value: float) -> bool:
    return value != value


def _to_int_setting(settings: dict[str, Any], key: str, default: int) -> int:
    value = settings.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    return parsed


def _to_float_setting(settings: dict[str, Any], key: str, default: float) -> float:
    value = settings.get(key, default)
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc
    return parsed


def _to_float_list(values: Iterable[float]) -> list[float]:
    out: list[float] = []
    for v in values:
        out.append(float(v) if v is not None else math.nan)
    return out


def _extract_ohlc_series(
    prices: list[dict[str, Any]],
) -> tuple[list[str], list[float], list[float], list[float]]:
    rows: list[tuple[str, float, float, float]] = []
    for row in prices:
        date = row.get("date")
        close = row.get("close")
        high = row.get("high")
        low = row.get("low")
        if not date or close is None or high is None or low is None:
            continue
        rows.append((str(date), float(close), float(high), float(low)))
    rows.sort(key=lambda entry: entry[0])
    dates = [row[0] for row in rows]
    closes = [row[1] for row in rows]
    highs = [row[2] for row in rows]
    lows = [row[3] for row in rows]
    return dates, closes, highs, lows


def _extract_close_series(prices: list[dict[str, Any]]) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for row in prices:
        date = row.get("date")
        close = row.get("close")
        if not date or close is None:
            continue
        rows.append((str(date), float(close)))
    rows.sort(key=lambda entry: entry[0])
    return rows


def _build_close_map(prices: list[dict[str, Any]]) -> dict[str, float]:
    series = _extract_close_series(prices)
    return {date: value for date, value in series}


def _compute_prior_extremes(
    values: Sequence[float],
    index: int,
    lookback: int,
) -> tuple[float, float] | None:
    if lookback <= 0:
        return None
    if index < lookback:
        return None

    window = values[index - lookback : index]
    valid: list[float] = []
    for value in window:
        if value is None:
            return None
        fv = float(value)
        if _is_nan(fv):
            return None
        valid.append(fv)
    if len(valid) != lookback:
        return None
    return max(valid), min(valid)


def _compute_scl_ma2_by_date(
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> dict[str, float]:
    dates, closes, highs, lows = _extract_ohlc_series(prices)
    if not dates:
        return {}

    outputs = scl_module.scl_v4_x5(
        closes,
        highs,
        lows,
        lag1=_to_int_setting(settings, "lag1", 2),
        lag2=_to_int_setting(settings, "lag2", 3),
        lag3=_to_int_setting(settings, "lag3", 4),
        lag4=_to_int_setting(settings, "lag4", 5),
        lag5=_to_int_setting(settings, "lag5", 11),
        cd_offset1=_to_int_setting(settings, "cd_offset1", 2),
        cd_offset2=_to_int_setting(settings, "cd_offset2", 3),
        ma_period1=_to_int_setting(settings, "ma_period1", 5),
        ma_period2=_to_int_setting(settings, "ma_period2", 11),
    )

    ma2_series = outputs.get("MA2", [])
    if len(ma2_series) != len(dates):
        return {}

    values = _to_float_list(ma2_series)
    return {dates[index]: values[index] for index in range(len(dates))}


def _compute_qrs_ma1_by_date(
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> dict[str, float]:
    context = settings.get("_context")
    if not isinstance(context, dict):
        raise ValueError("missing _context for qrs benchmarks")
    benchmark_prices_by_ticker = context.get("benchmark_prices_by_ticker") or {}
    if not isinstance(benchmark_prices_by_ticker, dict) or not benchmark_prices_by_ticker:
        raise ValueError("missing benchmark_prices_by_ticker context")

    benchmark_tickers = settings.get("benchmark_tickers") or context.get(
        "benchmark_tickers"
    )
    if not benchmark_tickers:
        benchmark_tickers = qrs_module.BENCHMARK_TICKERS
    if not isinstance(benchmark_tickers, list) or len(benchmark_tickers) != 3:
        raise ValueError("benchmark_tickers must be a list of 3 tickers")

    ticker_series = _extract_close_series(prices)
    if len(ticker_series) < 3:
        return {}

    bench_maps = {
        ticker: _build_close_map(benchmark_prices_by_ticker.get(ticker, []))
        for ticker in benchmark_tickers
    }
    missing_benchmarks = [ticker for ticker, mapping in bench_maps.items() if not mapping]
    if missing_benchmarks:
        missing_label = ", ".join(missing_benchmarks)
        raise ValueError(f"Missing benchmark prices for: {missing_label}")

    dates: list[str] = []
    close_values: list[float] = []
    bench_values: list[list[float]] = [[] for _ in benchmark_tickers]
    for date, close in ticker_series:
        if any(date not in bench_maps[ticker] for ticker in benchmark_tickers):
            continue
        dates.append(date)
        close_values.append(close)
        for index, ticker in enumerate(benchmark_tickers):
            bench_values[index].append(bench_maps[ticker][date])

    if len(dates) < 3:
        return {}

    outputs = qrs_module.qrs_consist_excess(
        close_values,
        bench_values[0],
        bench_values[1],
        bench_values[2],
        lookback=_to_int_setting(settings, "lookback", 84),
        deadband_period=_to_int_setting(settings, "deadband_period", 20),
        deadband_mult=_to_float_setting(settings, "deadband_mult", 0.25),
        map1=_to_int_setting(settings, "map1", 7),
        map2=_to_int_setting(settings, "map2", 21),
        map3=_to_int_setting(settings, "map3", 56),
        cons_weight=_to_float_setting(settings, "cons_weight", 0.6),
        excess_weight=_to_float_setting(settings, "excess_weight", 0.4),
        ma_shift=_to_int_setting(settings, "ma_shift", 3),
    )

    ma1_series = outputs.get("MA1", [])
    if len(ma1_series) != len(dates):
        return {}

    values = _to_float_list(ma1_series)
    return {dates[index]: values[index] for index in range(len(dates))}


def evaluate(
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[IndicatorSignal]:
    scl_ma2_by_date = _compute_scl_ma2_by_date(prices, settings)
    if not scl_ma2_by_date:
        return []

    qrs_ma1_by_date = _compute_qrs_ma1_by_date(prices, settings)
    if not qrs_ma1_by_date:
        return []

    common_dates = sorted(set(scl_ma2_by_date).intersection(qrs_ma1_by_date))
    if not common_dates:
        return []

    scl_ma2_values = [float(scl_ma2_by_date[date]) for date in common_dates]
    qrs_ma1_values = [float(qrs_ma1_by_date[date]) for date in common_dates]

    scl_lookback = _to_int_setting(settings, "scl_ma2_window", 12)
    qrs_lookback = _to_int_setting(settings, "qrs_ma1_window", 5)

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

        breakout_up = scl_current > scl_prior_high and qrs_current > qrs_prior_high
        breakout_down = scl_current < scl_prior_low and qrs_current < qrs_prior_low

        if breakout_up:
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

        if breakout_down:
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
