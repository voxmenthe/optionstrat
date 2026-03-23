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


def test_summary_tables_include_all_universe_rows() -> None:
    universe_aggregates = {
        "advances": 10,
        "declines": 5,
        "unchanged": 1,
        "net_advances": 5,
        "advance_decline_ratio": 2.0,
        "advance_pct": 0.625,
        "ma_13_above_pct": 0.7,
        "ma_13_below_pct": 0.2,
        "ma_13_equal_pct": 0.1,
        "ma_13_valid_count": 16,
        "ma_28_above_pct": 0.6,
        "ma_28_below_pct": 0.3,
        "ma_28_equal_pct": 0.1,
        "ma_28_valid_count": 16,
        "ma_46_above_pct": 0.5,
        "ma_46_below_pct": 0.4,
        "ma_46_equal_pct": 0.1,
        "ma_46_valid_count": 16,
        "ma_8_shift_5_above_pct": 0.65,
        "ma_8_shift_5_below_pct": 0.25,
        "ma_8_shift_5_equal_pct": 0.1,
        "ma_8_shift_5_valid_count": 16,
        "roc_17_vs_5_gt_pct": 0.6,
        "roc_17_vs_5_lt_pct": 0.3,
        "roc_17_vs_5_eq_pct": 0.1,
        "roc_17_vs_5_valid_count": 16,
        "roc_27_vs_4_gt_pct": 0.55,
        "roc_27_vs_4_lt_pct": 0.35,
        "roc_27_vs_4_eq_pct": 0.1,
        "roc_27_vs_4_valid_count": 16,
    }
    payload = {
        "run_metadata": {"end_date": "2025-01-03"},
        "aggregate_universes": {
            "all": {
                "label": "All Tickers",
                "aggregates": universe_aggregates,
                "aggregates_history": [],
            },
            "nasdaq": {
                "label": "NASDAQ Tickers",
                "aggregates": universe_aggregates,
                "aggregates_history": [],
            },
            "sp100": {
                "label": "S&P 100 Tickers",
                "aggregates": universe_aggregates,
                "aggregates_history": [],
            },
        },
        "signals": [],
        "issues": [],
    }

    markdown = render_markdown_report(payload)

    all_advances = markdown.index("| All Tickers | Advances |")
    nasdaq_advances = markdown.index("| NASDAQ Tickers | Advances |")
    sp100_advances = markdown.index("| S&P 100 Tickers | Advances |")
    all_declines = markdown.index("| All Tickers | Declines |")

    assert all_advances < nasdaq_advances < sp100_advances < all_declines

    all_sma_13 = markdown.index("| All Tickers | SMA 13 |")
    nasdaq_sma_13 = markdown.index("| NASDAQ Tickers | SMA 13 |")
    sp100_sma_13 = markdown.index("| S&P 100 Tickers | SMA 13 |")
    all_sma_28 = markdown.index("| All Tickers | SMA 28 |")

    assert all_sma_13 < nasdaq_sma_13 < sp100_sma_13 < all_sma_28

    all_roc_17 = markdown.index("| All Tickers | ROC 17 vs 5d |")
    nasdaq_roc_17 = markdown.index("| NASDAQ Tickers | ROC 17 vs 5d |")
    sp100_roc_17 = markdown.index("| S&P 100 Tickers | ROC 17 vs 5d |")
    all_roc_27 = markdown.index("| All Tickers | ROC 27 vs 4d |")

    assert all_roc_17 < nasdaq_roc_17 < sp100_roc_17 < all_roc_27


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
