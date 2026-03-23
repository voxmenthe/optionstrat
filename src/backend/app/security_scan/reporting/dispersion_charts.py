from __future__ import annotations

from typing import Iterable, TypedDict

from app.security_scan.dispersion import DEFAULT_DISPERSION_WINDOWS
from app.security_scan.reporting.aggregate_charts import build_timeseries_figure
from app.security_scan.reporting.aggregate_series import (
    AggregateSeries,
    AggregateSeriesPoint,
    assemble_aggregate_series,
    collect_aggregate_metric_keys,
)
from app.security_scan.reporting.dispersion_series import (
    build_dispersion_series_definitions,
)
from app.security_scan.storage import fetch_security_aggregate_series


class DispersionChartUniverse(TypedDict):
    universe_key: str
    universe_label: str
    set_hash: str


class DispersionUniverseSeries(TypedDict):
    universe_key: str
    universe_label: str
    series_payloads: list[AggregateSeries]


class DispersionSeriesPanel(TypedDict):
    label: str
    series: list[AggregateSeries]


class DispersionChartGroupDefinition(TypedDict):
    key: str
    title: str
    y_label: str
    tickformat: str | None
    reference_lines: list[float]
    metric_keys: list[str]


def build_multi_universe_dispersion_charts_html(
    *,
    universes: Iterable[DispersionChartUniverse],
    interval: str,
    start_date: str | None,
    end_date: str | None,
    windows: Iterable[int] | None = None,
    max_points: int | None = None,
    show_components: bool = True,
    show_diagnostics: bool = True,
    smoothing_days: int = 3,
) -> str:
    normalized_windows = _normalize_windows(windows)
    definitions = build_dispersion_series_definitions(
        windows=normalized_windows,
        include_components=show_components,
        include_diagnostics=show_diagnostics,
    )
    metric_keys = collect_aggregate_metric_keys(definitions)

    universe_series_payloads: list[DispersionUniverseSeries] = []
    for universe in universes:
        set_hash = universe.get("set_hash")
        if not isinstance(set_hash, str) or not set_hash:
            continue
        rows = fetch_security_aggregate_series(
            set_hash=set_hash,
            metric_keys=metric_keys,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
        if not rows:
            continue
        series_payloads = assemble_aggregate_series(rows, definitions)
        if max_points:
            series_payloads = _trim_series_payloads(series_payloads, max_points)
        if smoothing_days > 1:
            series_payloads = _append_lockstep_smoothing_series(
                series_payloads,
                smoothing_days=smoothing_days,
            )
        universe_series_payloads.append(
            {
                "universe_key": universe["universe_key"],
                "universe_label": universe["universe_label"],
                "series_payloads": series_payloads,
            }
        )

    if not universe_series_payloads:
        return ""

    group_definitions = _build_chart_group_definitions(
        windows=normalized_windows,
        show_components=show_components,
        show_diagnostics=show_diagnostics,
    )
    return render_multi_universe_dispersion_charts_html(
        universe_series_payloads,
        group_definitions=group_definitions,
    )


def render_multi_universe_dispersion_charts_html(
    universe_series_payloads: Iterable[DispersionUniverseSeries],
    *,
    group_definitions: Iterable[DispersionChartGroupDefinition],
) -> str:
    import plotly.io as pio

    universes = list(universe_series_payloads)
    if not universes:
        return ""

    html_parts: list[str] = []
    include_plotlyjs: str | bool = "inline"

    for group in group_definitions:
        panels: list[DispersionSeriesPanel] = []
        for universe in universes:
            series_list = _filter_series_by_keys(
                universe["series_payloads"],
                metric_keys=group["metric_keys"],
            )
            cleaned_series = [series for series in series_list if series["points"]]
            if not cleaned_series:
                continue
            panels.append(
                {
                    "label": f"{universe['universe_label']} {group['y_label']}",
                    "series": cleaned_series,
                }
            )

        if not panels:
            continue

        base_dates = _collect_panel_dates(panels)
        if not base_dates:
            continue
        allowed_dates = set(base_dates)
        filtered_panels: list[DispersionSeriesPanel] = []
        for panel in panels:
            filtered_panels.append(
                {
                    "label": panel["label"],
                    "series": [
                        _filter_series_dates(series, allowed_dates)
                        for series in panel["series"]
                    ],
                }
            )

        figure = build_timeseries_figure(
            title=group["title"],
            panels=filtered_panels,
            y_tickformat=group["tickformat"],
            reference_lines=group["reference_lines"],
            x_categories=base_dates,
            include_benchmark_rows=False,
        )
        chart_html = pio.to_html(
            figure,
            include_plotlyjs=include_plotlyjs,
            full_html=False,
        )
        include_plotlyjs = False
        html_parts.append(
            "<div class=\"chart-block\">\n"
            f"<h3>{group['title']}</h3>\n"
            f"{chart_html}\n"
            "</div>"
        )

    return "\n".join(html_parts)


def _build_chart_group_definitions(
    *,
    windows: Iterable[int],
    show_components: bool,
    show_diagnostics: bool,
) -> list[DispersionChartGroupDefinition]:
    normalized_windows = _normalize_windows(windows)
    definitions: list[DispersionChartGroupDefinition] = [
        {
            "key": "lockstep_score",
            "title": "Lockstep Score",
            "y_label": "Score",
            "tickformat": ".0f",
            "reference_lines": [25.0, 50.0, 75.0],
            "metric_keys": [
                "disp_lockstep_score",
                "disp_lockstep_score_ma",
                *[f"disp_lockstep_{window}d" for window in normalized_windows],
            ],
        }
    ]

    if show_components:
        definitions.extend(
            [
                {
                    "key": "components",
                    "title": "Co-Movement Components (21D)",
                    "y_label": "Component",
                    "tickformat": ".2f",
                    "reference_lines": [0.0, 0.5],
                    "metric_keys": [
                        "disp_corr_mean_21d",
                        "disp_pca_pc1_share_21d",
                        "disp_sign_consensus_21d",
                    ],
                },
                {
                    "key": "cross_sectional_dispersion",
                    "title": "Cross-Sectional Dispersion (XS MAD Z, 21D)",
                    "y_label": "MAD Z",
                    "tickformat": ".2f",
                    "reference_lines": [],
                    "metric_keys": ["disp_xs_mad_z_21d"],
                },
            ]
        )

    if show_diagnostics:
        definitions.extend(
            [
                {
                    "key": "data_quality_counts",
                    "title": "Data Quality Counts",
                    "y_label": "Count",
                    "tickformat": None,
                    "reference_lines": [],
                    "metric_keys": [
                        "disp_valid_ticker_count",
                        "disp_observation_count",
                    ],
                },
                {
                    "key": "reliability",
                    "title": "Reliability by Window",
                    "y_label": "Reliability",
                    "tickformat": ".0%",
                    "reference_lines": [0.5, 1.0],
                    "metric_keys": [
                        f"disp_reliability_{window}d" for window in normalized_windows
                    ],
                },
            ]
        )

    return definitions


def _append_lockstep_smoothing_series(
    series_payloads: Iterable[AggregateSeries],
    *,
    smoothing_days: int,
) -> list[AggregateSeries]:
    copied_series = list(series_payloads)
    lockstep_series = next(
        (
            series
            for series in copied_series
            if series["metric_key"] == "disp_lockstep_score"
        ),
        None,
    )
    if lockstep_series is None or len(lockstep_series["points"]) < smoothing_days:
        return copied_series

    smoothed_points: list[AggregateSeriesPoint] = []
    points = lockstep_series["points"]
    for index, point in enumerate(points):
        window_start = max(0, index - smoothing_days + 1)
        window_points = points[window_start : index + 1]
        numeric_values = [
            float(window_point["value"])
            for window_point in window_points
            if window_point["value"] is not None
        ]
        if not numeric_values:
            smoothed_points.append({"date": point["date"], "value": None})
            continue
        smoothed_points.append(
            {
                "date": point["date"],
                "value": sum(numeric_values) / len(numeric_values),
            }
        )

    copied_series.append(
        {
            "metric_key": "disp_lockstep_score_ma",
            "label": f"Lockstep Score MA {smoothing_days}",
            "points": smoothed_points,
            "style": {"color": "#2f80ed", "width": 2, "dash": "dot"},
        }
    )
    return copied_series


def _filter_series_by_keys(
    series_payloads: Iterable[AggregateSeries],
    *,
    metric_keys: Iterable[str],
) -> list[AggregateSeries]:
    ordered_keys = list(metric_keys)
    series_by_key = {series["metric_key"]: series for series in series_payloads}
    return [
        series_by_key[key]
        for key in ordered_keys
        if key in series_by_key
    ]


def _collect_panel_dates(panels: Iterable[DispersionSeriesPanel]) -> list[str]:
    seen: set[str] = set()
    ordered_dates: list[str] = []
    for panel in panels:
        for series in panel["series"]:
            for point in series["points"]:
                date_value = point["date"]
                if date_value in seen:
                    continue
                seen.add(date_value)
                ordered_dates.append(date_value)
    ordered_dates.sort()
    return ordered_dates


def _filter_series_dates(
    series: AggregateSeries,
    allowed_dates: set[str],
) -> AggregateSeries:
    filtered_points = [
        point for point in series["points"] if point["date"] in allowed_dates
    ]
    filtered_series: AggregateSeries = {
        "metric_key": series["metric_key"],
        "label": series["label"],
        "points": filtered_points,
    }
    if "style" in series:
        filtered_series["style"] = series["style"]
    return filtered_series


def _trim_series_payloads(
    series_payloads: Iterable[AggregateSeries],
    max_points: int,
) -> list[AggregateSeries]:
    trimmed: list[AggregateSeries] = []
    for series in series_payloads:
        points = series["points"]
        if len(points) > max_points:
            points = points[-max_points:]
        trimmed_series: AggregateSeries = {
            "metric_key": series["metric_key"],
            "label": series["label"],
            "points": points,
        }
        if "style" in series:
            trimmed_series["style"] = series["style"]
        trimmed.append(trimmed_series)
    return trimmed


def _normalize_windows(windows: Iterable[int] | None) -> list[int]:
    source = list(windows) if windows is not None else list(DEFAULT_DISPERSION_WINDOWS)
    normalized: list[int] = []
    seen: set[int] = set()
    for value in source:
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

