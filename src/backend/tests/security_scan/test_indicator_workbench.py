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


def _scl_v4_x5_request(
    settings: dict[str, Any] | None = None,
) -> IndicatorDashboardComputeRequest:
    return IndicatorDashboardComputeRequest(
        ticker="nvda",
        indicator_id="scl_v4_x5",
        settings=settings or {},
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 12),
        interval="day",
        benchmark_tickers=["spy", "qqq", "iwm"],
    )


def test_list_indicator_metadata_returns_dashboard_indicator_schemas() -> None:
    metadata = list_indicator_metadata()

    assert [indicator.id for indicator in metadata.indicators] == [
        "roc",
        "roc_aggregate",
        "scl_v4_x5",
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

    scl_metadata = metadata.indicators[2]
    assert scl_metadata.default_settings == {
        "lag1": 2,
        "lag2": 3,
        "lag3": 4,
        "lag4": 5,
        "lag5": 11,
        "cd_offset1": 2,
        "cd_offset2": 3,
        "ma_period1": 5,
        "ma_period2": 11,
    }
    assert [
        (parameter.key, parameter.type, parameter.min)
        for parameter in scl_metadata.parameters
    ] == [
        ("lag1", "integer", 1),
        ("lag2", "integer", 1),
        ("lag3", "integer", 1),
        ("lag4", "integer", 1),
        ("lag5", "integer", 1),
        ("cd_offset1", "integer", 1),
        ("cd_offset2", "integer", 1),
        ("ma_period1", "integer", 1),
        ("ma_period2", "integer", 1),
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


def test_compute_scl_v4_x5_dashboard_returns_multi_trace_payload() -> None:
    service = FakeMarketDataService(
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

    response = compute_indicator_dashboard(
        _scl_v4_x5_request(),
        service,  # type: ignore[arg-type]
    )

    assert response.ticker == "NVDA"
    assert response.indicator_id == "scl_v4_x5"
    assert response.resolved_settings == {
        "lag1": 2,
        "lag2": 3,
        "lag3": 4,
        "lag4": 5,
        "lag5": 11,
        "cd_offset1": 2,
        "cd_offset2": 3,
        "ma_period1": 5,
        "ma_period2": 11,
    }
    assert [trace.key for trace in response.indicator.panels[0].traces] == [
        "countdown",
        "ma1",
        "ma2",
    ]
    assert response.indicator.panels[0].reference_lines == [0.0]
    assert [len(trace.points) for trace in response.indicator.panels[0].traces] == [
        12,
        12,
        12,
    ]
    assert [signal.type for signal in response.signals] == [
        "seven_bar_high",
        "seven_bar_high",
        "seven_bar_high",
        "seven_bar_high",
        "seven_bar_high",
    ]
    assert [signal.date for signal in response.signals] == [
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-11",
        "2025-01-12",
    ]
    assert all(signal.target_trace == "countdown" for signal in response.signals)
    assert response.diagnostics.price_points == 12
    assert response.diagnostics.indicator_points == 12
    assert response.diagnostics.warnings == []


def test_compute_scl_v4_x5_dashboard_warns_when_price_rows_missing_ohlc() -> None:
    service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 10.0, "high": 11.0, "low": 9.0},
            {"date": "2025-01-02", "close": 11.0},
            {"date": "2025-01-03", "close": 12.0, "high": 13.0, "low": 11.0},
        ]
    )

    response = compute_indicator_dashboard(
        _scl_v4_x5_request(),
        service,  # type: ignore[arg-type]
    )

    assert [len(trace.points) for trace in response.indicator.panels[0].traces] == [
        2,
        2,
        2,
    ]
    assert response.signals == []
    assert response.diagnostics.price_points == 3
    assert response.diagnostics.indicator_points == 2
    assert response.diagnostics.warnings == [
        "Skipped 1 price rows missing high/low fields for SCL V4 X5."
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


def test_compute_scl_v4_x5_dashboard_rejects_invalid_lag() -> None:
    service = FakeMarketDataService(
        [
            {"date": "2025-01-01", "close": 10.0, "high": 11.0, "low": 9.0},
            {"date": "2025-01-02", "close": 11.0, "high": 12.0, "low": 10.0},
        ]
    )

    with pytest.raises(IndicatorSettingsValidationError, match="lag1 must be >= 1"):
        compute_indicator_dashboard(
            _scl_v4_x5_request({"lag1": 0}),
            service,  # type: ignore[arg-type]
        )
