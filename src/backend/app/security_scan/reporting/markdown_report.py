from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Iterable


RECENT_DATE_WINDOW = 5
TICKER_LIST_LIMIT = 10
DATE_DENSITY_LIMIT = 10


def _format_number(value: Any, decimals: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def _format_percent(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (TypeError, ValueError):
        return str(value)


def _format_bytes(value: Any) -> str:
    if value is None:
        return "-"
    try:
        size = float(value)
    except (TypeError, ValueError):
        return str(value)
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f}{units[index]}"


def _settings_summary(settings: dict[str, Any]) -> str:
    if not settings:
        return ""
    summary_parts: list[str] = []
    criteria = settings.get("criteria")
    if isinstance(criteria, list) and criteria:
        labels = []
        for item in criteria:
            if not isinstance(item, dict):
                continue
            label = item.get("label") or item.get("type")
            if isinstance(label, str):
                labels.append(label)
        if labels:
            summary_parts.append(f"criteria={','.join(labels)}")
    for key, value in settings.items():
        if key == "criteria":
            continue
        summary_parts.append(f"{key}={value}")
    return ", ".join(summary_parts)


def _format_metadata(metadata: dict[str, Any]) -> str:
    if not metadata:
        return "-"
    try:
        return json.dumps(metadata, sort_keys=True)
    except TypeError:
        return str(metadata)


def _format_metadata_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return _format_number(value)
    return str(value)


def _truncate_list(items: Iterable[str], limit: int = TICKER_LIST_LIMIT) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return "-"
    if len(cleaned) <= limit:
        return ", ".join(cleaned)
    remaining = len(cleaned) - limit
    return f"{', '.join(cleaned[:limit])} +{remaining} more"


def _signal_dates(signals: list[dict[str, Any]]) -> list[str]:
    dates = sorted({signal.get("signal_date") for signal in signals if signal.get("signal_date")})
    return sorted(dates, reverse=True)


def _group_by_date_and_type(
    signals: list[dict[str, Any]],
    dates: list[str] | None = None,
) -> list[tuple[str, str, list[str]]]:
    rollup: dict[tuple[str, str], set[str]] = defaultdict(set)
    for signal in signals:
        date = signal.get("signal_date")
        signal_type = signal.get("signal_type")
        ticker = signal.get("ticker")
        if not date or not signal_type:
            continue
        if dates is not None and date not in dates:
            continue
        if ticker:
            rollup[(date, signal_type)].add(ticker)
    rows = [
        (date, signal_type, sorted(tickers))
        for (date, signal_type), tickers in rollup.items()
    ]
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return rows


def _group_by_label(signals: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    rollup: dict[str, set[str]] = defaultdict(set)
    for signal in signals:
        metadata = signal.get("metadata") or {}
        label = metadata.get("label") or metadata.get("type") or signal.get("signal_type")
        ticker = signal.get("ticker")
        if isinstance(label, str) and label and ticker:
            rollup[label].add(ticker)
    rows = [(label, sorted(tickers)) for label, tickers in rollup.items()]
    rows.sort(key=lambda row: len(row[1]), reverse=True)
    return rows


def _signal_density(signals: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counts: dict[str, int] = defaultdict(int)
    for signal in signals:
        date = signal.get("signal_date")
        if date:
            counts[date] += 1
    rows = sorted(counts.items(), key=lambda row: row[0], reverse=True)
    return rows[:DATE_DENSITY_LIMIT]


def _direction_streaks(signals: list[dict[str, Any]], min_streak: int = 3) -> list[tuple[str, str, int, str]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        signal_type = signal.get("signal_type")
        ticker = signal.get("ticker")
        if not ticker or not isinstance(signal_type, str):
            continue
        if not signal_type.startswith("direction_"):
            continue
        by_ticker[ticker].append(signal)

    streaks: list[tuple[str, str, int, str]] = []
    for ticker, ticker_signals in by_ticker.items():
        ticker_signals.sort(key=lambda row: row.get("signal_date") or "")
        current_direction = None
        current_streak = 0
        last_date = ""
        for signal in ticker_signals:
            signal_type = signal.get("signal_type")
            if not signal_type:
                continue
            direction = signal_type.replace("direction_", "", 1)
            if direction == current_direction:
                current_streak += 1
            else:
                current_direction = direction
                current_streak = 1
            last_date = signal.get("signal_date") or last_date
        if current_streak >= min_streak and current_direction:
            streaks.append((ticker, current_direction, current_streak, last_date))
    streaks.sort(key=lambda row: row[2], reverse=True)
    return streaks


def render_markdown_report(payload: dict[str, Any]) -> str:
    run_metadata = payload.get("run_metadata", {})
    aggregates = payload.get("aggregates", {})
    signals = payload.get("signals", [])
    ticker_summaries = payload.get("ticker_summaries", [])
    issues = payload.get("issues", [])

    indicator_instances = run_metadata.get("indicator_instances", [])
    instance_map = {
        instance.get("instance_id"): instance for instance in indicator_instances
    }

    lines: list[str] = ["# Security Scan Report", ""]

    lines.append("## Market Snapshot")
    market_stats = payload.get("market_stats")
    if isinstance(market_stats, dict) and market_stats:
        lines.append("| Ticker | As Of | Last Close | 1D % | 5D % |")
        lines.append("| --- | --- | --- | --- | --- |")
        snapshot_order = ["SPY", "QQQ", "IWM"]
        seen = set()
        for ticker in snapshot_order:
            entry = market_stats.get(ticker)
            if not isinstance(entry, dict):
                continue
            seen.add(ticker)
            lines.append(
                f"| {ticker}"
                f" | {entry.get('as_of_date') or '-'}"
                f" | {_format_number(entry.get('last_close'))}"
                f" | {_format_percent(entry.get('change_1d_pct'))}"
                f" | {_format_percent(entry.get('change_5d_pct'))} |"
            )
        for ticker in sorted(market_stats.keys()):
            if ticker in seen:
                continue
            entry = market_stats.get(ticker)
            if not isinstance(entry, dict):
                continue
            lines.append(
                f"| {ticker}"
                f" | {entry.get('as_of_date') or '-'}"
                f" | {_format_number(entry.get('last_close'))}"
                f" | {_format_percent(entry.get('change_1d_pct'))}"
                f" | {_format_percent(entry.get('change_5d_pct'))} |"
            )
    else:
        lines.append("No market stats available.")
    lines.append("")

    lines.append("## Run Metadata")
    lines.append(
        f"- Run ID: {run_metadata.get('run_id', '-')}"
    )
    lines.append(
        f"- Timestamp: {run_metadata.get('run_timestamp', '-')}"
    )
    lines.append(
        f"- Date Range: {run_metadata.get('start_date', '-')} → {run_metadata.get('end_date', '-')}"
    )
    lines.append(
        f"- Interval: {run_metadata.get('interval', '-')}"
    )
    lines.append(
        f"- Tickers: {len(run_metadata.get('tickers', []))}"
    )
    lines.append(
        f"- Duration (s): {_format_number(run_metadata.get('duration_seconds'), 3)}"
    )
    output_path = run_metadata.get("output_path")
    markdown_path = run_metadata.get("markdown_path")
    html_path = run_metadata.get("html_path")
    if output_path:
        lines.append(f"- JSON Output: {output_path}")
    if markdown_path:
        lines.append(f"- Markdown Output: {markdown_path}")
    if html_path:
        lines.append(f"- HTML Output: {html_path}")
    storage_usage = payload.get("storage_usage")
    if isinstance(storage_usage, dict):
        scan_db = _format_bytes(storage_usage.get("scan_db_bytes"))
        options_db = _format_bytes(storage_usage.get("options_db_bytes"))
        task_logs = _format_bytes(storage_usage.get("task_logs_bytes"))
        total = _format_bytes(storage_usage.get("total_bytes"))
        lines.append(
            f"- Storage Usage: scan_db={scan_db} | options_db={options_db}"
            f" | task_logs={task_logs} | total={total}"
        )
    lines.append("")

    lines.append("## Summary (Breadth)")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Advances | {aggregates.get('advances', 0)} |")
    lines.append(f"| Declines | {aggregates.get('declines', 0)} |")
    lines.append(f"| Unchanged | {aggregates.get('unchanged', 0)} |")
    lines.append(f"| Net Advances | {aggregates.get('net_advances', 0)} |")
    lines.append(
        f"| Advance/Decline Ratio | {_format_number(aggregates.get('advance_decline_ratio'))} |"
    )
    lines.append(
        f"| Advance % | {_format_percent(aggregates.get('advance_pct'))} |"
    )
    lines.append("")

    advance_decline_lookbacks = run_metadata.get("advance_decline_lookbacks") or [1]
    lines.append("## Summary (Advance/Decline Lookbacks)")
    lines.append("| Lookback | Advances | Declines | Net | Ratio | Advance % | Valid |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for lookback in advance_decline_lookbacks:
        if lookback == 1:
            lines.append(
                f"| t-{lookback} | {aggregates.get('advances', 0)}"
                f" | {aggregates.get('declines', 0)}"
                f" | {aggregates.get('net_advances', 0)}"
                f" | {_format_number(aggregates.get('advance_decline_ratio'))}"
                f" | {_format_percent(aggregates.get('advance_pct'))}"
                f" | {aggregates.get('valid_ticker_count', 0)} |"
            )
            continue
        prefix = f"ad_{lookback}"
        lines.append(
            f"| t-{lookback} | {aggregates.get(f'{prefix}_advances', 0)}"
            f" | {aggregates.get(f'{prefix}_declines', 0)}"
            f" | {aggregates.get(f'{prefix}_net_advances', 0)}"
            f" | {_format_number(aggregates.get(f'{prefix}_advance_decline_ratio'))}"
            f" | {_format_percent(aggregates.get(f'{prefix}_advance_pct'))}"
            f" | {aggregates.get(f'{prefix}_valid_count', 0)} |"
        )
    lines.append("")

    lines.append("## Summary (MA Breadth)")
    lines.append("| Metric | Above % | Below % | Equal % | Valid |")
    lines.append("| --- | --- | --- | --- | --- |")
    ma_rows = [
        ("SMA 13", "ma_13"),
        ("SMA 28", "ma_28"),
        ("SMA 46", "ma_46"),
        ("SMA 8 (shift 5)", "ma_8_shift_5"),
    ]
    for label, prefix in ma_rows:
        lines.append(
            f"| {label} | {_format_percent(aggregates.get(f'{prefix}_above_pct'))}"
            f" | {_format_percent(aggregates.get(f'{prefix}_below_pct'))}"
            f" | {_format_percent(aggregates.get(f'{prefix}_equal_pct'))}"
            f" | {aggregates.get(f'{prefix}_valid_count', 0)} |"
        )
    lines.append("")

    lines.append("## Summary (ROC Breadth)")
    lines.append("| Metric | > % | < % | = % | Valid |")
    lines.append("| --- | --- | --- | --- | --- |")
    roc_rows = [
        ("ROC 17 vs 5d", "roc_17_vs_5"),
        ("ROC 27 vs 4d", "roc_27_vs_4"),
    ]
    for label, prefix in roc_rows:
        lines.append(
            f"| {label} | {_format_percent(aggregates.get(f'{prefix}_gt_pct'))}"
            f" | {_format_percent(aggregates.get(f'{prefix}_lt_pct'))}"
            f" | {_format_percent(aggregates.get(f'{prefix}_eq_pct'))}"
            f" | {aggregates.get(f'{prefix}_valid_count', 0)} |"
        )
    lines.append("")

    lines.append("## Indicator Overview")
    if not indicator_instances:
        lines.append("No indicators configured.")
        lines.append("")
    else:
        lines.append("| Indicator | Instance | Settings | Signals | Most Recent Hit |")
        lines.append("| --- | --- | --- | --- | --- |")
        signals_by_instance: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for signal in signals:
            signals_by_instance[signal.get("indicator_id", "unknown")].append(signal)
        for instance in indicator_instances:
            instance_id = instance.get("instance_id", "unknown")
            indicator_type = instance.get("id", "unknown")
            instance_signals = signals_by_instance.get(instance_id, [])
            most_recent = "-"
            if instance_signals:
                most_recent = max(
                    (signal.get("signal_date") or "" for signal in instance_signals),
                    default="-",
                )
            settings_summary = _settings_summary(instance.get("settings", {}))
            lines.append(
                f"| {indicator_type} | {instance_id} | {settings_summary or '-'}"
                f" | {len(instance_signals)} | {most_recent or '-'} |"
            )
        lines.append("")

    if signals:
        lines.append("## Latest-Day Highlight (All Indicators)")
        all_dates = _signal_dates(signals)
        if all_dates:
            latest_date = all_dates[0]
            latest_rows = _group_by_date_and_type(signals, [latest_date])
            if latest_rows:
                lines.append("| Date | Signal Type | Count | Tickers |")
                lines.append("| --- | --- | --- | --- |")
                for date, signal_type, tickers in latest_rows:
                    lines.append(
                        f"| {date} | {signal_type} | {len(tickers)}"
                        f" | {_truncate_list(tickers)} |"
                    )
            else:
                lines.append("No signals on latest date.")
        lines.append("")

        lines.append("## Top Tickers (Overall)")
        overall_counts: dict[str, int] = defaultdict(int)
        for signal in signals:
            ticker = signal.get("ticker")
            if ticker:
                overall_counts[ticker] += 1
        if overall_counts:
            lines.append("| Ticker | Signals |")
            lines.append("| --- | --- |")
            for ticker, count in sorted(
                overall_counts.items(), key=lambda row: row[1], reverse=True
            )[:TICKER_LIST_LIMIT]:
                lines.append(f"| {ticker} | {count} |")
        else:
            lines.append("No signals.")
        lines.append("")

        lines.append("## Signal Density (Overall)")
        density_rows = _signal_density(signals)
        if density_rows:
            lines.append("| Date | Signals |")
            lines.append("| --- | --- |")
            for date, count in density_rows:
                lines.append(f"| {date} | {count} |")
        else:
            lines.append("No signals.")
        lines.append("")

    lines.append("## Indicator Rollups")
    if not signals:
        lines.append("No indicator signals triggered.")
        lines.append("")
    else:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for signal in signals:
            grouped[signal.get("indicator_id", "unknown")].append(signal)

        for indicator_id in sorted(grouped.keys()):
            indicator_signals = sorted(
                grouped[indicator_id],
                key=lambda item: item.get("signal_date") or "",
                reverse=True,
            )
            indicator_type = indicator_signals[0].get("indicator_type", "unknown")
            lines.append(f"### {indicator_type} ({indicator_id})")
            instance = instance_map.get(indicator_id, {})
            settings = instance.get("settings", {})
            settings_summary = _settings_summary(settings)
            if settings_summary:
                lines.append(f"Settings: `{settings_summary}`")
            lines.append("")

            all_dates = _signal_dates(indicator_signals)
            if all_dates:
                latest_date = all_dates[0]
                lines.append(f"**Latest Day Highlight ({latest_date})**")
                latest_rows = _group_by_date_and_type(indicator_signals, [latest_date])
                if latest_rows:
                    lines.append("| Date | Signal Type | Count | Tickers |")
                    lines.append("| --- | --- | --- | --- |")
                    for date, signal_type, tickers in latest_rows:
                        lines.append(
                            f"| {date} | {signal_type} | {len(tickers)}"
                            f" | {_truncate_list(tickers)} |"
                        )
                else:
                    lines.append("No signals on latest date.")
                lines.append("")

            recent_dates = all_dates[:RECENT_DATE_WINDOW]
            lines.append(f"**Recent Window (last {RECENT_DATE_WINDOW} dates)**")
            recent_rows = _group_by_date_and_type(indicator_signals, recent_dates)
            if recent_rows:
                lines.append("| Date | Signal Type | Count | Tickers |")
                lines.append("| --- | --- | --- | --- |")
                for date, signal_type, tickers in recent_rows:
                    lines.append(
                        f"| {date} | {signal_type} | {len(tickers)}"
                        f" | {_truncate_list(tickers)} |"
                    )
            else:
                lines.append("No signals in recent window.")
            if len(all_dates) > len(recent_dates):
                remaining_dates = len(all_dates) - len(recent_dates)
                older_signals = [
                    signal
                    for signal in indicator_signals
                    if signal.get("signal_date") not in set(recent_dates)
                ]
                lines.append(
                    f"Older dates summarized: {remaining_dates} dates,"
                    f" {len(older_signals)} signals."
                )
            lines.append("")

            lines.append("**Per-Criteria Grouping**")
            label_rows = _group_by_label(indicator_signals)
            if label_rows:
                lines.append("| Criterion | Count | Tickers |")
                lines.append("| --- | --- | --- |")
                for label, tickers in label_rows:
                    lines.append(
                        f"| {label} | {len(tickers)} | {_truncate_list(tickers)} |"
                    )
            else:
                lines.append("No criteria labels found.")
            lines.append("")

            lines.append("**Signal Density (by date)**")
            density_rows = _signal_density(indicator_signals)
            if density_rows:
                lines.append("| Date | Signals |")
                lines.append("| --- | --- |")
                for date, count in density_rows:
                    lines.append(f"| {date} | {count} |")
            else:
                lines.append("No signals.")
            lines.append("")

            lines.append("**Top Tickers by Signal Count**")
            ticker_counts: dict[str, int] = defaultdict(int)
            for signal in indicator_signals:
                ticker = signal.get("ticker")
                if ticker:
                    ticker_counts[ticker] += 1
            if ticker_counts:
                top_tickers = sorted(
                    ticker_counts.items(), key=lambda row: row[1], reverse=True
                )
                lines.append("| Ticker | Signals |")
                lines.append("| --- | --- |")
                for ticker, count in top_tickers[:TICKER_LIST_LIMIT]:
                    lines.append(f"| {ticker} | {count} |")
            else:
                lines.append("No ticker counts.")
            lines.append("")

            lines.append("**Direction Streaks (if applicable)**")
            streaks = _direction_streaks(indicator_signals)
            if streaks:
                lines.append("| Ticker | Direction | Streak | Last Date |")
                lines.append("| --- | --- | --- | --- |")
                for ticker, direction, streak, last_date in streaks[:TICKER_LIST_LIMIT]:
                    lines.append(f"| {ticker} | {direction} | {streak} | {last_date} |")
            else:
                lines.append("No direction streaks.")
            lines.append("")

    lines.append("## Per-Ticker Summary")
    lines.append("| Ticker | Last Date | Last Close | Change | Change % | Signals | Issues |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    signal_counts: dict[str, int] = defaultdict(int)
    for signal in signals:
        ticker = signal.get("ticker")
        if ticker:
            signal_counts[ticker] += 1
    for summary in sorted(ticker_summaries, key=lambda item: item.get("ticker", "")):
        ticker = summary.get("ticker", "-")
        lines.append(
            f"| {ticker} | {summary.get('last_date', '-')}"
            f" | {_format_number(summary.get('last_close'))}"
            f" | {_format_number(summary.get('close_change'))}"
            f" | {_format_percent(summary.get('close_change_pct'))}"
            f" | {signal_counts.get(ticker, 0)}"
            f" | {', '.join(summary.get('issues', [])) or '-'} |"
        )
    lines.append("")

    if issues:
        lines.append("## Issues")
        for issue in issues:
            parts = []
            if issue.get("ticker"):
                parts.append(f"ticker={issue['ticker']}")
            if issue.get("indicator_id"):
                parts.append(f"indicator_id={issue['indicator_id']}")
            if issue.get("issue"):
                parts.append(f"issue={issue['issue']}")
            if issue.get("detail"):
                parts.append(f"detail={issue['detail']}")
            lines.append(f"- {'; '.join(parts)}")
        lines.append("")

    lines.append("## Indicator Signals (Appendix)")
    if not signals:
        lines.append("No indicator signals triggered.")
        lines.append("")
    else:
        metadata_keys = [
            "series",
            "level",
            "direction",
            "prev_value",
            "current_value",
            "lookback",
            "op",
            "label",
        ]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for signal in signals:
            grouped[signal.get("indicator_id", "unknown")].append(signal)

        for indicator_id in sorted(grouped.keys()):
            indicator_signals = sorted(
                grouped[indicator_id],
                key=lambda item: item.get("signal_date") or "",
                reverse=True,
            )
            indicator_type = indicator_signals[0].get("indicator_type", "unknown")
            lines.append(f"### {indicator_type} ({indicator_id})")
            lines.append(
                "| Ticker | Signal Date | Signal Type | "
                + " | ".join(metadata_keys)
                + " | Other Metadata |"
            )
            lines.append(
                "| --- | --- | --- | " + " | ".join(["---"] * len(metadata_keys)) + " | --- |"
            )
            for signal in indicator_signals:
                metadata = signal.get("metadata") or {}
                extra = {
                    key: value
                    for key, value in metadata.items()
                    if key not in metadata_keys
                }
                lines.append(
                    f"| {signal.get('ticker', '-')} | {signal.get('signal_date', '-')}"
                    f" | {signal.get('signal_type', '-')}"
                    + "".join(
                        f" | {_format_metadata_value(metadata.get(key))}"
                        for key in metadata_keys
                    )
                    + f" | {_format_metadata(extra)} |"
                )
            lines.append("")

    return "\n".join(lines)
