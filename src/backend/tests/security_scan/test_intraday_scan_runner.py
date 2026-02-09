from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from app.security_scan.config_loader import SecurityScanConfig
from app.security_scan import scan_runner


class FakeMarketDataService:
    def __init__(
        self,
        *,
        daily_by_ticker: dict[str, list[dict[str, object]]],
        intraday_by_ticker: dict[str, list[dict[str, object]]] | None = None,
    ) -> None:
        self.daily_by_ticker = daily_by_ticker
        self.intraday_by_ticker = intraday_by_ticker or {}
        self.intraday_calls: list[dict[str, object]] = []

    def get_historical_prices(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "day",
    ) -> list[dict[str, object]]:
        return list(self.daily_by_ticker.get(ticker, []))

    def get_intraday_prices(
        self,
        ticker: str,
        start_datetime: datetime,
        end_datetime: datetime,
        interval: str = "1m",
        regular_hours_only: bool = True,
    ) -> list[dict[str, object]]:
        self.intraday_calls.append(
            {
                "ticker": ticker,
                "interval": interval,
                "regular_hours_only": regular_hours_only,
            }
        )
        return list(self.intraday_by_ticker.get(ticker, []))


def _build_config() -> SecurityScanConfig:
    return SecurityScanConfig(
        tickers=["AAPL"],
        lookback_days=30,
        interval="day",
        intraday_interval="1m",
        intraday_regular_hours_only=True,
        intraday_min_bars_required=3,
        indicator_instances=[],
        advance_decline_lookbacks=[1],
        report_html=True,
        report_plot_lookbacks=[],
        report_aggregate_lookback_days=None,
        report_max_points=None,
        report_net_advances_ma_days=18,
        report_net_advances_secondary_ma_days=8,
        report_advance_pct_avg_smoothing_days=3,
        report_roc_breadth_avg_smoothing_days=3,
        config_dir=Path("."),
    )


def _daily_rows(close_today: float) -> list[dict[str, object]]:
    return [
        {
            "date": "2026-02-05",
            "open": 99.0,
            "high": 101.0,
            "low": 98.0,
            "close": 100.0,
            "volume": 1_000,
        },
        {
            "date": "2026-02-06",
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": close_today,
            "volume": 1_100,
        },
    ]


def _intraday_rows(*, closes: list[float]) -> list[dict[str, object]]:
    base = datetime(2026, 2, 6, 14, 30, tzinfo=timezone.utc)
    rows: list[dict[str, object]] = []
    for offset, close_value in enumerate(closes):
        timestamp = base.replace(minute=30 + offset)
        rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "open": close_value - 0.2,
                "high": close_value + 0.3,
                "low": close_value - 0.5,
                "close": close_value,
                "volume": 1_000 + offset,
            }
        )
    return rows


def _patch_storage(monkeypatch):
    metric_upserts: list[dict[str, object]] = []
    aggregate_upserts: list[dict[str, object]] = []

    monkeypatch.setattr(
        scan_runner,
        "fetch_security_metric_values",
        lambda **_: {},
    )
    monkeypatch.setattr(
        scan_runner,
        "upsert_security_metric_values",
        lambda values: metric_upserts.extend(list(values)),
    )
    monkeypatch.setattr(
        scan_runner,
        "upsert_security_aggregate_values",
        lambda values: aggregate_upserts.extend(list(values)),
    )
    monkeypatch.setattr(
        scan_runner,
        "get_or_create_security_set",
        lambda tickers: "test-set-hash",
    )
    monkeypatch.setattr(
        scan_runner,
        "fetch_security_aggregate_series",
        lambda **_: [],
    )
    return metric_upserts, aggregate_upserts


def _build_daily_universe() -> dict[str, list[dict[str, object]]]:
    return {
        "AAPL": _daily_rows(101.0),
        "SPY": _daily_rows(500.0),
        "QQQ": _daily_rows(400.0),
        "IWM": _daily_rows(250.0),
    }


def test_intraday_disabled_by_default(monkeypatch) -> None:
    metric_upserts, aggregate_upserts = _patch_storage(monkeypatch)
    service = FakeMarketDataService(daily_by_ticker=_build_daily_universe())

    payload = scan_runner.run_security_scan(
        _build_config(),
        start_date=date(2026, 2, 5),
        end_date=date(2026, 2, 6),
        market_data_service=service,
    )

    summary = payload["ticker_summaries"][0]
    assert service.intraday_calls == []
    assert summary["last_close"] == 101.0
    assert summary["uses_intraday_synthetic_bar"] is False
    assert payload["run_metadata"]["intraday_requested"] is False
    assert metric_upserts
    assert aggregate_upserts


def test_intraday_enabled_uses_synthetic_and_skips_persistence(monkeypatch) -> None:
    metric_upserts, aggregate_upserts = _patch_storage(monkeypatch)
    intraday_rows = _intraday_rows(closes=[105.0, 107.5, 110.0])
    service = FakeMarketDataService(
        daily_by_ticker=_build_daily_universe(),
        intraday_by_ticker={
            "AAPL": intraday_rows,
            "SPY": intraday_rows,
            "QQQ": intraday_rows,
            "IWM": intraday_rows,
        },
    )

    payload = scan_runner.run_security_scan(
        _build_config(),
        start_date=date(2026, 2, 5),
        end_date=date(2026, 2, 6),
        market_data_service=service,
        intraday_enabled=True,
        intraday_interval="1m",
        intraday_regular_hours_only=True,
        intraday_min_bars_required=3,
    )

    summary = payload["ticker_summaries"][0]
    assert summary["last_close"] == 110.0
    assert summary["uses_intraday_synthetic_bar"] is True
    assert payload["run_metadata"]["intraday_requested"] is True
    assert "AAPL" in payload["run_metadata"]["intraday_synthetic_scan_tickers"]
    assert metric_upserts == []
    assert aggregate_upserts == []


def test_intraday_insufficient_bars_falls_back_to_daily(monkeypatch) -> None:
    metric_upserts, aggregate_upserts = _patch_storage(monkeypatch)
    enough_rows = _intraday_rows(closes=[505.0, 507.0, 510.0])
    service = FakeMarketDataService(
        daily_by_ticker=_build_daily_universe(),
        intraday_by_ticker={
            "AAPL": _intraday_rows(closes=[105.0, 106.0]),
            "SPY": enough_rows,
            "QQQ": enough_rows,
            "IWM": enough_rows,
        },
    )

    payload = scan_runner.run_security_scan(
        _build_config(),
        start_date=date(2026, 2, 5),
        end_date=date(2026, 2, 6),
        market_data_service=service,
        intraday_enabled=True,
        intraday_interval="1m",
        intraday_regular_hours_only=True,
        intraday_min_bars_required=3,
    )

    summary = payload["ticker_summaries"][0]
    assert summary["last_close"] == 101.0
    assert summary["uses_intraday_synthetic_bar"] is False
    assert payload["run_metadata"]["intraday_synthetic_scan_tickers"] == []
    assert metric_upserts
    assert aggregate_upserts
    assert any(
        issue.get("ticker") == "AAPL"
        and issue.get("issue") == "intraday_synthetic_skipped"
        for issue in payload.get("issues", [])
    )
