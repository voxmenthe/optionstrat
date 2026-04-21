from __future__ import annotations

from datetime import datetime
from typing import Any

from app.dependencies import get_market_data_service
from app.main import app


class FakeMarketDataService:
    def __init__(self, prices: list[dict[str, Any]]) -> None:
        self.prices = prices
        self.calls: list[dict[str, Any]] = []

    def get_historical_prices(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "day",
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "interval": interval,
            }
        )
        return self.prices


def test_security_scan_indicator_metadata_endpoint(client) -> None:
    response = client.get("/security-scan/indicators")

    assert response.status_code == 200
    payload = response.json()
    assert [indicator["id"] for indicator in payload["indicators"]] == ["roc"]
    assert payload["indicators"][0]["parameters"][0]["key"] == "roc_lookback"


def test_security_scan_indicator_dashboard_compute_endpoint(client) -> None:
    fake_service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 100.0},
            {"date": "2025-01-02", "close": 110.0},
            {"date": "2025-01-03", "close": 99.0},
        ]
    )

    def override_market_data_service() -> FakeMarketDataService:
        return fake_service

    app.dependency_overrides[get_market_data_service] = override_market_data_service

    response = client.post(
        "/security-scan/indicator-dashboard/compute",
        json={
            "ticker": "aapl",
            "indicator_id": "roc",
            "settings": {"roc_lookback": 1},
            "start_date": "2025-01-01",
            "end_date": "2025-01-03",
            "interval": "day",
            "benchmark_tickers": ["spy", "qqq", "iwm"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["price"]["label"] == "AAPL Close"
    assert payload["indicator"]["panels"][0]["traces"][0]["key"] == "roc"
    assert payload["diagnostics"]["price_points"] == 3
    assert payload["signals"][0]["type"] == "zero_cross_down"
    assert fake_service.calls[0]["ticker"] == "AAPL"


def test_security_scan_indicator_dashboard_rejects_bad_settings(client) -> None:
    fake_service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 100.0},
            {"date": "2025-01-02", "close": 110.0},
        ]
    )

    def override_market_data_service() -> FakeMarketDataService:
        return fake_service

    app.dependency_overrides[get_market_data_service] = override_market_data_service

    response = client.post(
        "/security-scan/indicator-dashboard/compute",
        json={
            "ticker": "AAPL",
            "indicator_id": "roc",
            "settings": {"roc_lookback": 0},
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
            "interval": "day",
        },
    )

    assert response.status_code == 422
    assert "roc_lookback must be >= 1" in response.json()["detail"]
