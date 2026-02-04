"""
Python version of INDICATORS/SCL_v4_x5.txt

This is a direct, line-by-line translation of the ProTA Script indicator
into pure Python lists (no pandas dependency), with ProTA-specific behavior
documented inline.

Key ProTA semantics mirrored here:
- REF(Array, Period): Period < 0 looks back, Period > 0 looks ahead.
  Example: REF(Close, -1) returns the previous Close.
- BarsSince(ExpressionArray): number of bars since the expression was TRUE.
  When expression is TRUE on the current bar, BarsSince returns 0.
  If the expression has never been TRUE, this implementation returns the
  number of bars since the start of the series (1 on the first bar).
- MA(Period, S, Array): Simple moving average of Array over Period bars.

Notes:
- Comparisons involving NaN are treated as FALSE, which is consistent with
  typical ProTA behavior where insufficient history yields a FALSE comparison.
- MA uses the average of available (non-NaN) bars, even before a full window.
- Output series are sanitized to replace NaN with 0.0 to minimize gaps.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence


def _is_nan(value: float) -> bool:
    """True if value is NaN (NaN is not equal to itself)."""

    return value != value


def _to_float_list(values: Sequence[float]) -> List[float]:
    """
    Convert an input sequence to a list of floats, mapping None -> NaN.

    ProTA arrays can contain missing values on early bars due to REF/MA
    lookbacks; using NaN here preserves that missingness.
    """

    out: List[float] = []
    for v in values:
        out.append(float(v) if v is not None else math.nan)
    return out


def _ref(series: Sequence[float], period: int) -> List[float]:
    """
    ProTA REF(Array, Period) semantics.

    - period < 0: look BACK (lag). REF(Close, -1) is previous close.
    - period > 0: look AHEAD (lead). REF(Close, 5) is close 5 bars ahead.

    Out-of-range references are NaN.
    """

    n = len(series)
    out = [math.nan] * n
    for i in range(n):
        j = i + period
        if 0 <= j < n:
            out[i] = series[j]
    return out


def _truthy(value: float) -> bool:
    """
    ProTA uses numeric arrays for boolean expressions:
    - 0 is FALSE
    - non-zero is TRUE
    NaN is treated as FALSE for control flow.
    """

    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if _is_nan(float(value)):
            return False
        return float(value) != 0.0
    return bool(value)


def _bars_since(expr: Sequence[float]) -> List[float]:
    """
    ProTA BarsSince(ExpressionArray) implementation.

    Returns the number of bars since expr was TRUE.
    - If expr is TRUE on the current bar, result is 0.
    - If expr has never been TRUE, we count from the start of the series
      (1 on the first bar, 2 on the second, ...). This mirrors common
      trading-platform behavior and yields sensible streak counts.
    """

    n = len(expr)
    out = [math.nan] * n
    last_true_index = None
    for i in range(n):
        if _truthy(expr[i]):
            out[i] = 0.0
            last_true_index = i
        else:
            if last_true_index is None:
                # Never true so far: count from the start (1-based).
                out[i] = float(i + 1)
            else:
                out[i] = float(i - last_true_index)
    return out


def _sma(series: Sequence[float], period: int) -> List[float]:
    """
    Simple moving average (ProTA MA with type S).

    This implementation returns the average of available (non-NaN) bars
    in the current window, even before a full window exists. If no valid
    bars are available, it returns 0.0 for that bar.
    """

    n = len(series)
    out = [math.nan] * n
    if period <= 0:
        return out

    window_sum = 0.0
    window_count = 0
    window_vals: List[float] = []

    for i, val in enumerate(series):
        window_vals.append(val)
        if not _is_nan(val):
            window_sum += val
            window_count += 1

        # Maintain a fixed-size rolling window
        if len(window_vals) > period:
            removed = window_vals.pop(0)
            if not _is_nan(removed):
                window_sum -= removed
                window_count -= 1

        # Emit the average of available non-NaN bars in the window
        if window_count > 0:
            out[i] = window_sum / window_count
        else:
            out[i] = 0.0

    return out


def _nan_to_zero(series: Sequence[float]) -> List[float]:
    """
    Replace NaN (and None) with 0.0 to minimize gaps in output series.
    """

    out: List[float] = []
    for v in series:
        if v is None:
            out.append(0.0)
        else:
            fv = float(v)
            out.append(0.0 if _is_nan(fv) else fv)
    return out


def _compare_gt(a: Sequence[float], b: Sequence[float]) -> List[float]:
    """
    Elementwise (a > b) with NaN-safe FALSE behavior.

    Returns 1.0 for TRUE, 0.0 for FALSE, matching ProTA numeric booleans.
    """

    n = len(a)
    out = [0.0] * n
    for i in range(n):
        if _is_nan(a[i]) or _is_nan(b[i]):
            out[i] = 0.0
        else:
            out[i] = 1.0 if a[i] > b[i] else 0.0
    return out


def _compare_lt(a: Sequence[float], b: Sequence[float]) -> List[float]:
    """Elementwise (a < b) with NaN-safe FALSE behavior."""

    n = len(a)
    out = [0.0] * n
    for i in range(n):
        if _is_nan(a[i]) or _is_nan(b[i]):
            out[i] = 0.0
        else:
            out[i] = 1.0 if a[i] < b[i] else 0.0
    return out


def _compare_le(a: Sequence[float], b: Sequence[float]) -> List[float]:
    """Elementwise (a <= b) with NaN-safe FALSE behavior."""

    n = len(a)
    out = [0.0] * n
    for i in range(n):
        if _is_nan(a[i]) or _is_nan(b[i]):
            out[i] = 0.0
        else:
            out[i] = 1.0 if a[i] <= b[i] else 0.0
    return out


def _compare_ge(a: Sequence[float], b: Sequence[float]) -> List[float]:
    """Elementwise (a >= b) with NaN-safe FALSE behavior."""

    n = len(a)
    out = [0.0] * n
    for i in range(n):
        if _is_nan(a[i]) or _is_nan(b[i]):
            out[i] = 0.0
        else:
            out[i] = 1.0 if a[i] >= b[i] else 0.0
    return out


def scl_v4_x5(
    close: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    lag1: int = 2, # v1: 1 # v2: 1
    lag2: int = 3, # v1: 3 # v2: 2
    lag3: int = 4, # v1: 4 # v2: 3
    lag4: int = 5, # v1: 7 # v2: 5
    lag5: int = 11, # v1: 11 # v2: 8
    cd_offset1: int = 2,
    cd_offset2: int = 3,
    ma_period1: int = 5,
    ma_period2: int = 11,
) -> Dict[str, List[float]]:
    """
    Python translation of SCL_v4_x5 ProTA indicator.

    Parameters mirror the ProTA script defaults.
    Inputs are parallel sequences (Close, High, Low) of equal length.
    Returns a dict of output series matching the ProTA #output lines.
    """

    # ---- Basic input validation (avoid silent shape mismatches) ----
    n = len(close)
    if len(high) != n or len(low) != n:
        raise ValueError("close, high, low must be the same length")

    # Convert to float lists; None -> NaN for missing data
    c = _to_float_list(close)
    h = _to_float_list(high)
    l = _to_float_list(low)

    # ---- Setup (sequential) ----
    # ProTA: lagCloseX := REF(C, -lagX)
    # REF with negative period looks back in time.
    lag_close1 = _ref(c, -lag1)
    lag_close2 = _ref(c, -lag2)
    lag_close3 = _ref(c, -lag3)
    lag_close4 = _ref(c, -lag4)
    lag_close5 = _ref(c, -lag5)

    # ProTA comparisons return TRUE/FALSE but behave numerically (1/0).
    is_up1 = _compare_gt(c, lag_close1)
    is_up2 = _compare_gt(c, lag_close2)
    is_up3 = _compare_gt(c, lag_close3)
    is_up4 = _compare_gt(c, lag_close4)
    is_up5 = _compare_gt(c, lag_close5)

    is_down1 = _compare_lt(c, lag_close1)
    is_down2 = _compare_lt(c, lag_close2)
    is_down3 = _compare_lt(c, lag_close3)
    is_down4 = _compare_lt(c, lag_close4)
    is_down5 = _compare_lt(c, lag_close5)

    # ProTA: notUp := IF(isUp, 0, 1)
    # Here isUp is numeric (1/0). This flips it to 0/1.
    not_up1 = [0.0 if _truthy(v) else 1.0 for v in is_up1]
    not_up2 = [0.0 if _truthy(v) else 1.0 for v in is_up2]
    not_up3 = [0.0 if _truthy(v) else 1.0 for v in is_up3]
    not_up4 = [0.0 if _truthy(v) else 1.0 for v in is_up4]
    not_up5 = [0.0 if _truthy(v) else 1.0 for v in is_up5]

    not_down1 = [0.0 if _truthy(v) else 1.0 for v in is_down1]
    not_down2 = [0.0 if _truthy(v) else 1.0 for v in is_down2]
    not_down3 = [0.0 if _truthy(v) else 1.0 for v in is_down3]
    not_down4 = [0.0 if _truthy(v) else 1.0 for v in is_down4]
    not_down5 = [0.0 if _truthy(v) else 1.0 for v in is_down5]

    # ProTA: BarsSince(notUpX)
    # This yields the length (in bars) since the last "not up" condition.
    up_count1 = _bars_since(not_up1)
    up_count2 = _bars_since(not_up2)
    up_count3 = _bars_since(not_up3)
    up_count4 = _bars_since(not_up4)
    up_count5 = _bars_since(not_up5)

    down_count1 = _bars_since(not_down1)
    down_count2 = _bars_since(not_down2)
    down_count3 = _bars_since(not_down3)
    down_count4 = _bars_since(not_down4)
    down_count5 = _bars_since(not_down5)

    # seqValue := sum(upCounts) - sum(downCounts)
    seq_value: List[float] = []
    for i in range(n):
        seq_value.append(
            up_count1[i]
            + up_count2[i]
            + up_count3[i]
            + up_count4[i]
            + up_count5[i]
            - down_count1[i]
            - down_count2[i]
            - down_count3[i]
            - down_count4[i]
            - down_count5[i]
        )

    # ---- Countdown qualifiers ----
    # buyQual := C <= REF(L, -cdOffset)
    # sellQual := C >= REF(H, -cdOffset)
    buy_qual1 = _compare_le(c, _ref(l, -cd_offset1))
    buy_qual2 = _compare_le(c, _ref(l, -cd_offset2))
    sell_qual1 = _compare_ge(c, _ref(h, -cd_offset1))
    sell_qual2 = _compare_ge(c, _ref(h, -cd_offset2))

    # countValue := seqValue - buyQual1 - buyQual2 + sellQual1 + sellQual2
    count_value: List[float] = []
    for i in range(n):
        count_value.append(
            seq_value[i]
            - buy_qual1[i]
            - buy_qual2[i]
            + sell_qual1[i]
            + sell_qual2[i]
        )

    # ---- Smoothing ----
    count_ma1 = _sma(count_value, ma_period1)
    count_ma2 = _sma(count_value, ma_period2)

    # ---- Outputs (match ProTA #lines) ----
    return {
        "CountdownDisplay": _nan_to_zero(count_value),
        "MA1": _nan_to_zero(count_ma1),
        "MA2": _nan_to_zero(count_ma2),
        "Zero": [0.0] * n,
    }


__all__ = ["scl_v4_x5"]
