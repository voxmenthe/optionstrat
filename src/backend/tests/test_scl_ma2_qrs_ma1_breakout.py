from __future__ import annotations

from typing import Any

import pytest

from app.security_scan.criteria import SeriesPoint
from app.security_scan.indicators import qrs_consist_excess as qrs_indicator
from app.security_scan.indicators import scl_ma2_qrs_ma1_breakout as breakout
from app.security_scan.indicators import scl_v4_x5 as scl_indicator


def _build_prices(dates: list[str]) -> list[dict[str, Any]]:
    return [
        {"date": date, "close": 100.0, "high": 101.0, "low": 99.0} for date in dates
    ]


def _build_benchmark_prices(dates: list[str]) -> list[dict[str, Any]]:
    return [{"date": date, "close": 200.0} for date in dates]


def _build_scl_computation(
    dates: list[str],
    ma2_values: list[float],
) -> scl_indicator.SclV4X5Computation:
    series = [
        SeriesPoint(date=dates[index], value=value)
        for index, value in enumerate(ma2_values)
    ]
    return scl_indicator.SclV4X5Computation(
        resolved_settings={
            "lag1": 2,
            "lag2": 3,
            "lag3": 4,
            "lag4": 5,
            "lag5": 11,
            "cd_offset1": 2,
            "cd_offset2": 3,
            "ma_period1": 5,
            "ma_period2": 11,
        },
        countdown_series=[],
        ma1_series=[],
        ma2_series=series,
        signals=[],
        usable_ohlc_points=len(dates),
        skipped_price_rows=0,
    )


def _build_qrs_aligned_inputs(
    dates: list[str],
) -> qrs_indicator.QrsConsistExcessAlignedInputs:
    return qrs_indicator.QrsConsistExcessAlignedInputs(
        benchmark_tickers=["SPY", "QQQ", "IWM"],
        dates=dates,
        close_values=[100.0 for _ in dates],
        benchmark_close_values=[[200.0 for _ in dates] for _ in range(3)],
        source_price_points=len(dates),
        aligned_price_points=len(dates),
        dropped_price_points=0,
    )


def _build_qrs_computation(
    dates: list[str],
    ma1_values: list[float],
) -> qrs_indicator.QrsConsistExcessComputation:
    series = [
        SeriesPoint(date=dates[index], value=value)
        for index, value in enumerate(ma1_values)
    ]
    return qrs_indicator.QrsConsistExcessComputation(
        resolved_settings={
            "lookback": 84,
            "deadband_period": 20,
            "deadband_mult": 0.25,
            "map1": 7,
            "map2": 21,
            "map3": 56,
            "cons_weight": 0.6,
            "excess_weight": 0.4,
            "ma_shift": 3,
        },
        main_series=[],
        ma1_series=series,
        ma2_series=[],
        ma3_series=[],
        signals=[],
    )


def test_dual_breakout_up_requires_both_indicators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dates = [
        "2025-01-01",
        "2025-01-02",
        "2025-01-03",
        "2025-01-04",
        "2025-01-05",
        "2025-01-06",
    ]
    prices = _build_prices(dates)
    bench_prices = _build_benchmark_prices(dates)

    monkeypatch.setattr(
        breakout.scl_module,
        "compute_scl_v4_x5_computation",
        lambda *_args, **_kwargs: _build_scl_computation(
            dates,
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        ),
    )
    monkeypatch.setattr(
        breakout.qrs_module,
        "align_qrs_consist_excess_inputs",
        lambda *_args, **_kwargs: _build_qrs_aligned_inputs(dates),
    )
    monkeypatch.setattr(
        breakout.qrs_module,
        "compute_qrs_consist_excess_computation",
        lambda *_args, **_kwargs: _build_qrs_computation(
            dates,
            [0.0, 0.0, 0.0, 0.0, 2.0, 0.0],
        ),
    )

    settings = {
        "scl_ma2_window": 3,
        "qrs_ma1_window": 3,
        "_context": {
            "benchmark_prices_by_ticker": {
                "SPY": bench_prices,
                "QQQ": bench_prices,
                "IWM": bench_prices,
            },
            "benchmark_tickers": ["SPY", "QQQ", "IWM"],
        },
    }

    signals = breakout.evaluate(prices, settings)
    assert [(signal.signal_date, signal.signal_type) for signal in signals] == [
        ("2025-01-05", "dual_breakout_up")
    ]
    assert signals[0].metadata["scl_prior_high"] == 0.0
    assert signals[0].metadata["qrs_prior_high"] == 0.0

    monkeypatch.setattr(
        breakout.qrs_module,
        "compute_qrs_consist_excess_computation",
        lambda *_args, **_kwargs: _build_qrs_computation(
            dates,
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
    )
    assert breakout.evaluate(prices, settings) == []


def test_dual_breakout_down_emits_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dates = [
        "2025-02-01",
        "2025-02-02",
        "2025-02-03",
        "2025-02-04",
        "2025-02-05",
        "2025-02-06",
    ]
    prices = _build_prices(dates)
    bench_prices = _build_benchmark_prices(dates)

    monkeypatch.setattr(
        breakout.scl_module,
        "compute_scl_v4_x5_computation",
        lambda *_args, **_kwargs: _build_scl_computation(
            dates,
            [0.0, 0.0, 0.0, 0.0, -1.0, 0.0],
        ),
    )
    monkeypatch.setattr(
        breakout.qrs_module,
        "align_qrs_consist_excess_inputs",
        lambda *_args, **_kwargs: _build_qrs_aligned_inputs(dates),
    )
    monkeypatch.setattr(
        breakout.qrs_module,
        "compute_qrs_consist_excess_computation",
        lambda *_args, **_kwargs: _build_qrs_computation(
            dates,
            [0.0, 0.0, 0.0, 0.0, -2.0, 0.0],
        ),
    )

    settings = {
        "scl_ma2_window": 3,
        "qrs_ma1_window": 3,
        "_context": {
            "benchmark_prices_by_ticker": {
                "SPY": bench_prices,
                "QQQ": bench_prices,
                "IWM": bench_prices,
            },
            "benchmark_tickers": ["SPY", "QQQ", "IWM"],
        },
    }

    signals = breakout.evaluate(prices, settings)
    assert [(signal.signal_date, signal.signal_type) for signal in signals] == [
        ("2025-02-05", "dual_breakout_down")
    ]
    assert signals[0].metadata["scl_prior_low"] == 0.0
    assert signals[0].metadata["qrs_prior_low"] == 0.0


def test_breakout_is_strict_not_inclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dates = [
        "2025-03-01",
        "2025-03-02",
        "2025-03-03",
        "2025-03-04",
        "2025-03-05",
    ]
    prices = _build_prices(dates)
    bench_prices = _build_benchmark_prices(dates)

    monkeypatch.setattr(
        breakout.scl_module,
        "compute_scl_v4_x5_computation",
        lambda *_args, **_kwargs: _build_scl_computation(
            dates,
            [0.0, 1.0, 1.0, 1.0, 1.0],
        ),
    )
    monkeypatch.setattr(
        breakout.qrs_module,
        "align_qrs_consist_excess_inputs",
        lambda *_args, **_kwargs: _build_qrs_aligned_inputs(dates),
    )
    monkeypatch.setattr(
        breakout.qrs_module,
        "compute_qrs_consist_excess_computation",
        lambda *_args, **_kwargs: _build_qrs_computation(
            dates,
            [0.0, 2.0, 2.0, 2.0, 3.0],
        ),
    )

    settings = {
        "scl_ma2_window": 3,
        "qrs_ma1_window": 3,
        "_context": {
            "benchmark_prices_by_ticker": {
                "SPY": bench_prices,
                "QQQ": bench_prices,
                "IWM": bench_prices,
            },
            "benchmark_tickers": ["SPY", "QQQ", "IWM"],
        },
    }

    assert breakout.evaluate(prices, settings) == []


def test_compute_breakout_intersects_scl_and_qrs_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prices = _build_prices(
        [
            "2025-04-01",
            "2025-04-02",
            "2025-04-03",
            "2025-04-04",
            "2025-04-05",
        ]
    )

    monkeypatch.setattr(
        breakout.scl_module,
        "compute_scl_v4_x5_computation",
        lambda *_args, **_kwargs: _build_scl_computation(
            ["2025-04-01", "2025-04-03", "2025-04-04", "2025-04-05"],
            [0.0, 0.0, 0.0, 1.0],
        ),
    )
    monkeypatch.setattr(
        breakout.qrs_module,
        "align_qrs_consist_excess_inputs",
        lambda *_args, **_kwargs: _build_qrs_aligned_inputs(
            ["2025-04-01", "2025-04-02", "2025-04-04", "2025-04-05"]
        ),
    )
    monkeypatch.setattr(
        breakout.qrs_module,
        "compute_qrs_consist_excess_computation",
        lambda *_args, **_kwargs: _build_qrs_computation(
            ["2025-04-01", "2025-04-02", "2025-04-04", "2025-04-05"],
            [0.0, 0.0, 0.0, 2.0],
        ),
    )

    computation = breakout.compute_scl_ma2_qrs_ma1_breakout_computation(
        prices,
        {"scl_ma2_window": 2, "qrs_ma1_window": 2},
        benchmark_prices_by_ticker={
            "SPY": _build_benchmark_prices(["2025-04-01", "2025-04-04", "2025-04-05"]),
            "QQQ": _build_benchmark_prices(["2025-04-01", "2025-04-04", "2025-04-05"]),
            "IWM": _build_benchmark_prices(["2025-04-01", "2025-04-04", "2025-04-05"]),
        },
        benchmark_tickers=["SPY", "QQQ", "IWM"],
    )

    assert [point.date for point in computation.scl_ma2_series] == [
        "2025-04-01",
        "2025-04-04",
        "2025-04-05",
    ]
    assert [point.date for point in computation.qrs_ma1_series] == [
        "2025-04-01",
        "2025-04-04",
        "2025-04-05",
    ]
    assert [(signal.signal_date, signal.signal_type) for signal in computation.signals] == [
        ("2025-04-05", "dual_breakout_up")
    ]


def test_compute_breakout_forwards_qrs_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prices = _build_prices(
        ["2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04"]
    )

    monkeypatch.setattr(
        breakout.scl_module,
        "compute_scl_v4_x5_computation",
        lambda *_args, **_kwargs: _build_scl_computation(
            ["2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04"],
            [0.0, 0.0, 0.0, 0.0],
        ),
    )
    monkeypatch.setattr(
        breakout.qrs_module,
        "align_qrs_consist_excess_inputs",
        lambda *_args, **_kwargs: _build_qrs_aligned_inputs(
            ["2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04"]
        ),
    )

    def fake_compute_qrs_consist_excess_computation(*_args, **kwargs):
        assert kwargs["settings"]["map2"] == 27
        return _build_qrs_computation(
            ["2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04"],
            [0.0, 0.0, 0.0, 0.0],
        )

    monkeypatch.setattr(
        breakout.qrs_module,
        "compute_qrs_consist_excess_computation",
        fake_compute_qrs_consist_excess_computation,
    )

    breakout.compute_scl_ma2_qrs_ma1_breakout_computation(
        prices,
        {"map2": 27},
        benchmark_prices_by_ticker={
            "SPY": _build_benchmark_prices(
                ["2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04"]
            ),
            "QQQ": _build_benchmark_prices(
                ["2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04"]
            ),
            "IWM": _build_benchmark_prices(
                ["2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04"]
            ),
        },
        benchmark_tickers=["SPY", "QQQ", "IWM"],
    )


def test_evaluate_requires_benchmark_context() -> None:
    prices = _build_prices(["2025-06-01", "2025-06-02", "2025-06-03"])

    with pytest.raises(ValueError, match="missing _context for qrs benchmarks"):
        breakout.evaluate(prices, {"scl_ma2_window": 3, "qrs_ma1_window": 3})
