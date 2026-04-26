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
    assert [indicator["id"] for indicator in payload["indicators"]] == [
        "roc",
        "roc_aggregate",
        "scl_v4_x5",
    ]
    assert payload["indicators"][0]["parameters"][0]["key"] == "roc_lookback"
    assert payload["indicators"][1]["parameters"][0]["key"] == "roc_lookbacks"
    assert payload["indicators"][2]["parameters"][0]["key"] == "lag1"


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


def test_security_scan_roc_aggregate_dashboard_compute_endpoint(client) -> None:
    fake_service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 100.0},
            {"date": "2025-01-02", "close": 110.0},
            {"date": "2025-01-03", "close": 125.0},
            {"date": "2025-01-04", "close": 130.0},
            {"date": "2025-01-05", "close": 140.0},
            {"date": "2025-01-06", "close": 141.0},
        ]
    )

    def override_market_data_service() -> FakeMarketDataService:
        return fake_service

    app.dependency_overrides[get_market_data_service] = override_market_data_service

    response = client.post(
        "/security-scan/indicator-dashboard/compute",
        json={
            "ticker": "msft",
            "indicator_id": "roc_aggregate",
            "settings": {
                "roc_lookbacks": [1],
                "roc_change_lookbacks": [1],
                "ma_short": 2,
                "ma_long": 2,
            },
            "start_date": "2025-01-01",
            "end_date": "2025-01-06",
            "interval": "day",
            "benchmark_tickers": ["spy", "qqq", "iwm"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert [trace["key"] for trace in payload["indicator"]["panels"][0]["traces"]] == [
        "score",
        "ma_short",
        "ma_long",
    ]
    assert [signal["date"] for signal in payload["signals"]] == [
        "2025-01-05",
        "2025-01-06",
    ]
    assert payload["diagnostics"]["indicator_points"] == 4
    assert fake_service.calls[0]["ticker"] == "MSFT"


def test_security_scan_scl_v4_x5_dashboard_compute_endpoint(client) -> None:
    fake_service = FakeMarketDataService(
        [
            {
                "date": f"2025-01-{index:02d}",
                "close": float(close),
                "high": float(close + 1),
                "low": float(close - 1),
            }
            for index, close in enumerate(range(10, 22), start=1)
        ]
    )

    def override_market_data_service() -> FakeMarketDataService:
        return fake_service

    app.dependency_overrides[get_market_data_service] = override_market_data_service

    response = client.post(
        "/security-scan/indicator-dashboard/compute",
        json={
            "ticker": "nvda",
            "indicator_id": "scl_v4_x5",
            "settings": {},
            "start_date": "2025-01-01",
            "end_date": "2025-01-12",
            "interval": "day",
            "benchmark_tickers": ["spy", "qqq", "iwm"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "NVDA"
    assert [trace["key"] for trace in payload["indicator"]["panels"][0]["traces"]] == [
        "countdown",
        "ma1",
        "ma2",
    ]
    assert [signal["date"] for signal in payload["signals"]] == [
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-11",
        "2025-01-12",
    ]
    assert payload["diagnostics"]["indicator_points"] == 12
    assert fake_service.calls[0]["ticker"] == "NVDA"


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


def test_security_scan_roc_aggregate_dashboard_rejects_bad_list_settings(client) -> None:
    fake_service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 100.0},
            {"date": "2025-01-02", "close": 101.0},
            {"date": "2025-01-03", "close": 102.0},
        ]
    )

    def override_market_data_service() -> FakeMarketDataService:
        return fake_service

    app.dependency_overrides[get_market_data_service] = override_market_data_service

    response = client.post(
        "/security-scan/indicator-dashboard/compute",
        json={
            "ticker": "MSFT",
            "indicator_id": "roc_aggregate",
            "settings": {
                "roc_lookbacks": 1,
                "roc_change_lookbacks": [1],
                "ma_short": 2,
                "ma_long": 2,
            },
            "start_date": "2025-01-01",
            "end_date": "2025-01-03",
            "interval": "day",
        },
    )

    assert response.status_code == 422
    assert "roc_lookbacks must be a list of integers" in response.json()["detail"]


def test_security_scan_scl_v4_x5_dashboard_rejects_bad_settings(client) -> None:
    fake_service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 10.0, "high": 11.0, "low": 9.0},
            {"date": "2025-01-02", "close": 11.0, "high": 12.0, "low": 10.0},
        ]
    )

    def override_market_data_service() -> FakeMarketDataService:
        return fake_service

    app.dependency_overrides[get_market_data_service] = override_market_data_service

    response = client.post(
        "/security-scan/indicator-dashboard/compute",
        json={
            "ticker": "NVDA",
            "indicator_id": "scl_v4_x5",
            "settings": {"lag1": 0},
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
            "interval": "day",
        },
    )

    assert response.status_code == 422
    assert "lag1 must be >= 1" in response.json()["detail"]
