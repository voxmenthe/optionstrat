# %% [markdown]
"""# Indicator Sanity Check Notebook

Plot historical prices alongside any configured security-scan indicator to visually
validate behavior before rolling out changes.

- Load indicator instances from `scan_settings.toml`.
- Fetch price history through the existing `MarketDataService`.
- Recompute the indicator series + signals, then render a dual pane chart (price + indicator).
- Designed as a plain Python script with `# %%` cell markers so it can run directly
  via `uv run python src/backend/notebooks/indicator_sanity_check.py` or inside a
  Jupyter/VS Code notebook session.
"""

# %%
from __future__ import annotations

import site
import sys
import os
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

# Ensure `app.*` imports resolve whether executed as a script or notebook
NOTEBOOK_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = NOTEBOOK_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Prefer the repo-root managed virtualenv so notebook runs without `uv run`
REPO_ROOT = BACKEND_ROOT.parent.parent
VENV_CANDIDATES = [REPO_ROOT / ".venv", BACKEND_ROOT / ".venv"]
python_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
for venv_root in VENV_CANDIDATES:
    if not venv_root.exists():
        continue
    candidates = [
        venv_root / "lib" / python_dir / "site-packages",
        venv_root / "Lib" / "site-packages",
    ]
    for candidate in candidates:
        if candidate.exists():
            site.addsitedir(candidate)
            break
    else:
        continue
    break

os.environ.setdefault("REDIS_ENABLED", "false")

import matplotlib  # noqa: E402
import pandas as pd  # noqa: E402

DEFAULT_MPL_BACKEND = None  # e.g., "module://matplotlib_inline.backend_inline"
if DEFAULT_MPL_BACKEND:
    matplotlib.use(DEFAULT_MPL_BACKEND)
import matplotlib.pyplot as plt  # noqa: E402

from app.security_scan.config_loader import (  # noqa: E402
    IndicatorInstanceConfig,
    SecurityScanConfig,
    load_security_scan_config,
)
from app.security_scan.data_fetcher import (  # noqa: E402
    MarketDataFetcher,
    normalize_prices,
)
from app.security_scan.indicators import (  # noqa: E402
    load_indicator_registry,
)
from app.security_scan.indicators import roc as roc_indicator  # noqa: E402
from app.security_scan.indicators import (  # noqa: E402
    roc_aggregate as roc_aggregate_indicator,
)
from app.security_scan.criteria import SeriesPoint  # noqa: E402
from app.security_scan.db import (  # noqa: E402
    SecurityAggregateValue,
    SessionLocal as ScanSessionLocal,
)
from app.security_scan.signals import IndicatorSignal  # noqa: E402
from app.security_scan.storage import compute_security_set_hash  # noqa: E402
from app.services.market_data import MarketDataService  # noqa: E402

plt.style.use("seaborn-v0_8-darkgrid")


# %%
# --- Configuration (edit in notebook / per run) ---
CONFIG_DIR = BACKEND_ROOT / "app" / "security_scan" / "config"
TICKER = "AAPL"
# Indicators: "roc", "roc_aggregate"
INDICATOR_KEY = "roc_aggregate"  # Accepts indicator `id` or `instance_id`
LOOKBACK_DAYS = 365
END_DATE = date.today()  # Override for back-testing
INTERVAL = "day"
INDICATOR_OVERRIDES: dict[str, Any] = {}
SHOW_INSTANCE_TABLE = True
PLOT_AGGREGATES = True
AGGREGATE_TICKERS: list[str] | None = None  # None -> use scan config tickers
AGGREGATE_LOOKBACK_DAYS = 365
AGGREGATE_METRIC_KEYS = [
    "advance_pct",
    "ma_13_above_pct",
    "ma_28_above_pct",
    "ma_46_above_pct",
    "ma_8_shift_5_above_pct",
    "roc_17_vs_5_gt_pct",
    "roc_27_vs_4_gt_pct",
]


# %%
IndicatorSeriesBuilder = Callable[
    [list[dict[str, Any]], dict[str, Any]],
    tuple[dict[str, list[SeriesPoint]], dict[str, Any]],
]


def _list_indicator_instances(config: SecurityScanConfig) -> pd.DataFrame:
    rows = []
    for instance in config.indicator_instances:
        rows.append(
            {
                "id": instance.id,
                "instance_id": instance.instance_id or "(auto)",
                "settings": instance.settings,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["id", "instance_id", "settings"])
    return pd.DataFrame(rows)


def _resolve_indicator_instance(
    config: SecurityScanConfig, indicator_key: str
) -> IndicatorInstanceConfig:
    matches = []
    for instance in config.indicator_instances:
        if instance.instance_id and instance.instance_id == indicator_key:
            matches.append(instance)
        if instance.id == indicator_key:
            matches.append(instance)
    if not matches:
        available = ", ".join(
            sorted(
                {
                    instance.instance_id or instance.id
                    for instance in config.indicator_instances
                }
            )
        )
        raise ValueError(
            f"Indicator '{indicator_key}' not found. Available: {available or 'none'}."
        )
    return matches[0]


def _prices_to_frame(prices: Iterable[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(prices)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).set_index("date").sort_index()
    numeric_cols = [col for col in ["open", "high", "low", "close"] if col in frame]
    frame[numeric_cols] = frame[numeric_cols].apply(pd.to_numeric, errors="coerce")
    return frame


def _series_map_to_frame(series_map: dict[str, list[SeriesPoint]]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for label, points in series_map.items():
        if not points:
            continue
        frames.append(
            pd.DataFrame(
                {
                    "date": pd.to_datetime([point.date for point in points]),
                    label: [point.value for point in points],
                }
            ).set_index("date")
        )
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, axis=1).sort_index().dropna(how="all")
    return combined


def _extract_criteria_levels(
    criteria: Iterable[dict[str, Any]] | None,
    series_names: Iterable[str] | None,
) -> list[float]:
    if not criteria:
        return []

    series_name_set: set[str] | None = None
    if series_names is not None:
        series_name_set = {name for name in series_names if isinstance(name, str)}

    levels: list[float] = []
    for rule in criteria:
        if not isinstance(rule, dict):
            continue
        rule_type = rule.get("type")
        if not isinstance(rule_type, str):
            continue
        rule_type = rule_type.strip()
        if rule_type not in {"crossover", "threshold"}:
            continue

        rule_series = rule.get("series")
        if isinstance(rule_series, str) and rule_series.strip():
            if series_name_set is not None and rule_series.strip() not in series_name_set:
                continue

        if rule_type == "crossover":
            level_raw = rule.get("level", 0)
        else:
            level_raw = rule.get("level")
        if level_raw is None:
            continue
        try:
            level = float(level_raw)
        except (TypeError, ValueError):
            continue
        levels.append(level)

    unique_levels: list[float] = []
    seen_levels: set[float] = set()
    for level in levels:
        if level in seen_levels:
            continue
        seen_levels.add(level)
        unique_levels.append(level)
    return unique_levels


def _build_roc_series(
    prices: list[dict[str, Any]], settings: dict[str, Any]
) -> tuple[dict[str, list[SeriesPoint]], dict[str, Any]]:
    lookback_raw = settings.get("roc_lookback", 12)
    try:
        lookback = int(lookback_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("roc_lookback must be an integer") from exc
    if lookback <= 0:
        raise ValueError("roc_lookback must be > 0")

    close_series = roc_indicator._extract_close_series(prices)
    indicator_points = roc_indicator._compute_roc_series(close_series, lookback)
    return {"roc": indicator_points}, {"primary_series": "roc"}


def _build_roc_aggregate_series(
    prices: list[dict[str, Any]], settings: dict[str, Any]
) -> tuple[dict[str, list[SeriesPoint]], dict[str, Any]]:
    roc_lookbacks = roc_aggregate_indicator._to_positive_int_list(
        settings.get("roc_lookbacks"),
        "roc_lookbacks",
        [5, 10, 20],
    )
    change_lookbacks = roc_aggregate_indicator._to_positive_int_list(
        settings.get("roc_change_lookbacks"),
        "roc_change_lookbacks",
        [1, 3, 5],
    )
    ma_short = roc_aggregate_indicator._to_positive_int(
        settings.get("ma_short", 5), "ma_short"
    )
    ma_long = roc_aggregate_indicator._to_positive_int(
        settings.get("ma_long", 20), "ma_long"
    )

    close_series = roc_aggregate_indicator._extract_close_series(prices)
    if not close_series:
        return {"roc_aggregate": []}, {"primary_series": "roc_aggregate"}

    required_points = max(roc_lookbacks) + max(change_lookbacks) + 1
    if len(close_series) < required_points:
        return {"roc_aggregate": []}, {"primary_series": "roc_aggregate"}

    roc_by_index = {
        lookback: roc_aggregate_indicator._compute_roc_by_index(close_series, lookback)
        for lookback in roc_lookbacks
    }
    indicator_series = roc_aggregate_indicator._compute_indicator_series(
        close_series, roc_by_index, roc_lookbacks, change_lookbacks
    )
    sma_short_series = roc_aggregate_indicator._compute_sma_series(
        indicator_series, ma_short
    )
    sma_long_series = roc_aggregate_indicator._compute_sma_series(
        indicator_series, ma_long
    )
    series_map = {"roc_aggregate": indicator_series}
    if sma_short_series:
        series_map[f"SMA_{ma_short}"] = sma_short_series
    if sma_long_series:
        series_map[f"SMA_{ma_long}"] = sma_long_series
    return series_map, {
        "primary_series": "roc_aggregate",
        "ma_short": ma_short,
        "ma_long": ma_long,
    }


INDICATOR_SERIES_BUILDERS: dict[str, IndicatorSeriesBuilder] = {
    "roc": _build_roc_series,
    "roc_aggregate": _build_roc_aggregate_series,
}


def _compute_indicator_series(
    indicator_id: str,
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    builder = INDICATOR_SERIES_BUILDERS.get(indicator_id)
    if builder is None:
        raise ValueError(
            f"Indicator '{indicator_id}' is not wired for plotting yet."
        )
    series_map, metadata = builder(prices, settings)
    frame = _series_map_to_frame(series_map)
    return frame, metadata


def _evaluate_indicator_signals(
    indicator_id: str,
    prices: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[IndicatorSignal]:
    registry = load_indicator_registry()
    evaluator = registry.get(indicator_id)
    if evaluator is None:
        raise ValueError(f"Indicator '{indicator_id}' is not registered.")
    return evaluator(prices, settings)


def _fetch_prices(
    ticker: str,
    lookback_days: int,
    end_date: date,
    interval: str,
) -> list[dict[str, Any]]:
    resolved_end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
    resolved_start = resolved_end - timedelta(days=lookback_days)
    fetcher = MarketDataFetcher(market_data_service=MarketDataService())
    raw = fetcher.fetch_historical_prices(
        ticker=ticker,
        start_date=resolved_start,
        end_date=resolved_end + timedelta(days=1),
        interval=interval,
    )
    return normalize_prices(raw)


def _plot_price_and_indicator(
    ticker: str,
    price_frame: pd.DataFrame,
    indicator_frame: pd.DataFrame,
    indicator_meta: dict[str, Any],
    signals: list[IndicatorSignal],
    indicator_criteria: Iterable[dict[str, Any]] | None,
) -> None:
    if price_frame.empty:
        raise ValueError("Price frame is empty; nothing to plot.")
    if indicator_frame.empty:
        raise ValueError("Indicator frame is empty; adjust lookback or settings.")

    primary_series = indicator_meta.get("primary_series") or indicator_frame.columns[0]

    fig, (ax_price, ax_indicator) = plt.subplots(
        2,
        1,
        sharex=True,
        figsize=(14, 8),
        gridspec_kw={"height_ratios": [2, 1]},
    )

    ax_price.plot(price_frame.index, price_frame["close"], label=f"{ticker} Close")
    ax_price.set_ylabel("Price")
    ax_price.set_title(f"{ticker} Price vs. {primary_series}")
    ax_price.legend(loc="upper left")

    for column in indicator_frame.columns:
        ax_indicator.plot(
            indicator_frame.index,
            indicator_frame[column],
            label=column,
            linewidth=1.6 if column == primary_series else 1.0,
        )

    criteria_levels = _extract_criteria_levels(
        indicator_criteria, indicator_frame.columns
    )
    if criteria_levels:
        for level in criteria_levels:
            ax_indicator.axhline(
                level,
                color="goldenrod",
                linestyle="--",
                linewidth=1.4,
                alpha=0.7,
                label=f"criteria level {level:g}",
                zorder=1,
            )

    ax_indicator.set_ylabel(primary_series)
    ax_indicator.legend(loc="upper left")

    if signals:
        signal_styles = {
            "cross_above_both": {"marker": "^", "color": "green"},
            "cross_below_both": {"marker": "v", "color": "red"},
            "crossover_up": {"marker": "^", "color": "green"},
            "crossover_down": {"marker": "v", "color": "red"},
        }
        used_labels: set[str] = set()
        signal_dates: set[pd.Timestamp] = set()
        for signal in signals:
            dt = pd.to_datetime(signal.signal_date)
            if dt not in indicator_frame.index:
                continue
            signal_dates.add(dt)
            y_value = indicator_frame.loc[dt, primary_series]
            style = signal_styles.get(signal.signal_type, {"marker": "o", "color": "blue"})
            label = signal.signal_type if signal.signal_type not in used_labels else None
            ax_indicator.scatter(
                dt,
                y_value,
                label=label,
                marker=style["marker"],
                color=style["color"],
                zorder=5,
            )
            if label:
                used_labels.add(signal.signal_type)

        if signal_dates:
            for dt in sorted(signal_dates):
                for axis in (ax_price, ax_indicator):
                    axis.axvline(
                        dt,
                        color="gold",
                        linewidth=1.6,
                        alpha=0.55,
                        zorder=2,
                    )
    ax_indicator.set_xlabel("Date")
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show()


def _load_aggregate_frame(
    set_hash: str,
    metric_keys: Iterable[str],
    start_date: date | None,
    end_date: date | None,
    interval: str,
) -> pd.DataFrame:
    session = ScanSessionLocal()
    try:
        query = (
            session.query(SecurityAggregateValue)
            .filter(SecurityAggregateValue.set_hash == set_hash)
            .filter(SecurityAggregateValue.interval == interval)
        )
        if metric_keys:
            query = query.filter(SecurityAggregateValue.metric_key.in_(list(metric_keys)))
        if start_date:
            query = query.filter(SecurityAggregateValue.as_of_date >= start_date.isoformat())
        if end_date:
            query = query.filter(SecurityAggregateValue.as_of_date <= end_date.isoformat())
        rows = query.all()
    finally:
        session.close()

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(
        [
            {
                "date": row.as_of_date,
                "metric_key": row.metric_key,
                "value": row.value,
            }
            for row in rows
        ]
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])
    if frame.empty:
        return pd.DataFrame()
    pivoted = frame.pivot(index="date", columns="metric_key", values="value")
    return pivoted.sort_index()


def _plot_aggregate_series(
    frame: pd.DataFrame,
    title: str,
) -> None:
    if frame.empty:
        print("Aggregate series is empty; run a scan to populate security_scan.db.")
        return
    fig, ax = plt.subplots(figsize=(14, 5))
    for column in frame.columns:
        ax.plot(frame.index, frame[column], label=column)
    ax.set_title(title)
    ax.set_ylabel("Value")
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show()


# %%
scan_config = load_security_scan_config(CONFIG_DIR)
if SHOW_INSTANCE_TABLE:
    instances_df = _list_indicator_instances(scan_config)
    if instances_df.empty:
        print("No indicators configured in scan_settings.toml.")
    else:
        print("Configured indicator instances:")
        print(instances_df.to_string(index=False))

indicator_instance = _resolve_indicator_instance(scan_config, INDICATOR_KEY)
merged_settings = {**indicator_instance.settings, **INDICATOR_OVERRIDES}
print("\nSelected indicator instance:")
print(f"  id: {indicator_instance.id}")
print(f"  instance_id: {indicator_instance.instance_id}")
print(f"  settings: {merged_settings}")

prices = _fetch_prices(TICKER, LOOKBACK_DAYS, END_DATE, INTERVAL)
price_frame = _prices_to_frame(prices)
print(f"\nFetched {len(price_frame)} price bars for {TICKER}.")

indicator_frame, indicator_meta = _compute_indicator_series(
    indicator_instance.id, prices, merged_settings
)
if indicator_frame.empty:
    print(
        "Indicator series is empty. Increase lookback, adjust settings, or pick a "
        "different ticker."
    )
signals = _evaluate_indicator_signals(
    indicator_instance.id, prices, merged_settings
)
print(f"Indicator produced {len(signals)} signals in the selected window.")


# %%
if not price_frame.empty and not indicator_frame.empty:
    _plot_price_and_indicator(
        ticker=TICKER,
        price_frame=price_frame,
        indicator_frame=indicator_frame,
        indicator_meta=indicator_meta,
        signals=signals,
        indicator_criteria=merged_settings.get("criteria"),
    )
else:
    print("Skipping plot due to missing data.")


# %%
if PLOT_AGGREGATES:
    aggregate_tickers = AGGREGATE_TICKERS or scan_config.tickers
    if not aggregate_tickers:
        print("No tickers available for aggregate plotting.")
    else:
        set_hash, canonical = compute_security_set_hash(aggregate_tickers)
        aggregate_end = END_DATE
        aggregate_start = aggregate_end - timedelta(days=AGGREGATE_LOOKBACK_DAYS)
        aggregate_frame = _load_aggregate_frame(
            set_hash=set_hash,
            metric_keys=AGGREGATE_METRIC_KEYS,
            start_date=aggregate_start,
            end_date=aggregate_end,
            interval=INTERVAL,
        )
        title = f"Aggregate Metrics ({len(canonical)} tickers)"
        _plot_aggregate_series(aggregate_frame, title)


# %%
if not indicator_frame.empty:
    print("Indicator series preview:")
    print(indicator_frame.tail().to_string())

if signals:
    signals_frame = pd.DataFrame([asdict(signal) for signal in signals])
    print("\nSignals preview:")
    print(signals_frame.tail().to_string(index=False))
