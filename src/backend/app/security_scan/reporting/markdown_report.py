from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


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


def _settings_summary(settings: dict[str, Any]) -> str:
    if not settings:
        return ""
    summary_parts: list[str] = []
    criteria = settings.get("criteria")
    if isinstance(criteria, list) and criteria:
        types = [item.get("type") for item in criteria if isinstance(item, dict)]
        types = [item for item in types if isinstance(item, str)]
        if types:
            summary_parts.append(f"criteria={','.join(types)}")
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
    if output_path:
        lines.append(f"- JSON Output: {output_path}")
    if markdown_path:
        lines.append(f"- Markdown Output: {markdown_path}")
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

    lines.append("## Indicator Signals")
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
            lines.append("| Ticker | Signal Date | Signal Type | Metadata |")
            lines.append("| --- | --- | --- | --- |")
            for signal in indicator_signals:
                lines.append(
                    f"| {signal.get('ticker', '-')} | {signal.get('signal_date', '-')}"
                    f" | {signal.get('signal_type', '-')}"
                    f" | {_format_metadata(signal.get('metadata', {}))} |"
                )
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

    return "\n".join(lines)
