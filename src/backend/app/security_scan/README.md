# Security Scan Utilities

CLI utilities for scanning a configurable ticker list using the existing
`MarketDataService`. This module is intended for local, on-demand runs and
produces a JSON summary per scan.

Key points:
- Scan metrics/aggregates are stored in `security_scan.db` under `src/backend/`.
- Run the CLI from the repo root; DB and output paths are anchored to `src/backend/`.

## Quickstart

From the repo root:

```bash
uv run python -m app.security_scan.cli
```

Or, using the installed script:

```bash
uv run security-scan
```

## Usage

```bash
uv run python -m app.security_scan.cli \
  --config-dir /path/to/config \
  --start-date 2025-10-01 \
  --end-date 2025-12-31 \
  --provider yfinance \
  --use-cache \
  --output /path/to/scan-reports
```

Backfill aggregate history (so charts have more than the latest run):

```bash
uv run python -m app.security_scan.cli \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --backfill-aggregates
```

### Options
- `--config-dir`: Override config directory (defaults to `app/security_scan/config`).
- `--start-date`, `--end-date`: Optional date overrides (YYYY-MM-DD).
- `--provider`: Override market data provider (`yfinance`, `polygon`).
- `--use-cache`: Enable provider caching (Redis/DB).
- `--no-cache`: Disable provider caching (default).
- `--output`: Output file path or directory for JSON results.
- `--intraday`: Enable intraday nowcast mode (disabled by default).
- `--intraday-interval`: Override intraday interval (`1m`, `5m`, `15m`, `60m`).
- `--intraday-min-bars`: Minimum intraday bars required to build the synthetic bar.
- `--no-html`: Disable HTML report output.
- `--backfill-aggregates`: Compute and store daily aggregates for the date range.
- `--backfill-start-date`, `--backfill-end-date`: Override the backfill date range
  (defaults to `--start-date`/`--end-date`).

## Configuration

Default config lives under `src/backend/app/security_scan/config/`:

`securities.toml`
```toml
[tickers]
list = ["AAPL", "MSFT", "AMZN", "TSLA", "GOOG"]

[scan_defaults]
lookback_days = 90
interval = "day"

[scan_defaults.intraday]
interval = "1m"
regular_hours_only = true
min_bars_required = 30
```

`scan_settings.toml`
```toml
[indicators]
instances = [
  { id = "roc", roc_lookback = 12, criteria = [{ type = "crossover", series = "roc", level = 0, direction = "both" }] },
  { id = "roc_aggregate", roc_lookbacks = [5, 10, 20], roc_change_lookbacks = [1, 3, 5], ma_short = 5, ma_long = 20 }
]

[aggregates]
advance_decline_lookbacks = [1, 5, 10]

[report]
html = true
# aggregate_lookback_days = 120
# plot_lookbacks = [1, 5, 10]
# max_points = 120
# net_advances_ma_days = 18
# net_advances_secondary_ma_days = 8
# advance_pct_avg_smoothing_days = 3
# roc_breadth_avg_smoothing_days = 3
```

If `--start-date`/`--end-date` are not supplied, the CLI uses `lookback_days`
from `securities.toml`.

For charts, set `report.aggregate_lookback_days` to control how many days of
stored aggregates are included in the HTML report (independent of the scan
window).

Intraday nowcast mode is only activated when `--intraday` is passed on the CLI.
Without that flag, scans use the latest available daily bars only.

## Output

By default, output is written to `scan-reports/` at the repo root with filenames
like `security_scan_<run_id>.json`, `security_scan_<run_id>.md`, and
`security_scan_<run_id>.html`, and JSON is also printed to stdout. Use `--output`
to specify a file path or a directory.

Top-level JSON fields include:
- `run_metadata`
- `market_stats` (SPY/QQQ/IWM 1D/5D % change snapshot)
- `ticker_summaries`
- `signals`
- `aggregates`
- `issues`
- `storage_usage` (bytes for `scan_db`, `options_db`, `task_logs`, `total`)

## Providers and Cache

If `--provider` is not provided, the service will use the
`MARKET_DATA_PROVIDER` environment variable (default is `yfinance`). Cache is
disabled by default for scans to avoid Redis warnings; pass `--use-cache` if
you want Redis/DB caching enabled.
