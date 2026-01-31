from __future__ import annotations

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
            trimmed.append(
                {
                    "metric_key": series["metric_key"],
                    "label": series["label"],
                    "points": points,
                }
            )
        series_payloads = trimmed

    return render_aggregate_charts_html(series_payloads)


def render_aggregate_charts_html(series_payloads: Iterable[AggregateSeries]) -> str:
    import plotly.graph_objects as go
    import plotly.io as pio

    ordered_series = list(series_payloads)
    series_by_key = {series["metric_key"]: series for series in ordered_series}

    def filter_series(predicate: Callable[[str], bool]) -> list[AggregateSeries]:
        return [series for series in ordered_series if predicate(series["metric_key"])]

    chart_groups = [
        (
            "Advance/Decline Counts (t-1)",
            [
                series_by_key.get("advances"),
                series_by_key.get("declines"),
                series_by_key.get("unchanged"),
                series_by_key.get("net_advances"),
            ],
            "Count",
            None,
        ),
        (
            "Advance % (t-1 + lookbacks)",
            filter_series(
                lambda key: key == "advance_pct"
                or (key.startswith("ad_") and key.endswith("_advance_pct"))
            ),
            "Percent",
            ".0%",
        ),
        (
            "MA Breadth % Above",
            filter_series(lambda key: key.startswith("ma_") and key.endswith("_above_pct")),
            "Percent",
            ".0%",
        ),
        (
            "ROC Breadth % Greater",
            filter_series(lambda key: key.startswith("roc_") and key.endswith("_gt_pct")),
            "Percent",
            ".0%",
        ),
    ]

    html_parts: list[str] = []
    include_plotlyjs: str | bool = "inline"

    for title, series_list, y_label, tickformat in chart_groups:
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
) -> "go.Figure":
    import plotly.graph_objects as go

    figure = go.Figure()
    for series_item in series:
        points = series_item["points"]
        if not points:
            continue
        figure.add_trace(
            go.Scatter(
                x=[point["date"] for point in points],
                y=[point["value"] for point in points],
                mode="lines",
                name=series_item["label"],
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
    return figure
