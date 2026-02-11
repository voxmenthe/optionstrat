from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Iterable, TYPE_CHECKING

from app.security_scan.data_fetcher import MarketDataFetcher
from app.security_scan.reporting.aggregate_series import (
    AggregateSeries,
    assemble_aggregate_series,
    build_aggregate_series_definitions,
    collect_aggregate_metric_keys,
)
from app.security_scan.storage import fetch_security_aggregate_series
from app.services.market_data import MarketDataService

if TYPE_CHECKING:
    import plotly.graph_objects as go

BENCHMARK_TICKERS = ("QQQ", "SPY", "IWM")
BENCHMARK_TICKFORMAT = ".2%"
BENCHMARK_CHANGE_COLORS = {3: "#2f80ed", 1: "#27ae60"}


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
    net_advances_secondary_ma_days: int = 8,
    advance_pct_avg_smoothing_days: int = 3,
    roc_breadth_avg_smoothing_days: int = 3,
    market_data_service: MarketDataService | None = None,
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

    date_bounds = _series_date_bounds(series_payloads)
    benchmark_start = start_date or date_bounds[0]
    benchmark_end = end_date or date_bounds[1]
    benchmark_pct_maps: dict[int, dict[str, float]] = {}
    benchmark_trading_dates: set[str] = set()
    if benchmark_start and benchmark_end:
        benchmark_pct_maps, benchmark_trading_dates = _build_benchmark_change_maps(
            start_date=benchmark_start,
            end_date=benchmark_end,
            interval=interval,
            market_data_service=market_data_service,
            lookbacks=(3, 1),
        )

    return render_aggregate_charts_html(
        series_payloads,
        benchmark_pct_maps=benchmark_pct_maps,
        benchmark_trading_dates=benchmark_trading_dates,
        net_advances_ma_days=net_advances_ma_days,
        net_advances_secondary_ma_days=net_advances_secondary_ma_days,
        advance_pct_avg_smoothing_days=advance_pct_avg_smoothing_days,
        roc_breadth_avg_smoothing_days=roc_breadth_avg_smoothing_days,
    )


def render_aggregate_charts_html(
    series_payloads: Iterable[AggregateSeries],
    *,
    benchmark_pct_maps: dict[int, dict[str, float]],
    benchmark_trading_dates: set[str],
    net_advances_ma_days: int = 18,
    net_advances_secondary_ma_days: int = 8,
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
    net_advances_secondary_ma_series = None
    if net_advances_series and net_advances_series["points"]:
        net_advances_ma_series = _build_moving_average_series(
            net_advances_series,
            window=net_advances_ma_days,
            metric_key="net_advances_ma",
            label=f"Net Advances MA {net_advances_ma_days}",
        )
        if net_advances_secondary_ma_days != net_advances_ma_days:
            net_advances_secondary_ma_series = _build_moving_average_series(
                net_advances_series,
                window=net_advances_secondary_ma_days,
                metric_key="net_advances_secondary_ma",
                label=f"Net Advances MA {net_advances_secondary_ma_days}",
                style={"color": "#9b51e0", "width": 2, "dash": "dot"},
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
                net_advances_secondary_ma_series,
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

        base_dates = _collect_series_dates(cleaned_series)
        if benchmark_trading_dates:
            filtered_dates = [date for date in base_dates if date in benchmark_trading_dates]
            if filtered_dates:
                base_dates = filtered_dates
        allowed_dates = set(base_dates)
        filtered_series = [
            _filter_series_dates(series, allowed_dates)
            for series in cleaned_series
        ]

        benchmark_series_3d = _build_benchmark_series_for_dates(
            benchmark_pct_maps.get(3, {}),
            base_dates,
            lookback=3,
        )
        benchmark_series_1d = _build_benchmark_series_for_dates(
            benchmark_pct_maps.get(1, {}),
            base_dates,
            lookback=1,
        )

        figure = build_timeseries_figure(
            title=title,
            top_series=benchmark_series_3d,
            middle_series=benchmark_series_1d,
            top_y_label="Benchmark 3D % Chg",
            middle_y_label="Benchmark 1D % Chg",
            top_y_tickformat=BENCHMARK_TICKFORMAT,
            middle_y_tickformat=BENCHMARK_TICKFORMAT,
            series=filtered_series,
            y_label=y_label,
            y_tickformat=tickformat,
            reference_lines=reference_lines,
            x_categories=base_dates,
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
    top_series: AggregateSeries | None = None,
    middle_series: AggregateSeries | None = None,
    top_y_label: str | None = None,
    middle_y_label: str | None = None,
    top_y_tickformat: str | None = None,
    middle_y_tickformat: str | None = None,
    series: Iterable[AggregateSeries],
    y_label: str | None = None,
    y_tickformat: str | None = None,
    reference_lines: Iterable[float] | None = None,
    x_categories: Iterable[str] | None = None,
) -> "go.Figure":
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if top_series is None:
        top_series = {
            "metric_key": "benchmark_pct_change_3d",
            "label": "Benchmark 3D % Chg (QQQ+SPY+IWM)",
            "points": [],
        }
    if middle_series is None:
        middle_series = {
            "metric_key": "benchmark_pct_change_1d",
            "label": "Benchmark 1D % Chg (QQQ+SPY+IWM)",
            "points": [],
        }

    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.25, 0.25, 0.5],
    )

    _add_series_traces(figure, [top_series], row=1, col=1)
    _add_series_traces(figure, [middle_series], row=2, col=1)
    _add_series_traces(figure, list(series), row=3, col=1)

    figure.update_layout(
        # Chart titles are rendered by the surrounding HTML (<h3>) to avoid
        # duplicate title text inside the Plotly canvas.
        title=None,
        template="plotly_white",
        height=620,
        margin=dict(l=90, r=30, t=48, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        # Make it easier to compare series at the same date by showing a shared
        # hover readout + a vertical cursor line ("crosshair").
        hovermode="x unified",
        spikedistance=-1,
    )
    figure.update_xaxes(
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikethickness=1,
        spikecolor="rgba(15, 23, 42, 0.55)",
    )
    figure.update_xaxes(title_text="Date", row=3, col=1)
    figure.update_xaxes(showticklabels=False, row=1, col=1)
    figure.update_xaxes(showticklabels=False, row=2, col=1)
    category_array: list[str] | None = None
    if x_categories:
        category_array = list(x_categories)
        figure.update_xaxes(
            type="category",
            categoryorder="array",
            categoryarray=category_array,
            row=1,
            col=1,
        )
        figure.update_xaxes(
            type="category",
            categoryorder="array",
            categoryarray=category_array,
            row=2,
            col=1,
        )
        figure.update_xaxes(
            type="category",
            categoryorder="array",
            categoryarray=category_array,
            row=3,
            col=1,
        )
        # Use one shared vertical grid across all rows to avoid broken segments.
        figure.update_xaxes(showgrid=False, row=1, col=1)
        figure.update_xaxes(showgrid=False, row=2, col=1)
        figure.update_xaxes(showgrid=False, row=3, col=1)
    figure.update_yaxes(title_text=top_y_label, row=1, col=1)
    figure.update_yaxes(title_text=middle_y_label, row=2, col=1)
    figure.update_yaxes(title_text=y_label, row=3, col=1)
    figure.update_yaxes(automargin=True, title_standoff=10, row=1, col=1)
    figure.update_yaxes(automargin=True, title_standoff=10, row=2, col=1)
    figure.update_yaxes(automargin=True, title_standoff=10, row=3, col=1)
    if top_y_tickformat:
        figure.update_yaxes(tickformat=top_y_tickformat, row=1, col=1)
    if middle_y_tickformat:
        figure.update_yaxes(tickformat=middle_y_tickformat, row=2, col=1)
    if y_tickformat:
        figure.update_yaxes(tickformat=y_tickformat, row=3, col=1)
    shapes = list(figure.layout.shapes) if figure.layout.shapes else []
    if category_array:
        shapes.extend(_build_full_height_vertical_grid_shapes(category_array))
    if reference_lines:
        for line_value in reference_lines:
            shapes.append(
                dict(
                    type="line",
                    xref="paper",
                    x0=0,
                    x1=1,
                    yref="y3",
                    y0=line_value,
                    y1=line_value,
                    line=dict(color="rgba(0, 0, 0, 0.35)", width=1),
                    layer="below",
                )
            )
    if shapes:
        figure.update_layout(shapes=shapes)
    return figure


def _build_full_height_vertical_grid_shapes(
    x_categories: Iterable[str],
) -> list[dict[str, object]]:
    return [
        {
            "type": "line",
            "xref": "x3",
            "x0": category_value,
            "x1": category_value,
            "yref": "paper",
            "y0": 0,
            "y1": 1,
            # Plotly's "below" layer can render behind subplot backgrounds in some
            # environments, making these lines effectively invisible. We draw
            # them "above" with low opacity so they stay visible while remaining
            # subtle across all three subplots.
            "line": {"color": "rgba(71, 85, 105, 0.30)", "width": 1},
            "layer": "above",
        }
        for category_value in x_categories
    ]


def _add_series_traces(
    figure: "go.Figure",
    series_list: Iterable[AggregateSeries],
    *,
    row: int,
    col: int,
) -> None:
    import plotly.graph_objects as go

    for series_item in series_list:
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
            ),
            row=row,
            col=col,
        )


def _series_date_bounds(
    series_payloads: Iterable[AggregateSeries],
) -> tuple[str | None, str | None]:
    min_date = None
    max_date = None
    for series in series_payloads:
        for point in series.get("points", []):
            date_value = point.get("date")
            if not date_value:
                continue
            if min_date is None or date_value < min_date:
                min_date = date_value
            if max_date is None or date_value > max_date:
                max_date = date_value
    return min_date, max_date


def _collect_series_dates(series_payloads: Iterable[AggregateSeries]) -> list[str]:
    dates: set[str] = set()
    for series in series_payloads:
        for point in series.get("points", []):
            date_value = point.get("date")
            if date_value:
                dates.add(str(date_value))
    return sorted(dates)


def _filter_series_dates(
    series: AggregateSeries,
    allowed_dates: set[str],
) -> AggregateSeries:
    points = [
        point
        for point in series.get("points", [])
        if point.get("date") in allowed_dates
    ]
    filtered_series: AggregateSeries = {
        "metric_key": series["metric_key"],
        "label": series["label"],
        "points": points,
    }
    if "style" in series:
        filtered_series["style"] = series["style"]
    return filtered_series


def _build_benchmark_change_maps(
    *,
    start_date: str,
    end_date: str,
    interval: str,
    market_data_service: MarketDataService | None = None,
    lookbacks: Iterable[int] = (3, 1),
) -> tuple[dict[int, dict[str, float]], set[str]]:
    start_dt = _parse_date(start_date)
    end_dt = _parse_date(end_date)
    if start_dt is None or end_dt is None:
        return {}, set()

    fetcher = MarketDataFetcher(market_data_service=market_data_service)
    max_lookback = max(lookbacks) if lookbacks else 0
    fetch_start = start_dt - timedelta(days=max_lookback * 4)
    end_dt_inclusive = end_dt + timedelta(days=1)
    closes_by_ticker: dict[str, dict[str, float]] = {}
    ordered_dates_by_ticker: dict[str, list[str]] = {}
    for ticker in BENCHMARK_TICKERS:
        prices = fetcher.fetch_historical_prices(
            ticker=ticker,
            start_date=fetch_start,
            end_date=end_dt_inclusive,
            interval=interval,
        )
        closes = _close_by_date(prices)
        closes_by_ticker[ticker] = closes
        ordered_dates_by_ticker[ticker] = sorted(closes)

    if not closes_by_ticker:
        return {}, set()

    trading_date_sets = [
        set(values.keys()) for values in closes_by_ticker.values() if values
    ]
    trading_dates = (
        set.intersection(*trading_date_sets) if trading_date_sets else set()
    )
    trading_dates = {
        date_value
        for date_value in trading_dates
        if start_date <= date_value <= end_date
    }

    pct_by_lookback: dict[int, dict[str, float]] = {}
    for lookback in lookbacks:
        pct_by_ticker: dict[str, dict[str, float]] = {}
        for ticker in BENCHMARK_TICKERS:
            pct_by_ticker[ticker] = _pct_change_by_date(
                ordered_dates_by_ticker[ticker],
                closes_by_ticker[ticker],
                lookback,
            )

        pct_by_date: dict[str, float] = {}
        date_sets = [
            set(pct_by_ticker[ticker].keys()) for ticker in BENCHMARK_TICKERS
        ]
        if date_sets:
            shared_dates = set.intersection(*date_sets)
            for date_value in shared_dates:
                if date_value < start_date or date_value > end_date:
                    continue
                values = [
                    pct_by_ticker[ticker][date_value] for ticker in BENCHMARK_TICKERS
                ]
                pct_by_date[date_value] = sum(values)
        pct_by_lookback[lookback] = pct_by_date

    return pct_by_lookback, trading_dates


def _build_benchmark_series_for_dates(
    pct_by_date: dict[str, float],
    dates: Iterable[str],
    *,
    lookback: int,
) -> AggregateSeries:
    points = [
        {"date": date_value, "value": pct_by_date.get(date_value)}
        for date_value in dates
    ]
    return {
        "metric_key": f"benchmark_pct_change_{lookback}d",
        "label": f"Benchmark {lookback}D % Chg (QQQ+SPY+IWM)",
        "points": points,
        "style": {
            "color": BENCHMARK_CHANGE_COLORS.get(lookback, "#2f80ed"),
            "width": 2,
        },
    }


def _pct_change_by_date(
    ordered_dates: list[str],
    closes_by_date: dict[str, float],
    lookback: int,
) -> dict[str, float]:
    pct_by_date: dict[str, float] = {}
    if lookback <= 0:
        return pct_by_date
    for index, date_value in enumerate(ordered_dates):
        if index < lookback:
            continue
        prior_date = ordered_dates[index - lookback]
        prior_close = closes_by_date.get(prior_date)
        current_close = closes_by_date.get(date_value)
        if prior_close is None or current_close is None:
            continue
        if prior_close == 0:
            continue
        pct_by_date[date_value] = (current_close - prior_close) / prior_close
    return pct_by_date


def _close_by_date(prices: Iterable[dict[str, object]]) -> dict[str, float]:
    closes: dict[str, float] = {}
    for row in prices:
        if not isinstance(row, dict):
            continue
        date_value = row.get("date")
        close_value = row.get("close")
        if not date_value or close_value is None:
            continue
        try:
            closes[str(date_value)] = float(close_value)
        except (TypeError, ValueError):
            continue
    return closes


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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
