from __future__ import annotations

from collections import defaultdict
from typing import Callable, Iterable, TYPE_CHECKING

from app.security_scan.reporting.aggregate_series import (
    AggregateSeries,
    assemble_aggregate_series,
    build_aggregate_series_definitions,
    collect_aggregate_metric_keys,
)
from app.security_scan.storage import fetch_security_aggregate_series

if TYPE_CHECKING:
    import plotly.graph_objects as go


def build_aggregate_charts_html(
    *,
    set_hash: str,
    interval: str,
    start_date: str | None,
    end_date: str | None,
    advance_decline_lookbacks: Iterable[int] | None,
    plot_lookbacks: Iterable[int] | None = None,
    max_points: int | None = None,
    net_advances_ma_days: int = 18,
    advance_pct_avg_smoothing_days: int = 3,
    roc_breadth_avg_smoothing_days: int = 3,
) -> str:
    definitions = build_aggregate_series_definitions(
        plot_lookbacks or advance_decline_lookbacks
    )
    metric_keys = collect_aggregate_metric_keys(definitions)
    rows = fetch_security_aggregate_series(
        set_hash=set_hash,
        metric_keys=metric_keys,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )
    if not rows:
        return ""

    series_payloads = assemble_aggregate_series(rows, definitions)
    if max_points:
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
        series_payloads = trimmed

    return render_aggregate_charts_html(
        series_payloads,
        net_advances_ma_days=net_advances_ma_days,
        advance_pct_avg_smoothing_days=advance_pct_avg_smoothing_days,
        roc_breadth_avg_smoothing_days=roc_breadth_avg_smoothing_days,
    )


def render_aggregate_charts_html(
    series_payloads: Iterable[AggregateSeries],
    *,
    net_advances_ma_days: int = 18,
    advance_pct_avg_smoothing_days: int = 3,
    roc_breadth_avg_smoothing_days: int = 3,
) -> str:
    import plotly.graph_objects as go
    import plotly.io as pio

    ordered_series = list(series_payloads)
    series_by_key = {series["metric_key"]: series for series in ordered_series}

    def filter_series(predicate: Callable[[str], bool]) -> list[AggregateSeries]:
        return [series for series in ordered_series if predicate(series["metric_key"])]

    net_advances_series = series_by_key.get("net_advances")
    net_advances_ma_series = None
    if net_advances_series and net_advances_series["points"]:
        net_advances_ma_series = _build_moving_average_series(
            net_advances_series,
            window=net_advances_ma_days,
            metric_key="net_advances_ma",
            label=f"Net Advances MA {net_advances_ma_days}",
        )

    advance_pct_series = filter_series(
        lambda key: key == "advance_pct"
        or (key.startswith("ad_") and key.endswith("_advance_pct"))
    )
    advance_pct_avg_series = _build_smoothed_average_series(
        advance_pct_series,
        metric_key="advance_pct_avg",
        label="Advance % Avg",
        smoothing_days=advance_pct_avg_smoothing_days,
        style={"color": "#f2c94c", "width": 3},
    )

    roc_series = filter_series(lambda key: key.startswith("roc_") and key.endswith("_gt_pct"))
    roc_avg_series = _build_smoothed_average_series(
        roc_series,
        metric_key="roc_breadth_avg",
        label="ROC Breadth Avg",
        smoothing_days=roc_breadth_avg_smoothing_days,
    )
    scl_net_series = series_by_key.get("scl_5bar_net")

    percent_reference = 0.5
    chart_groups = [
        (
            "Advance/Decline Counts (t-1)",
            [
                net_advances_series,
                net_advances_ma_series,
            ],
            "Count",
            None,
            [0.0],
        ),
        (
            "Advance % (t-1 + lookbacks)",
            advance_pct_series + ([advance_pct_avg_series] if advance_pct_avg_series else []),
            "Percent",
            ".0%",
            [percent_reference],
        ),
        (
            "MA Breadth % Above",
            filter_series(lambda key: key.startswith("ma_") and key.endswith("_above_pct")),
            "Percent",
            ".0%",
            [percent_reference],
        ),
        (
            "ROC Breadth % Greater",
            roc_series + ([roc_avg_series] if roc_avg_series else []),
            "Percent",
            ".0%",
            [percent_reference],
        ),
        (
            "SCL 5-Bar High - Low",
            [scl_net_series],
            "Count",
            None,
            [0.0],
        ),
    ]

    html_parts: list[str] = []
    include_plotlyjs: str | bool = "inline"

    for title, series_list, y_label, tickformat, reference_lines in chart_groups:
        cleaned_series = [
            series for series in series_list if series and series["points"]
        ]
        if not cleaned_series:
            continue

        figure = build_timeseries_figure(
            title=title,
            series=cleaned_series,
            y_label=y_label,
            y_tickformat=tickformat,
            reference_lines=reference_lines,
        )
        chart_html = pio.to_html(
            figure,
            include_plotlyjs=include_plotlyjs,
            full_html=False,
        )
        include_plotlyjs = False
        html_parts.append(
            "<div class=\"chart-block\">\n"
            f"<h3>{title}</h3>\n"
            f"{chart_html}\n"
            "</div>"
        )

    return "\n".join(html_parts)


def build_timeseries_figure(
    *,
    title: str,
    series: Iterable[AggregateSeries],
    y_label: str | None = None,
    y_tickformat: str | None = None,
    reference_lines: Iterable[float] | None = None,
) -> "go.Figure":
    import plotly.graph_objects as go

    figure = go.Figure()
    for series_item in series:
        points = series_item["points"]
        if not points:
            continue
        mode = "lines" if len(points) > 1 else "markers"
        line: dict[str, object] = {}
        style = series_item.get("style")
        if style:
            if "color" in style:
                line["color"] = style["color"]
            if "width" in style:
                line["width"] = style["width"]
            if "dash" in style:
                line["dash"] = style["dash"]

        trace_kwargs: dict[str, object] = {}
        if line:
            trace_kwargs["line"] = line

        figure.add_trace(
            go.Scatter(
                x=[point["date"] for point in points],
                y=[point["value"] for point in points],
                mode=mode,
                name=series_item["label"],
                **trace_kwargs,
            )
        )

    figure.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_label,
        template="plotly_white",
        height=360,
        margin=dict(l=50, r=30, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    if y_tickformat:
        figure.update_yaxes(tickformat=y_tickformat)
    if reference_lines:
        shapes = list(figure.layout.shapes) if figure.layout.shapes else []
        for line_value in reference_lines:
            shapes.append(
                dict(
                    type="line",
                    xref="paper",
                    x0=0,
                    x1=1,
                    yref="y",
                    y0=line_value,
                    y1=line_value,
                    line=dict(color="rgba(0, 0, 0, 0.35)", width=1),
                    layer="below",
                )
            )
        figure.update_layout(shapes=shapes)
    return figure


def _build_smoothed_average_series(
    series_list: Iterable[AggregateSeries],
    *,
    metric_key: str,
    label: str,
    smoothing_days: int,
    style: dict[str, object] | None = None,
) -> AggregateSeries | None:
    series_with_points = [series for series in series_list if series and series["points"]]
    if not series_with_points:
        return None
    averaged_points = _average_points_by_date(series_with_points)
    if not averaged_points:
        return None
    smoothed_points = _moving_average_points(averaged_points, smoothing_days)
    avg_series: AggregateSeries = {
        "metric_key": metric_key,
        "label": f"{label} (MA {smoothing_days})",
        "points": smoothed_points,
    }
    if style:
        avg_series["style"] = style
    return avg_series


def _build_moving_average_series(
    base_series: AggregateSeries,
    *,
    window: int,
    metric_key: str,
    label: str,
    style: dict[str, object] | None = None,
) -> AggregateSeries:
    points = _moving_average_points(base_series["points"], window)
    ma_series: AggregateSeries = {
        "metric_key": metric_key,
        "label": label,
        "points": points,
    }
    if style:
        ma_series["style"] = style
    return ma_series


def _average_points_by_date(
    series_list: Iterable[AggregateSeries],
) -> list[dict[str, float | None]]:
    values_by_date: dict[str, list[float]] = defaultdict(list)
    for series in series_list:
        for point in series["points"]:
            value = point["value"]
            if value is None:
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            values_by_date[point["date"]].append(numeric_value)

    averaged_points: list[dict[str, float | None]] = []
    for date in sorted(values_by_date):
        values = values_by_date[date]
        averaged_points.append(
            {
                "date": date,
                "value": sum(values) / len(values) if values else None,
            }
        )
    return averaged_points


def _moving_average_points(
    points: Iterable[dict[str, float | None]],
    window: int,
) -> list[dict[str, float | None]]:
    normalized_points = list(points)
    if len(normalized_points) > 1:
        normalized_points.sort(key=lambda point: point["date"])
    if window <= 1:
        return [
            {"date": point["date"], "value": point["value"]}
            for point in normalized_points
        ]

    averaged: list[dict[str, float | None]] = []
    for index, point in enumerate(normalized_points):
        start_index = max(0, index - window + 1)
        window_values = [
            normalized_points[offset]["value"]
            for offset in range(start_index, index + 1)
            if normalized_points[offset]["value"] is not None
        ]
        if window_values:
            average_value = sum(float(value) for value in window_values) / len(
                window_values
            )
        else:
            average_value = None
        averaged.append({"date": point["date"], "value": average_value})
    return averaged
