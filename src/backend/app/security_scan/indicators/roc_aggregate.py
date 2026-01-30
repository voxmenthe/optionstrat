from __future__ import annotations

from typing import Any

from app.security_scan.criteria import SeriesPoint
from app.security_scan.signals import IndicatorSignal

INDICATOR_ID = "roc_aggregate"


def _extract_close_series(prices: list[dict[str, Any]]) -> list[SeriesPoint]:
    points: list[SeriesPoint] = []
    for row in prices:
        date = row.get("date")
        close = row.get("close")
        if not date or close is None:
            continue
        points.append(SeriesPoint(date=str(date), value=float(close)))
    points.sort(key=lambda point: point.date)
    return points


def _to_positive_int(value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{label} must be > 0")
    return parsed


def _to_positive_int_list(
    value: Any,
    label: str,
    default: list[int],
) -> list[int]:
    if value is None:
        items = default
    elif isinstance(value, int):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        raise ValueError(f"{label} must be a list of integers")

    if not items:
        raise ValueError(f"{label} must be a non-empty list of integers")

    parsed: list[int] = []
    for item in items:
        parsed.append(_to_positive_int(item, label))
    return parsed


def _compute_roc_by_index(
    close_series: list[SeriesPoint],
    lookback: int,
) -> list[float | None]:
    roc_values: list[float | None] = [None] * len(close_series)
    for index in range(lookback, len(close_series)):
        current = close_series[index]
        prior = close_series[index - lookback]
        if prior.value == 0:
            continue
        roc_values[index] = (current.value - prior.value) / prior.value
    return roc_values


def _compute_indicator_series(
    close_series: list[SeriesPoint],
    roc_by_index: dict[int, list[float | None]],
    roc_lookbacks: list[int],
    change_lookbacks: list[int],
) -> list[SeriesPoint]:
    max_roc_lookback = max(roc_lookbacks)
    max_change_lookback = max(change_lookbacks)
    series: list[SeriesPoint] = []

    for close_index in range(max_roc_lookback + max_change_lookback, len(close_series)):
        total_score = 0
        missing_data = False
        for roc_lookback in roc_lookbacks:
            roc_values = roc_by_index[roc_lookback]
            current = roc_values[close_index]
            if current is None:
                missing_data = True
                break
            for change_lookback in change_lookbacks:
                prior = roc_values[close_index - change_lookback]
                if prior is None:
                    missing_data = True
                    break
                if current > prior:
                    total_score += 1
                elif current < prior:
                    total_score -= 1
            if missing_data:
                break
        if missing_data:
            continue
        series.append(
            SeriesPoint(date=close_series[close_index].date, value=float(total_score))
        )
    return series


def _compute_sma_series(series: list[SeriesPoint], window: int) -> list[SeriesPoint]:
    if window <= 0:
        raise ValueError("ma window must be > 0")
    if len(series) < window:
        return []

    sma_series: list[SeriesPoint] = []
    running_sum = sum(point.value for point in series[:window])
    sma_series.append(
        SeriesPoint(date=series[window - 1].date, value=running_sum / window)
    )
    for index in range(window, len(series)):
        running_sum += series[index].value - series[index - window].value
        sma_series.append(
            SeriesPoint(date=series[index].date, value=running_sum / window)
        )
    return sma_series


def evaluate(
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[IndicatorSignal]:
    roc_lookbacks = _to_positive_int_list(
        settings.get("roc_lookbacks"),
        "roc_lookbacks",
        [5, 10, 20],
    )
    change_lookbacks = _to_positive_int_list(
        settings.get("roc_change_lookbacks"),
        "roc_change_lookbacks",
        [1, 3, 5],
    )
    ma_short = _to_positive_int(settings.get("ma_short", 5), "ma_short")
    ma_long = _to_positive_int(settings.get("ma_long", 20), "ma_long")

    close_series = _extract_close_series(prices)
    if not close_series:
        return []

    required_points = max(roc_lookbacks) + max(change_lookbacks) + 1
    if len(close_series) < required_points:
        return []

    roc_by_index = {
        lookback: _compute_roc_by_index(close_series, lookback)
        for lookback in roc_lookbacks
    }
    indicator_series = _compute_indicator_series(
        close_series, roc_by_index, roc_lookbacks, change_lookbacks
    )
    if len(indicator_series) < 2:
        return []

    sma_short_series = _compute_sma_series(indicator_series, ma_short)
    sma_long_series = _compute_sma_series(indicator_series, ma_long)
    if not sma_short_series or not sma_long_series:
        return []

    sma_short_by_date = {point.date: point.value for point in sma_short_series}
    sma_long_by_date = {point.date: point.value for point in sma_long_series}

    signals: list[IndicatorSignal] = []
    for index in range(1, len(indicator_series)):
        prev = indicator_series[index - 1]
        current = indicator_series[index]
        prev_short = sma_short_by_date.get(prev.date)
        prev_long = sma_long_by_date.get(prev.date)
        current_short = sma_short_by_date.get(current.date)
        current_long = sma_long_by_date.get(current.date)
        if (
            prev_short is None
            or prev_long is None
            or current_short is None
            or current_long is None
        ):
            continue

        prev_above = prev.value > prev_short and prev.value > prev_long
        current_above = current.value > current_short and current.value > current_long
        prev_below = prev.value < prev_short and prev.value < prev_long
        current_below = current.value < current_short and current.value < current_long

        metadata = {
            "indicator_value": current.value,
            "ma_short_value": current_short,
            "ma_long_value": current_long,
            "ma_short_window": ma_short,
            "ma_long_window": ma_long,
            "roc_lookbacks": roc_lookbacks,
            "roc_change_lookbacks": change_lookbacks,
        }

        if not prev_above and current_above:
            signals.append(
                IndicatorSignal(
                    signal_date=current.date,
                    signal_type="cross_above_both",
                    metadata=metadata,
                )
            )
        if not prev_below and current_below:
            signals.append(
                IndicatorSignal(
                    signal_date=current.date,
                    signal_type="cross_below_both",
                    metadata=metadata,
                )
            )

    return signals
