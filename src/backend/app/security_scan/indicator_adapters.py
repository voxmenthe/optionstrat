from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Callable

from app.security_scan.indicators import roc_aggregate as roc_aggregate_indicator
from app.security_scan.indicators import roc as roc_indicator


class IndicatorSettingsError(ValueError):
    """Raised when dashboard indicator settings fail adapter validation."""


@dataclass(frozen=True)
class IndicatorParameter:
    key: str
    label: str
    type: str
    default: Any
    required: bool = True
    min: int | float | None = None
    max: int | float | None = None
    description: str | None = None
    item_type: str | None = None


@dataclass(frozen=True)
class TracePoint:
    date: str
    value: float


@dataclass(frozen=True)
class IndicatorTrace:
    key: str
    label: str
    points: list[TracePoint]
    color: str | None = None


@dataclass(frozen=True)
class IndicatorPanel:
    id: str
    label: str
    traces: list[IndicatorTrace]
    reference_lines: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class IndicatorDashboardSignal:
    date: str
    type: str
    label: str
    target_trace: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IndicatorDashboardInput:
    ticker: str
    prices: list[dict[str, Any]]
    settings: dict[str, Any]
    benchmark_prices_by_ticker: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class IndicatorDashboardOutput:
    resolved_settings: dict[str, Any]
    panels: list[IndicatorPanel]
    signals: list[IndicatorDashboardSignal]
    diagnostics: dict[str, Any]


IndicatorCompute = Callable[[IndicatorDashboardInput], IndicatorDashboardOutput]


@dataclass(frozen=True)
class IndicatorDashboardAdapter:
    id: str
    label: str
    description: str
    parameters: list[IndicatorParameter]
    default_settings: dict[str, Any]
    requires_benchmarks: bool
    supported_intervals: list[str]
    compute: IndicatorCompute


def _parse_integer(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise IndicatorSettingsError(f"{label} must be an integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float) and value.is_integer():
        parsed = int(value)
    elif isinstance(value, str) and value.strip():
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise IndicatorSettingsError(f"{label} must be an integer") from exc
    else:
        raise IndicatorSettingsError(f"{label} must be an integer")
    return parsed


def _parse_float(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise IndicatorSettingsError(f"{label} must be a number")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise IndicatorSettingsError(f"{label} must be a number") from exc
    if not isfinite(parsed):
        raise IndicatorSettingsError(f"{label} must be finite")
    return parsed


def _parse_integer_list(value: Any, label: str) -> list[int]:
    if not isinstance(value, list):
        raise IndicatorSettingsError(f"{label} must be a list of integers")
    if not value:
        raise IndicatorSettingsError(f"{label} must be a non-empty list")
    return [_parse_integer(item, label) for item in value]


def _validate_parameter_bounds(value: Any, parameter: IndicatorParameter) -> None:
    values = value if isinstance(value, list) else [value]
    for item in values:
        if parameter.min is not None and item < parameter.min:
            raise IndicatorSettingsError(f"{parameter.key} must be >= {parameter.min}")
        if parameter.max is not None and item > parameter.max:
            raise IndicatorSettingsError(f"{parameter.key} must be <= {parameter.max}")


def _parse_parameter_value(value: Any, parameter: IndicatorParameter) -> Any:
    if parameter.type == "integer":
        parsed = _parse_integer(value, parameter.key)
    elif parameter.type == "float":
        parsed = _parse_float(value, parameter.key)
    elif parameter.type == "integer_list":
        parsed = _parse_integer_list(value, parameter.key)
    elif parameter.type == "boolean":
        if not isinstance(value, bool):
            raise IndicatorSettingsError(f"{parameter.key} must be a boolean")
        parsed = value
    else:
        parsed = value

    _validate_parameter_bounds(parsed, parameter)
    return parsed


def resolve_adapter_settings(
    adapter: IndicatorDashboardAdapter,
    raw_settings: dict[str, Any] | None,
) -> dict[str, Any]:
    settings = raw_settings or {}
    parameter_by_key = {parameter.key: parameter for parameter in adapter.parameters}
    allowed_keys = set(parameter_by_key)
    unknown_keys = sorted(set(settings) - allowed_keys)
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise IndicatorSettingsError(f"Unsupported settings for {adapter.id}: {joined}")

    resolved: dict[str, Any] = {}
    for parameter in adapter.parameters:
        value = settings.get(parameter.key, adapter.default_settings.get(parameter.key))
        if value is None:
            if parameter.required:
                raise IndicatorSettingsError(f"{parameter.key} is required")
            continue
        resolved[parameter.key] = _parse_parameter_value(value, parameter)
    return resolved


def _trace_points_from_series(series: list[Any]) -> list[TracePoint]:
    return [
        TracePoint(date=point.date, value=float(point.value))
        for point in series
        if point.date and point.value is not None
    ]


def _build_zero_cross_signals(
    points: list[TracePoint],
) -> list[IndicatorDashboardSignal]:
    signals: list[IndicatorDashboardSignal] = []
    for index in range(1, len(points)):
        previous = points[index - 1]
        current = points[index]
        crossed_up = previous.value <= 0 < current.value
        crossed_down = previous.value >= 0 > current.value
        if not crossed_up and not crossed_down:
            continue

        direction = "up" if crossed_up else "down"
        signals.append(
            IndicatorDashboardSignal(
                date=current.date,
                type=f"zero_cross_{direction}",
                label=f"ROC crossed {'above' if crossed_up else 'below'} 0",
                target_trace="roc",
                metadata={
                    "level": 0,
                    "direction": direction,
                    "previous_value": previous.value,
                    "current_value": current.value,
                },
            )
        )
    return signals


def _signal_type_label(signal_type: str) -> str:
    return signal_type.replace("_", " ").title()


def _compute_roc_dashboard(
    dashboard_input: IndicatorDashboardInput,
) -> IndicatorDashboardOutput:
    resolved_settings = resolve_adapter_settings(
        ROC_DASHBOARD_ADAPTER,
        dashboard_input.settings,
    )
    lookback = resolved_settings["roc_lookback"]
    close_series = roc_indicator._extract_close_series(dashboard_input.prices)
    roc_series = roc_indicator._compute_roc_series(close_series, lookback)
    roc_points = _trace_points_from_series(roc_series)

    warnings: list[str] = []
    if not roc_points:
        warnings.append(f"Need more than {lookback} valid close prices to compute ROC.")

    return IndicatorDashboardOutput(
        resolved_settings=resolved_settings,
        panels=[
            IndicatorPanel(
                id="main",
                label="Rate of Change",
                traces=[
                    IndicatorTrace(
                        key="roc",
                        label=f"ROC {lookback}",
                        points=roc_points,
                        color="#0f766e",
                    )
                ],
                reference_lines=[0.0],
            )
        ],
        signals=_build_zero_cross_signals(roc_points),
        diagnostics={
            "price_points": len(close_series),
            "indicator_points": len(roc_points),
            "benchmark_tickers_used": [],
            "warnings": warnings,
        },
    )


def _compute_roc_aggregate_dashboard(
    dashboard_input: IndicatorDashboardInput,
) -> IndicatorDashboardOutput:
    resolved_settings = resolve_adapter_settings(
        ROC_AGGREGATE_DASHBOARD_ADAPTER,
        dashboard_input.settings,
    )
    computation = roc_aggregate_indicator.compute_roc_aggregate_computation(
        dashboard_input.prices,
        resolved_settings,
    )
    resolved_settings = computation.resolved_settings
    score_points = _trace_points_from_series(computation.score_series)
    short_ma_points = _trace_points_from_series(computation.short_ma_series)
    long_ma_points = _trace_points_from_series(computation.long_ma_series)

    warnings: list[str] = []
    if not score_points:
        required_points = (
            max(resolved_settings["roc_lookbacks"])
            + max(resolved_settings["roc_change_lookbacks"])
            + 1
        )
        warnings.append(
            f"Need at least {required_points} valid close prices to compute ROC Aggregate score."
        )
    if score_points and not short_ma_points:
        warnings.append(
            f"Need at least {resolved_settings['ma_short']} score points to compute the short moving average."
        )
    if score_points and not long_ma_points:
        warnings.append(
            f"Need at least {resolved_settings['ma_long']} score points to compute the long moving average."
        )

    return IndicatorDashboardOutput(
        resolved_settings=resolved_settings,
        panels=[
            IndicatorPanel(
                id="main",
                label="ROC Aggregate",
                traces=[
                    IndicatorTrace(
                        key="score",
                        label="ROC Aggregate Score",
                        points=score_points,
                        color="#0f766e",
                    ),
                    IndicatorTrace(
                        key="ma_short",
                        label=f"Short MA {resolved_settings['ma_short']}",
                        points=short_ma_points,
                        color="#b45309",
                    ),
                    IndicatorTrace(
                        key="ma_long",
                        label=f"Long MA {resolved_settings['ma_long']}",
                        points=long_ma_points,
                        color="#1d4ed8",
                    ),
                ],
                reference_lines=[0.0],
            )
        ],
        signals=[
            IndicatorDashboardSignal(
                date=signal.signal_date,
                type=signal.signal_type,
                label=_signal_type_label(signal.signal_type),
                target_trace="score",
                metadata=dict(signal.metadata),
            )
            for signal in computation.signals
        ],
        diagnostics={
            "price_points": len(computation.close_series),
            "indicator_points": len(score_points),
            "benchmark_tickers_used": [],
            "warnings": warnings,
        },
    )


ROC_DASHBOARD_ADAPTER = IndicatorDashboardAdapter(
    id="roc",
    label="Rate of Change",
    description="Close-to-close percentage rate of change over a configurable lookback.",
    parameters=[
        IndicatorParameter(
            key="roc_lookback",
            label="ROC Lookback",
            type="integer",
            default=12,
            min=1,
            required=True,
            description="Number of bars between the current close and comparison close.",
        )
    ],
    default_settings={"roc_lookback": 12},
    requires_benchmarks=False,
    supported_intervals=["day"],
    compute=_compute_roc_dashboard,
)

ROC_AGGREGATE_DASHBOARD_ADAPTER = IndicatorDashboardAdapter(
    id="roc_aggregate",
    label="ROC Aggregate",
    description="Aggregate ROC trend score with short and long moving-average overlays.",
    parameters=[
        IndicatorParameter(
            key="roc_lookbacks",
            label="ROC Lookbacks",
            type="integer_list",
            default=[5, 10, 20],
            min=1,
            required=True,
            description="Comma-separated ROC lookback windows used to build the aggregate score.",
            item_type="integer",
        ),
        IndicatorParameter(
            key="roc_change_lookbacks",
            label="ROC Change Lookbacks",
            type="integer_list",
            default=[1, 3, 5],
            min=1,
            required=True,
            description="Comma-separated score-comparison windows used to measure ROC acceleration or decay.",
            item_type="integer",
        ),
        IndicatorParameter(
            key="ma_short",
            label="Short MA Window",
            type="integer",
            default=5,
            min=1,
            required=True,
            description="Window for the short moving-average overlay on the aggregate score.",
        ),
        IndicatorParameter(
            key="ma_long",
            label="Long MA Window",
            type="integer",
            default=20,
            min=1,
            required=True,
            description="Window for the long moving-average overlay on the aggregate score.",
        ),
    ],
    default_settings={
        "roc_lookbacks": [5, 10, 20],
        "roc_change_lookbacks": [1, 3, 5],
        "ma_short": 5,
        "ma_long": 20,
    },
    requires_benchmarks=False,
    supported_intervals=["day"],
    compute=_compute_roc_aggregate_dashboard,
)


DASHBOARD_ADAPTERS: dict[str, IndicatorDashboardAdapter] = {
    ROC_DASHBOARD_ADAPTER.id: ROC_DASHBOARD_ADAPTER,
    ROC_AGGREGATE_DASHBOARD_ADAPTER.id: ROC_AGGREGATE_DASHBOARD_ADAPTER,
}


def get_dashboard_adapters() -> dict[str, IndicatorDashboardAdapter]:
    return DASHBOARD_ADAPTERS


__all__ = [
    "IndicatorDashboardAdapter",
    "IndicatorDashboardInput",
    "IndicatorDashboardOutput",
    "IndicatorDashboardSignal",
    "IndicatorPanel",
    "IndicatorParameter",
    "IndicatorSettingsError",
    "IndicatorTrace",
    "TracePoint",
    "get_dashboard_adapters",
    "resolve_adapter_settings",
]
