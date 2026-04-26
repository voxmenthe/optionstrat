from __future__ import annotations

from app.security_scan.indicators.scl_v4_x5 import compute_scl_v4_x5_computation


def test_compute_scl_v4_x5_computation_returns_traces_and_signals() -> None:
    prices = [
        {
            "date": f"2025-01-{index:02d}",
            "close": float(close),
            "high": float(close + 1),
            "low": float(close - 1),
        }
        for index, close in enumerate(range(10, 22), start=1)
    ]

    computation = compute_scl_v4_x5_computation(prices)

    assert computation.resolved_settings == {
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
    assert len(computation.countdown_series) == 12
    assert len(computation.ma1_series) == 12
    assert len(computation.ma2_series) == 12
    assert [signal.signal_date for signal in computation.signals] == [
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-11",
        "2025-01-12",
    ]
    assert {signal.signal_type for signal in computation.signals} == {"seven_bar_high"}
    assert computation.usable_ohlc_points == 12
    assert computation.skipped_price_rows == 0


def test_compute_scl_v4_x5_computation_counts_skipped_missing_ohlc_rows() -> None:
    prices = [
        {"date": "2025-01-01", "close": 10.0, "high": 11.0, "low": 9.0},
        {"date": "2025-01-02", "close": 11.0},
        {"date": "2025-01-03", "close": 12.0, "high": 13.0, "low": 11.0},
    ]

    computation = compute_scl_v4_x5_computation(prices)

    assert [point.date for point in computation.countdown_series] == [
        "2025-01-01",
        "2025-01-03",
    ]
    assert computation.signals == []
    assert computation.usable_ohlc_points == 2
    assert computation.skipped_price_rows == 1
