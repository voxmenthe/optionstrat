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
from app.security_scan.reporting import (
    render_dispersion_html_report,
    render_dispersion_markdown_report,
    render_html_report,
    render_markdown_report,
)
from app.security_scan.scan_runner import BREADTH_HISTORY_METRICS, run_security_scan
from app.security_scan.storage import fetch_security_aggregate_series
from app.services.market_data import MarketDataService

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPORT_CHART_UNIVERSE_LABELS = {
    "all": "All Tickers",
    "nasdaq": "NASDAQ Tickers",
    "sp100": "S&P 100 Tickers",
}


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
        "--intraday",
        dest="intraday",
        action="store_true",
        help="Enable intraday nowcast mode (default is disabled).",
    )
    parser.add_argument(
        "--intraday-interval",
        type=str,
        default=None,
        help="Override intraday bar interval (e.g., 1m, 5m, 15m, 60m).",
    )
    parser.add_argument(
        "--intraday-min-bars",
        type=int,
        default=None,
        help="Minimum intraday bars required to synthesize the current session bar.",
    )
    parser.add_argument(
        "--no-html",
        dest="no_html",
        action="store_true",
        help="Disable HTML report output.",
    )
    parser.add_argument(
        "--no-dispersion-html",
        dest="no_dispersion_html",
        action="store_true",
        help="Disable dispersion HTML report output.",
    )
    parser.add_argument(
        "--backfill-aggregates",
        dest="backfill_aggregates",
        action="store_true",
        help="Backfill aggregate series across a date range.",
    )
    parser.add_argument(
        "--backfill-start-date",
        type=_parse_date,
        default=None,
        help="Override backfill start date (YYYY-MM-DD). Defaults to --start-date.",
    )
    parser.add_argument(
        "--backfill-end-date",
        type=_parse_date,
        default=None,
        help="Override backfill end date (YYYY-MM-DD). Defaults to --end-date.",
    )
    return parser


def _find_scan_reports_dir(start: Path) -> Path:
    for base in [start, *start.parents]:
        candidate = base / "scan-reports"
        if candidate.is_dir():
            return candidate
    return start / "scan-reports"


def _resolve_output_paths(
    output_arg: str | None,
    run_id: str,
) -> tuple[Path, Path, Path, Path, Path]:
    base_filename = f"security_scan_{run_id}"
    dispersion_base_filename = f"{base_filename}_dispersion"

    if output_arg:
        output_path = Path(output_arg).expanduser()
        if output_path.is_dir():
            return (
                output_path / f"{base_filename}.json",
                output_path / f"{base_filename}.md",
                output_path / f"{base_filename}.html",
                output_path / f"{dispersion_base_filename}.md",
                output_path / f"{dispersion_base_filename}.html",
            )
        json_path = output_path
        markdown_path = output_path.with_suffix(".md")
        html_path = output_path.with_suffix(".html")
        dispersion_markdown_path = output_path.with_name(
            f"{output_path.stem}_dispersion.md"
        )
        dispersion_html_path = output_path.with_name(
            f"{output_path.stem}_dispersion.html"
        )
        return (
            json_path,
            markdown_path,
            html_path,
            dispersion_markdown_path,
            dispersion_html_path,
        )

    scan_reports_dir = _find_scan_reports_dir(Path.cwd())
    scan_reports_dir.mkdir(parents=True, exist_ok=True)
    return (
        scan_reports_dir / f"{base_filename}.json",
        scan_reports_dir / f"{base_filename}.md",
        scan_reports_dir / f"{base_filename}.html",
        scan_reports_dir / f"{dispersion_base_filename}.md",
        scan_reports_dir / f"{dispersion_base_filename}.html",
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


def _collect_storage_usage(scan_reports_dir: Path) -> dict[str, int]:
    options_db_path = BACKEND_ROOT / "options.db"
    scan_db_bytes = _file_size(SECURITY_SCAN_DB_PATH)
    options_db_bytes = _file_size(options_db_path)
    task_logs_bytes = _directory_size(scan_reports_dir)
    return {
        "scan_db_bytes": scan_db_bytes,
        "options_db_bytes": options_db_bytes,
        "task_logs_bytes": task_logs_bytes,
        "total_bytes": scan_db_bytes + options_db_bytes + task_logs_bytes,
    }


def _serialize_aggregate_history_rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "as_of_date": row.as_of_date,
            "metric_key": row.metric_key,
            "value": row.value,
        }
        for row in rows
    ]


def _refresh_payload_aggregate_histories(
    payload: dict[str, Any],
    *,
    history_lookback_days: int = 30,
) -> list[dict[str, str]]:
    run_metadata = payload.get("run_metadata")
    aggregate_universes = payload.get("aggregate_universes")
    if not isinstance(run_metadata, dict) or not isinstance(aggregate_universes, dict):
        return []

    end_date_raw = run_metadata.get("end_date")
    if not isinstance(end_date_raw, str) or not end_date_raw:
        return []
    try:
        end_date = datetime.strptime(end_date_raw, "%Y-%m-%d").date()
    except ValueError:
        return []

    interval_raw = run_metadata.get("interval")
    interval = interval_raw if isinstance(interval_raw, str) and interval_raw else "day"
    start_date = (end_date - timedelta(days=history_lookback_days)).isoformat()

    aggregate_set_hashes_raw = run_metadata.get("aggregate_set_hashes")
    aggregate_set_hashes = (
        dict(aggregate_set_hashes_raw)
        if isinstance(aggregate_set_hashes_raw, dict)
        else {}
    )
    all_set_hash = run_metadata.get("set_hash")
    if isinstance(all_set_hash, str) and all_set_hash:
        aggregate_set_hashes.setdefault("all", all_set_hash)

    issues: list[dict[str, str]] = []
    for universe_key, universe_entry in aggregate_universes.items():
        if not isinstance(universe_entry, dict):
            continue

        set_hash_raw = universe_entry.get("set_hash")
        set_hash = (
            set_hash_raw
            if isinstance(set_hash_raw, str) and set_hash_raw
            else aggregate_set_hashes.get(universe_key)
        )
        if not isinstance(set_hash, str) or not set_hash:
            continue

        universe_entry["set_hash"] = set_hash
        try:
            history_rows = fetch_security_aggregate_series(
                set_hash=set_hash,
                metric_keys=BREADTH_HISTORY_METRICS,
                start_date=start_date,
                end_date=end_date_raw,
                interval=interval,
            )
            universe_entry["aggregates_history"] = _serialize_aggregate_history_rows(
                history_rows
            )
        except Exception as exc:
            issues.append(
                {
                    "universe": str(universe_key),
                    "issue": "aggregate_history_refresh_error",
                    "detail": str(exc),
                }
            )

    all_universe = aggregate_universes.get("all")
    if isinstance(all_universe, dict):
        all_history = all_universe.get("aggregates_history")
        if isinstance(all_history, list):
            payload["aggregates_history"] = all_history

    return issues


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
    intraday_interval = args.intraday_interval or config.intraday_interval
    intraday_min_bars = (
        args.intraday_min_bars
        if args.intraday_min_bars is not None
        else config.intraday_min_bars_required
    )
    if intraday_min_bars <= 0:
        print("Error: intraday-min-bars must be > 0", file=sys.stderr)
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
            intraday_enabled=args.intraday,
            intraday_interval=intraday_interval,
            intraday_regular_hours_only=config.intraday_regular_hours_only,
            intraday_min_bars_required=intraday_min_bars,
        )
    except Exception as exc:
        print(f"Error running scan: {exc}", file=sys.stderr)
        return 1

    run_id = payload.get("run_metadata", {}).get("run_id", "unknown")
    (
        json_path,
        markdown_path,
        html_path,
        dispersion_markdown_path,
        dispersion_html_path,
    ) = _resolve_output_paths(args.output, run_id)
    payload["run_metadata"]["output_path"] = str(json_path)
    payload["run_metadata"]["markdown_path"] = str(markdown_path)
    html_enabled = config.report_html and not args.no_html
    dispersion_html_enabled = (
        config.report_dispersion_html
        and config.dispersion.enabled
        and not args.no_dispersion_html
    )
    if html_enabled:
        payload["run_metadata"]["html_path"] = str(html_path)
    if dispersion_html_enabled:
        payload["run_metadata"]["dispersion_markdown_path"] = str(
            dispersion_markdown_path
        )
        payload["run_metadata"]["dispersion_html_path"] = str(dispersion_html_path)
    scan_reports_dir = _find_scan_reports_dir(Path.cwd())
    payload["storage_usage"] = _collect_storage_usage(scan_reports_dir)

    if args.backfill_aggregates:
        backfill_start = args.backfill_start_date or args.start_date
        backfill_end = args.backfill_end_date or args.end_date
        if backfill_start is None or backfill_end is None:
            print(
                "Error: backfill requires start and end dates",
                file=sys.stderr,
            )
            return 1
        if backfill_start > backfill_end:
            print(
                "Error: backfill start-date must be on or before end-date",
                file=sys.stderr,
            )
            return 1
        try:
            from app.security_scan.scan_runner import backfill_security_aggregates

            payload["run_metadata"]["aggregate_backfill"] = (
                backfill_security_aggregates(
                    config,
                    start_date=backfill_start,
                    end_date=backfill_end,
                    market_data_service=market_data_service,
                )
            )
            refresh_issues = _refresh_payload_aggregate_histories(payload)
            if refresh_issues:
                issues = payload.setdefault("issues", [])
                issues.extend(refresh_issues)
        except Exception as exc:
            issues = payload.setdefault("issues", [])
            issues.append({"issue": "aggregate_backfill_error", "detail": str(exc)})

    charts_html = ""
    if html_enabled:
        run_metadata = payload.get("run_metadata", {})
        aggregate_set_hashes = run_metadata.get("aggregate_set_hashes")
        if not isinstance(aggregate_set_hashes, dict):
            aggregate_set_hashes = {}
        all_set_hash = run_metadata.get("set_hash")
        if isinstance(all_set_hash, str) and all_set_hash:
            aggregate_set_hashes.setdefault("all", all_set_hash)
        if aggregate_set_hashes:
            plot_lookbacks = (
                config.report_plot_lookbacks
                or run_metadata.get("advance_decline_lookbacks")
                or [1]
            )
            chart_start_date = run_metadata.get("start_date")
            chart_end_date = run_metadata.get("end_date")
            if config.report_aggregate_lookback_days:
                chart_end = args.end_date or date.today()
                chart_start = chart_end - timedelta(
                    days=config.report_aggregate_lookback_days
                )
                chart_start_date = chart_start.isoformat()
                chart_end_date = chart_end.isoformat()
            try:
                from app.security_scan.reporting.aggregate_charts import (
                    build_multi_universe_aggregate_charts_html,
                )

                chart_universes: list[dict[str, str]] = []
                for universe_key in config.report_chart_universes:
                    set_hash = aggregate_set_hashes.get(universe_key)
                    if not isinstance(set_hash, str) or not set_hash:
                        continue
                    chart_universes.append(
                        {
                            "universe_key": universe_key,
                            "universe_label": REPORT_CHART_UNIVERSE_LABELS.get(
                                universe_key, universe_key
                            ),
                            "set_hash": set_hash,
                        }
                    )

                if chart_universes:
                    charts_html = build_multi_universe_aggregate_charts_html(
                        universes=chart_universes,
                        interval=run_metadata.get("interval", config.interval),
                        start_date=chart_start_date,
                        end_date=chart_end_date,
                        advance_decline_lookbacks=run_metadata.get(
                            "advance_decline_lookbacks"
                        ),
                        plot_lookbacks=plot_lookbacks,
                        max_points=config.report_max_points,
                        net_advances_ma_days=config.report_net_advances_ma_days,
                        net_advances_secondary_ma_days=(
                            config.report_net_advances_secondary_ma_days
                        ),
                        advance_pct_avg_smoothing_days=(
                            config.report_advance_pct_avg_smoothing_days
                        ),
                        roc_breadth_avg_smoothing_days=(
                            config.report_roc_breadth_avg_smoothing_days
                        ),
                        market_data_service=market_data_service,
                    )
            except Exception as exc:
                issues = payload.setdefault("issues", [])
                issues.append({"issue": "aggregate_chart_error", "detail": str(exc)})

    dispersion_charts_html = ""
    if dispersion_html_enabled:
        run_metadata = payload.get("run_metadata", {})
        aggregate_set_hashes = run_metadata.get("aggregate_set_hashes")
        if not isinstance(aggregate_set_hashes, dict):
            aggregate_set_hashes = {}
        all_set_hash = run_metadata.get("set_hash")
        if isinstance(all_set_hash, str) and all_set_hash:
            aggregate_set_hashes.setdefault("all", all_set_hash)
        if aggregate_set_hashes:
            chart_start_date = run_metadata.get("start_date")
            chart_end_date = run_metadata.get("end_date")
            if config.report_dispersion_lookback_days:
                chart_end = args.end_date or date.today()
                chart_start = chart_end - timedelta(
                    days=config.report_dispersion_lookback_days
                )
                chart_start_date = chart_start.isoformat()
                chart_end_date = chart_end.isoformat()

            try:
                from app.security_scan.reporting.dispersion_charts import (
                    build_multi_universe_dispersion_charts_html,
                )

                chart_universes: list[dict[str, str]] = []
                for universe_key in config.report_chart_universes:
                    set_hash = aggregate_set_hashes.get(universe_key)
                    if not isinstance(set_hash, str) or not set_hash:
                        continue
                    chart_universes.append(
                        {
                            "universe_key": universe_key,
                            "universe_label": REPORT_CHART_UNIVERSE_LABELS.get(
                                universe_key, universe_key
                            ),
                            "set_hash": set_hash,
                        }
                    )

                if chart_universes:
                    dispersion_charts_html = (
                        build_multi_universe_dispersion_charts_html(
                            universes=chart_universes,
                            interval=run_metadata.get("interval", config.interval),
                            start_date=chart_start_date,
                            end_date=chart_end_date,
                            windows=run_metadata.get("dispersion_windows"),
                            max_points=config.report_max_points,
                            show_components=config.report_dispersion_show_components,
                            show_diagnostics=config.report_dispersion_show_diagnostics,
                            smoothing_days=config.report_dispersion_smoothing_days,
                        )
                    )
            except Exception as exc:
                issues = payload.setdefault("issues", [])
                issues.append({"issue": "dispersion_chart_error", "detail": str(exc)})

    _write_json(json_path, payload)
    markdown_report = render_markdown_report(payload)
    _write_text(markdown_path, markdown_report)
    if html_enabled:
        html_report = render_html_report(payload, charts_html=charts_html)
        _write_text(html_path, html_report)
    if dispersion_html_enabled:
        dispersion_markdown_report = render_dispersion_markdown_report(payload)
        _write_text(dispersion_markdown_path, dispersion_markdown_report)
        dispersion_html_report = render_dispersion_html_report(
            payload,
            charts_html=dispersion_charts_html,
        )
        _write_text(dispersion_html_path, dispersion_html_report)

    print(json.dumps(payload, indent=2, sort_keys=True))
    artifact_paths = [
        json_path.resolve(),
        markdown_path.resolve(),
    ]
    if html_enabled:
        artifact_paths.append(html_path.resolve())
    if dispersion_html_enabled:
        artifact_paths.append(dispersion_markdown_path.resolve())
        artifact_paths.append(dispersion_html_path.resolve())
    print("Artifacts written:\n" + "\n".join(str(path) for path in artifact_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
