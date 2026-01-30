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
from app.security_scan.reporting import render_markdown_report
from app.security_scan.scan_runner import run_security_scan
from app.services.market_data import MarketDataService


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
    return parser


def _find_task_logs_dir(start: Path) -> Path:
    for base in [start, *start.parents]:
        candidate = base / "task-logs"
        if candidate.is_dir():
            return candidate
    return start / "task-logs"


def _resolve_output_paths(output_arg: str | None, run_id: str) -> tuple[Path, Path]:
    base_filename = f"security_scan_{run_id}"

    if output_arg:
        output_path = Path(output_arg).expanduser()
        if output_path.is_dir():
            return (
                output_path / f"{base_filename}.json",
                output_path / f"{base_filename}.md",
            )
        json_path = output_path
        markdown_path = output_path.with_suffix(".md")
        return json_path, markdown_path

    task_logs_dir = _find_task_logs_dir(Path.cwd())
    task_logs_dir.mkdir(parents=True, exist_ok=True)
    return (
        task_logs_dir / f"{base_filename}.json",
        task_logs_dir / f"{base_filename}.md",
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
    options_db_path = Path.cwd() / "options.db"
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
    json_path, markdown_path = _resolve_output_paths(args.output, run_id)
    payload["run_metadata"]["output_path"] = str(json_path)
    payload["run_metadata"]["markdown_path"] = str(markdown_path)
    task_logs_dir = _find_task_logs_dir(Path.cwd())
    payload["storage_usage"] = _collect_storage_usage(task_logs_dir)

    _write_json(json_path, payload)
    markdown_report = render_markdown_report(payload)
    _write_text(markdown_path, markdown_report)

    print(json.dumps(payload, indent=2, sort_keys=True))
    resolved_json_path = json_path.resolve()
    resolved_markdown_path = markdown_path.resolve()
    print(f"Artifacts written:\n{resolved_json_path}\n{resolved_markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
