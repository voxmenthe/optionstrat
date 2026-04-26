from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Callable

from app.security_scan.indicators import scl_ma2_qrs_ma1_breakout as breakout_indicator
from app.security_scan.indicators import qrs_consist_excess as qrs_consist_excess_indicator
from app.security_scan.indicators import roc_aggregate as roc_aggregate_indicator
from app.security_scan.indicators import roc as roc_indicator
from app.security_scan.indicators import scl_v4_x5 as scl_v4_x5_indicator


class IndicatorSettingsError(ValueError):
    """Raised when dashboard indicator settings fail adapter validation."""


class IndicatorDataError(ValueError):
    """Raised when dashboard indicator input data is unusable for compute."""


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
    benchmark_tickers: list[str] = field(default_factory=list)
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
    default_benchmark_tickers: list[str] = field(default_factory=list)
    required_benchmark_count: int | None = None


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


def _scl_signal_label(signal_type: str) -> str:
    labels = {
        "seven_bar_high": "7-Bar High",
        "seven_bar_low": "7-Bar Low",
    }
    return labels.get(signal_type, _signal_type_label(signal_type))


def _qrs_signal_label(signal_type: str) -> str:
    labels = {
        "main_cross_above_zero_3d": "Main Crossed Above Zero",
        "main_cross_below_zero_3d": "Main Crossed Below Zero",
        "ma1_cross_above_ma2": "MA1 Crossed Above MA2",
        "ma1_cross_below_ma2": "MA1 Crossed Below MA2",
        "main_above_all_mas_pos_regime": "Main Above All MAs in Positive Regime",
        "main_below_all_mas_neg_regime": "Main Below All MAs in Negative Regime",
        "ma1_cross_above_zero": "MA1 Crossed Above Zero",
        "ma1_cross_below_zero": "MA1 Crossed Below Zero",
    }
    return labels.get(signal_type, _signal_type_label(signal_type))


def _qrs_signal_target_trace(signal_type: str) -> str:
    if signal_type.startswith("ma1_"):
        return "ma1"
    return "qrs"


def _breakout_signal_label(signal_type: str) -> str:
    labels = {
        "dual_breakout_up": "Dual Breakout Up",
        "dual_breakout_down": "Dual Breakout Down",
    }
    return labels.get(signal_type, _signal_type_label(signal_type))


def _build_breakout_dashboard_signals(
    signals: list[Any],
) -> list[IndicatorDashboardSignal]:
    dashboard_signals: list[IndicatorDashboardSignal] = []
    for signal in signals:
        label = _breakout_signal_label(signal.signal_type)
        metadata = dict(signal.metadata)
        if signal.signal_type.endswith("_up"):
            threshold_key = "prior_high"
        else:
            threshold_key = "prior_low"

        dashboard_signals.extend(
            [
                IndicatorDashboardSignal(
                    date=signal.signal_date,
                    type=signal.signal_type,
                    label=label,
                    target_trace="scl_ma2",
                    metadata={
                        "series": "SCL MA2",
                        "lookback": metadata.get("scl_lookback"),
                        "current_value": metadata.get("scl_current"),
                        threshold_key: metadata.get(f"scl_{threshold_key}"),
                        "paired_series": "QRS MA1",
                        "paired_current": metadata.get("qrs_current"),
                        f"paired_{threshold_key}": metadata.get(
                            f"qrs_{threshold_key}"
                        ),
                    },
                ),
                IndicatorDashboardSignal(
                    date=signal.signal_date,
                    type=signal.signal_type,
                    label=label,
                    target_trace="qrs_ma1",
                    metadata={
                        "series": "QRS MA1",
                        "lookback": metadata.get("qrs_lookback"),
                        "current_value": metadata.get("qrs_current"),
                        threshold_key: metadata.get(f"qrs_{threshold_key}"),
                        "paired_series": "SCL MA2",
                        "paired_current": metadata.get("scl_current"),
                        f"paired_{threshold_key}": metadata.get(
                            f"scl_{threshold_key}"
                        ),
                    },
                ),
            ]
        )
    return dashboard_signals


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


def _compute_scl_v4_x5_dashboard(
    dashboard_input: IndicatorDashboardInput,
) -> IndicatorDashboardOutput:
    resolved_settings = resolve_adapter_settings(
        SCL_V4_X5_DASHBOARD_ADAPTER,
        dashboard_input.settings,
    )
    computation = scl_v4_x5_indicator.compute_scl_v4_x5_computation(
        dashboard_input.prices,
        resolved_settings,
    )
    countdown_points = _trace_points_from_series(computation.countdown_series)
    ma1_points = _trace_points_from_series(computation.ma1_series)
    ma2_points = _trace_points_from_series(computation.ma2_series)

    warnings: list[str] = []
    if computation.usable_ohlc_points == 0:
        warnings.append("Need close, high, and low prices to compute SCL V4 X5.")
    elif computation.skipped_price_rows > 0:
        warnings.append(
            f"Skipped {computation.skipped_price_rows} price rows missing high/low fields for SCL V4 X5."
        )
    elif not countdown_points:
        warnings.append("SCL V4 X5 returned no usable dashboard series.")

    return IndicatorDashboardOutput(
        resolved_settings=computation.resolved_settings,
        panels=[
            IndicatorPanel(
                id="main",
                label="SCL V4 X5",
                traces=[
                    IndicatorTrace(
                        key="countdown",
                        label="Countdown Display",
                        points=countdown_points,
                        color="#0f766e",
                    ),
                    IndicatorTrace(
                        key="ma1",
                        label=f"MA1 {computation.resolved_settings['ma_period1']}",
                        points=ma1_points,
                        color="#b45309",
                    ),
                    IndicatorTrace(
                        key="ma2",
                        label=f"MA2 {computation.resolved_settings['ma_period2']}",
                        points=ma2_points,
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
                label=_scl_signal_label(signal.signal_type),
                target_trace="countdown",
                metadata=dict(signal.metadata),
            )
            for signal in computation.signals
        ],
        diagnostics={
            "indicator_points": len(countdown_points),
            "benchmark_tickers_used": [],
            "warnings": warnings,
        },
    )


def _compute_qrs_consist_excess_dashboard(
    dashboard_input: IndicatorDashboardInput,
) -> IndicatorDashboardOutput:
    resolved_settings = resolve_adapter_settings(
        QRS_CONSIST_EXCESS_DASHBOARD_ADAPTER,
        dashboard_input.settings,
    )
    aligned_inputs = qrs_consist_excess_indicator.align_qrs_consist_excess_inputs(
        prices=dashboard_input.prices,
        benchmark_prices_by_ticker=dashboard_input.benchmark_prices_by_ticker,
        benchmark_tickers=dashboard_input.benchmark_tickers,
    )
    if aligned_inputs.aligned_price_points == 0:
        benchmarks = ", ".join(aligned_inputs.benchmark_tickers)
        raise IndicatorDataError(
            f"No common dates remain after aligning {dashboard_input.ticker} with benchmark prices for {benchmarks}."
        )

    computation = qrs_consist_excess_indicator.compute_qrs_consist_excess_computation(
        aligned_inputs=aligned_inputs,
        settings=resolved_settings,
    )
    main_points = _trace_points_from_series(computation.main_series)
    ma1_points = _trace_points_from_series(computation.ma1_series)
    ma2_points = _trace_points_from_series(computation.ma2_series)
    ma3_points = _trace_points_from_series(computation.ma3_series)

    warnings: list[str] = []
    if aligned_inputs.dropped_price_points > 0:
        benchmarks = ", ".join(aligned_inputs.benchmark_tickers)
        warnings.append(
            "Dropped "
            f"{aligned_inputs.dropped_price_points} price rows without full benchmark coverage across {benchmarks}."
        )
    if not main_points:
        warnings.append("QRS Consistency + Excess returned no usable dashboard series.")

    return IndicatorDashboardOutput(
        resolved_settings=computation.resolved_settings,
        panels=[
            IndicatorPanel(
                id="main",
                label="QRS Consistency + Excess",
                traces=[
                    IndicatorTrace(
                        key="qrs",
                        label="QRS Consistency + Excess",
                        points=main_points,
                        color="#0f766e",
                    ),
                    IndicatorTrace(
                        key="ma1",
                        label=f"MA1 {int(computation.resolved_settings['map1'])}",
                        points=ma1_points,
                        color="#b45309",
                    ),
                    IndicatorTrace(
                        key="ma2",
                        label=f"MA2 {int(computation.resolved_settings['map2'])}",
                        points=ma2_points,
                        color="#1d4ed8",
                    ),
                    IndicatorTrace(
                        key="ma3",
                        label=f"MA3 {int(computation.resolved_settings['map3'])}",
                        points=ma3_points,
                        color="#7c3aed",
                    ),
                ],
                reference_lines=[0.0],
            )
        ],
        signals=[
            IndicatorDashboardSignal(
                date=signal.signal_date,
                type=signal.signal_type,
                label=_qrs_signal_label(signal.signal_type),
                target_trace=_qrs_signal_target_trace(signal.signal_type),
                metadata=dict(signal.metadata),
            )
            for signal in computation.signals
        ],
        diagnostics={
            "indicator_points": len(main_points),
            "benchmark_tickers_used": list(aligned_inputs.benchmark_tickers),
            "warnings": warnings,
        },
    )


def _compute_scl_ma2_qrs_ma1_breakout_dashboard(
    dashboard_input: IndicatorDashboardInput,
) -> IndicatorDashboardOutput:
    resolved_settings = resolve_adapter_settings(
        SCL_MA2_QRS_MA1_BREAKOUT_DASHBOARD_ADAPTER,
        dashboard_input.settings,
    )
    computation = breakout_indicator.compute_scl_ma2_qrs_ma1_breakout_computation(
        dashboard_input.prices,
        resolved_settings,
        benchmark_prices_by_ticker=dashboard_input.benchmark_prices_by_ticker,
        benchmark_tickers=dashboard_input.benchmark_tickers,
    )
    if computation.common_aligned_points == 0:
        raise IndicatorDataError(
            "No common dates remain after aligning SCL MA2 and QRS MA1 series. "
            "Check high/low availability and benchmark overlap."
        )

    scl_ma2_points = _trace_points_from_series(computation.scl_ma2_series)
    qrs_ma1_points = _trace_points_from_series(computation.qrs_ma1_series)

    warnings: list[str] = []
    if computation.scl_skipped_price_rows > 0:
        warnings.append(
            "Skipped "
            f"{computation.scl_skipped_price_rows} price rows missing high/low fields while computing SCL MA2."
        )
    if computation.qrs_dropped_price_points > 0:
        benchmarks = ", ".join(computation.benchmark_tickers)
        warnings.append(
            "Dropped "
            f"{computation.qrs_dropped_price_points} price rows without full benchmark coverage across {benchmarks}."
        )

    return IndicatorDashboardOutput(
        resolved_settings=computation.resolved_settings,
        panels=[
            IndicatorPanel(
                id="main",
                label="SCL MA2 + QRS MA1 Breakout",
                traces=[
                    IndicatorTrace(
                        key="scl_ma2",
                        label=f"SCL MA2 {int(computation.resolved_settings['ma_period2'])}",
                        points=scl_ma2_points,
                        color="#b45309",
                    ),
                    IndicatorTrace(
                        key="qrs_ma1",
                        label=f"QRS MA1 {int(computation.resolved_settings['map1'])}",
                        points=qrs_ma1_points,
                        color="#0f766e",
                    ),
                ],
                reference_lines=[0.0],
            )
        ],
        signals=_build_breakout_dashboard_signals(computation.signals),
        diagnostics={
            "indicator_points": len(scl_ma2_points),
            "benchmark_tickers_used": list(computation.benchmark_tickers),
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

SCL_V4_X5_DASHBOARD_ADAPTER = IndicatorDashboardAdapter(
    id="scl_v4_x5",
    label="SCL V4 X5",
    description="Sequential countdown oscillator with MA1 and MA2 overlays plus seven-bar breakout markers.",
    parameters=[
        IndicatorParameter(
            key="lag1",
            label="Lag 1",
            type="integer",
            default=2,
            min=1,
            required=True,
            description="First close-to-close comparison lag used in the countdown sequence.",
        ),
        IndicatorParameter(
            key="lag2",
            label="Lag 2",
            type="integer",
            default=3,
            min=1,
            required=True,
            description="Second close-to-close comparison lag used in the countdown sequence.",
        ),
        IndicatorParameter(
            key="lag3",
            label="Lag 3",
            type="integer",
            default=4,
            min=1,
            required=True,
            description="Third close-to-close comparison lag used in the countdown sequence.",
        ),
        IndicatorParameter(
            key="lag4",
            label="Lag 4",
            type="integer",
            default=5,
            min=1,
            required=True,
            description="Fourth close-to-close comparison lag used in the countdown sequence.",
        ),
        IndicatorParameter(
            key="lag5",
            label="Lag 5",
            type="integer",
            default=11,
            min=1,
            required=True,
            description="Fifth close-to-close comparison lag used in the countdown sequence.",
        ),
        IndicatorParameter(
            key="cd_offset1",
            label="Countdown Offset 1",
            type="integer",
            default=2,
            min=1,
            required=True,
            description="First high/low comparison offset for the countdown adjustment.",
        ),
        IndicatorParameter(
            key="cd_offset2",
            label="Countdown Offset 2",
            type="integer",
            default=3,
            min=1,
            required=True,
            description="Second high/low comparison offset for the countdown adjustment.",
        ),
        IndicatorParameter(
            key="ma_period1",
            label="MA Period 1",
            type="integer",
            default=5,
            min=1,
            required=True,
            description="Window for the faster moving-average overlay on the countdown series.",
        ),
        IndicatorParameter(
            key="ma_period2",
            label="MA Period 2",
            type="integer",
            default=11,
            min=1,
            required=True,
            description="Window for the slower moving-average overlay on the countdown series.",
        ),
    ],
    default_settings={
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
    requires_benchmarks=False,
    supported_intervals=["day"],
    compute=_compute_scl_v4_x5_dashboard,
)

QRS_CONSIST_EXCESS_DASHBOARD_ADAPTER = IndicatorDashboardAdapter(
    id="qrs_consist_excess",
    label="QRS Consistency + Excess",
    description="Benchmark-relative QRS score with MA1, MA2, and MA3 overlays plus regime and crossover markers.",
    parameters=[
        IndicatorParameter(
            key="lookback",
            label="Lookback",
            type="integer",
            default=84,
            min=1,
            required=True,
            description="Rolling window used to score benchmark-relative consistency and excess return.",
        ),
        IndicatorParameter(
            key="deadband_period",
            label="Deadband Period",
            type="integer",
            default=20,
            min=1,
            required=True,
            description="Rolling window used to estimate benchmark volatility for the deadband gate.",
        ),
        IndicatorParameter(
            key="deadband_mult",
            label="Deadband Multiplier",
            type="float",
            default=0.25,
            min=0,
            required=True,
            description="Multiplier applied to benchmark volatility when deciding whether a day is directionally active.",
        ),
        IndicatorParameter(
            key="map1",
            label="MA1 Period",
            type="integer",
            default=7,
            min=1,
            required=True,
            description="Window for the fastest QRS moving-average overlay.",
        ),
        IndicatorParameter(
            key="map2",
            label="MA2 Period",
            type="integer",
            default=21,
            min=1,
            required=True,
            description="Window for the middle QRS moving-average overlay.",
        ),
        IndicatorParameter(
            key="map3",
            label="MA3 Period",
            type="integer",
            default=56,
            min=1,
            required=True,
            description="Window for the slowest QRS moving-average overlay.",
        ),
        IndicatorParameter(
            key="cons_weight",
            label="Consistency Weight",
            type="float",
            default=0.6,
            min=0,
            required=True,
            description="Weight applied to the directional consistency component in the combined QRS score.",
        ),
        IndicatorParameter(
            key="excess_weight",
            label="Excess Weight",
            type="float",
            default=0.4,
            min=0,
            required=True,
            description="Weight applied to the normalized excess-return component in the combined QRS score.",
        ),
        IndicatorParameter(
            key="ma_shift",
            label="MA Shift",
            type="integer",
            default=3,
            min=0,
            required=True,
            description="Forward offset applied to the moving-average overlays after smoothing.",
        ),
    ],
    default_settings={
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
    requires_benchmarks=True,
    supported_intervals=["day"],
    default_benchmark_tickers=list(qrs_consist_excess_indicator.BENCHMARK_TICKERS),
    required_benchmark_count=3,
    compute=_compute_qrs_consist_excess_dashboard,
)

SCL_MA2_QRS_MA1_BREAKOUT_DASHBOARD_ADAPTER = IndicatorDashboardAdapter(
    id="scl_ma2_qrs_ma1_breakout",
    label="SCL MA2 + QRS MA1 Breakout",
    description="Composite benchmark-aware breakout view that overlays SCL MA2 and QRS MA1 and marks dates where both exceed their prior windows in the same direction.",
    parameters=[
        IndicatorParameter(
            key="scl_ma2_window",
            label="SCL MA2 Breakout Window",
            type="integer",
            default=12,
            min=1,
            required=True,
            description="Prior-window length used when checking whether SCL MA2 breaks above or below its recent range.",
        ),
        IndicatorParameter(
            key="lag1",
            label="SCL Lag 1",
            type="integer",
            default=2,
            min=1,
            required=True,
            description="First close-to-close comparison lag used in the SCL countdown sequence.",
        ),
        IndicatorParameter(
            key="lag2",
            label="SCL Lag 2",
            type="integer",
            default=3,
            min=1,
            required=True,
            description="Second close-to-close comparison lag used in the SCL countdown sequence.",
        ),
        IndicatorParameter(
            key="lag3",
            label="SCL Lag 3",
            type="integer",
            default=4,
            min=1,
            required=True,
            description="Third close-to-close comparison lag used in the SCL countdown sequence.",
        ),
        IndicatorParameter(
            key="lag4",
            label="SCL Lag 4",
            type="integer",
            default=5,
            min=1,
            required=True,
            description="Fourth close-to-close comparison lag used in the SCL countdown sequence.",
        ),
        IndicatorParameter(
            key="lag5",
            label="SCL Lag 5",
            type="integer",
            default=11,
            min=1,
            required=True,
            description="Fifth close-to-close comparison lag used in the SCL countdown sequence.",
        ),
        IndicatorParameter(
            key="cd_offset1",
            label="SCL Countdown Offset 1",
            type="integer",
            default=2,
            min=1,
            required=True,
            description="First high/low comparison offset used in the SCL countdown adjustment.",
        ),
        IndicatorParameter(
            key="cd_offset2",
            label="SCL Countdown Offset 2",
            type="integer",
            default=3,
            min=1,
            required=True,
            description="Second high/low comparison offset used in the SCL countdown adjustment.",
        ),
        IndicatorParameter(
            key="ma_period1",
            label="SCL MA Period 1",
            type="integer",
            default=5,
            min=1,
            required=True,
            description="Window for the faster SCL moving-average overlay.",
        ),
        IndicatorParameter(
            key="ma_period2",
            label="SCL MA Period 2",
            type="integer",
            default=11,
            min=1,
            required=True,
            description="Window for the slower SCL moving-average overlay that feeds the composite breakout test.",
        ),
        IndicatorParameter(
            key="qrs_ma1_window",
            label="QRS MA1 Breakout Window",
            type="integer",
            default=5,
            min=1,
            required=True,
            description="Prior-window length used when checking whether QRS MA1 breaks above or below its recent range.",
        ),
        IndicatorParameter(
            key="lookback",
            label="QRS Lookback",
            type="integer",
            default=84,
            min=1,
            required=True,
            description="Rolling window used to score benchmark-relative consistency and excess return.",
        ),
        IndicatorParameter(
            key="deadband_period",
            label="QRS Deadband Period",
            type="integer",
            default=20,
            min=1,
            required=True,
            description="Rolling window used to estimate benchmark volatility for the QRS deadband gate.",
        ),
        IndicatorParameter(
            key="deadband_mult",
            label="QRS Deadband Multiplier",
            type="float",
            default=0.25,
            min=0,
            required=True,
            description="Multiplier applied to benchmark volatility when deciding whether a day is directionally active.",
        ),
        IndicatorParameter(
            key="map1",
            label="QRS MA1 Period",
            type="integer",
            default=7,
            min=1,
            required=True,
            description="Window for the fastest QRS moving-average overlay used by the composite breakout test.",
        ),
        IndicatorParameter(
            key="map2",
            label="QRS MA2 Period",
            type="integer",
            default=21,
            min=1,
            required=True,
            description="Window for the middle QRS moving-average overlay.",
        ),
        IndicatorParameter(
            key="map3",
            label="QRS MA3 Period",
            type="integer",
            default=56,
            min=1,
            required=True,
            description="Window for the slowest QRS moving-average overlay.",
        ),
        IndicatorParameter(
            key="cons_weight",
            label="QRS Consistency Weight",
            type="float",
            default=0.6,
            min=0,
            required=True,
            description="Weight applied to the directional consistency component in the combined QRS score.",
        ),
        IndicatorParameter(
            key="excess_weight",
            label="QRS Excess Weight",
            type="float",
            default=0.4,
            min=0,
            required=True,
            description="Weight applied to the normalized excess-return component in the combined QRS score.",
        ),
        IndicatorParameter(
            key="ma_shift",
            label="QRS MA Shift",
            type="integer",
            default=3,
            min=0,
            required=True,
            description="Forward offset applied to the QRS moving-average overlays after smoothing.",
        ),
    ],
    default_settings={
        "scl_ma2_window": 12,
        "lag1": 2,
        "lag2": 3,
        "lag3": 4,
        "lag4": 5,
        "lag5": 11,
        "cd_offset1": 2,
        "cd_offset2": 3,
        "ma_period1": 5,
        "ma_period2": 11,
        "qrs_ma1_window": 5,
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
    requires_benchmarks=True,
    supported_intervals=["day"],
    default_benchmark_tickers=list(qrs_consist_excess_indicator.BENCHMARK_TICKERS),
    required_benchmark_count=3,
    compute=_compute_scl_ma2_qrs_ma1_breakout_dashboard,
)


DASHBOARD_ADAPTERS: dict[str, IndicatorDashboardAdapter] = {
    ROC_DASHBOARD_ADAPTER.id: ROC_DASHBOARD_ADAPTER,
    ROC_AGGREGATE_DASHBOARD_ADAPTER.id: ROC_AGGREGATE_DASHBOARD_ADAPTER,
    SCL_V4_X5_DASHBOARD_ADAPTER.id: SCL_V4_X5_DASHBOARD_ADAPTER,
    QRS_CONSIST_EXCESS_DASHBOARD_ADAPTER.id: QRS_CONSIST_EXCESS_DASHBOARD_ADAPTER,
    SCL_MA2_QRS_MA1_BREAKOUT_DASHBOARD_ADAPTER.id: SCL_MA2_QRS_MA1_BREAKOUT_DASHBOARD_ADAPTER,
}


def get_dashboard_adapters() -> dict[str, IndicatorDashboardAdapter]:
    return DASHBOARD_ADAPTERS


__all__ = [
    "IndicatorDashboardAdapter",
    "IndicatorDataError",
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
