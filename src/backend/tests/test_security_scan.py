from __future__ import annotations

from pathlib import Path

from app.security_scan.aggregates import compute_breadth
from app.security_scan.config_loader import load_security_scan_config
from app.security_scan.indicators.roc import evaluate as evaluate_roc
from app.security_scan.reporting.markdown_report import render_markdown_report


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
""".strip()
    )

    config = load_security_scan_config(tmp_path)
    assert config.tickers == ["AAPL"]
    assert len(config.indicator_instances) == 1
    instance = config.indicator_instances[0]
    assert instance.id == "roc"
    assert instance.settings["roc_lookback"] == 12
    assert isinstance(instance.settings["criteria"], list)


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
            "indicator_instances": [
                {
                    "id": "roc",
                    "instance_id": "roc_1",
                    "settings": {"roc_lookback": 12},
                }
            ],
        },
        "aggregates": {
            "advances": 1,
            "declines": 0,
            "unchanged": 0,
            "net_advances": 1,
            "advance_decline_ratio": None,
            "advance_pct": 1.0,
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
    assert "Summary (Breadth)" in report
    assert "Indicator Signals" in report
    assert "AAPL" in report
