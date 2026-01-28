from __future__ import annotations

from typing import Any

from app.security_scan.criteria import SeriesPoint, evaluate_criteria
from app.security_scan.signals import IndicatorSignal

INDICATOR_ID = "roc"


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


def _compute_roc_series(
    close_series: list[SeriesPoint], lookback: int
) -> list[SeriesPoint]:
    if lookback <= 0:
        raise ValueError("roc_lookback must be > 0")
    roc_series: list[SeriesPoint] = []
    for index in range(lookback, len(close_series)):
        current = close_series[index]
        prior = close_series[index - lookback]
        if prior.value == 0:
            continue
        roc_value = (current.value - prior.value) / prior.value
        roc_series.append(SeriesPoint(date=current.date, value=roc_value))
    return roc_series


def evaluate(
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[IndicatorSignal]:
    lookback_raw = settings.get("roc_lookback", 12)
    try:
        lookback = int(lookback_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("roc_lookback must be an integer") from exc

    close_series = _extract_close_series(prices)
    if len(close_series) <= lookback:
        return []

    roc_series = _compute_roc_series(close_series, lookback)
    criteria = settings.get("criteria", [])
    if criteria is None:
        criteria = []
    return evaluate_criteria(roc_series, criteria, series_name="roc")
