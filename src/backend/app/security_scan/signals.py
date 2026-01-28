from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IndicatorSignal:
    signal_date: str
    signal_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Signal:
    ticker: str
    indicator_id: str
    indicator_type: str
    signal_date: str
    signal_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
