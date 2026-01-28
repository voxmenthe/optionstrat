from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict
from datetime import date, datetime, time as time_module, timedelta, timezone
from typing import Any

from app.security_scan.aggregates import compute_breadth
from app.security_scan.config_loader import IndicatorInstanceConfig, SecurityScanConfig
from app.security_scan.data_fetcher import MarketDataFetcher
from app.security_scan.indicators import load_indicator_registry
from app.security_scan.signals import IndicatorSignal, Signal
from app.services.market_data import MarketDataService

logger = logging.getLogger(__name__)


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
    issues: list[str] = []
    ordered = _ordered_prices(prices)
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
    close_series = _extract_close_series(ordered)
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


def run_security_scan(
    config: SecurityScanConfig,
    start_date: date | None = None,
    end_date: date | None = None,
    market_data_service: MarketDataService | None = None,
) -> dict[str, Any]:
    resolved_start, resolved_end = _resolve_date_range(config, start_date, end_date)
    start_dt = datetime.combine(resolved_start, time_module.min)
    end_dt = datetime.combine(resolved_end + timedelta(days=1), time_module.min)

    run_id = uuid.uuid4().hex
    run_timestamp = datetime.now(timezone.utc).isoformat()

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
        summary, summary_issues = _summarize_prices(ticker, prices)
        if summary_issues:
            for issue in summary_issues:
                issues.append({"ticker": ticker, "issue": issue})
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

    return {
        "run_metadata": run_metadata,
        "ticker_summaries": ticker_summaries,
        "signals": [asdict(signal) for signal in signals],
        "aggregates": compute_breadth(ticker_summaries),
        "issues": issues,
    }
