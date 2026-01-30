from __future__ import annotations

from typing import Sequence


def compute_sma(closes: Sequence[float], window: int, shift: int = 0) -> float | None:
    if window <= 0:
        raise ValueError("window must be > 0")
    if shift < 0:
        raise ValueError("shift must be >= 0")
    end_index = len(closes) - 1 - shift
    start_index = end_index - window + 1
    if start_index < 0 or end_index < 0:
        return None
    window_values = closes[start_index : end_index + 1]
    return sum(window_values) / window


def compute_roc(closes: Sequence[float], lookback: int, shift: int = 0) -> float | None:
    if lookback <= 0:
        raise ValueError("lookback must be > 0")
    if shift < 0:
        raise ValueError("shift must be >= 0")
    index = len(closes) - 1 - shift
    prior_index = index - lookback
    if prior_index < 0 or index < 0:
        return None
    prior_value = closes[prior_index]
    if prior_value == 0:
        return None
    return (closes[index] - prior_value) / prior_value
