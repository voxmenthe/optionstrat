from __future__ import annotations

import logging
import time
from dataclasses import asdict
from datetime import date, datetime, time as time_module, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.security_scan.aggregates import compute_breadth
from app.security_scan.config_loader import IndicatorInstanceConfig, SecurityScanConfig
from app.security_scan.data_fetcher import MarketDataFetcher
from app.security_scan.dispersion import (
    DEFAULT_DISPERSION_WINDOWS,
    DispersionConfig,
    build_dispersion_metric_keys,
    build_dispersion_state,
    compute_dispersion_snapshot,
)
from app.security_scan.indicators import load_indicator_registry
from app.security_scan.indicators.scl_v4_x5 import (
    compute_countdown_series as compute_scl_countdown_series,
    compute_prior_window_flags as compute_scl_prior_window_flags,
)
from app.security_scan.series_math import compute_roc, compute_sma
from app.security_scan.signals import IndicatorSignal, Signal
from app.security_scan.storage import (
    get_or_create_security_set,
    fetch_security_aggregate_series,
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
AGGREGATE_UNIVERSE_ORDER = ("all", "nasdaq", "sp100")
AGGREGATE_UNIVERSE_LABELS = {
    "all": "All Tickers",
    "nasdaq": "NASDAQ Tickers",
    "sp100": "S&P 100 Tickers",
}
BREADTH_HISTORY_METRICS = [
    "advances",
    "declines",
    "unchanged",
    "net_advances",
    "advance_decline_ratio",
    "advance_pct",
]
DISPERSION_HISTORY_METRICS = build_dispersion_metric_keys(DEFAULT_DISPERSION_WINDOWS)
MARKET_SNAPSHOT_TICKERS = ["SPY", "QQQ", "IWM"]
MARKET_TIMEZONE = ZoneInfo("America/New_York")
REGULAR_SESSION_START = time_module(9, 30)
REGULAR_SESSION_END = time_module(16, 0)


def _compute_percent_change(
    close_series: list[tuple[str, float]], lookback: int
) -> float | None:
    if len(close_series) <= lookback:
        return None
    last_close = close_series[-1][1]
    prior_close = close_series[-1 - lookback][1]
    if prior_close == 0:
        return None
    return (last_close - prior_close) / prior_close


def _compute_market_stats(
    fetcher: MarketDataFetcher,
    start_dt: datetime,
    end_dt: datetime,
    interval: str,
    market_prices_by_ticker: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for ticker in MARKET_SNAPSHOT_TICKERS:
        prices = None
        if market_prices_by_ticker is not None:
            prices = market_prices_by_ticker.get(ticker)
        if prices is None:
            prices = fetcher.fetch_historical_prices(
                ticker=ticker,
                start_date=start_dt,
                end_date=end_dt,
                interval=interval,
            )
        ordered_prices = _ordered_prices(prices)
        close_series = _extract_close_series(ordered_prices)
        last_date = close_series[-1][0] if close_series else None
        last_close = close_series[-1][1] if close_series else None
        stats[ticker] = {
            "as_of_date": last_date,
            "last_close": last_close,
            "change_1d_pct": _compute_percent_change(close_series, 1),
            "change_5d_pct": _compute_percent_change(close_series, 5),
        }
    return stats


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


def _to_utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt_value = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            dt_value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_intraday_synthetic_bar(
    intraday_prices: list[dict[str, Any]],
    *,
    min_bars_required: int,
    regular_hours_only: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    rows_by_market_date: dict[str, list[dict[str, Any]]] = {}
    for row in intraday_prices:
        timestamp_utc = _to_utc_datetime(row.get("timestamp") or row.get("date"))
        if timestamp_utc is None:
            continue
        timestamp_local = timestamp_utc.astimezone(MARKET_TIMEZONE)
        if regular_hours_only:
            local_time = timestamp_local.time()
            if local_time < REGULAR_SESSION_START or local_time > REGULAR_SESSION_END:
                continue
        open_value = _to_float(row.get("open"))
        high_value = _to_float(row.get("high"))
        low_value = _to_float(row.get("low"))
        close_value = _to_float(row.get("close"))
        volume_value = _to_float(row.get("volume"))
        if (
            open_value is None
            or high_value is None
            or low_value is None
            or close_value is None
            or volume_value is None
        ):
            continue
        market_date = timestamp_local.date().isoformat()
        rows_by_market_date.setdefault(market_date, []).append(
            {
                "timestamp_utc": timestamp_utc,
                "open": open_value,
                "high": high_value,
                "low": low_value,
                "close": close_value,
                "volume": volume_value,
            }
        )

    if not rows_by_market_date:
        return None, None

    latest_market_date = max(rows_by_market_date.keys())
    latest_rows = rows_by_market_date[latest_market_date]
    latest_rows.sort(key=lambda item: item["timestamp_utc"])
    if len(latest_rows) < max(1, min_bars_required):
        return (
            None,
            {
                "market_date": latest_market_date,
                "bar_count": len(latest_rows),
                "reason": "insufficient_bars",
            },
        )

    synthetic_bar = {
        "date": latest_market_date,
        "open": latest_rows[0]["open"],
        "high": max(row["high"] for row in latest_rows),
        "low": min(row["low"] for row in latest_rows),
        "close": latest_rows[-1]["close"],
        "volume": int(round(sum(row["volume"] for row in latest_rows))),
        "_intraday_synthetic": True,
        "_intraday_bar_count": len(latest_rows),
        "_intraday_last_bar_timestamp": latest_rows[-1]["timestamp_utc"].isoformat(),
    }
    return synthetic_bar, None


def _merge_with_synthetic_bar(
    daily_prices: list[dict[str, Any]],
    synthetic_bar: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    merged_prices: list[dict[str, Any]] = []
    replaced = False
    synthetic_date = str(synthetic_bar.get("date"))
    for row in _ordered_prices(daily_prices):
        row_date = row.get("date")
        if row_date and str(row_date) == synthetic_date:
            merged_row = {**row, **synthetic_bar}
            merged_prices.append(merged_row)
            replaced = True
        else:
            merged_prices.append(row)
    if not replaced:
        merged_prices.append(synthetic_bar)
    return _ordered_prices(merged_prices), replaced


def _summarize_prices(
    ticker: str,
    prices: list[dict[str, Any]],
    advance_decline_lookbacks: list[int] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    ordered = _ordered_prices(prices)
    close_series = _extract_close_series(ordered)
    return _summarize_prices_from_series(
        ticker,
        ordered,
        close_series,
        advance_decline_lookbacks=advance_decline_lookbacks,
    )


def _summarize_prices_from_series(
    ticker: str,
    ordered: list[dict[str, Any]],
    close_series: list[tuple[str, float]],
    advance_decline_lookbacks: list[int] | None = None,
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

    close_by_offset: dict[int, float | None] = {}
    if advance_decline_lookbacks and close_series:
        last_index = len(close_series) - 1
        for lookback in advance_decline_lookbacks:
            index = last_index - lookback
            if index < 0:
                close_by_offset[lookback] = None
            else:
                close_by_offset[lookback] = close_series[index][1]

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
            "close_by_offset": close_by_offset,
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
    aggregate_group_prefixes: list[str],
    universe_ticker_count: int | None = None,
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
        for prefix in aggregate_group_prefixes:
            if key.startswith(f"{prefix}_") and key.endswith("_pct"):
                record["valid_count"] = aggregates.get(f"{prefix}_valid_count")
                record["missing_count"] = aggregates.get(f"{prefix}_missing_count")
                break
        if key.startswith("disp_"):
            valid_count_raw = aggregates.get("disp_valid_ticker_count")
            if valid_count_raw is not None:
                try:
                    valid_count = max(0, int(valid_count_raw))
                except (TypeError, ValueError):
                    valid_count = None
                if valid_count is not None:
                    record["valid_count"] = valid_count
                    if universe_ticker_count is not None:
                        record["missing_count"] = max(
                            0, int(universe_ticker_count) - valid_count
                        )
        records.append(record)
    return records


def _normalize_lookbacks(advance_decline_lookbacks: list[int] | None) -> list[int]:
    if not advance_decline_lookbacks:
        return [1]
    seen: set[int] = set()
    normalized: list[int] = []
    for value in advance_decline_lookbacks:
        lookback = int(value)
        if lookback <= 0 or lookback in seen:
            continue
        seen.add(lookback)
        normalized.append(lookback)
    return normalized or [1]


def _dedupe_tickers(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for ticker in tickers:
        normalized = str(ticker).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _aggregate_group_prefixes(lookbacks: list[int] | None) -> list[str]:
    normalized_lookbacks = _normalize_lookbacks(lookbacks)
    return AGGREGATE_GROUP_PREFIXES + [
        f"ad_{lookback}" for lookback in normalized_lookbacks if lookback != 1
    ]


def _build_aggregate_universe_tickers(
    config: SecurityScanConfig,
) -> dict[str, list[str]]:
    all_tickers = _dedupe_tickers(config.tickers)
    all_set = set(all_tickers)
    nasdaq_tickers = [
        ticker for ticker in _dedupe_tickers(config.nasdaq_tickers) if ticker in all_set
    ]
    sp100_tickers = [
        ticker for ticker in _dedupe_tickers(config.sp100_tickers) if ticker in all_set
    ]
    return {
        "all": all_tickers,
        "nasdaq": nasdaq_tickers,
        "sp100": sp100_tickers,
    }


def _select_ticker_summaries(
    ticker_summaries: list[dict[str, Any]],
    universe_tickers: list[str],
) -> list[dict[str, Any]]:
    if not universe_tickers:
        return []
    summary_by_ticker: dict[str, dict[str, Any]] = {}
    for summary in ticker_summaries:
        ticker = summary.get("ticker")
        if not isinstance(ticker, str) or not ticker:
            continue
        summary_by_ticker[ticker] = summary
    return [
        summary_by_ticker[ticker]
        for ticker in universe_tickers
        if ticker in summary_by_ticker
    ]


def _serialize_history(
    rows: list[Any],
) -> list[dict[str, Any]]:
    return [
        {
            "as_of_date": row.as_of_date,
            "metric_key": row.metric_key,
            "value": row.value,
        }
        for row in rows
    ]


def _build_daily_ticker_summaries(
    ticker: str,
    ordered_prices: list[dict[str, Any]],
    close_series: list[tuple[str, float]],
    advance_decline_lookbacks: list[int] | None = None,
) -> dict[str, dict[str, Any]]:
    lookbacks = _normalize_lookbacks(advance_decline_lookbacks)
    summaries: dict[str, dict[str, Any]] = {}
    if not close_series:
        return summaries
    closes = [value for _, value in close_series]
    scl_flags_by_date: dict[str, dict[str, float | bool | None]] = {}
    scl_series = compute_scl_countdown_series(ordered_prices)
    if scl_series:
        scl_flags_by_date = compute_scl_prior_window_flags(scl_series, lookback=5)
    for index, (date_value, last_close) in enumerate(close_series):
        prior_close = closes[index - 1] if index > 0 else None
        close_by_offset = {}
        for lookback in lookbacks:
            offset_index = index - lookback
            close_by_offset[lookback] = (
                closes[offset_index] if offset_index >= 0 else None
            )
        metric_values = _compute_metric_values(closes[: index + 1])
        scl_flags = scl_flags_by_date.get(date_value) or {}
        summaries[date_value] = {
            "ticker": ticker,
            "last_date": date_value,
            "last_close": last_close,
            "prior_close": prior_close,
            "close_by_offset": close_by_offset,
            "metric_values": metric_values,
            "scl_5bar_high": scl_flags.get("high"),
            "scl_5bar_low": scl_flags.get("low"),
        }
    return summaries


def _empty_ticker_summary(
    ticker: str,
    advance_decline_lookbacks: list[int] | None = None,
) -> dict[str, Any]:
    lookbacks = _normalize_lookbacks(advance_decline_lookbacks)
    return {
        "ticker": ticker,
        "last_date": None,
        "last_close": None,
        "prior_close": None,
        "close_by_offset": {lookback: None for lookback in lookbacks},
        "metric_values": {},
        "scl_5bar_high": None,
        "scl_5bar_low": None,
    }


def build_backfill_aggregate_records(
    *,
    tickers: list[str],
    price_series_by_ticker: dict[str, list[dict[str, Any]]],
    advance_decline_lookbacks: list[int] | None,
    dispersion_config: DispersionConfig | None = None,
    set_hash: str,
    interval: str,
) -> list[dict[str, Any]]:
    summaries_by_ticker: dict[str, dict[str, dict[str, Any]]] = {}
    all_dates: set[str] = set()
    for ticker in tickers:
        ordered = _ordered_prices(price_series_by_ticker.get(ticker, []))
        close_series = _extract_close_series(ordered)
        summaries = _build_daily_ticker_summaries(
            ticker,
            ordered,
            close_series,
            advance_decline_lookbacks=advance_decline_lookbacks,
        )
        summaries_by_ticker[ticker] = summaries
        all_dates.update(summaries.keys())

    if not all_dates:
        return []

    lookbacks = _normalize_lookbacks(advance_decline_lookbacks)
    aggregate_group_prefixes = _aggregate_group_prefixes(lookbacks)
    dispersion_state = None
    if dispersion_config and dispersion_config.enabled:
        return_horizon = (
            dispersion_config.return_horizons[0]
            if dispersion_config.return_horizons
            else 1
        )
        dispersion_state = build_dispersion_state(
            price_series_by_ticker,
            tickers,
            return_horizon=return_horizon,
        )
    records: list[dict[str, Any]] = []
    for as_of_date in sorted(all_dates):
        ticker_summaries = []
        for ticker in tickers:
            summary = summaries_by_ticker.get(ticker, {}).get(as_of_date)
            if summary is None:
                summary = _empty_ticker_summary(
                    ticker,
                    advance_decline_lookbacks=lookbacks,
                )
            ticker_summaries.append(summary)
        aggregates = compute_breadth(
            ticker_summaries,
            advance_decline_lookbacks=lookbacks,
        )
        if dispersion_state is not None and dispersion_config is not None:
            dispersion_metrics = compute_dispersion_snapshot(
                dispersion_state,
                as_of_date=as_of_date,
                config=dispersion_config,
            )
            aggregates.update(dispersion_metrics)
        records.extend(
            _build_aggregate_records(
                aggregates=aggregates,
                set_hash=set_hash,
                as_of_date=as_of_date,
                interval=interval,
                aggregate_group_prefixes=aggregate_group_prefixes,
                universe_ticker_count=len(tickers),
            )
        )
    return records


def backfill_security_aggregates(
    config: SecurityScanConfig,
    *,
    start_date: date,
    end_date: date,
    market_data_service: MarketDataService | None = None,
) -> dict[str, Any]:
    resolved_start, resolved_end = _resolve_date_range(
        config, start_date=start_date, end_date=end_date
    )
    logger.info(
        "security_scan.aggregate_backfill.start",
        extra={
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "ticker_count": len(config.tickers),
        },
    )
    start_dt = datetime.combine(resolved_start, time_module.min)
    end_dt = datetime.combine(resolved_end + timedelta(days=1), time_module.min)

    fetcher = MarketDataFetcher(market_data_service=market_data_service)
    price_series_by_ticker: dict[str, list[dict[str, Any]]] = {}
    issues: list[dict[str, str]] = []
    for ticker in config.tickers:
        prices = fetcher.fetch_historical_prices(
            ticker=ticker,
            start_date=start_dt,
            end_date=end_dt,
            interval=config.interval,
        )
        if not prices:
            issues.append({"ticker": ticker, "issue": "empty_prices"})
        price_series_by_ticker[ticker] = prices

    universe_tickers_map = _build_aggregate_universe_tickers(config)
    set_hashes: dict[str, str] = {}
    date_count_by_universe: dict[str, int] = {}
    records_written_by_universe: dict[str, int] = {}
    total_records_written = 0
    for universe_key in AGGREGATE_UNIVERSE_ORDER:
        universe_tickers = universe_tickers_map.get(universe_key, [])
        if not universe_tickers:
            date_count_by_universe[universe_key] = 0
            records_written_by_universe[universe_key] = 0
            continue
        try:
            set_hash = get_or_create_security_set(universe_tickers)
            set_hashes[universe_key] = set_hash
            records = build_backfill_aggregate_records(
                tickers=universe_tickers,
                price_series_by_ticker=price_series_by_ticker,
                advance_decline_lookbacks=config.advance_decline_lookbacks,
                dispersion_config=config.dispersion,
                set_hash=set_hash,
                interval=config.interval,
            )
            if records:
                upsert_security_aggregate_values(records)
            records_written = len(records)
            date_count = len({record["as_of_date"] for record in records})
            records_written_by_universe[universe_key] = records_written
            date_count_by_universe[universe_key] = date_count
            total_records_written += records_written
        except Exception as exc:
            issues.append(
                {
                    "universe": universe_key,
                    "issue": "aggregate_backfill_storage_error",
                    "detail": str(exc),
                }
            )
            records_written_by_universe[universe_key] = 0
            date_count_by_universe[universe_key] = 0

    all_set_hash = set_hashes.get("all")
    all_date_count = date_count_by_universe.get("all", 0)
    all_records_written = records_written_by_universe.get("all", 0)
    logger.info(
        "security_scan.aggregate_backfill.finish",
        extra={
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "dates": all_date_count,
            "records_written": all_records_written,
            "total_records_written": total_records_written,
        },
    )
    return {
        "set_hash": all_set_hash,
        "set_hashes": set_hashes,
        "start_date": resolved_start.isoformat(),
        "end_date": resolved_end.isoformat(),
        "date_count": all_date_count,
        "date_count_by_universe": date_count_by_universe,
        "records_written": all_records_written,
        "records_written_by_universe": records_written_by_universe,
        "total_records_written": total_records_written,
        "issues": issues,
    }


def run_security_scan(
    config: SecurityScanConfig,
    start_date: date | None = None,
    end_date: date | None = None,
    market_data_service: MarketDataService | None = None,
    *,
    intraday_enabled: bool = False,
    intraday_interval: str = "1m",
    intraday_regular_hours_only: bool = True,
    intraday_min_bars_required: int = 30,
) -> dict[str, Any]:
    resolved_start, resolved_end = _resolve_date_range(config, start_date, end_date)
    start_dt = datetime.combine(resolved_start, time_module.min)
    end_dt = datetime.combine(resolved_end + timedelta(days=1), time_module.min)
    now = datetime.now(timezone.utc)
    intraday_start_dt = now - timedelta(days=2)
    intraday_end_dt = now + timedelta(minutes=1)

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
    issues: list[dict[str, str]] = []
    signals: list[Signal] = []
    ticker_summaries: list[dict[str, Any]] = []
    intraday_synthetic_tickers: set[str] = set()
    intraday_synthetic_scan_tickers: set[str] = set()
    intraday_last_bar_by_ticker: dict[str, str] = {}
    intraday_bar_count_by_ticker: dict[str, int] = {}

    market_prices_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for ticker in MARKET_SNAPSHOT_TICKERS:
        benchmark_prices = fetcher.fetch_historical_prices(
            ticker=ticker,
            start_date=start_dt,
            end_date=end_dt,
            interval=config.interval,
        )
        if intraday_enabled:
            intraday_prices = fetcher.fetch_intraday_prices(
                ticker=ticker,
                start_datetime=intraday_start_dt,
                end_datetime=intraday_end_dt,
                interval=intraday_interval,
                regular_hours_only=intraday_regular_hours_only,
            )
            synthetic_bar, intraday_skip = _build_intraday_synthetic_bar(
                intraday_prices,
                min_bars_required=intraday_min_bars_required,
                regular_hours_only=intraday_regular_hours_only,
            )
            if synthetic_bar:
                benchmark_prices, _ = _merge_with_synthetic_bar(
                    benchmark_prices,
                    synthetic_bar,
                )
                intraday_synthetic_tickers.add(ticker)
                intraday_last_bar_by_ticker[ticker] = str(
                    synthetic_bar.get("_intraday_last_bar_timestamp")
                )
                intraday_bar_count_by_ticker[ticker] = int(
                    synthetic_bar.get("_intraday_bar_count", 0)
                )
            elif intraday_skip:
                issues.append(
                    {
                        "ticker": ticker,
                        "issue": "intraday_synthetic_skipped",
                        "detail": (
                            f"{intraday_skip.get('reason')} "
                            f"(date={intraday_skip.get('market_date')}, "
                            f"bars={intraday_skip.get('bar_count')})"
                        ),
                    }
                )
            elif not intraday_prices:
                issues.append(
                    {
                        "ticker": ticker,
                        "issue": "intraday_fetch_error",
                        "detail": "no_intraday_prices",
                    }
                )
        market_prices_by_ticker[ticker] = benchmark_prices

    indicator_context = {
        "benchmark_prices_by_ticker": market_prices_by_ticker,
        "benchmark_tickers": MARKET_SNAPSHOT_TICKERS,
    }

    resolved_indicators = _resolve_indicator_instances(config.indicator_instances)
    indicator_instances_metadata: list[dict[str, Any]] = []
    price_series_by_ticker: dict[str, list[dict[str, Any]]] = {}
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
        effective_prices = prices
        synthetic_bar: dict[str, Any] | None = None
        if intraday_enabled:
            intraday_prices = fetcher.fetch_intraday_prices(
                ticker=ticker,
                start_datetime=intraday_start_dt,
                end_datetime=intraday_end_dt,
                interval=intraday_interval,
                regular_hours_only=intraday_regular_hours_only,
            )
            synthetic_bar, intraday_skip = _build_intraday_synthetic_bar(
                intraday_prices,
                min_bars_required=intraday_min_bars_required,
                regular_hours_only=intraday_regular_hours_only,
            )
            if synthetic_bar:
                effective_prices, _ = _merge_with_synthetic_bar(
                    effective_prices,
                    synthetic_bar,
                )
                intraday_synthetic_tickers.add(ticker)
                intraday_synthetic_scan_tickers.add(ticker)
                intraday_last_bar_by_ticker[ticker] = str(
                    synthetic_bar.get("_intraday_last_bar_timestamp")
                )
                intraday_bar_count_by_ticker[ticker] = int(
                    synthetic_bar.get("_intraday_bar_count", 0)
                )
            elif intraday_skip:
                issues.append(
                    {
                        "ticker": ticker,
                        "issue": "intraday_synthetic_skipped",
                        "detail": (
                            f"{intraday_skip.get('reason')} "
                            f"(date={intraday_skip.get('market_date')}, "
                            f"bars={intraday_skip.get('bar_count')})"
                        ),
                    }
                )
            elif not intraday_prices:
                issues.append(
                    {
                        "ticker": ticker,
                        "issue": "intraday_fetch_error",
                        "detail": "no_intraday_prices",
                    }
                )

        price_series_by_ticker[ticker] = effective_prices
        ordered_prices = _ordered_prices(effective_prices)
        close_series = _extract_close_series(ordered_prices)
        summary, summary_issues = _summarize_prices_from_series(
            ticker,
            ordered_prices,
            close_series,
            advance_decline_lookbacks=config.advance_decline_lookbacks,
        )
        scl_flags_by_date: dict[str, dict[str, float | bool | None]] = {}
        scl_series = compute_scl_countdown_series(ordered_prices)
        if scl_series:
            scl_flags_by_date = compute_scl_prior_window_flags(
                scl_series, lookback=5
            )
        last_date = summary.get("last_date")
        if last_date:
            scl_flags = scl_flags_by_date.get(str(last_date)) or {}
            summary["scl_5bar_high"] = scl_flags.get("high")
            summary["scl_5bar_low"] = scl_flags.get("low")
        else:
            summary["scl_5bar_high"] = None
            summary["scl_5bar_low"] = None
        summary["uses_intraday_synthetic_bar"] = bool(synthetic_bar)
        summary["intraday_bar_count"] = (
            int(synthetic_bar.get("_intraday_bar_count", 0)) if synthetic_bar else None
        )
        summary["intraday_last_bar_timestamp"] = (
            str(synthetic_bar.get("_intraday_last_bar_timestamp"))
            if synthetic_bar
            else None
        )
        if summary_issues:
            for issue in summary_issues:
                issues.append({"ticker": ticker, "issue": issue})
        metric_values: dict[str, float | None] = {}
        if close_series:
            last_date = summary.get("last_date")
            cached_values: dict[str, float | None] = {}
            if last_date and not summary["uses_intraday_synthetic_bar"]:
                cached_values = fetch_security_metric_values(
                    ticker=ticker,
                    as_of_date=str(last_date),
                    metric_keys=METRIC_KEYS,
                    interval=config.interval,
                )
            closes = [value for _, value in close_series]
            metric_values = _compute_metric_values(closes, cached_values)
            summary["metric_values"] = metric_values
            if last_date and not summary["uses_intraday_synthetic_bar"]:
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
                settings = resolved.get("settings") or {}
                if not isinstance(settings, dict):
                    settings = {}
                settings_for_eval = {**settings, "_context": indicator_context}
                raw_signals = evaluator(effective_prices, settings_for_eval)
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
        "advance_decline_lookbacks": config.advance_decline_lookbacks,
        "start_date": resolved_start.isoformat(),
        "end_date": resolved_end.isoformat(),
        "config_dir": str(config.config_dir),
        "duration_seconds": duration_seconds,
        "indicator_instances": indicator_instances_metadata,
        "indicator_count": len(indicator_instances_metadata),
        "intraday_requested": intraday_enabled,
        "intraday_interval": intraday_interval if intraday_enabled else None,
        "intraday_regular_hours_only": (
            intraday_regular_hours_only if intraday_enabled else None
        ),
        "intraday_min_bars_required": (
            intraday_min_bars_required if intraday_enabled else None
        ),
        "intraday_synthetic_ticker_count": len(intraday_synthetic_tickers),
        "intraday_synthetic_tickers": sorted(intraday_synthetic_tickers),
        "intraday_synthetic_scan_tickers": sorted(intraday_synthetic_scan_tickers),
        "intraday_last_bar_by_ticker": intraday_last_bar_by_ticker,
        "intraday_bar_count_by_ticker": intraday_bar_count_by_ticker,
        "intraday_metric_persistence_skipped": bool(
            intraday_synthetic_scan_tickers
        ),
        "intraday_aggregate_persistence_skipped": bool(
            intraday_synthetic_scan_tickers
        ),
        "dispersion_enabled": config.dispersion.enabled,
        "dispersion_windows": config.dispersion.windows,
        "dispersion_return_horizons": config.dispersion.return_horizons,
    }

    market_stats: dict[str, Any] = {}
    try:
        market_stats = _compute_market_stats(
            fetcher=fetcher,
            start_dt=start_dt,
            end_dt=end_dt,
            interval=config.interval,
            market_prices_by_ticker=market_prices_by_ticker,
        )
    except Exception as exc:
        issues.append({"issue": "market_stats_error", "detail": str(exc)})

    aggregate_universe_tickers = _build_aggregate_universe_tickers(config)
    aggregate_universes: dict[str, dict[str, Any]] = {}
    dispersion_return_horizon = (
        config.dispersion.return_horizons[0]
        if config.dispersion.return_horizons
        else 1
    )
    for universe_key in AGGREGATE_UNIVERSE_ORDER:
        universe_tickers = aggregate_universe_tickers.get(universe_key, [])
        universe_summaries = _select_ticker_summaries(ticker_summaries, universe_tickers)
        universe_aggregates = compute_breadth(
            universe_summaries,
            advance_decline_lookbacks=config.advance_decline_lookbacks,
        )
        if config.dispersion.enabled and universe_tickers:
            try:
                dispersion_state = build_dispersion_state(
                    price_series_by_ticker,
                    universe_tickers,
                    return_horizon=dispersion_return_horizon,
                )
                dispersion_metrics = compute_dispersion_snapshot(
                    dispersion_state,
                    as_of_date=resolved_end.isoformat(),
                    config=config.dispersion,
                )
                universe_aggregates.update(dispersion_metrics)
            except Exception as exc:
                issues.append(
                    {
                        "universe": universe_key,
                        "issue": "dispersion_compute_error",
                        "detail": str(exc),
                    }
                )
        aggregate_universes[universe_key] = {
            "label": AGGREGATE_UNIVERSE_LABELS[universe_key],
            "ticker_count": len(universe_tickers),
            "aggregates": universe_aggregates,
            "aggregates_history": [],
        }

    should_persist_aggregates = not intraday_synthetic_scan_tickers
    aggregate_group_prefixes = _aggregate_group_prefixes(
        config.advance_decline_lookbacks
    )
    aggregate_set_hashes: dict[str, str] = {}
    skipped_aggregate_persistence = False
    for universe_key in AGGREGATE_UNIVERSE_ORDER:
        universe_tickers = aggregate_universe_tickers.get(universe_key, [])
        universe_entry = aggregate_universes[universe_key]
        if not universe_tickers:
            continue
        try:
            set_hash = get_or_create_security_set(universe_tickers)
            aggregate_set_hashes[universe_key] = set_hash
            universe_entry["set_hash"] = set_hash
            aggregate_records = _build_aggregate_records(
                aggregates=universe_entry["aggregates"],
                set_hash=set_hash,
                as_of_date=resolved_end.isoformat(),
                interval=config.interval,
                aggregate_group_prefixes=aggregate_group_prefixes,
                universe_ticker_count=len(universe_tickers),
            )
            if aggregate_records and should_persist_aggregates:
                upsert_security_aggregate_values(aggregate_records)
            elif aggregate_records:
                skipped_aggregate_persistence = True
        except Exception as exc:
            issues.append(
                {
                    "universe": universe_key,
                    "issue": "aggregate_storage_error",
                    "detail": str(exc),
                }
            )
    if skipped_aggregate_persistence:
        issues.append(
            {
                "issue": "intraday_synthetic_skipped",
                "detail": "aggregate_persistence_skipped_for_intraday_synthetic_data",
            }
        )

    run_metadata["set_hash"] = aggregate_set_hashes.get("all")
    run_metadata["aggregate_set_hashes"] = aggregate_set_hashes

    hist_start = (resolved_end - timedelta(days=30)).isoformat()
    for universe_key in AGGREGATE_UNIVERSE_ORDER:
        universe_entry = aggregate_universes[universe_key]
        set_hash = universe_entry.get("set_hash")
        if not set_hash:
            continue
        try:
            hist_data = fetch_security_aggregate_series(
                set_hash=set_hash,
                metric_keys=BREADTH_HISTORY_METRICS,
                start_date=hist_start,
                end_date=resolved_end.isoformat(),
                interval=config.interval,
            )
            universe_entry["aggregates_history"] = _serialize_history(hist_data)
        except Exception as exc:
            issues.append(
                {
                    "universe": universe_key,
                    "issue": "historical_aggregates_error",
                    "detail": str(exc),
                }
            )

    all_universe = aggregate_universes.get("all", {})
    aggregates = (
        all_universe.get("aggregates")
        if isinstance(all_universe.get("aggregates"), dict)
        else {}
    )
    historical_aggregates = (
        all_universe.get("aggregates_history")
        if isinstance(all_universe.get("aggregates_history"), list)
        else []
    )

    return {
        "run_metadata": run_metadata,
        "market_stats": market_stats,
        "ticker_summaries": ticker_summaries,
        "signals": [asdict(signal) for signal in signals],
        "aggregates": aggregates,
        "aggregates_history": historical_aggregates,
        "aggregate_universes": aggregate_universes,
        "issues": issues,
    }
