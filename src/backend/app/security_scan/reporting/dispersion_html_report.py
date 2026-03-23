from __future__ import annotations

from typing import Any

from app.security_scan.reporting.dispersion_markdown_report import (
    render_dispersion_markdown_report,
)
from app.security_scan.reporting.html_report import render_markdown_html_document


def render_dispersion_html_report(
    payload: dict[str, Any],
    *,
    charts_html: str | None = None,
) -> str:
    markdown_report = render_dispersion_markdown_report(payload)
    return render_markdown_html_document(
        markdown_report=markdown_report,
        report_title="Security Scan Dispersion Report",
        charts_html=charts_html,
        charts_heading="Dispersion Timeseries",
    )

