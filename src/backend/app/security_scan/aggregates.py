from __future__ import annotations

from typing import Any


def compute_breadth(ticker_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    advances = 0
    declines = 0
    unchanged = 0
    missing = 0

    for summary in ticker_summaries:
        last_close = summary.get("last_close")
        prior_close = summary.get("prior_close")
        if last_close is None or prior_close is None:
            missing += 1
            continue
        if last_close > prior_close:
            advances += 1
        elif last_close < prior_close:
            declines += 1
        else:
            unchanged += 1

    valid = advances + declines + unchanged
    ratio = None if declines == 0 else round(advances / declines, 4)
    advance_pct = None if valid == 0 else round(advances / valid, 4)

    return {
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "valid_ticker_count": valid,
        "missing_ticker_count": missing,
        "advance_decline_ratio": ratio,
        "net_advances": advances - declines,
        "advance_pct": advance_pct,
    }
