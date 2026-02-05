from __future__ import annotations

from typing import Any

from markdown_it import MarkdownIt

from app.security_scan.reporting.markdown_report import render_markdown_report


def _wrap_indicator_appendix(body_html: str) -> str:
    marker = "<h2>Indicator Signals (Appendix)</h2>"
    marker_index = body_html.find(marker)
    if marker_index == -1:
        return body_html

    before = body_html[:marker_index]
    after = body_html[marker_index + len(marker) :]
    next_section_index = after.find("<h2>")
    if next_section_index == -1:
        appendix_body = after
        remainder = ""
    else:
        appendix_body = after[:next_section_index]
        remainder = after[next_section_index:]

    details_block = (
        "<details class=\"appendix\">\n"
        "<summary>Indicator Signals (Appendix)</summary>\n"
        f"{appendix_body}\n"
        "</details>\n"
    )
    return before + details_block + remainder


def render_html_report(
    payload: dict[str, Any],
    charts_html: str | None = None,
) -> str:
    markdown_report = render_markdown_report(payload)
    renderer = MarkdownIt("commonmark").enable("table")
    body_html = _wrap_indicator_appendix(renderer.render(markdown_report))

    if charts_html:
        charts_section = (
            "\n<section class=\"charts\">\n"
            "<h2>Aggregate Timeseries</h2>\n"
            f"{charts_html}\n"
            "</section>\n"
        )
        h1_end_index = body_html.find("</h1>")
        if h1_end_index != -1:
            insert_pos = h1_end_index + 5
            body_html = body_html[:insert_pos] + charts_section + body_html[insert_pos:]
        else:
            body_html = charts_section + body_html

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
        "      border: 2px solid #444;\n"
        "    }\n"
        "    th, td {\n"
        "      border: 1px solid #888;\n"
        "      padding: 8px 10px;\n"
        "      text-align: left;\n"
        "    }\n"
        "    th {\n"
        "      background: #e0e0e0;\n"
        "      font-weight: 700;\n"
        "      border-bottom: 2px solid #444;\n"
        "    }\n"
        "    tr:nth-child(even) {\n"
        "      background-color: #f4f4f4;\n"
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
        "      margin: 2rem 0;\n"
        "    }\n"
        "    .chart-block {\n"
        "      margin-top: 1.5rem;\n"
        "    }\n"
        "    .chart-block h3 {\n"
        "      margin: 0 0 0.75rem;\n"
        "    }\n"
        "    details.appendix {\n"
        "      margin-top: 1.4rem;\n"
        "    }\n"
        "    details.appendix summary {\n"
        "      cursor: pointer;\n"
        "      font-weight: 600;\n"
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
