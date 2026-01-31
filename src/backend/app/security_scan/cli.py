from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.security_scan.config_loader import load_security_scan_config
from app.security_scan.db import SECURITY_SCAN_DB_PATH
from app.security_scan.reporting import render_html_report, render_markdown_report
from app.security_scan.scan_runner import run_security_scan
from app.services.market_data import MarketDataService

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Expected YYYY-MM-DD."
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the security scan utility.")
    parser.add_argument(
        "--config-dir",
        type=str,
        default=None,
        help="Override config directory (defaults to module config folder).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path or directory for JSON results.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override market data provider (e.g., yfinance, polygon).",
    )
    cache_group = parser.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--use-cache",
        dest="use_cache",
        action="store_true",
        help="Enable provider caching (Redis/DB).",
    )
    cache_group.add_argument(
        "--no-cache",
        dest="use_cache",
        action="store_false",
        help="Disable provider caching (default).",
    )
    parser.set_defaults(use_cache=False)
    parser.add_argument(
        "--start-date",
        type=_parse_date,
        default=None,
        help="Override start date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=_parse_date,
        default=None,
        help="Override end date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--no-html",
        dest="no_html",
        action="store_true",
        help="Disable HTML report output.",
    )
    return parser


def _find_task_logs_dir(start: Path) -> Path:
    for base in [start, *start.parents]:
        candidate = base / "task-logs"
        if candidate.is_dir():
            return candidate
    return start / "task-logs"


def _resolve_output_paths(
    output_arg: str | None,
    run_id: str,
) -> tuple[Path, Path, Path]:
    base_filename = f"security_scan_{run_id}"

    if output_arg:
        output_path = Path(output_arg).expanduser()
        if output_path.is_dir():
            return (
                output_path / f"{base_filename}.json",
                output_path / f"{base_filename}.md",
                output_path / f"{base_filename}.html",
            )
        json_path = output_path
        markdown_path = output_path.with_suffix(".md")
        html_path = output_path.with_suffix(".html")
        return json_path, markdown_path, html_path

    task_logs_dir = _find_task_logs_dir(Path.cwd())
    task_logs_dir.mkdir(parents=True, exist_ok=True)
    return (
        task_logs_dir / f"{base_filename}.json",
        task_logs_dir / f"{base_filename}.md",
        task_logs_dir / f"{base_filename}.html",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def _file_size(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _collect_storage_usage(task_logs_dir: Path) -> dict[str, int]:
    options_db_path = BACKEND_ROOT / "options.db"
    scan_db_bytes = _file_size(SECURITY_SCAN_DB_PATH)
    options_db_bytes = _file_size(options_db_path)
    task_logs_bytes = _directory_size(task_logs_dir)
    return {
        "scan_db_bytes": scan_db_bytes,
        "options_db_bytes": options_db_bytes,
        "task_logs_bytes": task_logs_bytes,
        "total_bytes": scan_db_bytes + options_db_bytes + task_logs_bytes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _configure_logging()

    try:
        config = load_security_scan_config(args.config_dir)
    except Exception as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        return 1

    if args.end_date is None:
        args.end_date = date.today()
    if args.start_date is None:
        args.start_date = args.end_date - timedelta(days=config.lookback_days)

    if args.start_date and args.end_date and args.start_date > args.end_date:
        print("Error: start-date must be on or before end-date", file=sys.stderr)
        return 1

    market_data_service = MarketDataService(
        provider_name=args.provider,
        use_cache=args.use_cache,
    )

    try:
        payload = run_security_scan(
            config,
            start_date=args.start_date,
            end_date=args.end_date,
            market_data_service=market_data_service,
        )
    except Exception as exc:
        print(f"Error running scan: {exc}", file=sys.stderr)
        return 1

    run_id = payload.get("run_metadata", {}).get("run_id", "unknown")
    json_path, markdown_path, html_path = _resolve_output_paths(args.output, run_id)
    payload["run_metadata"]["output_path"] = str(json_path)
    payload["run_metadata"]["markdown_path"] = str(markdown_path)
    html_enabled = config.report_html and not args.no_html
    if html_enabled:
        payload["run_metadata"]["html_path"] = str(html_path)
    task_logs_dir = _find_task_logs_dir(Path.cwd())
    payload["storage_usage"] = _collect_storage_usage(task_logs_dir)

    charts_html = ""
    if html_enabled:
        run_metadata = payload.get("run_metadata", {})
        set_hash = run_metadata.get("set_hash")
        if set_hash:
            plot_lookbacks = (
                config.report_plot_lookbacks
                or run_metadata.get("advance_decline_lookbacks")
                or [1]
            )
            try:
                from app.security_scan.reporting.aggregate_charts import (
                    build_aggregate_charts_html,
                )

                charts_html = build_aggregate_charts_html(
                    set_hash=set_hash,
                    interval=run_metadata.get("interval", config.interval),
                    start_date=run_metadata.get("start_date"),
                    end_date=run_metadata.get("end_date"),
                    advance_decline_lookbacks=run_metadata.get(
                        "advance_decline_lookbacks"
                    ),
                    plot_lookbacks=plot_lookbacks,
                    max_points=config.report_max_points,
                )
            except Exception as exc:
                issues = payload.setdefault("issues", [])
                issues.append({"issue": "aggregate_chart_error", "detail": str(exc)})

    _write_json(json_path, payload)
    markdown_report = render_markdown_report(payload)
    _write_text(markdown_path, markdown_report)
    if html_enabled:
        html_report = render_html_report(payload, charts_html=charts_html)
        _write_text(html_path, html_report)

    print(json.dumps(payload, indent=2, sort_keys=True))
    resolved_json_path = json_path.resolve()
    resolved_markdown_path = markdown_path.resolve()
    if html_enabled:
        resolved_html_path = html_path.resolve()
        print(
            "Artifacts written:"
            f"\n{resolved_json_path}\n{resolved_markdown_path}\n{resolved_html_path}"
        )
    else:
        print(
            "Artifacts written:"
            f"\n{resolved_json_path}\n{resolved_markdown_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
