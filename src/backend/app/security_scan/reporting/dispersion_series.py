from __future__ import annotations

from typing import Iterable

from app.security_scan.dispersion import DEFAULT_DISPERSION_WINDOWS
from app.security_scan.reporting.aggregate_series import AggregateSeriesDefinition


def _normalize_windows(windows: Iterable[int] | None) -> list[int]:
    source = list(windows) if windows is not None else list(DEFAULT_DISPERSION_WINDOWS)
    normalized: list[int] = []
    seen: set[int] = set()
    for value in source:
        try:
            window = int(value)
        except (TypeError, ValueError):
            continue
        if window <= 0 or window in seen:
            continue
        seen.add(window)
        normalized.append(window)
    if not normalized:
        return list(DEFAULT_DISPERSION_WINDOWS)
    normalized.sort()
    return normalized


def build_dispersion_series_definitions(
    *,
    windows: Iterable[int] | None = None,
    include_components: bool = True,
    include_diagnostics: bool = True,
) -> list[AggregateSeriesDefinition]:
    normalized_windows = _normalize_windows(windows)
    definitions: list[AggregateSeriesDefinition] = [
        {"metric_key": "disp_lockstep_score", "label": "Lockstep Score"},
        {"metric_key": "disp_dispersion_score", "label": "Dispersion Score"},
    ]
    for window in normalized_windows:
        definitions.append(
            {
                "metric_key": f"disp_lockstep_{window}d",
                "label": f"Lockstep {window}D",
            }
        )

    if include_components:
        definitions.extend(
            [
                {"metric_key": "disp_corr_mean_21d", "label": "Corr Mean (21D)"},
                {
                    "metric_key": "disp_pca_pc1_share_21d",
                    "label": "PC1 Share (21D)",
                },
                {
                    "metric_key": "disp_sign_consensus_21d",
                    "label": "Sign Consensus (21D)",
                },
                {"metric_key": "disp_xs_mad_z_21d", "label": "XS MAD Z (21D)"},
            ]
        )

    if include_diagnostics:
        definitions.extend(
            [
                {
                    "metric_key": "disp_valid_ticker_count",
                    "label": "Valid Ticker Count",
                },
                {"metric_key": "disp_valid_pair_count", "label": "Valid Pair Count"},
                {
                    "metric_key": "disp_observation_count",
                    "label": "Observation Count",
                },
            ]
        )
        for window in normalized_windows:
            definitions.append(
                {
                    "metric_key": f"disp_reliability_{window}d",
                    "label": f"Reliability {window}D",
                }
            )

    return definitions

