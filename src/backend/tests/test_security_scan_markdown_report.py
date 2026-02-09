from __future__ import annotations

from app.security_scan.reporting.html_report import render_html_report
from app.security_scan.reporting.markdown_report import render_markdown_report


def test_latest_day_highlight_includes_indicator_column() -> None:
    payload = {
        "run_metadata": {
            "end_date": "2025-01-02",
            "indicator_instances": [
                {"instance_id": "roc_1", "settings": {}},
                {"instance_id": "qrs_1", "settings": {}},
            ],
        },
        "signals": [
            {
                "ticker": "AAA",
                "indicator_id": "roc_1",
                "indicator_type": "roc",
                "signal_date": "2025-01-02",
                "signal_type": "crossover_up",
                "metadata": {"label": "roc_cross"},
            },
            {
                "ticker": "BBB",
                "indicator_id": "qrs_1",
                "indicator_type": "qrs_consist_excess",
                "signal_date": "2025-01-02",
                "signal_type": "main_above_all_mas_pos_regime",
                "metadata": {"label": "qrs_regime"},
            },
        ],
    }

    markdown = render_markdown_report(payload)

    assert "## Latest-Day Highlight (All Indicators)" in markdown
    assert "| Date | Indicator | Signal Type | Count | Tickers |" in markdown
    assert "| 2025-01-02 | roc (roc_1) | crossover_up | 1 | AAA |" in markdown
    assert (
        "| 2025-01-02 | qrs_consist_excess (qrs_1) | main_above_all_mas_pos_regime | 1 | BBB |"
        in markdown
    )


def test_indicator_rollup_omits_removed_subsections() -> None:
    payload = {
        "run_metadata": {
            "end_date": "2025-01-03",
            "indicator_instances": [
                {"instance_id": "roc_1", "settings": {"roc_lookback": 12}},
            ],
        },
        "signals": [
            {
                "ticker": "AAA",
                "indicator_id": "roc_1",
                "indicator_type": "roc",
                "signal_date": "2025-01-03",
                "signal_type": "direction_up",
                "metadata": {"label": "up_streak"},
            },
            {
                "ticker": "BBB",
                "indicator_id": "roc_1",
                "indicator_type": "roc",
                "signal_date": "2025-01-02",
                "signal_type": "crossover_up",
                "metadata": {"label": "roc_cross"},
            },
            {
                "ticker": "CCC",
                "indicator_id": "roc_1",
                "indicator_type": "roc",
                "signal_date": "2025-01-01",
                "signal_type": "crossover_down",
                "metadata": {"label": "roc_cross"},
            },
        ],
    }

    markdown = render_markdown_report(payload)

    assert "## Indicator Rollups" in markdown
    assert "**Recent Window (last" in markdown

    assert "**Latest Day Highlight (" not in markdown
    assert "**Per-Criteria Grouping**" not in markdown
    assert "**Direction Streaks" not in markdown
    assert "## Indicator Signals (Appendix)" not in markdown


def test_render_html_report_has_no_indicator_appendix_wrapper() -> None:
    payload = {
        "run_metadata": {
            "end_date": "2025-01-02",
            "indicator_instances": [
                {"instance_id": "roc_1", "settings": {"roc_lookback": 12}},
            ],
        },
        "market_stats": {},
        "ticker_summaries": [],
        "signals": [
            {
                "ticker": "AAA",
                "indicator_id": "roc_1",
                "indicator_type": "roc",
                "signal_date": "2025-01-02",
                "signal_type": "crossover_up",
                "metadata": {"label": "roc_cross"},
            }
        ],
        "aggregates": {},
        "issues": [],
    }

    html = render_html_report(payload)
    assert "<html" in html
    assert "Indicator Signals (Appendix)" not in html
    assert "<details class=\"appendix\">" not in html
