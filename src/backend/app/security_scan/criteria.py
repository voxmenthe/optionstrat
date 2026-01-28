from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from app.security_scan.signals import IndicatorSignal


@dataclass(frozen=True)
class SeriesPoint:
    date: str
    value: float


def _to_float(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected {label} to be a number.") from exc


def _to_int(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected {label} to be an integer.") from exc


def _normalize_direction(value: Any) -> str:
    if value is None:
        return "both"
    if isinstance(value, str):
        direction = value.strip().lower()
        if direction in {"up", "down", "both"}:
            return direction
    raise ValueError("direction must be one of: up, down, both")


def _rule_label(rule: dict[str, Any], default: str) -> str:
    label = rule.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    return default


def _evaluate_crossover(
    series: list[SeriesPoint],
    rule: dict[str, Any],
    series_name: str,
) -> list[IndicatorSignal]:
    level = _to_float(rule.get("level", 0), "criteria.level")
    direction = _normalize_direction(rule.get("direction"))

    matches: list[IndicatorSignal] = []
    if len(series) < 2:
        return matches

    for index in range(1, len(series)):
        prev = series[index - 1]
        current = series[index]
        prev_delta = prev.value - level
        current_delta = current.value - level

        crossed_up = prev_delta <= 0 and current_delta > 0
        crossed_down = prev_delta >= 0 and current_delta < 0

        if crossed_up and direction in {"up", "both"}:
            matches.append(
                IndicatorSignal(
                    signal_date=current.date,
                    signal_type="crossover_up",
                    metadata={
                        "series": series_name,
                        "level": level,
                        "direction": "up",
                        "prev_value": prev.value,
                        "current_value": current.value,
                        "label": _rule_label(rule, f"crossover_up_{series_name}_{level}"),
                    },
                )
            )
        if crossed_down and direction in {"down", "both"}:
            matches.append(
                IndicatorSignal(
                    signal_date=current.date,
                    signal_type="crossover_down",
                    metadata={
                        "series": series_name,
                        "level": level,
                        "direction": "down",
                        "prev_value": prev.value,
                        "current_value": current.value,
                        "label": _rule_label(rule, f"crossover_down_{series_name}_{level}"),
                    },
                )
            )
    return matches


def _evaluate_threshold(
    series: list[SeriesPoint],
    rule: dict[str, Any],
    series_name: str,
) -> list[IndicatorSignal]:
    op = rule.get("op")
    if not isinstance(op, str) or op not in {">", ">=", "<", "<="}:
        raise ValueError("criteria.op must be one of: >, >=, <, <=")
    level = _to_float(rule.get("level"), "criteria.level")

    comparisons: dict[str, Callable[[float, float], bool]] = {
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
    }

    matches: list[IndicatorSignal] = []
    for point in series:
        if not comparisons[op](point.value, level):
            continue
        matches.append(
            IndicatorSignal(
                signal_date=point.date,
                signal_type=f"threshold_{op}",
                metadata={
                    "series": series_name,
                    "level": level,
                    "op": op,
                    "current_value": point.value,
                    "label": _rule_label(rule, f"threshold_{op}_{series_name}_{level}"),
                },
            )
        )
    return matches


def _evaluate_direction(
    series: list[SeriesPoint],
    rule: dict[str, Any],
    series_name: str,
) -> list[IndicatorSignal]:
    lookback = _to_int(rule.get("lookback", 1), "criteria.lookback")
    if lookback <= 0:
        raise ValueError("criteria.lookback must be > 0")
    if len(series) <= lookback:
        return []

    matches: list[IndicatorSignal] = []
    for index in range(lookback, len(series)):
        current = series[index]
        prior = series[index - lookback]
        if current.value > prior.value:
            direction = "up"
        elif current.value < prior.value:
            direction = "down"
        else:
            direction = "flat"
        matches.append(
            IndicatorSignal(
                signal_date=current.date,
                signal_type=f"direction_{direction}",
                metadata={
                    "series": series_name,
                    "lookback": lookback,
                    "direction": direction,
                    "prior_value": prior.value,
                    "current_value": current.value,
                    "label": _rule_label(rule, f"direction_{series_name}_{lookback}"),
                },
            )
        )
    return matches


def evaluate_criteria(
    series: Iterable[SeriesPoint],
    rules: list[dict[str, Any]],
    series_name: str,
) -> list[IndicatorSignal]:
    rule_handlers: dict[str, Callable[[list[SeriesPoint], dict[str, Any], str], list[IndicatorSignal]]] = {
        "crossover": _evaluate_crossover,
        "threshold": _evaluate_threshold,
        "direction": _evaluate_direction,
    }

    series_list = [point for point in series if point.value is not None and point.date]
    if not series_list or not rules:
        return []

    matches: list[IndicatorSignal] = []
    for rule in rules:
        rule_type = rule.get("type")
        if not isinstance(rule_type, str):
            raise ValueError("criteria.type must be a non-empty string")
        rule_type = rule_type.strip()
        if rule_type not in rule_handlers:
            raise ValueError(f"Unsupported criteria.type: {rule_type}")
        rule_series = rule.get("series")
        if isinstance(rule_series, str) and rule_series.strip():
            if rule_series.strip() != series_name:
                continue

        handler = rule_handlers[rule_type]
        matches.extend(handler(series_list, rule, series_name))

    return matches
