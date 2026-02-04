from __future__ import annotations

from typing import Any


MA_BREADTH_DEFINITIONS = [
    ("ma_13", "sma:13"),
    ("ma_28", "sma:28"),
    ("ma_46", "sma:46"),
    ("ma_8_shift_5", "sma:8:shift=5"),
]

ROC_BREADTH_DEFINITIONS = [
    ("roc_17_vs_5", "roc:17", "roc:17:shift=5"),
    ("roc_27_vs_4", "roc:27", "roc:27:shift=4"),
]


def compute_breadth(
    ticker_summaries: list[dict[str, Any]],
    advance_decline_lookbacks: list[int] | None = None,
) -> dict[str, Any]:
    if not advance_decline_lookbacks:
        advance_decline_lookbacks = [1]
    else:
        seen: set[int] = set()
        normalized: list[int] = []
        for value in advance_decline_lookbacks:
            lookback = int(value)
            if lookback in seen:
                continue
            seen.add(lookback)
            normalized.append(lookback)
        advance_decline_lookbacks = normalized
    extra_lookbacks = [value for value in advance_decline_lookbacks if value != 1]

    advances = 0
    declines = 0
    unchanged = 0
    missing = 0

    ad_counts = {
        lookback: {"advances": 0, "declines": 0, "unchanged": 0, "missing": 0}
        for lookback in extra_lookbacks
    }

    ma_counts = {
        prefix: {"above": 0, "below": 0, "equal": 0, "missing": 0}
        for prefix, _ in MA_BREADTH_DEFINITIONS
    }
    roc_counts = {
        prefix: {"gt": 0, "lt": 0, "eq": 0, "missing": 0}
        for prefix, _, _ in ROC_BREADTH_DEFINITIONS
    }
    scl_high = 0
    scl_low = 0
    scl_missing = 0

    for summary in ticker_summaries:
        last_close = summary.get("last_close")
        prior_close = summary.get("prior_close")
        if last_close is None or prior_close is None:
            missing += 1
        else:
            if last_close > prior_close:
                advances += 1
            elif last_close < prior_close:
                declines += 1
            else:
                unchanged += 1

        close_by_offset = summary.get("close_by_offset") or {}
        for lookback in extra_lookbacks:
            prior_value = close_by_offset.get(lookback)
            if last_close is None or prior_value is None:
                ad_counts[lookback]["missing"] += 1
            else:
                if last_close > prior_value:
                    ad_counts[lookback]["advances"] += 1
                elif last_close < prior_value:
                    ad_counts[lookback]["declines"] += 1
                else:
                    ad_counts[lookback]["unchanged"] += 1

        metric_values = summary.get("metric_values") or {}
        for prefix, metric_key in MA_BREADTH_DEFINITIONS:
            sma_value = metric_values.get(metric_key)
            if last_close is None or sma_value is None:
                ma_counts[prefix]["missing"] += 1
                continue
            if last_close > sma_value:
                ma_counts[prefix]["above"] += 1
            elif last_close < sma_value:
                ma_counts[prefix]["below"] += 1
            else:
                ma_counts[prefix]["equal"] += 1

        for prefix, current_key, prior_key in ROC_BREADTH_DEFINITIONS:
            current_value = metric_values.get(current_key)
            prior_value = metric_values.get(prior_key)
            if current_value is None or prior_value is None:
                roc_counts[prefix]["missing"] += 1
                continue
            if current_value > prior_value:
                roc_counts[prefix]["gt"] += 1
            elif current_value < prior_value:
                roc_counts[prefix]["lt"] += 1
            else:
                roc_counts[prefix]["eq"] += 1

        scl_high_flag = summary.get("scl_5bar_high")
        scl_low_flag = summary.get("scl_5bar_low")
        if scl_high_flag is None and scl_low_flag is None:
            scl_missing += 1
        else:
            if scl_high_flag:
                scl_high += 1
            if scl_low_flag:
                scl_low += 1

    valid = advances + declines + unchanged
    ratio = None if declines == 0 else round(advances / declines, 4)
    advance_pct = None if valid == 0 else round(advances / valid, 4)

    aggregates: dict[str, Any] = {
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "valid_ticker_count": valid,
        "missing_ticker_count": missing,
        "advance_decline_ratio": ratio,
        "net_advances": advances - declines,
        "advance_pct": advance_pct,
        "scl_5bar_high_count": scl_high,
        "scl_5bar_low_count": scl_low,
        "scl_5bar_net": scl_high - scl_low,
        "scl_5bar_valid_count": len(ticker_summaries) - scl_missing,
        "scl_5bar_missing_count": scl_missing,
    }

    for lookback, counts in ad_counts.items():
        ad_advances = counts["advances"]
        ad_declines = counts["declines"]
        ad_unchanged = counts["unchanged"]
        ad_missing = counts["missing"]
        ad_valid = ad_advances + ad_declines + ad_unchanged
        ad_ratio = None if ad_declines == 0 else round(ad_advances / ad_declines, 4)
        ad_advance_pct = None if ad_valid == 0 else round(ad_advances / ad_valid, 4)
        prefix = f"ad_{lookback}"
        aggregates[f"{prefix}_advances"] = ad_advances
        aggregates[f"{prefix}_declines"] = ad_declines
        aggregates[f"{prefix}_unchanged"] = ad_unchanged
        aggregates[f"{prefix}_valid_count"] = ad_valid
        aggregates[f"{prefix}_missing_count"] = ad_missing
        aggregates[f"{prefix}_advance_decline_ratio"] = ad_ratio
        aggregates[f"{prefix}_net_advances"] = ad_advances - ad_declines
        aggregates[f"{prefix}_advance_pct"] = ad_advance_pct

    for prefix, counts in ma_counts.items():
        above = counts["above"]
        below = counts["below"]
        equal = counts["equal"]
        missing_count = counts["missing"]
        valid_count = above + below + equal
        aggregates[f"{prefix}_above_count"] = above
        aggregates[f"{prefix}_below_count"] = below
        aggregates[f"{prefix}_equal_count"] = equal
        aggregates[f"{prefix}_missing_count"] = missing_count
        aggregates[f"{prefix}_valid_count"] = valid_count
        aggregates[f"{prefix}_above_pct"] = (
            None if valid_count == 0 else round(above / valid_count, 4)
        )
        aggregates[f"{prefix}_below_pct"] = (
            None if valid_count == 0 else round(below / valid_count, 4)
        )
        aggregates[f"{prefix}_equal_pct"] = (
            None if valid_count == 0 else round(equal / valid_count, 4)
        )

    for prefix, counts in roc_counts.items():
        greater = counts["gt"]
        less = counts["lt"]
        equal = counts["eq"]
        missing_count = counts["missing"]
        valid_count = greater + less + equal
        aggregates[f"{prefix}_gt_count"] = greater
        aggregates[f"{prefix}_lt_count"] = less
        aggregates[f"{prefix}_eq_count"] = equal
        aggregates[f"{prefix}_missing_count"] = missing_count
        aggregates[f"{prefix}_valid_count"] = valid_count
        aggregates[f"{prefix}_gt_pct"] = (
            None if valid_count == 0 else round(greater / valid_count, 4)
        )
        aggregates[f"{prefix}_lt_pct"] = (
            None if valid_count == 0 else round(less / valid_count, 4)
        )
        aggregates[f"{prefix}_eq_pct"] = (
            None if valid_count == 0 else round(equal / valid_count, 4)
        )

    return aggregates
