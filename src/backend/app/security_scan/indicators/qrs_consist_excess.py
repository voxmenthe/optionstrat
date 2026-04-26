from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from app.security_scan.criteria import SeriesPoint
from app.security_scan.signals import IndicatorSignal

INDICATOR_ID = "qrs_consist_excess"

BENCHMARK_TICKERS = ["SPY", "QQQ", "IWM"]


@dataclass(frozen=True)
class QrsConsistExcessAlignedInputs:
    benchmark_tickers: list[str]
    dates: list[str]
    close_values: list[float]
    benchmark_close_values: list[list[float]]
    source_price_points: int
    aligned_price_points: int
    dropped_price_points: int


@dataclass(frozen=True)
class QrsConsistExcessComputation:
    resolved_settings: dict[str, int | float]
    main_series: list[SeriesPoint]
    ma1_series: list[SeriesPoint]
    ma2_series: list[SeriesPoint]
    ma3_series: list[SeriesPoint]
    signals: list[IndicatorSignal]


def _is_nan(value: float) -> bool:
    return value != value


def _to_float_list(values: Sequence[float]) -> List[float]:
    out: List[float] = []
    for v in values:
        out.append(float(v) if v is not None else math.nan)
    return out


def _pct_change(series: Sequence[float]) -> List[float]:
    n = len(series)
    out = [0.0] * n
    for i in range(n):
        j = i - 1
        if j >= 0:
            cur = series[i]
            prev = series[j]
            if not _is_nan(cur) and not _is_nan(prev) and prev != 0:
                out[i] = (cur / prev - 1.0) * 100.0
    return out


def _rolling_sum(series: Sequence[float], period: int) -> List[float]:
    n = len(series)
    out = [0.0] * n
    if period <= 0:
        return out

    window: List[float] = []
    window_sum = 0.0

    for i, val in enumerate(series):
        v = 0.0 if _is_nan(val) else float(val)
        window.append(v)
        window_sum += v
        if len(window) > period:
            window_sum -= window.pop(0)
        out[i] = window_sum
    return out


def _rolling_std(series: Sequence[float], period: int) -> List[float]:
    n = len(series)
    out = [0.0] * n
    if period <= 0:
        return out

    window: List[float] = []
    for i, val in enumerate(series):
        window.append(val)
        if len(window) > period:
            window.pop(0)

        valid = [v for v in window if not _is_nan(v)]
        count = len(valid)
        if count <= 1:
            out[i] = 0.0
        else:
            mean = sum(valid) / count
            var = sum((v - mean) ** 2 for v in valid) / count
            out[i] = math.sqrt(var)
    return out


def _sma(series: Sequence[float], period: int) -> List[float]:
    n = len(series)
    out = [math.nan] * n
    if period <= 0:
        return out

    window: List[float] = []
    window_sum = 0.0
    window_count = 0

    for i, val in enumerate(series):
        window.append(val)
        if not _is_nan(val):
            window_sum += val
            window_count += 1

        if len(window) > period:
            removed = window.pop(0)
            if not _is_nan(removed):
                window_sum -= removed
                window_count -= 1

        if window_count > 0:
            out[i] = window_sum / window_count
        else:
            out[i] = 0.0

    return out


def _ref(series: Sequence[float], period: int) -> List[float]:
    n = len(series)
    out = [math.nan] * n
    for i in range(n):
        j = i + period
        if 0 <= j < n:
            out[i] = series[j]
    return out


def _nan_to_zero(series: Sequence[float]) -> List[float]:
    out: List[float] = []
    for v in series:
        if v is None or _is_nan(float(v)):
            out.append(0.0)
        else:
            out.append(float(v))
    return out


def _safe_max(value: float, floor: float) -> float:
    if value is None or _is_nan(value):
        return floor
    return value if value > floor else floor


def _avg_available(values: Sequence[float]) -> float:
    valid = [v for v in values if not _is_nan(v)]
    if not valid:
        return 0.0
    return sum(valid) / len(valid)


def qrs_consist_excess(
    close: Sequence[float],
    spy_close: Sequence[float],
    qqq_close: Sequence[float],
    iwm_close: Sequence[float],
    lookback: int = 84,
    deadband_period: int = 20,
    deadband_mult: float = 0.25,
    map1: int = 7,
    map2: int = 21,
    map3: int = 56,
    cons_weight: float = 0.6,
    excess_weight: float = 0.4,
    ma_shift: int = 3,
) -> Dict[str, List[float]]:
    close_list = _to_float_list(close)
    spy_list = _to_float_list(spy_close)
    qqq_list = _to_float_list(qqq_close)
    iwm_list = _to_float_list(iwm_close)

    stock_ret = _pct_change(close_list)
    spy_ret = _pct_change(spy_list)
    qqq_ret = _pct_change(qqq_list)
    iwm_ret = _pct_change(iwm_list)

    n = len(close_list)
    bench_ret = [
        _avg_available([spy_ret[i], qqq_ret[i], iwm_ret[i]]) for i in range(n)
    ]

    bench_ret_std = _rolling_std(bench_ret, deadband_period)
    deadband = [bench_ret_std[i] * deadband_mult for i in range(n)]

    up_day = [1.0 if bench_ret[i] > deadband[i] else 0.0 for i in range(n)]
    down_day = [1.0 if bench_ret[i] < -deadband[i] else 0.0 for i in range(n)]

    excess_ret = [stock_ret[i] - bench_ret[i] for i in range(n)]

    up_day_count = _rolling_sum(up_day, lookback)
    down_day_count = _rolling_sum(down_day, lookback)
    active_day = [1.0 if (up_day[i] > 0.0 or down_day[i] > 0.0) else 0.0 for i in range(n)]
    active_day_count = _rolling_sum(active_day, lookback)

    day_score: List[float] = []
    for i in range(n):
        if active_day[i] > 0.0:
            if not _is_nan(stock_ret[i]) and not _is_nan(bench_ret[i]) and stock_ret[i] > bench_ret[i]:
                day_score.append(1.0)
            else:
                day_score.append(-1.0)
        else:
            day_score.append(0.0)

    consistency = [
        (day_score_sum / _safe_max(active_day_count[i], 1.0))
        for i, day_score_sum in enumerate(_rolling_sum(day_score, lookback))
    ]

    up_excess_sum = _rolling_sum(
        [excess_ret[i] if up_day[i] > 0.0 else 0.0 for i in range(n)],
        lookback,
    )
    down_excess_sum = _rolling_sum(
        [excess_ret[i] if down_day[i] > 0.0 else 0.0 for i in range(n)],
        lookback,
    )

    up_excess_avg = [up_excess_sum[i] / _safe_max(up_day_count[i], 1.0) for i in range(n)]
    down_excess_avg = [down_excess_sum[i] / _safe_max(down_day_count[i], 1.0) for i in range(n)]
    raw_excess = [up_excess_avg[i] + down_excess_avg[i] for i in range(n)]

    excess_std = _rolling_std(excess_ret, lookback)
    excess_norm = [
        raw_excess[i] / _safe_max(excess_std[i], 0.1)
        for i in range(n)
    ]

    combined = [
        (consistency[i] * cons_weight) + (excess_norm[i] * excess_weight)
        for i in range(n)
    ]

    # v2 logic: soft confidence weighting to reduce long all-zero plateaus.
    min_active_days = lookback * 0.4
    min_active_days_floor = max(min_active_days, 1.0)
    sample_conf = [
        min(active_day_count[i] / min_active_days_floor, 1.0) for i in range(n)
    ]

    min_dir_days = lookback * 0.2
    balance_floor = max(min_dir_days, 1.0)
    balance_conf = [
        (min(up_day_count[i], down_day_count[i]) + balance_floor)
        / (max(up_day_count[i], down_day_count[i]) + balance_floor)
        for i in range(n)
    ]

    align_penalty = 0.25
    align_conf = [
        1.0 if (raw_excess[i] * consistency[i]) >= 0.0 else align_penalty
        for i in range(n)
    ]

    confidence = [
        sample_conf[i] * balance_conf[i] * align_conf[i] for i in range(n)
    ]
    quiet_score = [combined[i] * confidence[i] for i in range(n)]

    ma1 = _ref(_sma(quiet_score, map1), -ma_shift)
    ma2 = _ref(_sma(quiet_score, map2), -ma_shift)
    ma3 = _ref(_sma(quiet_score, map3), -ma_shift)

    return {
        "QRSConsistExcess": _nan_to_zero(quiet_score),
        "QRSConsistExcessV2": _nan_to_zero(quiet_score),
        "CrossoverLine": [0.0] * n,
        "MA1": _nan_to_zero(ma1),
        "MA2": _nan_to_zero(ma2),
        "MA3": _nan_to_zero(ma3),
    }


def _extract_close_series(prices: list[dict[str, Any]]) -> list[tuple[str, float]]:
    points: list[tuple[str, float]] = []
    for row in prices:
        date = row.get("date")
        close = row.get("close")
        if not date or close is None:
            continue
        points.append((str(date), float(close)))
    points.sort(key=lambda point: point[0])
    return points


def _build_benchmark_map(
    benchmark_prices_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
) -> dict[str, float]:
    prices = benchmark_prices_by_ticker.get(ticker, [])
    series = _extract_close_series(prices)
    return {date: value for date, value in series}


def _to_int_setting(settings: dict[str, Any], key: str, default: int) -> int:
    value = settings.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc


def _to_float_setting(settings: dict[str, Any], key: str, default: float) -> float:
    value = settings.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc


def _resolve_benchmark_tickers(benchmark_tickers: Any) -> list[str]:
    if benchmark_tickers is None:
        return list(BENCHMARK_TICKERS)
    if not isinstance(benchmark_tickers, list):
        raise ValueError("benchmark_tickers must be a list of 3 tickers")

    normalized: list[str] = []
    for value in benchmark_tickers:
        if not isinstance(value, str):
            raise ValueError("benchmark_tickers must be a list of 3 tickers")
        ticker = value.strip().upper()
        if not ticker:
            raise ValueError("benchmark_tickers must be a list of 3 tickers")
        normalized.append(ticker)

    if len(normalized) != 3:
        raise ValueError("benchmark_tickers must be a list of 3 tickers")
    return normalized


def _resolve_settings(settings: dict[str, Any] | None) -> dict[str, int | float]:
    normalized = settings or {}
    return {
        "lookback": _to_int_setting(normalized, "lookback", 84),
        "deadband_period": _to_int_setting(
            normalized, "deadband_period", 20
        ),
        "deadband_mult": _to_float_setting(normalized, "deadband_mult", 0.25),
        "map1": _to_int_setting(normalized, "map1", 7),
        "map2": _to_int_setting(normalized, "map2", 21),
        "map3": _to_int_setting(normalized, "map3", 56),
        "cons_weight": _to_float_setting(normalized, "cons_weight", 0.6),
        "excess_weight": _to_float_setting(normalized, "excess_weight", 0.4),
        "ma_shift": _to_int_setting(normalized, "ma_shift", 3),
    }


def _series_points_from_values(
    dates: Sequence[str],
    values: Sequence[float],
) -> list[SeriesPoint]:
    if len(dates) != len(values):
        return []
    return [
        SeriesPoint(date=dates[index], value=float(value))
        for index, value in enumerate(values)
    ]


def align_qrs_consist_excess_inputs(
    prices: list[dict[str, Any]],
    benchmark_prices_by_ticker: dict[str, list[dict[str, Any]]],
    benchmark_tickers: Sequence[str] | None = None,
) -> QrsConsistExcessAlignedInputs:
    resolved_benchmark_tickers = _resolve_benchmark_tickers(
        list(benchmark_tickers) if benchmark_tickers is not None else None
    )
    ticker_series = _extract_close_series(prices)

    bench_maps = {
        ticker: _build_benchmark_map(benchmark_prices_by_ticker, ticker)
        for ticker in resolved_benchmark_tickers
    }
    missing_benchmarks = [
        ticker for ticker, mapping in bench_maps.items() if not mapping
    ]
    if missing_benchmarks:
        missing_label = ", ".join(missing_benchmarks)
        raise ValueError(f"Missing benchmark prices for: {missing_label}")

    dates: list[str] = []
    close_values: list[float] = []
    benchmark_close_values = [[] for _ in resolved_benchmark_tickers]
    for date, close in ticker_series:
        if any(date not in bench_maps[ticker] for ticker in resolved_benchmark_tickers):
            continue
        dates.append(date)
        close_values.append(close)
        for index, ticker in enumerate(resolved_benchmark_tickers):
            benchmark_close_values[index].append(bench_maps[ticker][date])

    source_price_points = len(ticker_series)
    aligned_price_points = len(dates)
    return QrsConsistExcessAlignedInputs(
        benchmark_tickers=resolved_benchmark_tickers,
        dates=dates,
        close_values=close_values,
        benchmark_close_values=benchmark_close_values,
        source_price_points=source_price_points,
        aligned_price_points=aligned_price_points,
        dropped_price_points=max(0, source_price_points - aligned_price_points),
    )


def compute_qrs_consist_excess_computation(
    aligned_inputs: QrsConsistExcessAlignedInputs,
    settings: dict[str, Any] | None = None,
) -> QrsConsistExcessComputation:
    resolved_settings = _resolve_settings(settings)
    if aligned_inputs.aligned_price_points == 0:
        return QrsConsistExcessComputation(
            resolved_settings=resolved_settings,
            main_series=[],
            ma1_series=[],
            ma2_series=[],
            ma3_series=[],
            signals=[],
        )

    if len(aligned_inputs.benchmark_close_values) != 3:
        raise ValueError("QRS indicator requires exactly 3 benchmark series")

    outputs = qrs_consist_excess(
        aligned_inputs.close_values,
        aligned_inputs.benchmark_close_values[0],
        aligned_inputs.benchmark_close_values[1],
        aligned_inputs.benchmark_close_values[2],
        lookback=int(resolved_settings["lookback"]),
        deadband_period=int(resolved_settings["deadband_period"]),
        deadband_mult=float(resolved_settings["deadband_mult"]),
        map1=int(resolved_settings["map1"]),
        map2=int(resolved_settings["map2"]),
        map3=int(resolved_settings["map3"]),
        cons_weight=float(resolved_settings["cons_weight"]),
        excess_weight=float(resolved_settings["excess_weight"]),
        ma_shift=int(resolved_settings["ma_shift"]),
    )

    main_series = _series_points_from_values(
        aligned_inputs.dates, outputs.get("QRSConsistExcess", [])
    )
    ma1_series = _series_points_from_values(aligned_inputs.dates, outputs.get("MA1", []))
    ma2_series = _series_points_from_values(aligned_inputs.dates, outputs.get("MA2", []))
    ma3_series = _series_points_from_values(aligned_inputs.dates, outputs.get("MA3", []))
    if not main_series or not ma1_series or not ma2_series or not ma3_series:
        return QrsConsistExcessComputation(
            resolved_settings=resolved_settings,
            main_series=[],
            ma1_series=[],
            ma2_series=[],
            ma3_series=[],
            signals=[],
        )

    signals: list[IndicatorSignal] = []
    signals.extend(
        _build_main_zero_cross_signals(
            aligned_inputs.dates, [point.value for point in main_series]
        )
    )
    signals.extend(
        _build_ma1_ma2_cross_signals(
            aligned_inputs.dates,
            [point.value for point in ma1_series],
            [point.value for point in ma2_series],
        )
    )
    signals.extend(
        _build_main_vs_all_mas_regime_signals(
            aligned_inputs.dates,
            [point.value for point in main_series],
            [point.value for point in ma1_series],
            [point.value for point in ma2_series],
            [point.value for point in ma3_series],
        )
    )

    for index in range(1, len(ma1_series)):
        current = ma1_series[index].value
        prev = ma1_series[index - 1].value
        if prev <= 0 and current > 0:
            signals.append(
                IndicatorSignal(
                    signal_date=ma1_series[index].date,
                    signal_type="ma1_cross_above_zero",
                    metadata={
                        "indicator": "MA1",
                        "current_value": current,
                        "prev_value": prev,
                        "label": "qrs_ma1_cross_up",
                    },
                )
            )
        if prev >= 0 and current < 0:
            signals.append(
                IndicatorSignal(
                    signal_date=ma1_series[index].date,
                    signal_type="ma1_cross_below_zero",
                    metadata={
                        "indicator": "MA1",
                        "current_value": current,
                        "prev_value": prev,
                        "label": "qrs_ma1_cross_down",
                    },
                )
            )

    return QrsConsistExcessComputation(
        resolved_settings=resolved_settings,
        main_series=main_series,
        ma1_series=ma1_series,
        ma2_series=ma2_series,
        ma3_series=ma3_series,
        signals=signals,
    )


def evaluate(
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[IndicatorSignal]:
    context = settings.get("_context") if isinstance(settings, dict) else None
    benchmark_prices_by_ticker = {}
    if isinstance(context, dict):
        benchmark_prices_by_ticker = context.get("benchmark_prices_by_ticker") or {}
    if not benchmark_prices_by_ticker:
        raise ValueError("QRS indicator requires benchmark_prices_by_ticker context")

    benchmark_tickers = settings.get("benchmark_tickers")
    if not benchmark_tickers:
        if isinstance(context, dict):
            benchmark_tickers = context.get("benchmark_tickers")
    aligned_inputs = align_qrs_consist_excess_inputs(
        prices=prices,
        benchmark_prices_by_ticker=benchmark_prices_by_ticker,
        benchmark_tickers=benchmark_tickers,
    )
    if aligned_inputs.aligned_price_points < 3:
        return []
    return compute_qrs_consist_excess_computation(
        aligned_inputs=aligned_inputs,
        settings=settings,
    ).signals


def _build_ma1_ma2_cross_signals(
    dates: Sequence[str],
    ma1_series: Sequence[float],
    ma2_series: Sequence[float],
) -> list[IndicatorSignal]:
    signals: list[IndicatorSignal] = []
    if len(ma1_series) < 2 or len(ma2_series) < 2:
        return signals

    length = min(len(dates), len(ma1_series), len(ma2_series))
    for index in range(1, length):
        prev_delta = ma1_series[index - 1] - ma2_series[index - 1]
        current_delta = ma1_series[index] - ma2_series[index]

        crossed_up = prev_delta <= 0 and current_delta > 0
        crossed_down = prev_delta >= 0 and current_delta < 0

        if crossed_up:
            signals.append(
                IndicatorSignal(
                    signal_date=dates[index],
                    signal_type="ma1_cross_above_ma2",
                    metadata={
                        "indicator": "MA1_vs_MA2",
                        "prev_ma1": ma1_series[index - 1],
                        "prev_ma2": ma2_series[index - 1],
                        "current_ma1": ma1_series[index],
                        "current_ma2": ma2_series[index],
                        "label": "qrs_ma1_cross_above_ma2",
                    },
                )
            )
        if crossed_down:
            signals.append(
                IndicatorSignal(
                    signal_date=dates[index],
                    signal_type="ma1_cross_below_ma2",
                    metadata={
                        "indicator": "MA1_vs_MA2",
                        "prev_ma1": ma1_series[index - 1],
                        "prev_ma2": ma2_series[index - 1],
                        "current_ma1": ma1_series[index],
                        "current_ma2": ma2_series[index],
                        "label": "qrs_ma1_cross_below_ma2",
                    },
                )
            )

    return signals


def _build_main_vs_all_mas_regime_signals(
    dates: Sequence[str],
    main_series: Sequence[float],
    ma1_series: Sequence[float],
    ma2_series: Sequence[float],
    ma3_series: Sequence[float],
) -> list[IndicatorSignal]:
    signals: list[IndicatorSignal] = []
    if (
        len(main_series) < 2
        or len(ma1_series) < 2
        or len(ma2_series) < 2
        or len(ma3_series) < 2
    ):
        return signals

    length = min(len(dates), len(main_series), len(ma1_series), len(ma2_series), len(ma3_series))
    for index in range(1, length):
        ma1 = ma1_series[index]
        ma2 = ma2_series[index]
        ma3 = ma3_series[index]
        main = main_series[index]

        pos_regime = ma1 > 0 and ma2 > 0 and ma3 > 0
        neg_regime = ma1 < 0 and ma2 < 0 and ma3 < 0

        cur_above_all = main > ma1 and main > ma2 and main > ma3
        cur_below_all = main < ma1 and main < ma2 and main < ma3

        prev_main = main_series[index - 1]
        prev_ma1 = ma1_series[index - 1]
        prev_ma2 = ma2_series[index - 1]
        prev_ma3 = ma3_series[index - 1]

        prev_above_all = prev_main > prev_ma1 and prev_main > prev_ma2 and prev_main > prev_ma3
        prev_below_all = prev_main < prev_ma1 and prev_main < prev_ma2 and prev_main < prev_ma3

        if pos_regime and cur_above_all and not prev_above_all:
            signals.append(
                IndicatorSignal(
                    signal_date=dates[index],
                    signal_type="main_above_all_mas_pos_regime",
                    metadata={
                        "indicator": "QRSConsistExcess",
                        "current_main": main,
                        "current_ma1": ma1,
                        "current_ma2": ma2,
                        "current_ma3": ma3,
                        "prev_main": prev_main,
                        "prev_ma1": prev_ma1,
                        "prev_ma2": prev_ma2,
                        "prev_ma3": prev_ma3,
                        "label": "qrs_main_above_all_mas_pos_regime",
                    },
                )
            )
        if neg_regime and cur_below_all and not prev_below_all:
            signals.append(
                IndicatorSignal(
                    signal_date=dates[index],
                    signal_type="main_below_all_mas_neg_regime",
                    metadata={
                        "indicator": "QRSConsistExcess",
                        "current_main": main,
                        "current_ma1": ma1,
                        "current_ma2": ma2,
                        "current_ma3": ma3,
                        "prev_main": prev_main,
                        "prev_ma1": prev_ma1,
                        "prev_ma2": prev_ma2,
                        "prev_ma3": prev_ma3,
                        "label": "qrs_main_below_all_mas_neg_regime",
                    },
                )
            )

    return signals


def _build_main_zero_cross_signals(
    dates: Sequence[str],
    series: Sequence[float],
) -> list[IndicatorSignal]:
    signals: list[IndicatorSignal] = []
    if len(series) < 4:
        return signals

    for index in range(3, len(series)):
        current = series[index]
        prev1 = series[index - 1]
        prev2 = series[index - 2]
        prev3 = series[index - 3]
        if current > 0 and prev1 <= 0 and prev2 <= 0 and prev3 <= 0:
            signals.append(
                IndicatorSignal(
                    signal_date=dates[index],
                    signal_type="main_cross_above_zero_3d",
                    metadata={
                        "indicator": "QRSConsistExcess",
                        "current_value": current,
                        "prev_1": prev1,
                        "prev_2": prev2,
                        "prev_3": prev3,
                        "label": "qrs_main_cross_up_3d",
                    },
                )
            )
        if current < 0 and prev1 >= 0 and prev2 >= 0 and prev3 >= 0:
            signals.append(
                IndicatorSignal(
                    signal_date=dates[index],
                    signal_type="main_cross_below_zero_3d",
                    metadata={
                        "indicator": "QRSConsistExcess",
                        "current_value": current,
                        "prev_1": prev1,
                        "prev_2": prev2,
                        "prev_3": prev3,
                        "label": "qrs_main_cross_down_3d",
                    },
                )
            )
    return signals


__all__ = [
    "BENCHMARK_TICKERS",
    "QrsConsistExcessAlignedInputs",
    "QrsConsistExcessComputation",
    "align_qrs_consist_excess_inputs",
    "compute_qrs_consist_excess_computation",
    "evaluate",
    "qrs_consist_excess",
]
