from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.security_scan import cli


def test_refresh_payload_aggregate_histories_updates_universe_history(monkeypatch) -> None:
    payload = {
        "run_metadata": {
            "end_date": "2026-02-11",
            "interval": "day",
            "aggregate_set_hashes": {
                "all": "set-all",
                "nasdaq": "set-nasdaq",
            },
        },
        "aggregate_universes": {
            "all": {
                "label": "All Tickers",
                "aggregates_history": [],
            },
            "nasdaq": {
                "label": "NASDAQ Tickers",
                "aggregates_history": [],
            },
            "sp100": {
                "label": "S&P 100 Tickers",
                "aggregates_history": [],
            },
        },
    }

    calls: list[dict[str, str]] = []
    rows_by_set_hash = {
        "set-all": [
            SimpleNamespace(
                as_of_date="2026-02-10",
                metric_key="advances",
                value=100.0,
            ),
            SimpleNamespace(
                as_of_date="2026-02-11",
                metric_key="advances",
                value=102.0,
            ),
        ],
        "set-nasdaq": [
            SimpleNamespace(
                as_of_date="2026-02-10",
                metric_key="advances",
                value=60.0,
            )
        ],
    }

    def fake_fetch_security_aggregate_series(**kwargs):
        calls.append(
            {
                "set_hash": kwargs["set_hash"],
                "start_date": kwargs["start_date"],
                "end_date": kwargs["end_date"],
                "interval": kwargs["interval"],
            }
        )
        return rows_by_set_hash[kwargs["set_hash"]]

    monkeypatch.setattr(
        cli,
        "fetch_security_aggregate_series",
        fake_fetch_security_aggregate_series,
    )

    issues = cli._refresh_payload_aggregate_histories(payload)

    assert issues == []
    assert calls == [
        {
            "set_hash": "set-all",
            "start_date": "2026-01-12",
            "end_date": "2026-02-11",
            "interval": "day",
        },
        {
            "set_hash": "set-nasdaq",
            "start_date": "2026-01-12",
            "end_date": "2026-02-11",
            "interval": "day",
        },
    ]
    assert payload["aggregate_universes"]["all"]["aggregates_history"] == [
        {
            "as_of_date": "2026-02-10",
            "metric_key": "advances",
            "value": 100.0,
        },
        {
            "as_of_date": "2026-02-11",
            "metric_key": "advances",
            "value": 102.0,
        },
    ]
    assert payload["aggregates_history"] == payload["aggregate_universes"]["all"][
        "aggregates_history"
    ]


def test_refresh_payload_aggregate_histories_collects_fetch_errors(monkeypatch) -> None:
    payload = {
        "run_metadata": {
            "end_date": "2026-02-11",
            "interval": "day",
            "aggregate_set_hashes": {"all": "set-all"},
        },
        "aggregate_universes": {
            "all": {
                "label": "All Tickers",
                "aggregates_history": [],
            },
        },
    }

    def failing_fetch_security_aggregate_series(**kwargs):
        raise RuntimeError(f"boom for {kwargs['set_hash']}")

    monkeypatch.setattr(
        cli,
        "fetch_security_aggregate_series",
        failing_fetch_security_aggregate_series,
    )

    issues = cli._refresh_payload_aggregate_histories(payload)

    assert issues == [
        {
            "universe": "all",
            "issue": "aggregate_history_refresh_error",
            "detail": "boom for set-all",
        }
    ]
    assert payload["aggregate_universes"]["all"]["aggregates_history"] == []
    assert payload["aggregates_history"] == []


def test_resolve_output_paths_in_directory() -> None:
    json_path, markdown_path, html_path, dispersion_md_path, dispersion_html_path = (
        cli._resolve_output_paths("/tmp", "20260211-1200")
    )
    assert json_path == Path("/tmp/security_scan_20260211-1200.json")
    assert markdown_path == Path("/tmp/security_scan_20260211-1200.md")
    assert html_path == Path("/tmp/security_scan_20260211-1200.html")
    assert dispersion_md_path == Path("/tmp/security_scan_20260211-1200_dispersion.md")
    assert dispersion_html_path == Path(
        "/tmp/security_scan_20260211-1200_dispersion.html"
    )


def test_resolve_output_paths_with_file_prefix() -> None:
    json_path, markdown_path, html_path, dispersion_md_path, dispersion_html_path = (
        cli._resolve_output_paths("/tmp/custom_scan.json", "unused")
    )
    assert json_path == Path("/tmp/custom_scan.json")
    assert markdown_path == Path("/tmp/custom_scan.md")
    assert html_path == Path("/tmp/custom_scan.html")
    assert dispersion_md_path == Path("/tmp/custom_scan_dispersion.md")
    assert dispersion_html_path == Path("/tmp/custom_scan_dispersion.html")
