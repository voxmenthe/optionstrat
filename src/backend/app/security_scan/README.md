# Security Scan Utilities

CLI utilities for scanning a configurable ticker list using the existing
`MarketDataService`. This module is intended for local, on-demand runs and
produces a JSON summary per scan.

## Quickstart

From the repo root:

```bash
cd src/backend
.venv/bin/python -m app.security_scan.cli
```

## Usage

```bash
.venv/bin/python -m app.security_scan.cli \
  --config-dir /path/to/config \
  --start-date 2025-10-01 \
  --end-date 2025-12-31 \
  --provider yfinance \
  --use-cache \
  --output /path/to/task-logs
```

### Options
- `--config-dir`: Override config directory (defaults to `app/security_scan/config`).
- `--start-date`, `--end-date`: Optional date overrides (YYYY-MM-DD).
- `--provider`: Override market data provider (`yfinance`, `polygon`).
- `--use-cache`: Enable provider caching (Redis/DB).
- `--no-cache`: Disable provider caching (default).
- `--output`: Output file path or directory for JSON results.

## Configuration

Default config lives under `src/backend/app/security_scan/config/`:

`securities.toml`
```toml
[tickers]
list = ["AAPL", "MSFT", "AMZN", "TSLA", "GOOG"]

[scan_defaults]
lookback_days = 90
interval = "day"
```

`scan_settings.toml`
```toml
[indicators]
instances = [
  { id = "roc", roc_lookback = 12, criteria = [{ type = "crossover", series = "roc", level = 0, direction = "both" }] }
]
```

If `--start-date`/`--end-date` are not supplied, the CLI uses `lookback_days`
from `securities.toml`.

## Output

By default, output is written to `task-logs/` at the repo root with filenames
like `security_scan_<run_id>.json` and `security_scan_<run_id>.md`, and JSON
is also printed to stdout. Use `--output` to specify a file path or a directory.

## Providers and Cache

If `--provider` is not provided, the service will use the
`MARKET_DATA_PROVIDER` environment variable (default is `yfinance`). Cache is
disabled by default for scans to avoid Redis warnings; pass `--use-cache` if
you want Redis/DB caching enabled.
