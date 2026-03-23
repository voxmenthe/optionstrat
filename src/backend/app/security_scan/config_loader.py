from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Iterable, Mapping
import tomllib

from app.security_scan.dispersion import (
    DEFAULT_DISPERSION_WINDOWS,
    DEFAULT_METHOD_WEIGHTS,
    DEFAULT_WINDOW_WEIGHTS,
    DispersionConfig,
)


@dataclass(frozen=True)
class IndicatorInstanceConfig:
    id: str
    instance_id: str | None
    settings: dict[str, Any]


@dataclass(frozen=True)
class SecurityScanConfig:
    tickers: list[str]
    nasdaq_tickers: list[str]
    sp100_tickers: list[str]
    lookback_days: int
    interval: str
    intraday_interval: str
    intraday_regular_hours_only: bool
    intraday_min_bars_required: int
    indicator_instances: list[IndicatorInstanceConfig]
    advance_decline_lookbacks: list[int]
    report_html: bool
    report_plot_lookbacks: list[int]
    report_aggregate_lookback_days: int | None
    report_max_points: int | None
    report_net_advances_ma_days: int
    report_net_advances_secondary_ma_days: int
    report_advance_pct_avg_smoothing_days: int
    report_roc_breadth_avg_smoothing_days: int
    report_chart_universes: list[str]
    config_dir: Path
    dispersion: DispersionConfig = field(default_factory=DispersionConfig)
    report_dispersion_html: bool = True
    report_dispersion_lookback_days: int = 252
    report_dispersion_show_components: bool = True
    report_dispersion_show_diagnostics: bool = True
    report_dispersion_smoothing_days: int = 3


REPORT_CHART_UNIVERSE_KEYS = {"all", "nasdaq", "sp100"}


def resolve_config_dir(config_dir: str | Path | None) -> Path:
    if config_dir is None:
        module_dir = Path(__file__).resolve().parent
        return module_dir / "config"

    candidate = Path(config_dir).expanduser()
    if not candidate.is_absolute():
        return (Path.cwd() / candidate).resolve()

    return candidate.resolve()


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("rb") as handle:
        return tomllib.load(handle)


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected {label} to be a table (mapping).")
    return value


def _require_list_of_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Expected {label} to be a non-empty list of strings.")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"Expected {label} to contain only non-empty strings.")
    return [item.strip() for item in value]


def _optional_list_of_strings(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Expected {label} to be a list of strings.")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"Expected {label} to contain only non-empty strings.")
    return [item.strip() for item in value]


def _require_list_of_mappings(value: Any, label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Expected {label} to be a list of tables (mappings).")
    mappings: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"Expected {label}[{index}] to be a table (mapping).")
        mappings.append(item)
    return mappings


def _require_list_of_positive_ints(value: Any, label: str) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list) or not value:
        raise ValueError(f"Expected {label} to be a non-empty list of integers.")
    results: list[int] = []
    for index, item in enumerate(value):
        try:
            number = int(item)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Expected {label}[{index}] to be an integer."
            ) from exc
        if number <= 0:
            raise ValueError(f"Expected {label}[{index}] to be > 0.")
        results.append(number)
    return results


def _require_bool(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"Expected {label} to be a boolean.")


def _require_optional_positive_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected {label} to be an integer.") from exc
    if number <= 0:
        raise ValueError(f"Expected {label} to be > 0.")
    return number


def _require_optional_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected {label} to be a number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"Expected {label} to be finite.")
    return number


def _require_optional_unit_float(value: Any, label: str) -> float | None:
    number = _require_optional_float(value, label)
    if number is None:
        return None
    if number < 0.0 or number > 1.0:
        raise ValueError(f"Expected {label} to be between 0 and 1.")
    return number


def _normalize_positive_int_list(
    values: list[int],
    *,
    fallback: Iterable[int],
) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    source = values if values else list(fallback)
    for value in source:
        number = int(value)
        if number <= 0 or number in seen:
            continue
        seen.add(number)
        normalized.append(number)
    return normalized


def _default_window_weights(windows: Iterable[int]) -> dict[int, float]:
    normalized = _normalize_positive_int_list(list(windows), fallback=DEFAULT_DISPERSION_WINDOWS)
    weighted = {window: DEFAULT_WINDOW_WEIGHTS.get(window, 0.0) for window in normalized}
    total = sum(weighted.values())
    if total <= 0.0:
        equal_weight = 1.0 / len(normalized)
        return {window: equal_weight for window in normalized}
    return {window: weight / total for window, weight in weighted.items()}


def _require_weight_sum(weights: Mapping[Any, float], label: str) -> None:
    total = sum(float(weight) for weight in weights.values())
    if not math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError(f"Expected {label} weights to sum to 1.0; got {total}.")


def _parse_window_weights(
    raw_weights: dict[str, Any],
    *,
    windows: Iterable[int],
    label: str,
) -> dict[int, float]:
    normalized_windows = _normalize_positive_int_list(
        list(windows), fallback=DEFAULT_DISPERSION_WINDOWS
    )
    if not raw_weights:
        return _default_window_weights(normalized_windows)
    weights: dict[int, float] = {}
    for window in normalized_windows:
        key_candidates = (f"w{window}", str(window))
        value_raw = None
        resolved_key = None
        for key in key_candidates:
            if key in raw_weights:
                value_raw = raw_weights[key]
                resolved_key = key
                break
        if value_raw is None:
            continue
        value = _require_optional_float(value_raw, f"{label}.{resolved_key}")
        if value is None:
            continue
        if value < 0.0:
            raise ValueError(f"Expected {label}.{resolved_key} to be >= 0.")
        weights[window] = value
    if len(weights) != len(normalized_windows):
        missing = [
            f"w{window}"
            for window in normalized_windows
            if window not in weights
        ]
        raise ValueError(f"Missing window weights for: {', '.join(missing)}.")
    _require_weight_sum(weights, label)
    return weights


def _parse_method_weights(
    raw_weights: dict[str, Any],
    *,
    label: str,
) -> dict[str, float]:
    method_keys = tuple(DEFAULT_METHOD_WEIGHTS.keys())
    if not raw_weights:
        return dict(DEFAULT_METHOD_WEIGHTS)

    weights: dict[str, float] = {}
    for method_key in method_keys:
        value = _require_optional_float(
            raw_weights.get(method_key),
            f"{label}.{method_key}",
        )
        if value is None:
            raise ValueError(f"Missing method weight: {label}.{method_key}.")
        if value < 0.0:
            raise ValueError(f"Expected {label}.{method_key} to be >= 0.")
        weights[method_key] = value
    _require_weight_sum(weights, label)
    return weights


def _normalize_criteria(value: Any, label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        if not all(isinstance(item, dict) for item in value):
            raise ValueError(f"Expected {label} to contain only tables (mappings).")
        return value
    raise ValueError(f"Expected {label} to be a table or list of tables.")


def load_security_scan_config(
    config_dir: str | Path | None = None,
) -> SecurityScanConfig:
    resolved_dir = resolve_config_dir(config_dir)
    securities_path = resolved_dir / "securities.toml"
    settings_path = resolved_dir / "scan_settings.toml"

    securities_config = _load_toml(securities_path)
    scan_settings = _load_toml(settings_path)

    tickers_section = _require_mapping(securities_config.get("tickers"), "[tickers]")
    nasdaq_tickers_section = _require_mapping(
        securities_config.get("nasdaq_tickers"),
        "[nasdaq_tickers]",
    )
    sp100_tickers_section = _require_mapping(
        securities_config.get("sp100_tickers"),
        "[sp100_tickers]",
    )
    defaults_section = _require_mapping(
        securities_config.get("scan_defaults"), "[scan_defaults]"
    )

    tickers = _require_list_of_strings(tickers_section.get("list"), "tickers.list")
    nasdaq_tickers = _optional_list_of_strings(
        nasdaq_tickers_section.get("list"), "nasdaq_tickers.list"
    )
    sp100_tickers = _optional_list_of_strings(
        sp100_tickers_section.get("list"), "sp100_tickers.list"
    )

    lookback_raw = defaults_section.get("lookback_days", 90)
    try:
        lookback_days = int(lookback_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("scan_defaults.lookback_days must be an integer") from exc
    if lookback_days <= 0:
        raise ValueError("scan_defaults.lookback_days must be > 0")

    interval_raw = defaults_section.get("interval", "day")
    if not isinstance(interval_raw, str) or not interval_raw.strip():
        raise ValueError("scan_defaults.interval must be a non-empty string")
    interval = interval_raw.strip()
    intraday_section = _require_mapping(
        defaults_section.get("intraday"), "[scan_defaults.intraday]"
    )
    intraday_interval_raw = intraday_section.get("interval", "1m")
    if (
        not isinstance(intraday_interval_raw, str)
        or not intraday_interval_raw.strip()
    ):
        raise ValueError("scan_defaults.intraday.interval must be a non-empty string")
    intraday_interval = intraday_interval_raw.strip()
    intraday_regular_hours_only = _require_bool(
        intraday_section.get("regular_hours_only", True),
        "scan_defaults.intraday.regular_hours_only",
    )
    intraday_min_bars_required = (
        _require_optional_positive_int(
            intraday_section.get("min_bars_required"),
            "scan_defaults.intraday.min_bars_required",
        )
        or 30
    )

    indicators_section = _require_mapping(scan_settings.get("indicators"), "[indicators]")
    aggregates_section = _require_mapping(scan_settings.get("aggregates"), "[aggregates]")
    report_section = _require_mapping(scan_settings.get("report"), "[report]")
    instances_raw = _require_list_of_mappings(
        indicators_section.get("instances", []), "indicators.instances"
    )
    indicator_instances: list[IndicatorInstanceConfig] = []
    for index, instance in enumerate(instances_raw):
        indicator_id = instance.get("id")
        if not isinstance(indicator_id, str) or not indicator_id.strip():
            raise ValueError(f"Expected indicators.instances[{index}].id to be a string.")
        instance_id = instance.get("instance_id")
        if instance_id is not None and (
            not isinstance(instance_id, str) or not instance_id.strip()
        ):
            raise ValueError(
                f"Expected indicators.instances[{index}].instance_id to be a string."
            )
        settings = {
            key: value
            for key, value in instance.items()
            if key not in {"id", "instance_id"}
        }
        if "criteria" in settings:
            settings["criteria"] = _normalize_criteria(
                settings.get("criteria"), f"indicators.instances[{index}].criteria"
            )
        indicator_instances.append(
            IndicatorInstanceConfig(
                id=indicator_id.strip(),
                instance_id=instance_id.strip() if isinstance(instance_id, str) else None,
                settings=settings,
            )
        )

    lookbacks_raw = _require_list_of_positive_ints(
        aggregates_section.get("advance_decline_lookbacks"),
        "aggregates.advance_decline_lookbacks",
    )
    if not lookbacks_raw:
        advance_decline_lookbacks = [1]
    else:
        seen: set[int] = set()
        advance_decline_lookbacks = []
        for lookback in lookbacks_raw:
            if lookback in seen:
                continue
            seen.add(lookback)
            advance_decline_lookbacks.append(lookback)

    dispersion_section = _require_mapping(
        aggregates_section.get("dispersion"),
        "[aggregates.dispersion]",
    )
    dispersion_enabled = _require_bool(
        dispersion_section.get("enabled", True),
        "aggregates.dispersion.enabled",
    )
    dispersion_return_horizons = _normalize_positive_int_list(
        _require_list_of_positive_ints(
            dispersion_section.get("return_horizons"),
            "aggregates.dispersion.return_horizons",
        ),
        fallback=[1],
    )
    dispersion_windows = _normalize_positive_int_list(
        _require_list_of_positive_ints(
            dispersion_section.get("windows"),
            "aggregates.dispersion.windows",
        ),
        fallback=DEFAULT_DISPERSION_WINDOWS,
    )
    dispersion_window_weights = _parse_window_weights(
        _require_mapping(
            dispersion_section.get("window_weights"),
            "[aggregates.dispersion.window_weights]",
        ),
        windows=dispersion_windows,
        label="aggregates.dispersion.window_weights",
    )
    dispersion_method_weights = _parse_method_weights(
        _require_mapping(
            dispersion_section.get("method_weights"),
            "[aggregates.dispersion.method_weights]",
        ),
        label="aggregates.dispersion.method_weights",
    )
    dispersion_min_tickers = (
        _require_optional_positive_int(
            dispersion_section.get("min_tickers"),
            "aggregates.dispersion.min_tickers",
        )
        or 20
    )
    dispersion_min_observations = (
        _require_optional_positive_int(
            dispersion_section.get("min_observations"),
            "aggregates.dispersion.min_observations",
        )
        or 15
    )
    dispersion_min_pair_coverage = (
        _require_optional_unit_float(
            dispersion_section.get("min_pair_coverage"),
            "aggregates.dispersion.min_pair_coverage",
        )
        or 0.60
    )
    dispersion_use_robust_xs = _require_bool(
        dispersion_section.get("use_robust_xs_dispersion", True),
        "aggregates.dispersion.use_robust_xs_dispersion",
    )
    dispersion_xs_lockstep_decay = (
        _require_optional_float(
            dispersion_section.get("xs_lockstep_decay"),
            "aggregates.dispersion.xs_lockstep_decay",
        )
        or 1.0
    )
    if dispersion_xs_lockstep_decay < 0.0:
        raise ValueError("Expected aggregates.dispersion.xs_lockstep_decay to be >= 0.")
    dispersion_volatility_gate_enabled = _require_bool(
        dispersion_section.get("volatility_gate_enabled", False),
        "aggregates.dispersion.volatility_gate_enabled",
    )
    dispersion_volatility_gate_lookback = (
        _require_optional_positive_int(
            dispersion_section.get("volatility_gate_lookback"),
            "aggregates.dispersion.volatility_gate_lookback",
        )
        or 20
    )
    dispersion_volatility_gate_percentile = (
        _require_optional_unit_float(
            dispersion_section.get("volatility_gate_percentile"),
            "aggregates.dispersion.volatility_gate_percentile",
        )
        or 0.60
    )
    dispersion_segment_up_down = _require_bool(
        dispersion_section.get("segment_up_down", False),
        "aggregates.dispersion.segment_up_down",
    )
    dispersion_segment_threshold_sigma = (
        _require_optional_float(
            dispersion_section.get("segment_threshold_sigma"),
            "aggregates.dispersion.segment_threshold_sigma",
        )
        or 0.0
    )
    dispersion_segment_min_events = (
        _require_optional_positive_int(
            dispersion_section.get("segment_min_events"),
            "aggregates.dispersion.segment_min_events",
        )
        or 8
    )
    dispersion_config = DispersionConfig(
        enabled=dispersion_enabled,
        return_horizons=dispersion_return_horizons,
        windows=dispersion_windows,
        window_weights=dispersion_window_weights,
        method_weights=dispersion_method_weights,
        min_tickers=dispersion_min_tickers,
        min_observations=dispersion_min_observations,
        min_pair_coverage=dispersion_min_pair_coverage,
        use_robust_xs_dispersion=dispersion_use_robust_xs,
        xs_lockstep_decay=dispersion_xs_lockstep_decay,
        volatility_gate_enabled=dispersion_volatility_gate_enabled,
        volatility_gate_lookback=dispersion_volatility_gate_lookback,
        volatility_gate_percentile=dispersion_volatility_gate_percentile,
        segment_up_down=dispersion_segment_up_down,
        segment_threshold_sigma=dispersion_segment_threshold_sigma,
        segment_min_events=dispersion_segment_min_events,
    )

    html_raw = report_section.get("html", True)
    report_html = _require_bool(html_raw, "report.html")
    report_plot_lookbacks = _require_list_of_positive_ints(
        report_section.get("plot_lookbacks"),
        "report.plot_lookbacks",
    )
    report_aggregate_lookback_days = _require_optional_positive_int(
        report_section.get("aggregate_lookback_days"),
        "report.aggregate_lookback_days",
    )
    report_max_points = _require_optional_positive_int(
        report_section.get("max_points"),
        "report.max_points",
    )
    report_net_advances_ma_days = (
        _require_optional_positive_int(
            report_section.get("net_advances_ma_days"),
            "report.net_advances_ma_days",
        )
        or 18
    )
    report_net_advances_secondary_ma_days = (
        _require_optional_positive_int(
            report_section.get("net_advances_secondary_ma_days"),
            "report.net_advances_secondary_ma_days",
        )
        or 8
    )
    report_advance_pct_avg_smoothing_days = (
        _require_optional_positive_int(
            report_section.get("advance_pct_avg_smoothing_days"),
            "report.advance_pct_avg_smoothing_days",
        )
        or 3
    )
    report_roc_breadth_avg_smoothing_days = (
        _require_optional_positive_int(
            report_section.get("roc_breadth_avg_smoothing_days"),
            "report.roc_breadth_avg_smoothing_days",
        )
        or 3
    )
    report_dispersion_html = _require_bool(
        report_section.get("dispersion_html", True),
        "report.dispersion_html",
    )
    report_dispersion_lookback_days = (
        _require_optional_positive_int(
            report_section.get("dispersion_lookback_days"),
            "report.dispersion_lookback_days",
        )
        or 252
    )
    report_dispersion_show_components = _require_bool(
        report_section.get("dispersion_show_components", True),
        "report.dispersion_show_components",
    )
    report_dispersion_show_diagnostics = _require_bool(
        report_section.get("dispersion_show_diagnostics", True),
        "report.dispersion_show_diagnostics",
    )
    report_dispersion_smoothing_days = (
        _require_optional_positive_int(
            report_section.get("dispersion_smoothing_days"),
            "report.dispersion_smoothing_days",
        )
        or 3
    )
    chart_universes_raw = report_section.get("chart_universes")
    if chart_universes_raw is None:
        report_chart_universes = ["all"]
    else:
        chart_universes = _optional_list_of_strings(
            chart_universes_raw, "report.chart_universes"
        )
        if not chart_universes:
            raise ValueError("Expected report.chart_universes to be a non-empty list.")
        report_chart_universes = []
        seen_universes: set[str] = set()
        for index, universe_key in enumerate(chart_universes):
            if universe_key not in REPORT_CHART_UNIVERSE_KEYS:
                allowed_universes = ", ".join(sorted(REPORT_CHART_UNIVERSE_KEYS))
                raise ValueError(
                    f"Expected report.chart_universes[{index}] to be one of: {allowed_universes}."
                )
            if universe_key in seen_universes:
                continue
            seen_universes.add(universe_key)
            report_chart_universes.append(universe_key)

    return SecurityScanConfig(
        tickers=tickers,
        nasdaq_tickers=nasdaq_tickers,
        sp100_tickers=sp100_tickers,
        lookback_days=lookback_days,
        interval=interval,
        intraday_interval=intraday_interval,
        intraday_regular_hours_only=intraday_regular_hours_only,
        intraday_min_bars_required=intraday_min_bars_required,
        indicator_instances=indicator_instances,
        advance_decline_lookbacks=advance_decline_lookbacks,
        report_html=report_html,
        report_plot_lookbacks=report_plot_lookbacks,
        report_aggregate_lookback_days=report_aggregate_lookback_days,
        report_max_points=report_max_points,
        report_net_advances_ma_days=report_net_advances_ma_days,
        report_net_advances_secondary_ma_days=report_net_advances_secondary_ma_days,
        report_advance_pct_avg_smoothing_days=report_advance_pct_avg_smoothing_days,
        report_roc_breadth_avg_smoothing_days=report_roc_breadth_avg_smoothing_days,
        report_chart_universes=report_chart_universes,
        config_dir=resolved_dir,
        dispersion=dispersion_config,
        report_dispersion_html=report_dispersion_html,
        report_dispersion_lookback_days=report_dispersion_lookback_days,
        report_dispersion_show_components=report_dispersion_show_components,
        report_dispersion_show_diagnostics=report_dispersion_show_diagnostics,
        report_dispersion_smoothing_days=report_dispersion_smoothing_days,
    )
