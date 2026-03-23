from __future__ import annotations

from typing import Any


AGGREGATE_UNIVERSE_ORDER = [
    ("all", "All Tickers"),
    ("nasdaq", "NASDAQ Tickers"),
    ("sp100", "S&P 100 Tickers"),
]


def _format_number(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer() and decimals <= 0:
        return str(int(number))
    return f"{number:.{decimals}f}"


def _format_count(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _resolve_aggregate_universes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    aggregate_universes = payload.get("aggregate_universes")
    if not isinstance(aggregate_universes, dict):
        return []

    resolved: list[dict[str, Any]] = []
    for key, default_label in AGGREGATE_UNIVERSE_ORDER:
        universe = aggregate_universes.get(key)
        if not isinstance(universe, dict):
            continue
        label_raw = universe.get("label")
        label = (
            label_raw.strip()
            if isinstance(label_raw, str) and label_raw.strip()
            else default_label
        )
        aggregates = universe.get("aggregates")
        resolved.append(
            {
                "key": key,
                "label": label,
                "aggregates": aggregates if isinstance(aggregates, dict) else {},
            }
        )
    return resolved


def render_dispersion_markdown_report(payload: dict[str, Any]) -> str:
    run_metadata = payload.get("run_metadata", {})
    aggregate_universes = _resolve_aggregate_universes(payload)
    dispersion_windows = run_metadata.get("dispersion_windows")
    if not isinstance(dispersion_windows, list) or not dispersion_windows:
        dispersion_windows = [5, 21, 63]

    lines: list[str] = [
        "# Security Scan Dispersion Report",
        "",
        "Lockstep score is in `[0, 100]` where higher values indicate stronger co-movement.",
        "",
        "## Headline",
        "| Universe | Lockstep Score | Dispersion Score | Valid Tickers | Observations |",
        "| --- | --- | --- | --- | --- |",
    ]
    for universe in aggregate_universes:
        aggregates = universe["aggregates"]
        lines.append(
            f"| {universe['label']}"
            f" | {_format_number(aggregates.get('disp_lockstep_score'), 2)}"
            f" | {_format_number(aggregates.get('disp_dispersion_score'), 2)}"
            f" | {_format_count(aggregates.get('disp_valid_ticker_count'))}"
            f" | {_format_count(aggregates.get('disp_observation_count'))} |"
        )
    lines.append("")

    lines.extend(
        [
            "## Components (21D)",
            "| Universe | Corr Mean | PC1 Share | Sign Consensus | XS MAD Z |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for universe in aggregate_universes:
        aggregates = universe["aggregates"]
        lines.append(
            f"| {universe['label']}"
            f" | {_format_number(aggregates.get('disp_corr_mean_21d'), 4)}"
            f" | {_format_number(aggregates.get('disp_pca_pc1_share_21d'), 4)}"
            f" | {_format_number(aggregates.get('disp_sign_consensus_21d'), 4)}"
            f" | {_format_number(aggregates.get('disp_xs_mad_z_21d'), 4)} |"
        )
    lines.append("")

    lines.extend(
        [
            "## Reliability",
            "| Universe | "
            + " | ".join([f"Lockstep {window}D" for window in dispersion_windows])
            + " | "
            + " | ".join([f"Reliability {window}D" for window in dispersion_windows])
            + " |",
            "| --- | "
            + " | ".join(["---" for _ in dispersion_windows])
            + " | "
            + " | ".join(["---" for _ in dispersion_windows])
            + " |",
        ]
    )
    for universe in aggregate_universes:
        aggregates = universe["aggregates"]
        lockstep_cells = [
            _format_number(aggregates.get(f"disp_lockstep_{window}d"), 2)
            for window in dispersion_windows
        ]
        reliability_cells = [
            _format_number(aggregates.get(f"disp_reliability_{window}d"), 4)
            for window in dispersion_windows
        ]
        lines.append(
            f"| {universe['label']} | "
            + " | ".join(lockstep_cells + reliability_cells)
            + " |"
        )
    lines.append("")

    lines.append("## Run Metadata")
    lines.append(f"- Run ID: {run_metadata.get('run_id', '-')}")
    lines.append(f"- Timestamp: {run_metadata.get('run_timestamp', '-')}")
    lines.append(
        f"- Date Range: {run_metadata.get('start_date', '-')} → {run_metadata.get('end_date', '-')}"
    )
    lines.append(f"- Interval: {run_metadata.get('interval', '-')}")
    if run_metadata.get("dispersion_markdown_path"):
        lines.append(
            f"- Dispersion Markdown Output: {run_metadata.get('dispersion_markdown_path')}"
        )
    if run_metadata.get("dispersion_html_path"):
        lines.append(f"- Dispersion HTML Output: {run_metadata.get('dispersion_html_path')}")
    lines.append("")

    return "\n".join(lines)

