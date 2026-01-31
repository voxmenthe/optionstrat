from __future__ import annotations

from typing import Any

from markdown_it import MarkdownIt

from app.security_scan.reporting.markdown_report import render_markdown_report


def render_html_report(
    payload: dict[str, Any],
    charts_html: str | None = None,
) -> str:
    markdown_report = render_markdown_report(payload)
    renderer = MarkdownIt("commonmark").enable("table")
    body_html = renderer.render(markdown_report)

    if charts_html:
        body_html += "\n<section class=\"charts\">\n<h2>Aggregate Timeseries</h2>\n"
        body_html += charts_html
        body_html += "\n</section>\n"

    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>Security Scan Report</title>\n"
        "  <style>\n"
        "    :root {\n"
        "      color-scheme: light;\n"
        "    }\n"
        "    body {\n"
        "      margin: 24px;\n"
        "      font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif;\n"
        "      color: #111;\n"
        "      background: #fff;\n"
        "    }\n"
        "    .report {\n"
        "      max-width: 1100px;\n"
        "      margin: 0 auto;\n"
        "    }\n"
        "    h1, h2, h3 {\n"
        "      margin-top: 1.4rem;\n"
        "    }\n"
        "    table {\n"
        "      border-collapse: collapse;\n"
        "      width: 100%;\n"
        "      margin-bottom: 1.5rem;\n"
        "      font-size: 0.95rem;\n"
        "    }\n"
        "    th, td {\n"
        "      border: 1px solid #ddd;\n"
        "      padding: 6px 8px;\n"
        "      text-align: left;\n"
        "    }\n"
        "    th {\n"
        "      background: #f4f4f4;\n"
        "      font-weight: 600;\n"
        "    }\n"
        "    code {\n"
        "      background: #f6f6f6;\n"
        "      padding: 0 4px;\n"
        "      border-radius: 4px;\n"
        "    }\n"
        "    pre {\n"
        "      background: #f6f6f6;\n"
        "      padding: 12px;\n"
        "      border-radius: 6px;\n"
        "      overflow-x: auto;\n"
        "    }\n"
        "    .charts {\n"
        "      margin-top: 2rem;\n"
        "    }\n"
        "    .chart-block {\n"
        "      margin-top: 1.5rem;\n"
        "    }\n"
        "    .chart-block h3 {\n"
        "      margin: 0 0 0.75rem;\n"
        "    }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <article class=\"report\">\n"
        f"{body_html}\n"
        "  </article>\n"
        "</body>\n"
        "</html>\n"
    )
