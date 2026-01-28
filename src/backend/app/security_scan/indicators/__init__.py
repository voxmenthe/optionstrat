"""Indicator registry utilities."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Callable

from app.security_scan.signals import IndicatorSignal

IndicatorEvaluator = Callable[[list[dict[str, Any]], dict[str, Any]], list[IndicatorSignal]]


def load_indicator_registry() -> dict[str, IndicatorEvaluator]:
    registry: dict[str, IndicatorEvaluator] = {}
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        indicator_id = getattr(module, "INDICATOR_ID", None)
        evaluate = getattr(module, "evaluate", None)
        if isinstance(indicator_id, str) and indicator_id.strip() and callable(evaluate):
            registry[indicator_id] = evaluate
    return registry
