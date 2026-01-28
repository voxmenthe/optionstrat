from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterable

from app.services.market_data import MarketDataService

logger = logging.getLogger(__name__)


def _normalize_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str):
        return value
    return None


def normalize_prices(raw_prices: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in raw_prices:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "date": _normalize_date(row.get("date")),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
            }
        )
    return normalized


class MarketDataFetcher:
    def __init__(self, market_data_service: MarketDataService | None = None) -> None:
        self.market_data_service = market_data_service or MarketDataService()

    def fetch_historical_prices(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str,
    ) -> list[dict[str, Any]]:
        logger.info(
            "security_scan.fetch_historical_prices",
            extra={
                "ticker": ticker,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "interval": interval,
            },
        )
        try:
            raw_prices = self.market_data_service.get_historical_prices(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
            )
        except Exception as exc:
            logger.error(
                "security_scan.fetch_historical_prices_failed",
                extra={"ticker": ticker, "error": str(exc)},
            )
            return []

        return normalize_prices(raw_prices)
