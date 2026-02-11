from __future__ import annotations

from app.security_scan.indicators.qrs_consist_excess import (
    _build_main_zero_cross_signals,
    _build_ma1_ma2_cross_signals,
    _build_main_vs_all_mas_regime_signals,
    qrs_consist_excess,
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


def test_qrs_ma1_cross_above_ma2_emits_signal() -> None:
    dates = ["2025-01-01", "2025-01-02", "2025-01-03"]
    ma1 = [0.0, 0.9, 1.1]
    ma2 = [1.0, 1.0, 1.0]

    signals = _build_ma1_ma2_cross_signals(dates, ma1, ma2)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "ma1_cross_above_ma2"
    assert signal.signal_date == "2025-01-03"
    assert signal.metadata["label"] == "qrs_ma1_cross_above_ma2"


def test_qrs_ma1_cross_below_ma2_emits_signal() -> None:
    dates = ["2025-02-01", "2025-02-02", "2025-02-03"]
    ma1 = [2.0, 1.1, 0.9]
    ma2 = [1.0, 1.0, 1.0]

    signals = _build_ma1_ma2_cross_signals(dates, ma1, ma2)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "ma1_cross_below_ma2"
    assert signal.signal_date == "2025-02-03"
    assert signal.metadata["label"] == "qrs_ma1_cross_below_ma2"


def test_qrs_main_above_all_mas_pos_regime_requires_regime_and_transition() -> None:
    dates = ["2025-04-01", "2025-04-02"]
    main = [0.5, 2.0]
    ma1 = [1.0, 1.0]
    ma2 = [1.0, 1.0]
    ma3 = [1.0, 1.0]

    signals = _build_main_vs_all_mas_regime_signals(dates, main, ma1, ma2, ma3)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "main_above_all_mas_pos_regime"
    assert signal.signal_date == "2025-04-02"
    assert signal.metadata["label"] == "qrs_main_above_all_mas_pos_regime"


def test_qrs_main_below_all_mas_neg_regime_requires_regime_and_transition() -> None:
    dates = ["2025-05-01", "2025-05-02"]
    main = [-0.5, -2.0]
    ma1 = [-1.0, -1.0]
    ma2 = [-1.0, -1.0]
    ma3 = [-1.0, -1.0]

    signals = _build_main_vs_all_mas_regime_signals(dates, main, ma1, ma2, ma3)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "main_below_all_mas_neg_regime"
    assert signal.signal_date == "2025-05-02"
    assert signal.metadata["label"] == "qrs_main_below_all_mas_neg_regime"


def test_qrs_consist_excess_v2_confidence_weighting_avoids_hard_zero_plateau() -> None:
    # Benchmark is consistently up; stock consistently outperforms.
    # v2 logic should output a non-zero series even when one-sided market direction
    # would have failed the old hard "up+down day minimums" gate.
    n = 140
    stock_close = [100.0 * (1.02**i) for i in range(n)]
    bench_close = [100.0 * (1.01**i) for i in range(n)]

    outputs = qrs_consist_excess(
        stock_close,
        bench_close,
        bench_close,
        bench_close,
        lookback=84,
        deadband_period=20,
        deadband_mult=0.25,
        map1=7,
        map2=21,
        map3=56,
        cons_weight=0.6,
        excess_weight=0.4,
        ma_shift=3,
    )

    qrs = outputs.get("QRSConsistExcess") or []
    qrs_v2 = outputs.get("QRSConsistExcessV2") or []

    assert len(qrs) == n
    assert qrs == qrs_v2
    assert any(abs(value) > 0 for value in qrs)
    assert qrs[-1] > 0
