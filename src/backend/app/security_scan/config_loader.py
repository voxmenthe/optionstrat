from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib


@dataclass(frozen=True)
class IndicatorInstanceConfig:
    id: str
    instance_id: str | None
    settings: dict[str, Any]


@dataclass(frozen=True)
class SecurityScanConfig:
    tickers: list[str]
    lookback_days: int
    interval: str
    indicator_instances: list[IndicatorInstanceConfig]
    advance_decline_lookbacks: list[int]
    report_html: bool
    report_plot_lookbacks: list[int]
    report_aggregate_lookback_days: int | None
    report_max_points: int | None
    report_net_advances_ma_days: int
    report_advance_pct_avg_smoothing_days: int
    report_roc_breadth_avg_smoothing_days: int
    config_dir: Path


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
    defaults_section = _require_mapping(
        securities_config.get("scan_defaults"), "[scan_defaults]"
    )

    tickers = _require_list_of_strings(tickers_section.get("list"), "tickers.list")

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

    return SecurityScanConfig(
        tickers=tickers,
        lookback_days=lookback_days,
        interval=interval,
        indicator_instances=indicator_instances,
        advance_decline_lookbacks=advance_decline_lookbacks,
        report_html=report_html,
        report_plot_lookbacks=report_plot_lookbacks,
        report_aggregate_lookback_days=report_aggregate_lookback_days,
        report_max_points=report_max_points,
        report_net_advances_ma_days=report_net_advances_ma_days,
        report_advance_pct_avg_smoothing_days=report_advance_pct_avg_smoothing_days,
        report_roc_breadth_avg_smoothing_days=report_roc_breadth_avg_smoothing_days,
        config_dir=resolved_dir,
    )
