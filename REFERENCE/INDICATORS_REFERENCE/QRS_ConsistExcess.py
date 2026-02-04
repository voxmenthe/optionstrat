"""
Python version of INDICATORS/QRS_ConsistExcess.txt

Notes:
- Uses simple rolling sums and simple moving averages.
- Rolling StdDev uses population variance (divide by N) and returns 0.0
  when fewer than 2 valid values are available.
- Boolean expressions are treated as 1.0/0.0 in rolling sums.
- Percent change uses 0.0 when prior data is missing or zero to keep
  early bars neutral rather than NaN.
- Outputs replace NaN with 0.0 to minimize gaps.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence


def _is_nan(value: float) -> bool:
    return value != value


def _to_float_list(values: Sequence[float]) -> List[float]:
    out: List[float] = []
    for v in values:
        out.append(float(v) if v is not None else math.nan)
    return out


def _pct_change(series: Sequence[float]) -> List[float]:
    """
    Percent change with neutral fallback.

    If prior data is missing or zero, return 0.0 for that bar. This keeps
    early bars neutral rather than NaN, which is more practical for
    ProTA-style boolean gating.
    """

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
    """
    Rolling population standard deviation.

    Uses available non-NaN values in the window. If fewer than 2 valid
    values exist, returns 0.0 for that bar (a principled neutral std).
    """

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
    map2: int = 14,
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
    bench_ret = [_avg_available([spy_ret[i], qqq_ret[i], iwm_ret[i]]) for i in range(n)]

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

    min_day_frac = 0.2
    min_up_days = lookback * min_day_frac
    min_down_days = lookback * min_day_frac

    valid_counts = [
        1.0 if (up_day_count[i] >= min_up_days and down_day_count[i] >= min_down_days) else 0.0
        for i in range(n)
    ]

    sign_aligned = [
        1.0
        if ((raw_excess[i] > 0 and consistency[i] > 0) or (raw_excess[i] < 0 and consistency[i] < 0))
        else 0.0
        for i in range(n)
    ]

    combined = [
        (consistency[i] * cons_weight) + (excess_norm[i] * excess_weight)
        for i in range(n)
    ]

    quiet_score = [
        combined[i] if (valid_counts[i] > 0.0 and sign_aligned[i] > 0.0) else 0.0
        for i in range(n)
    ]

    ma1 = _ref(_sma(quiet_score, map1), -ma_shift)
    ma2 = _ref(_sma(quiet_score, map2), -ma_shift)

    return {
        "QRSConsistExcess": _nan_to_zero(quiet_score),
        "CrossoverLine": [0.0] * n,
        "MA1": _nan_to_zero(ma1),
        "MA2": _nan_to_zero(ma2),
    }


__all__ = ["qrs_consist_excess"]
