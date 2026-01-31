"""Reporting utilities."""

from app.security_scan.reporting.html_report import render_html_report
from app.security_scan.reporting.markdown_report import render_markdown_report

__all__ = ["render_html_report", "render_markdown_report"]
