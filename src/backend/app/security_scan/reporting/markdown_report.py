from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Iterable


RECENT_DATE_WINDOW = 5
TICKER_LIST_LIMIT = 10


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


def _format_compact_scalar(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if value.is_integer():
            return str(int(value))
        return format(value, "g")
    if isinstance(value, str):
        return value
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(parsed):
        return "nan"
    if parsed.is_integer():
        return str(int(parsed))
    return format(parsed, "g")


def _describe_criteria_rule(rule: dict[str, Any]) -> str:
    rule_type = rule.get("type")
    if not isinstance(rule_type, str) or not rule_type.strip():
        return str(rule)
    rule_type = rule_type.strip()

    series = rule.get("series")
    series_label = "*"
    if isinstance(series, str) and series.strip():
        series_label = series.strip()

    label = rule.get("label")
    label_suffix = ""
    if isinstance(label, str) and label.strip():
        label_suffix = f" (label={label.strip()})"

    if rule_type == "crossover":
        level = _format_compact_scalar(rule.get("level", 0))
        direction = rule.get("direction")
        direction_norm = (
            str(direction).strip().lower() if direction is not None else "both"
        )
        if direction_norm == "up":
            action = "crosses above"
        elif direction_norm == "down":
            action = "crosses below"
        else:
            action = "crosses above/below"
        return f"crossover: {series_label} {action} {level}{label_suffix}"

    if rule_type == "threshold":
        op = rule.get("op")
        op_label = str(op).strip() if isinstance(op, str) and op.strip() else "?"
        level = _format_compact_scalar(rule.get("level"))
        return f"threshold: {series_label} {op_label} {level}{label_suffix}"

    if rule_type == "direction":
        lookback = _format_compact_scalar(rule.get("lookback", 1))
        return (
            f"direction: {series_label} over {lookback} bars"
            f" (emits up/down/flat){label_suffix}"
        )

    details = []
    for key in sorted(rule.keys()):
        if key == "type":
            continue
        details.append(f"{key}={rule.get(key)}")
    if not details:
        return rule_type
    return f"{rule_type}: {', '.join(details)}"


def _describe_criteria(criteria: Any) -> str:
    if not criteria:
        return "none"
    if isinstance(criteria, dict):
        return _describe_criteria_rule(criteria)
    if isinstance(criteria, list):
        descriptions: list[str] = []
        for item in criteria:
            if isinstance(item, dict):
                descriptions.append(_describe_criteria_rule(item))
            else:
                descriptions.append(str(item))
        return "none" if not descriptions else "; ".join(descriptions)
    return str(criteria)


def _settings_summary(settings: dict[str, Any]) -> str:
    if not settings:
        return ""
    summary_parts: list[str] = []
    criteria_description = _describe_criteria(settings.get("criteria"))
    if criteria_description != "none":
        summary_parts.append(f"criteria={criteria_description}")
    for key, value in settings.items():
        if key in {"criteria", "_context"}:
            continue
        summary_parts.append(f"{key}={value}")
    return ", ".join(summary_parts)


def _escape_markdown_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")

def _truncate_list(items: Iterable[str], limit: int = TICKER_LIST_LIMIT) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return "-"
    # Render all matching tickers in report tables; HTML cells will wrap.
    return ", ".join(cleaned)


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


def _group_by_date_indicator_and_type(
    signals: list[dict[str, Any]],
    dates: list[str] | None = None,
) -> list[tuple[str, str, str, list[str]]]:
    rollup: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for signal in signals:
        date = signal.get("signal_date")
        signal_type = signal.get("signal_type")
        ticker = signal.get("ticker")
        if not date or not signal_type:
            continue
        if dates is not None and date not in dates:
            continue
        indicator_type = signal.get("indicator_type") or "unknown"
        indicator_id = signal.get("indicator_id") or "unknown"
        indicator_label = f"{indicator_type} ({indicator_id})"
        if ticker:
            rollup[(date, indicator_label, signal_type)].add(ticker)
    rows = [
        (date, indicator, signal_type, sorted(tickers))
        for (date, indicator, signal_type), tickers in rollup.items()
    ]
    rows.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    return rows

def _compute_history_stats(
    aggregates_history: list[dict[str, Any]] | None,
    *,
    metric_keys: Iterable[str],
    end_date: str | None = None,
) -> dict[str, dict[str, Any]]:
    if not aggregates_history:
        return {}

    by_date: dict[str, dict[str, Any]] = defaultdict(dict)
    for entry in aggregates_history:
        if not isinstance(entry, dict):
            continue
        as_of_date = entry.get("as_of_date")
        metric_key = entry.get("metric_key")
        if not as_of_date or not metric_key:
            continue
        by_date[str(as_of_date)][str(metric_key)] = entry.get("value")

    if not by_date:
        return {}

    ordered_dates = sorted(by_date.keys(), reverse=True)
    if end_date and end_date in by_date:
        ordered_dates = [end_date] + [d for d in ordered_dates if d != end_date]

    stats: dict[str, dict[str, Any]] = {}
    for key in metric_keys:
        t_minus_1 = None
        if len(ordered_dates) > 1:
            t_minus_1 = by_date[ordered_dates[1]].get(key)

        t_minus_2 = None
        if len(ordered_dates) > 2:
            t_minus_2 = by_date[ordered_dates[2]].get(key)

        values: list[float] = []
        for date_value in ordered_dates[:10]:
            value = by_date[date_value].get(key)
            if value is None:
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        avg_10d = None if not values else (sum(values) / len(values))

        stats[key] = {
            "t_minus_1": t_minus_1,
            "t_minus_2": t_minus_2,
            "avg_10d": avg_10d,
        }

    return stats


def render_markdown_report(payload: dict[str, Any]) -> str:
    run_metadata = payload.get("run_metadata", {})
    aggregates = payload.get("aggregates", {})
    aggregates_history = payload.get("aggregates_history", [])
    signals = payload.get("signals", [])
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

    breadth_metric_keys = [
        "advances",
        "declines",
        "unchanged",
        "net_advances",
        "advance_decline_ratio",
        "advance_pct",
    ]
    breadth_stats = _compute_history_stats(
        aggregates_history,
        metric_keys=breadth_metric_keys,
        end_date=run_metadata.get("end_date"),
    )

    def _format_count(value: Any) -> str:
        if value is None:
            return "-"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value)
        if numeric.is_integer():
            return str(int(numeric))
        return _format_number(numeric, 4)

    def _add_breadth_row(label: str, key: str, formatter) -> None:
        stats = breadth_stats.get(key, {})
        lines.append(
            f"| {label}"
            f" | {formatter(aggregates.get(key))}"
            f" | {formatter(stats.get('t_minus_1'))}"
            f" | {formatter(stats.get('t_minus_2'))}"
            f" | {formatter(stats.get('avg_10d'))} |"
        )

    lines.append("## Summary (Breadth)")
    lines.append("| Metric | Value | t-1 | t-2 | 10d Avg |")
    lines.append("| --- | --- | --- | --- | --- |")
    _add_breadth_row("Advances", "advances", _format_count)
    _add_breadth_row("Declines", "declines", _format_count)
    _add_breadth_row("Unchanged", "unchanged", _format_count)
    _add_breadth_row("Net Advances", "net_advances", _format_count)
    _add_breadth_row(
        "Advance/Decline Ratio",
        "advance_decline_ratio",
        lambda value: _format_number(value, 4),
    )
    _add_breadth_row("Advance %", "advance_pct", _format_percent)
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

    if signals:
        lines.append("## Latest-Day Highlight (All Indicators)")
        all_dates = _signal_dates(signals)
        if all_dates:
            latest_date = all_dates[0]
            latest_rows = _group_by_date_indicator_and_type(signals, [latest_date])
            if latest_rows:
                lines.append("| Date | Indicator | Signal Type | Count | Tickers |")
                lines.append("| --- | --- | --- | --- | --- |")
                for date, indicator, signal_type, tickers in latest_rows:
                    lines.append(
                        f"| {date} | {indicator} | {signal_type} | {len(tickers)}"
                        f" | {_truncate_list(tickers)} |"
                    )
            else:
                lines.append("No signals on latest date.")
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

    lines.append("## Run Metadata")
    lines.append(f"- Run ID: {run_metadata.get('run_id', '-')}")
    lines.append(f"- Timestamp: {run_metadata.get('run_timestamp', '-')}")
    lines.append(
        f"- Date Range: {run_metadata.get('start_date', '-')} → {run_metadata.get('end_date', '-')}"
    )
    lines.append(f"- Interval: {run_metadata.get('interval', '-')}")
    lines.append(
        f"- Intraday Mode: {'enabled' if run_metadata.get('intraday_requested') else 'disabled'}"
    )
    if run_metadata.get("intraday_requested"):
        lines.append(
            f"- Intraday Interval: {run_metadata.get('intraday_interval', '-')}"
        )
        lines.append(
            "- Intraday RTH Only: "
            f"{run_metadata.get('intraday_regular_hours_only', '-')}"
        )
        lines.append(
            "- Intraday Synthetic Tickers: "
            f"{run_metadata.get('intraday_synthetic_ticker_count', 0)}"
        )
        lines.append(
            "- Intraday Persistence Skipped: metrics="
            f"{run_metadata.get('intraday_metric_persistence_skipped', False)}"
            ", aggregates="
            f"{run_metadata.get('intraday_aggregate_persistence_skipped', False)}"
        )
    lines.append(f"- Tickers: {len(run_metadata.get('tickers', []))}")

    lines.append("")
    lines.append("### Indicator Instances")
    if not isinstance(indicator_instances, list) or not indicator_instances:
        lines.append("No indicator instances configured.")
    else:
        lines.append("| Indicator | Criteria | Settings |")
        lines.append("| --- | --- | --- |")
        for instance in indicator_instances:
            if not isinstance(instance, dict):
                continue
            indicator_type = instance.get("id") or "unknown"
            instance_id = instance.get("instance_id") or "unknown"
            indicator_label = f"{indicator_type} ({instance_id})"

            settings = instance.get("settings") if isinstance(instance.get("settings"), dict) else {}
            criteria_description = _describe_criteria(settings.get("criteria"))

            settings_kv_parts: list[str] = []
            for key in sorted(settings.keys()):
                if key in {"criteria", "_context"}:
                    continue
                settings_kv_parts.append(f"{key}={settings[key]}")
            settings_description = "-" if not settings_kv_parts else ", ".join(settings_kv_parts)

            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_markdown_table_cell(str(indicator_label)),
                        _escape_markdown_table_cell(str(criteria_description)),
                        _escape_markdown_table_cell(str(settings_description)),
                    ]
                )
                + " |"
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

    return "\n".join(lines)
