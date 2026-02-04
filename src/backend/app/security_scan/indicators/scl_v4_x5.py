from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

from app.security_scan.criteria import SeriesPoint
from app.security_scan.signals import IndicatorSignal

INDICATOR_ID = "scl_v4_x5"


def _is_nan(value: float) -> bool:
    return value != value


def _to_float_list(values: Sequence[float]) -> List[float]:
    out: List[float] = []
    for v in values:
        out.append(float(v) if v is not None else math.nan)
    return out


def _ref(series: Sequence[float], period: int) -> List[float]:
    n = len(series)
    out = [math.nan] * n
    for i in range(n):
        j = i + period
        if 0 <= j < n:
            out[i] = series[j]
    return out


def _truthy(value: float) -> bool:
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
    n = len(expr)
    out = [math.nan] * n
    last_true_index: int | None = None
    for i in range(n):
        if _truthy(expr[i]):
            out[i] = 0.0
            last_true_index = i
        else:
            if last_true_index is None:
                out[i] = float(i + 1)
            else:
                out[i] = float(i - last_true_index)
    return out


def _sma(series: Sequence[float], period: int) -> List[float]:
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

        if len(window_vals) > period:
            removed = window_vals.pop(0)
            if not _is_nan(removed):
                window_sum -= removed
                window_count -= 1

        if window_count > 0:
            out[i] = window_sum / window_count
        else:
            out[i] = 0.0

    return out


def _nan_to_zero(series: Sequence[float]) -> List[float]:
    out: List[float] = []
    for v in series:
        if v is None:
            out.append(0.0)
        else:
            fv = float(v)
            out.append(0.0 if _is_nan(fv) else fv)
    return out


def _compare_gt(a: Sequence[float], b: Sequence[float]) -> List[float]:
    n = len(a)
    out = [0.0] * n
    for i in range(n):
        if _is_nan(a[i]) or _is_nan(b[i]):
            out[i] = 0.0
        else:
            out[i] = 1.0 if a[i] > b[i] else 0.0
    return out


def _compare_lt(a: Sequence[float], b: Sequence[float]) -> List[float]:
    n = len(a)
    out = [0.0] * n
    for i in range(n):
        if _is_nan(a[i]) or _is_nan(b[i]):
            out[i] = 0.0
        else:
            out[i] = 1.0 if a[i] < b[i] else 0.0
    return out


def _compare_le(a: Sequence[float], b: Sequence[float]) -> List[float]:
    n = len(a)
    out = [0.0] * n
    for i in range(n):
        if _is_nan(a[i]) or _is_nan(b[i]):
            out[i] = 0.0
        else:
            out[i] = 1.0 if a[i] <= b[i] else 0.0
    return out


def _compare_ge(a: Sequence[float], b: Sequence[float]) -> List[float]:
    n = len(a)
    out = [0.0] * n
    for i in range(n):
        if _is_nan(a[i]) or _is_nan(b[i]):
            out[i] = 0.0
        else:
            out[i] = 1.0 if a[i] >= b[i] else 0.0
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


def _to_int_setting(settings: dict[str, Any], key: str, default: int) -> int:
    value = settings.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    return parsed


def scl_v4_x5(
    close: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    *,
    lag1: int = 2,
    lag2: int = 3,
    lag3: int = 4,
    lag4: int = 5,
    lag5: int = 11,
    cd_offset1: int = 2,
    cd_offset2: int = 3,
    ma_period1: int = 5,
    ma_period2: int = 11,
) -> Dict[str, List[float]]:
    n = len(close)
    if len(high) != n or len(low) != n:
        raise ValueError("close, high, low must be the same length")

    c = _to_float_list(close)
    h = _to_float_list(high)
    l = _to_float_list(low)

    lag_close1 = _ref(c, -lag1)
    lag_close2 = _ref(c, -lag2)
    lag_close3 = _ref(c, -lag3)
    lag_close4 = _ref(c, -lag4)
    lag_close5 = _ref(c, -lag5)

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

    buy_qual1 = _compare_le(c, _ref(l, -cd_offset1))
    buy_qual2 = _compare_le(c, _ref(l, -cd_offset2))
    sell_qual1 = _compare_ge(c, _ref(h, -cd_offset1))
    sell_qual2 = _compare_ge(c, _ref(h, -cd_offset2))

    count_value: List[float] = []
    for i in range(n):
        count_value.append(
            seq_value[i]
            - buy_qual1[i]
            - buy_qual2[i]
            + sell_qual1[i]
            + sell_qual2[i]
        )

    count_ma1 = _sma(count_value, ma_period1)
    count_ma2 = _sma(count_value, ma_period2)

    return {
        "CountdownDisplay": _nan_to_zero(count_value),
        "MA1": _nan_to_zero(count_ma1),
        "MA2": _nan_to_zero(count_ma2),
        "Zero": [0.0] * n,
    }


def compute_countdown_series(
    prices: list[dict[str, Any]],
    settings: dict[str, Any] | None = None,
) -> list[SeriesPoint]:
    settings = settings or {}
    dates, closes, highs, lows = _extract_ohlc_series(prices)
    if not dates:
        return []

    outputs = scl_v4_x5(
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

    countdown = outputs.get("CountdownDisplay", [])
    if len(countdown) != len(dates):
        return []

    return [
        SeriesPoint(date=dates[index], value=float(value))
        for index, value in enumerate(countdown)
    ]


def compute_prior_window_flags(
    series: list[SeriesPoint],
    lookback: int,
) -> dict[str, dict[str, float | bool | None]]:
    flags: dict[str, dict[str, float | bool | None]] = {}
    if lookback <= 0:
        return flags
    values = [point.value for point in series]
    for index, point in enumerate(series):
        if index < lookback:
            flags[point.date] = {
                "high": None,
                "low": None,
                "prior_high": None,
                "prior_low": None,
            }
            continue
        window = values[index - lookback : index]
        prior_high = max(window)
        prior_low = min(window)
        flags[point.date] = {
            "high": point.value >= prior_high,
            "low": point.value <= prior_low,
            "prior_high": prior_high,
            "prior_low": prior_low,
        }
    return flags


def evaluate(
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[IndicatorSignal]:
    series = compute_countdown_series(prices, settings)
    if len(series) < 8:
        return []

    flags = compute_prior_window_flags(series, lookback=7)
    signals: list[IndicatorSignal] = []
    for point in series:
        info = flags.get(point.date)
        if not info:
            continue
        prior_high = info.get("prior_high")
        prior_low = info.get("prior_low")
        if info.get("high"):
            signals.append(
                IndicatorSignal(
                    signal_date=point.date,
                    signal_type="seven_bar_high",
                    metadata={
                        "indicator": "CountdownDisplay",
                        "lookback": 7,
                        "current_value": point.value,
                        "prior_high": prior_high,
                        "label": "scl_7bar_high",
                    },
                )
            )
        if info.get("low"):
            signals.append(
                IndicatorSignal(
                    signal_date=point.date,
                    signal_type="seven_bar_low",
                    metadata={
                        "indicator": "CountdownDisplay",
                        "lookback": 7,
                        "current_value": point.value,
                        "prior_low": prior_low,
                        "label": "scl_7bar_low",
                    },
                )
            )

    return signals


__all__ = [
    "compute_countdown_series",
    "compute_prior_window_flags",
    "evaluate",
    "scl_v4_x5",
]
