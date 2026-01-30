from __future__ import annotations

import logging
import time
from dataclasses import asdict
from datetime import date, datetime, time as time_module, timedelta, timezone
from typing import Any

from app.security_scan.aggregates import compute_breadth
from app.security_scan.config_loader import IndicatorInstanceConfig, SecurityScanConfig
from app.security_scan.data_fetcher import MarketDataFetcher
from app.security_scan.indicators import load_indicator_registry
from app.security_scan.series_math import compute_roc, compute_sma
from app.security_scan.signals import IndicatorSignal, Signal
from app.security_scan.storage import (
    get_or_create_security_set,
    fetch_security_metric_values,
    upsert_security_aggregate_values,
    upsert_security_metric_values,
)
from app.services.market_data import MarketDataService

logger = logging.getLogger(__name__)

METRIC_DEFINITIONS: list[tuple[str, str, int, int]] = [
    ("sma:13", "sma", 13, 0),
    ("sma:28", "sma", 28, 0),
    ("sma:46", "sma", 46, 0),
    ("sma:8:shift=5", "sma", 8, 5),
    ("roc:17", "roc", 17, 0),
    ("roc:17:shift=5", "roc", 17, 5),
    ("roc:27", "roc", 27, 0),
    ("roc:27:shift=4", "roc", 27, 4),
]
METRIC_KEYS = [definition[0] for definition in METRIC_DEFINITIONS]
AGGREGATE_GROUP_PREFIXES = [
    "ma_13",
    "ma_28",
    "ma_46",
    "ma_8_shift_5",
    "roc_17_vs_5",
    "roc_27_vs_4",
]


def _resolve_date_range(
    config: SecurityScanConfig,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    resolved_end = end_date or datetime.now(timezone.utc).date()
    resolved_start = start_date or (resolved_end - timedelta(days=config.lookback_days))
    if resolved_start > resolved_end:
        raise ValueError("start_date must be on or before end_date")
    return resolved_start, resolved_end


def _ordered_prices(prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [row for row in prices if row.get("date")],
        key=lambda row: row.get("date") or "",
    )


def _extract_close_series(
    ordered: list[dict[str, Any]],
) -> list[tuple[str, float]]:
    closes: list[tuple[str, float]] = []
    for row in ordered:
        close = row.get("close")
        date_value = row.get("date")
        if close is None or not date_value:
            continue
        closes.append((str(date_value), float(close)))
    return closes


def _summarize_prices(
    ticker: str, prices: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    ordered = _ordered_prices(prices)
    close_series = _extract_close_series(ordered)
    return _summarize_prices_from_series(ticker, ordered, close_series)


def _summarize_prices_from_series(
    ticker: str,
    ordered: list[dict[str, Any]],
    close_series: list[tuple[str, float]],
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    if not ordered:
        return (
            {
                "ticker": ticker,
                "series_length": 0,
                "first_date": None,
                "last_date": None,
                "last_close": None,
                "prior_close": None,
                "close_change": None,
                "close_change_pct": None,
                "issues": ["empty_series"],
            },
            ["empty_series"],
        )

    first = ordered[0]
    last = ordered[-1]
    last_close = close_series[-1][1] if close_series else None
    prior_close = close_series[-2][1] if len(close_series) >= 2 else None
    close_change = None
    close_change_pct = None
    if last_close is None:
        issues.append("missing_last_close")
    if prior_close is None:
        issues.append("missing_prior_close")
    if last_close is not None and prior_close is not None:
        close_change = last_close - prior_close
        if prior_close == 0:
            issues.append("prior_close_zero")
        else:
            close_change_pct = close_change / prior_close

    return (
        {
            "ticker": ticker,
            "series_length": len(ordered),
            "first_date": first.get("date"),
            "last_date": last.get("date"),
            "last_close": last_close,
            "prior_close": prior_close,
            "close_change": close_change,
            "close_change_pct": close_change_pct,
            "issues": issues,
        },
        issues,
    )


def _resolve_indicator_instances(
    indicator_instances: list[IndicatorInstanceConfig],
) -> list[dict[str, Any]]:
    registry = load_indicator_registry()
    resolved: list[dict[str, Any]] = []
    for index, instance in enumerate(indicator_instances):
        evaluator = registry.get(instance.id)
        if evaluator is None:
            resolved.append(
                {
                    "id": instance.id,
                    "instance_id": instance.instance_id or f"{instance.id}_{index + 1}",
                    "settings": instance.settings,
                    "evaluator": None,
                    "error": "unknown_indicator",
                }
            )
            continue
        resolved.append(
            {
                "id": instance.id,
                "instance_id": instance.instance_id or f"{instance.id}_{index + 1}",
                "settings": instance.settings,
                "evaluator": evaluator,
            }
        )
    return resolved


def _ensure_indicator_signals(
    raw_signals: list[IndicatorSignal] | None,
    ticker: str,
    indicator_id: str,
    indicator_type: str,
) -> list[Signal]:
    if not raw_signals:
        return []
    signals: list[Signal] = []
    for raw in raw_signals:
        signals.append(
            Signal(
                ticker=ticker,
                indicator_id=indicator_id,
                indicator_type=indicator_type,
                signal_date=raw.signal_date,
                signal_type=raw.signal_type,
                metadata=raw.metadata,
            )
        )
    return signals


def _compute_metric_values(
    closes: list[float],
    cached_values: dict[str, float | None] | None = None,
) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    cached_values = cached_values or {}
    for metric_key, metric_type, period, shift in METRIC_DEFINITIONS:
        if metric_key in cached_values:
            values[metric_key] = cached_values[metric_key]
            continue
        if metric_type == "sma":
            values[metric_key] = compute_sma(closes, period, shift)
        else:
            values[metric_key] = compute_roc(closes, period, shift)
    return values


def _build_aggregate_records(
    aggregates: dict[str, Any],
    set_hash: str,
    as_of_date: str,
    interval: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key, value in aggregates.items():
        record: dict[str, Any] = {
            "set_hash": set_hash,
            "as_of_date": as_of_date,
            "interval": interval,
            "metric_key": key,
            "value": value,
        }
        if key in {"advance_pct"}:
            record["valid_count"] = aggregates.get("valid_ticker_count")
            record["missing_count"] = aggregates.get("missing_ticker_count")
        for prefix in AGGREGATE_GROUP_PREFIXES:
            if key.startswith(f"{prefix}_") and key.endswith("_pct"):
                record["valid_count"] = aggregates.get(f"{prefix}_valid_count")
                record["missing_count"] = aggregates.get(f"{prefix}_missing_count")
                break
        records.append(record)
    return records


def run_security_scan(
    config: SecurityScanConfig,
    start_date: date | None = None,
    end_date: date | None = None,
    market_data_service: MarketDataService | None = None,
) -> dict[str, Any]:
    resolved_start, resolved_end = _resolve_date_range(config, start_date, end_date)
    start_dt = datetime.combine(resolved_start, time_module.min)
    end_dt = datetime.combine(resolved_end + timedelta(days=1), time_module.min)

    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%d-%H%M")
    run_timestamp = now.isoformat()

    logger.info(
        "security_scan.run.start",
        extra={
            "run_id": run_id,
            "ticker_count": len(config.tickers),
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "interval": config.interval,
        },
    )

    started_at = time.monotonic()
    fetcher = MarketDataFetcher(market_data_service=market_data_service)
    ticker_summaries: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    signals: list[Signal] = []

    resolved_indicators = _resolve_indicator_instances(config.indicator_instances)
    indicator_instances_metadata: list[dict[str, Any]] = []
    for resolved in resolved_indicators:
        indicator_instances_metadata.append(
            {
                "id": resolved["id"],
                "instance_id": resolved["instance_id"],
                "settings": resolved["settings"],
            }
        )
        if resolved.get("error") == "unknown_indicator":
            issues.append(
                {
                    "indicator_id": resolved["instance_id"],
                    "issue": "unknown_indicator",
                    "detail": f"Indicator '{resolved['id']}' not registered.",
                }
            )

    for ticker in config.tickers:
        prices = fetcher.fetch_historical_prices(
            ticker=ticker,
            start_date=start_dt,
            end_date=end_dt,
            interval=config.interval,
        )
        ordered_prices = _ordered_prices(prices)
        close_series = _extract_close_series(ordered_prices)
        summary, summary_issues = _summarize_prices_from_series(
            ticker, ordered_prices, close_series
        )
        if summary_issues:
            for issue in summary_issues:
                issues.append({"ticker": ticker, "issue": issue})
        metric_values: dict[str, float | None] = {}
        if close_series:
            last_date = summary.get("last_date")
            cached_values: dict[str, float | None] = {}
            if last_date:
                cached_values = fetch_security_metric_values(
                    ticker=ticker,
                    as_of_date=str(last_date),
                    metric_keys=METRIC_KEYS,
                    interval=config.interval,
                )
            closes = [value for _, value in close_series]
            metric_values = _compute_metric_values(closes, cached_values)
            summary["metric_values"] = metric_values
            if last_date:
                values_to_upsert = []
                for metric_key, value in metric_values.items():
                    if metric_key in cached_values:
                        continue
                    values_to_upsert.append(
                        {
                            "ticker": ticker,
                            "as_of_date": str(last_date),
                            "interval": config.interval,
                            "metric_key": metric_key,
                            "value": value,
                        }
                    )
                if values_to_upsert:
                    try:
                        upsert_security_metric_values(values_to_upsert)
                    except Exception as exc:
                        issues.append(
                            {
                                "ticker": ticker,
                                "issue": "metric_storage_error",
                                "detail": str(exc),
                            }
                        )
        ticker_summaries.append(summary)

        for resolved in resolved_indicators:
            evaluator = resolved.get("evaluator")
            if evaluator is None:
                continue
            try:
                raw_signals = evaluator(prices, resolved["settings"])
            except Exception as exc:
                issues.append(
                    {
                        "ticker": ticker,
                        "indicator_id": resolved["instance_id"],
                        "issue": "indicator_error",
                        "detail": str(exc),
                    }
                )
                continue
            signals.extend(
                _ensure_indicator_signals(
                    raw_signals,
                    ticker=ticker,
                    indicator_id=resolved["instance_id"],
                    indicator_type=resolved["id"],
                )
            )

    duration_seconds = round(time.monotonic() - started_at, 3)

    logger.info(
        "security_scan.run.finish",
        extra={
            "run_id": run_id,
            "duration_seconds": duration_seconds,
            "ticker_count": len(config.tickers),
            "issues": len(issues),
        },
    )

    run_metadata = {
        "run_id": run_id,
        "run_timestamp": run_timestamp,
        "tickers": config.tickers,
        "lookback_days": config.lookback_days,
        "interval": config.interval,
        "start_date": resolved_start.isoformat(),
        "end_date": resolved_end.isoformat(),
        "config_dir": str(config.config_dir),
        "duration_seconds": duration_seconds,
        "indicator_instances": indicator_instances_metadata,
        "indicator_count": len(indicator_instances_metadata),
    }

    aggregates = compute_breadth(ticker_summaries)
    try:
        set_hash = get_or_create_security_set(config.tickers)
        aggregate_records = _build_aggregate_records(
            aggregates=aggregates,
            set_hash=set_hash,
            as_of_date=resolved_end.isoformat(),
            interval=config.interval,
        )
        if aggregate_records:
            upsert_security_aggregate_values(aggregate_records)
    except Exception as exc:
        issues.append({"issue": "aggregate_storage_error", "detail": str(exc)})

    return {
        "run_metadata": run_metadata,
        "ticker_summaries": ticker_summaries,
        "signals": [asdict(signal) for signal in signals],
        "aggregates": aggregates,
        "issues": issues,
    }
