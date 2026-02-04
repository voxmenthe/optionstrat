from __future__ import annotations

from collections import defaultdict
from typing import Iterable, NotRequired, TypedDict

from app.security_scan.db import SecurityAggregateValue


class AggregateSeriesPoint(TypedDict):
    date: str
    value: float | None


class AggregateSeries(TypedDict):
    metric_key: str
    label: str
    points: list[AggregateSeriesPoint]
    style: NotRequired["AggregateSeriesStyle"]


class AggregateSeriesStyle(TypedDict, total=False):
    color: str
    width: float
    dash: str


class AggregateSeriesDefinition(TypedDict):
    metric_key: str
    label: str


def _normalize_lookbacks(advance_decline_lookbacks: Iterable[int] | None) -> list[int]:
    if not advance_decline_lookbacks:
        return [1]
    seen: set[int] = set()
    normalized: list[int] = []
    for value in advance_decline_lookbacks:
        lookback = int(value)
        if lookback <= 0 or lookback in seen:
            continue
        seen.add(lookback)
        normalized.append(lookback)
    return normalized or [1]


def build_aggregate_series_definitions(
    advance_decline_lookbacks: Iterable[int] | None = None,
) -> list[AggregateSeriesDefinition]:
    definitions: list[AggregateSeriesDefinition] = [
        {"metric_key": "advances", "label": "Advances (t-1)"},
        {"metric_key": "declines", "label": "Declines (t-1)"},
        {"metric_key": "unchanged", "label": "Unchanged (t-1)"},
        {"metric_key": "net_advances", "label": "Net Advances (t-1)"},
        {"metric_key": "advance_pct", "label": "Advance % (t-1)"},
    ]

    for lookback in _normalize_lookbacks(advance_decline_lookbacks):
        if lookback == 1:
            continue
        definitions.append(
            {
                "metric_key": f"ad_{lookback}_advance_pct",
                "label": f"Advance % (t-{lookback})",
            }
        )

    definitions.extend(
        [
            {"metric_key": "ma_13_above_pct", "label": "SMA 13 % Above"},
            {"metric_key": "ma_28_above_pct", "label": "SMA 28 % Above"},
            {"metric_key": "ma_46_above_pct", "label": "SMA 46 % Above"},
            {"metric_key": "ma_8_shift_5_above_pct", "label": "SMA 8 (shift 5) % Above"},
        ]
    )

    definitions.extend(
        [
            {"metric_key": "roc_17_vs_5_gt_pct", "label": "ROC 17 vs 5 % Greater"},
            {"metric_key": "roc_27_vs_4_gt_pct", "label": "ROC 27 vs 4 % Greater"},
        ]
    )

    definitions.append(
        {"metric_key": "scl_5bar_net", "label": "SCL 5-Bar High - Low"}
    )

    return definitions


def collect_aggregate_metric_keys(
    series_definitions: Iterable[AggregateSeriesDefinition],
) -> list[str]:
    return [definition["metric_key"] for definition in series_definitions]


def assemble_aggregate_series(
    rows: Iterable[SecurityAggregateValue],
    series_definitions: Iterable[AggregateSeriesDefinition],
) -> list[AggregateSeries]:
    points_by_key: dict[str, list[AggregateSeriesPoint]] = defaultdict(list)
    for row in rows:
        points_by_key[row.metric_key].append(
            {"date": row.as_of_date, "value": row.value}
        )

    series_payloads: list[AggregateSeries] = []
    for definition in series_definitions:
        metric_key = definition["metric_key"]
        points = points_by_key.get(metric_key, [])
        if len(points) > 1:
            points.sort(key=lambda point: point["date"])
        series_payloads.append(
            {
                "metric_key": metric_key,
                "label": definition["label"],
                "points": points,
            }
        )
    return series_payloads
