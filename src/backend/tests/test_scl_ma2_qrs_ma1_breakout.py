from __future__ import annotations

from typing import Any

from app.security_scan.indicators import scl_ma2_qrs_ma1_breakout as breakout


def _build_prices(dates: list[str]) -> list[dict[str, Any]]:
    return [
        {"date": date, "close": 100.0, "high": 101.0, "low": 99.0} for date in dates
    ]


def _build_benchmark_prices(dates: list[str]) -> list[dict[str, Any]]:
    return [{"date": date, "close": 200.0} for date in dates]


def test_dual_breakout_up_requires_both_indicators(monkeypatch) -> None:
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

    def fake_scl_v4_x5(*_args, **_kwargs):
        return {"MA2": [0.0, 0.0, 0.0, 0.0, 1.0, 0.0]}

    def fake_qrs_consist_excess(*_args, **_kwargs):
        return {"MA1": [0.0, 0.0, 0.0, 0.0, 2.0, 0.0]}

    monkeypatch.setattr(breakout.scl_module, "scl_v4_x5", fake_scl_v4_x5)
    monkeypatch.setattr(breakout.qrs_module, "qrs_consist_excess", fake_qrs_consist_excess)

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

    # If only one indicator breaks out, the composite scan must not emit a signal.
    def fake_qrs_no_breakout(*_args, **_kwargs):
        return {"MA1": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}

    monkeypatch.setattr(breakout.qrs_module, "qrs_consist_excess", fake_qrs_no_breakout)
    assert breakout.evaluate(prices, settings) == []


def test_dual_breakout_down_emits_signal(monkeypatch) -> None:
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

    def fake_scl_v4_x5(*_args, **_kwargs):
        return {"MA2": [0.0, 0.0, 0.0, 0.0, -1.0, 0.0]}

    def fake_qrs_consist_excess(*_args, **_kwargs):
        return {"MA1": [0.0, 0.0, 0.0, 0.0, -2.0, 0.0]}

    monkeypatch.setattr(breakout.scl_module, "scl_v4_x5", fake_scl_v4_x5)
    monkeypatch.setattr(breakout.qrs_module, "qrs_consist_excess", fake_qrs_consist_excess)

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


def test_breakout_is_strict_not_inclusive(monkeypatch) -> None:
    dates = [
        "2025-03-01",
        "2025-03-02",
        "2025-03-03",
        "2025-03-04",
        "2025-03-05",
    ]
    prices = _build_prices(dates)
    bench_prices = _build_benchmark_prices(dates)

    # On 2025-03-05, MA2 equals the prior high (1.0) so this should not count as a breakout.
    def fake_scl_v4_x5(*_args, **_kwargs):
        return {"MA2": [0.0, 1.0, 1.0, 1.0, 1.0]}

    def fake_qrs_consist_excess(*_args, **_kwargs):
        return {"MA1": [0.0, 2.0, 2.0, 2.0, 3.0]}

    monkeypatch.setattr(breakout.scl_module, "scl_v4_x5", fake_scl_v4_x5)
    monkeypatch.setattr(breakout.qrs_module, "qrs_consist_excess", fake_qrs_consist_excess)

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

