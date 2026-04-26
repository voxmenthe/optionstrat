from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from app.security_scan.indicator_workbench import (
    IndicatorDashboardComputeRequest,
    IndicatorNoDataError,
    IndicatorSettingsValidationError,
    compute_indicator_dashboard,
    list_indicator_metadata,
)


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


def _roc_request(
    settings: dict[str, Any] | None = None,
) -> IndicatorDashboardComputeRequest:
    return IndicatorDashboardComputeRequest(
        ticker="aapl",
        indicator_id="ROC",
        settings=settings or {"roc_lookback": 1},
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 5),
        interval="day",
        benchmark_tickers=["spy", "qqq", "iwm"],
    )


def _roc_aggregate_request(
    settings: dict[str, Any] | None = None,
) -> IndicatorDashboardComputeRequest:
    return IndicatorDashboardComputeRequest(
        ticker="msft",
        indicator_id="roc_aggregate",
        settings=settings
        or {
            "roc_lookbacks": [1],
            "roc_change_lookbacks": [1],
            "ma_short": 2,
            "ma_long": 2,
        },
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 6),
        interval="day",
        benchmark_tickers=["spy", "qqq", "iwm"],
    )


def test_list_indicator_metadata_returns_dashboard_indicator_schemas() -> None:
    metadata = list_indicator_metadata()

    assert [indicator.id for indicator in metadata.indicators] == [
        "roc",
        "roc_aggregate",
    ]
    roc_metadata = metadata.indicators[0]
    assert roc_metadata.default_settings == {"roc_lookback": 12}
    assert roc_metadata.requires_benchmarks is False
    assert roc_metadata.supported_intervals == ["day"]
    assert [
        (parameter.key, parameter.type, parameter.min)
        for parameter in roc_metadata.parameters
    ] == [
        ("roc_lookback", "integer", 1),
    ]

    roc_aggregate_metadata = metadata.indicators[1]
    assert roc_aggregate_metadata.default_settings == {
        "roc_lookbacks": [5, 10, 20],
        "roc_change_lookbacks": [1, 3, 5],
        "ma_short": 5,
        "ma_long": 20,
    }
    assert [
        (
            parameter.key,
            parameter.type,
            parameter.min,
            parameter.item_type,
        )
        for parameter in roc_aggregate_metadata.parameters
    ] == [
        ("roc_lookbacks", "integer_list", 1, "integer"),
        ("roc_change_lookbacks", "integer_list", 1, "integer"),
        ("ma_short", "integer", 1, None),
        ("ma_long", "integer", 1, None),
    ]


def test_compute_roc_dashboard_uses_normalized_fetcher_path() -> None:
    service = FakeMarketDataService(
        [
            {"date": "2025-01-03", "close": 99.0},
            {"date": "2025-01-01", "close": 100.0},
            {"date": "2025-01-02", "close": 110.0},
            {"date": "2025-01-04", "close": 120.0},
            {"date": "2025-01-05", "close": 108.0},
        ]
    )

    response = compute_indicator_dashboard(_roc_request(), service)  # type: ignore[arg-type]

    assert service.calls == [
        {
            "ticker": "AAPL",
            "start_date": datetime(2025, 1, 1),
            "end_date": datetime(2025, 1, 6),
            "interval": "day",
        }
    ]
    assert response.ticker == "AAPL"
    assert response.indicator_id == "roc"
    assert response.resolved_settings == {"roc_lookback": 1}
    assert response.price.points[0].date == "2025-01-01"
    assert [point.date for point in response.indicator.panels[0].traces[0].points] == [
        "2025-01-02",
        "2025-01-03",
        "2025-01-04",
        "2025-01-05",
    ]
    assert response.indicator.panels[0].reference_lines == [0.0]
    assert [signal.type for signal in response.signals] == [
        "zero_cross_down",
        "zero_cross_up",
        "zero_cross_down",
    ]
    assert response.signals[0].target_trace == "roc"
    assert response.diagnostics.price_points == 5
    assert response.diagnostics.indicator_points == 4
    assert response.diagnostics.benchmark_tickers_used == []
    assert response.diagnostics.warnings == []


def test_compute_roc_dashboard_rejects_unknown_settings() -> None:
    service = FakeMarketDataService(
        [{"date": "2025-01-01", "close": 100.0}, {"date": "2025-01-02", "close": 101.0}]
    )

    with pytest.raises(IndicatorSettingsValidationError, match="Unsupported settings"):
        compute_indicator_dashboard(
            _roc_request({"roc_lookback": 1, "surprise": True}),
            service,  # type: ignore[arg-type]
        )


def test_compute_roc_aggregate_dashboard_returns_multi_trace_payload() -> None:
    service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 100.0},
            {"date": "2025-01-02", "close": 110.0},
            {"date": "2025-01-03", "close": 125.0},
            {"date": "2025-01-04", "close": 130.0},
            {"date": "2025-01-05", "close": 140.0},
            {"date": "2025-01-06", "close": 141.0},
        ]
    )

    response = compute_indicator_dashboard(
        _roc_aggregate_request(),
        service,  # type: ignore[arg-type]
    )

    assert response.ticker == "MSFT"
    assert response.indicator_id == "roc_aggregate"
    assert response.resolved_settings == {
        "roc_lookbacks": [1],
        "roc_change_lookbacks": [1],
        "ma_short": 2,
        "ma_long": 2,
    }
    assert [trace.key for trace in response.indicator.panels[0].traces] == [
        "score",
        "ma_short",
        "ma_long",
    ]
    assert [
        point.date for point in response.indicator.panels[0].traces[0].points
    ] == [
        "2025-01-03",
        "2025-01-04",
        "2025-01-05",
        "2025-01-06",
    ]
    assert [
        point.date for point in response.indicator.panels[0].traces[1].points
    ] == [
        "2025-01-04",
        "2025-01-05",
        "2025-01-06",
    ]
    assert [
        point.date for point in response.indicator.panels[0].traces[2].points
    ] == [
        "2025-01-04",
        "2025-01-05",
        "2025-01-06",
    ]
    assert [signal.type for signal in response.signals] == [
        "cross_above_both",
        "cross_below_both",
    ]
    assert [signal.date for signal in response.signals] == [
        "2025-01-05",
        "2025-01-06",
    ]
    assert all(signal.target_trace == "score" for signal in response.signals)
    assert response.diagnostics.price_points == 6
    assert response.diagnostics.indicator_points == 4
    assert response.diagnostics.benchmark_tickers_used == []
    assert response.diagnostics.warnings == []


def test_compute_roc_aggregate_dashboard_returns_warning_for_insufficient_history() -> None:
    service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 100.0},
            {"date": "2025-01-02", "close": 110.0},
            {"date": "2025-01-03", "close": 105.0},
        ]
    )

    response = compute_indicator_dashboard(
        _roc_aggregate_request(
            {
                "roc_lookbacks": [2],
                "roc_change_lookbacks": [2],
                "ma_short": 3,
                "ma_long": 3,
            }
        ),
        service,  # type: ignore[arg-type]
    )

    assert [len(trace.points) for trace in response.indicator.panels[0].traces] == [
        0,
        0,
        0,
    ]
    assert response.signals == []
    assert response.diagnostics.price_points == 3
    assert response.diagnostics.indicator_points == 0
    assert response.diagnostics.warnings == [
        "Need at least 5 valid close prices to compute ROC Aggregate score."
    ]


def test_compute_roc_dashboard_rejects_invalid_lookback() -> None:
    service = FakeMarketDataService(
        [{"date": "2025-01-01", "close": 100.0}, {"date": "2025-01-02", "close": 101.0}]
    )

    with pytest.raises(
        IndicatorSettingsValidationError, match="roc_lookback must be >= 1"
    ):
        compute_indicator_dashboard(
            _roc_request({"roc_lookback": 0}),
            service,  # type: ignore[arg-type]
        )


def test_compute_roc_aggregate_dashboard_rejects_non_list_lookbacks() -> None:
    service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 100.0},
            {"date": "2025-01-02", "close": 101.0},
            {"date": "2025-01-03", "close": 102.0},
        ]
    )

    with pytest.raises(
        IndicatorSettingsValidationError,
        match="roc_lookbacks must be a list of integers",
    ):
        compute_indicator_dashboard(
            _roc_aggregate_request(
                {
                    "roc_lookbacks": 1,
                    "roc_change_lookbacks": [1],
                    "ma_short": 2,
                    "ma_long": 2,
                }
            ),
            service,  # type: ignore[arg-type]
        )


def test_compute_roc_dashboard_returns_no_data_error_for_empty_prices() -> None:
    service = FakeMarketDataService([])

    with pytest.raises(IndicatorNoDataError, match="No usable historical close prices"):
        compute_indicator_dashboard(_roc_request(), service)  # type: ignore[arg-type]
