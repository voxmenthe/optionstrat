from __future__ import annotations

from pathlib import Path

from app.security_scan.aggregates import compute_breadth
from app.security_scan.config_loader import load_security_scan_config
from app.security_scan.db import SecurityAggregateValue
from app.security_scan.indicators.roc_aggregate import evaluate as evaluate_roc_aggregate
from app.security_scan.indicators.roc import evaluate as evaluate_roc
from app.security_scan.reporting.aggregate_charts import render_aggregate_charts_html
from app.security_scan.reporting.aggregate_series import (
    assemble_aggregate_series,
    build_aggregate_series_definitions,
)
from app.security_scan.reporting.markdown_report import render_markdown_report
from app.security_scan.reporting.html_report import render_html_report


def test_load_security_scan_config_instances(tmp_path: Path) -> None:
    (tmp_path / "securities.toml").write_text(
        """
[tickers]
list = ["AAPL"]

[scan_defaults]
lookback_days = 30
interval = "day"
""".strip()
    )
    (tmp_path / "scan_settings.toml").write_text(
        """
[indicators]
instances = [
  { id = "roc", roc_lookback = 12, criteria = [{ type = "crossover", series = "roc", level = 0, direction = "both" }] }
]

[aggregates]
advance_decline_lookbacks = [1, 5, 10]

[report]
html = true
plot_lookbacks = [1, 5]
max_points = 120
""".strip()
    )

    config = load_security_scan_config(tmp_path)
    assert config.tickers == ["AAPL"]
    assert len(config.indicator_instances) == 1
    instance = config.indicator_instances[0]
    assert instance.id == "roc"
    assert instance.settings["roc_lookback"] == 12
    assert isinstance(instance.settings["criteria"], list)
    assert config.advance_decline_lookbacks == [1, 5, 10]
    assert config.report_html is True
    assert config.report_plot_lookbacks == [1, 5]
    assert config.report_max_points == 120


def test_compute_breadth_counts() -> None:
    summaries = [
        {"last_close": 10, "prior_close": 9},
        {"last_close": 8, "prior_close": 9},
        {"last_close": 5, "prior_close": 5},
        {"last_close": None, "prior_close": 5},
    ]
    aggregates = compute_breadth(summaries)
    assert aggregates["advances"] == 1
    assert aggregates["declines"] == 1
    assert aggregates["unchanged"] == 1
    assert aggregates["missing_ticker_count"] == 1


def test_compute_breadth_ma_roc_metrics() -> None:
    summaries = [
        {
            "last_close": 110,
            "prior_close": 100,
            "metric_values": {
                "sma:13": 100,
                "sma:28": 110,
                "sma:46": 120,
                "sma:8:shift=5": 105,
                "roc:17": 0.1,
                "roc:17:shift=5": 0.05,
                "roc:27": 0.02,
                "roc:27:shift=4": 0.02,
            },
        },
        {
            "last_close": 90,
            "prior_close": 100,
            "metric_values": {
                "sma:13": 100,
                "sma:28": None,
                "sma:46": 80,
                "sma:8:shift=5": 90,
                "roc:17": -0.1,
                "roc:17:shift=5": -0.2,
                "roc:27": None,
                "roc:27:shift=4": None,
            },
        },
    ]
    aggregates = compute_breadth(summaries)

    assert aggregates["ma_13_above_count"] == 1
    assert aggregates["ma_13_below_count"] == 1
    assert aggregates["ma_13_valid_count"] == 2
    assert aggregates["ma_28_equal_count"] == 1
    assert aggregates["ma_28_missing_count"] == 1
    assert aggregates["ma_46_above_count"] == 1
    assert aggregates["ma_46_below_count"] == 1
    assert aggregates["ma_8_shift_5_equal_count"] == 1
    assert aggregates["ma_8_shift_5_above_count"] == 1

    assert aggregates["roc_17_vs_5_gt_count"] == 2
    assert aggregates["roc_17_vs_5_valid_count"] == 2
    assert aggregates["roc_27_vs_4_eq_count"] == 1
    assert aggregates["roc_27_vs_4_missing_count"] == 1

    assert aggregates["ma_13_above_pct"] == 0.5
    assert aggregates["roc_17_vs_5_gt_pct"] == 1.0
    assert aggregates["roc_27_vs_4_eq_pct"] == 1.0


def test_compute_breadth_multiple_lookbacks() -> None:
    summaries = [
        {
            "last_close": 110,
            "prior_close": 100,
            "close_by_offset": {5: 90},
        },
        {
            "last_close": 90,
            "prior_close": 100,
            "close_by_offset": {5: 95},
        },
        {
            "last_close": 100,
            "prior_close": None,
            "close_by_offset": {5: None},
        },
    ]
    aggregates = compute_breadth(summaries, advance_decline_lookbacks=[1, 5])

    assert aggregates["ad_5_advances"] == 1
    assert aggregates["ad_5_declines"] == 1
    assert aggregates["ad_5_unchanged"] == 0
    assert aggregates["ad_5_missing_count"] == 1
    assert aggregates["ad_5_valid_count"] == 2
    assert aggregates["ad_5_net_advances"] == 0
    assert aggregates["ad_5_advance_decline_ratio"] == 1.0
    assert aggregates["ad_5_advance_pct"] == 0.5


def test_build_aggregate_series_definitions_includes_lookbacks() -> None:
    definitions = build_aggregate_series_definitions([1, 5, 10])
    metric_keys = [definition["metric_key"] for definition in definitions]
    assert "advance_pct" in metric_keys
    assert "ad_5_advance_pct" in metric_keys
    assert "ad_10_advance_pct" in metric_keys


def test_assemble_aggregate_series_orders_points() -> None:
    rows = [
        SecurityAggregateValue(
            set_hash="abc",
            as_of_date="2025-01-02",
            interval="day",
            metric_key="advance_pct",
            value=0.6,
        ),
        SecurityAggregateValue(
            set_hash="abc",
            as_of_date="2025-01-01",
            interval="day",
            metric_key="advance_pct",
            value=0.4,
        ),
    ]
    definitions = build_aggregate_series_definitions([1])
    series_payloads = assemble_aggregate_series(rows, definitions)
    advance_series = next(
        series for series in series_payloads if series["metric_key"] == "advance_pct"
    )
    assert [point["date"] for point in advance_series["points"]] == [
        "2025-01-01",
        "2025-01-02",
    ]


def test_render_aggregate_charts_html_embeds_plotly() -> None:
    series_payloads = [
        {
            "metric_key": "advance_pct",
            "label": "Advance %",
            "points": [{"date": "2025-01-01", "value": 0.5}],
        }
    ]
    html = render_aggregate_charts_html(series_payloads)
    assert "Plotly.newPlot" in html


def test_roc_crossover_up_signal() -> None:
    prices = [
        {"date": "2025-01-01", "close": 100},
        {"date": "2025-01-02", "close": 90},
        {"date": "2025-01-03", "close": 95},
    ]
    settings = {
        "roc_lookback": 1,
        "criteria": [
            {"type": "crossover", "series": "roc", "level": 0, "direction": "both"}
        ],
    }
    signals = evaluate_roc(prices, settings)
    assert len(signals) == 1
    assert signals[0].signal_type == "crossover_up"
    assert signals[0].signal_date == "2025-01-03"


def test_roc_crossover_multiple_hits() -> None:
    prices = [
        {"date": "2025-01-01", "close": 100},
        {"date": "2025-01-02", "close": 90},
        {"date": "2025-01-03", "close": 110},
        {"date": "2025-01-04", "close": 90},
        {"date": "2025-01-05", "close": 110},
    ]
    settings = {
        "roc_lookback": 1,
        "criteria": [
            {"type": "crossover", "series": "roc", "level": 0, "direction": "both"}
        ],
    }
    signals = evaluate_roc(prices, settings)
    assert [signal.signal_type for signal in signals] == [
        "crossover_up",
        "crossover_down",
        "crossover_up",
    ]
    assert [signal.signal_date for signal in signals] == [
        "2025-01-03",
        "2025-01-04",
        "2025-01-05",
    ]


def test_roc_aggregate_cross_above_below() -> None:
    prices = [
        {"date": "2025-01-01", "close": 100},
        {"date": "2025-01-02", "close": 110},
        {"date": "2025-01-03", "close": 125},
        {"date": "2025-01-04", "close": 130},
        {"date": "2025-01-05", "close": 140},
        {"date": "2025-01-06", "close": 141},
    ]
    settings = {
        "roc_lookbacks": [1],
        "roc_change_lookbacks": [1],
        "ma_short": 2,
        "ma_long": 2,
    }
    signals = evaluate_roc_aggregate(prices, settings)
    assert [signal.signal_type for signal in signals] == [
        "cross_above_both",
        "cross_below_both",
    ]
    assert [signal.signal_date for signal in signals] == [
        "2025-01-05",
        "2025-01-06",
    ]


def test_roc_aggregate_insufficient_data() -> None:
    prices = [
        {"date": "2025-01-01", "close": 100},
        {"date": "2025-01-02", "close": 110},
        {"date": "2025-01-03", "close": 105},
    ]
    settings = {
        "roc_lookbacks": [2],
        "roc_change_lookbacks": [2],
        "ma_short": 3,
        "ma_long": 3,
    }
    assert evaluate_roc_aggregate(prices, settings) == []


def test_markdown_report_contains_sections() -> None:
    payload = {
        "run_metadata": {
            "run_id": "test",
            "run_timestamp": "2025-01-01T00:00:00Z",
            "start_date": "2024-12-01",
            "end_date": "2025-01-01",
            "interval": "day",
            "tickers": ["AAPL"],
            "duration_seconds": 1.23,
            "output_path": "/tmp/output.json",
            "markdown_path": "/tmp/output.md",
            "html_path": "/tmp/output.html",
            "advance_decline_lookbacks": [1, 5],
            "indicator_instances": [
                {
                    "id": "roc",
                    "instance_id": "roc_1",
                    "settings": {"roc_lookback": 12},
                }
            ],
        },
        "market_stats": {
            "SPY": {
                "as_of_date": "2025-01-01",
                "last_close": 480.0,
                "change_1d_pct": 0.01,
                "change_5d_pct": 0.02,
            },
            "QQQ": {
                "as_of_date": "2025-01-01",
                "last_close": 410.0,
                "change_1d_pct": -0.005,
                "change_5d_pct": 0.015,
            },
            "IWM": {
                "as_of_date": "2025-01-01",
                "last_close": 200.0,
                "change_1d_pct": 0.0,
                "change_5d_pct": -0.01,
            },
        },
        "storage_usage": {
            "scan_db_bytes": 1024,
            "options_db_bytes": 2048,
            "task_logs_bytes": 512,
            "total_bytes": 3584,
        },
        "aggregates": {
            "advances": 1,
            "declines": 0,
            "unchanged": 0,
            "net_advances": 1,
            "advance_decline_ratio": None,
            "advance_pct": 1.0,
            "ad_5_advances": 1,
            "ad_5_declines": 0,
            "ad_5_unchanged": 0,
            "ad_5_net_advances": 1,
            "ad_5_advance_decline_ratio": None,
            "ad_5_advance_pct": 1.0,
            "ad_5_valid_count": 1,
            "ma_13_above_pct": 1.0,
            "ma_13_below_pct": 0.0,
            "ma_13_equal_pct": 0.0,
            "ma_13_valid_count": 1,
            "roc_17_vs_5_gt_pct": 1.0,
            "roc_17_vs_5_lt_pct": 0.0,
            "roc_17_vs_5_eq_pct": 0.0,
            "roc_17_vs_5_valid_count": 1,
        },
        "signals": [
            {
                "ticker": "AAPL",
                "indicator_id": "roc_1",
                "indicator_type": "roc",
                "signal_date": "2025-01-01",
                "signal_type": "crossover_up",
                "metadata": {"series": "roc"},
            }
        ],
        "ticker_summaries": [
            {
                "ticker": "AAPL",
                "last_date": "2025-01-01",
                "last_close": 100,
                "close_change": 1,
                "close_change_pct": 0.01,
                "issues": [],
            }
        ],
        "issues": [],
    }

    report = render_markdown_report(payload)
    assert "Security Scan Report" in report
    assert "Market Snapshot" in report
    assert "HTML Output" in report


def test_render_html_report_contains_title() -> None:
    payload = {
        "run_metadata": {"run_id": "test", "tickers": ["AAPL"]},
        "market_stats": {},
        "ticker_summaries": [],
        "signals": [],
        "aggregates": {},
        "issues": [],
    }
    html_report = render_html_report(payload)
    assert "<html" in html_report
    assert "Security Scan Report" in html_report


def test_render_html_report_includes_charts_section() -> None:
    payload = {
        "run_metadata": {"run_id": "test", "tickers": ["AAPL"]},
        "market_stats": {},
        "ticker_summaries": [],
        "signals": [],
        "aggregates": {},
        "issues": [],
    }
    charts_html = "<div>chart</div>"
    html_report = render_html_report(payload, charts_html=charts_html)
    assert "Aggregate Timeseries" in html_report
    assert charts_html in html_report
