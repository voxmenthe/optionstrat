from __future__ import annotations

from app.security_scan.indicators.qrs_consist_excess import (
    _build_main_zero_cross_signals,
)


def test_qrs_main_cross_above_zero_requires_three_days() -> None:
    dates = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"]
    series = [-1.0, -0.5, 0.0, 0.2]

    signals = _build_main_zero_cross_signals(dates, series)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "main_cross_above_zero_3d"
    assert signal.signal_date == "2025-01-04"
    assert signal.metadata["label"] == "qrs_main_cross_up_3d"
    assert signal.metadata["prev_1"] == 0.0
    assert signal.metadata["prev_2"] == -0.5
    assert signal.metadata["prev_3"] == -1.0


def test_qrs_main_cross_below_zero_requires_three_days() -> None:
    dates = ["2025-02-01", "2025-02-02", "2025-02-03", "2025-02-04"]
    series = [0.1, 0.0, 0.2, -0.3]

    signals = _build_main_zero_cross_signals(dates, series)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "main_cross_below_zero_3d"
    assert signal.signal_date == "2025-02-04"
    assert signal.metadata["label"] == "qrs_main_cross_down_3d"
    assert signal.metadata["prev_1"] == 0.2
    assert signal.metadata["prev_2"] == 0.0
    assert signal.metadata["prev_3"] == 0.1


def test_qrs_main_cross_requires_full_streak() -> None:
    dates = ["2025-03-01", "2025-03-02", "2025-03-03"]
    series = [-1.0, -0.5, 0.3]

    signals = _build_main_zero_cross_signals(dates, series)

    assert signals == []
