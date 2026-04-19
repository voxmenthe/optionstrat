# Security Scan

Local CLI for scanning a configurable ticker universe with the backend
`MarketDataService`. A run fetches market data, evaluates the configured
indicator instances, computes breadth and dispersion aggregates, stores
aggregate history in `src/backend/security_scan.db`, and writes report artifacts.

Run commands from the repository root so `uv`, relative config paths, the scan
database, and `scan-reports/` resolve consistently.

## Quick Run

Use the installed project script:

```bash
uv run security-scan
```

Equivalent module invocation:

```bash
uv run python -m app.security_scan.cli
```

The default run loads:

- `src/backend/app/security_scan/config/securities.toml`
- `src/backend/app/security_scan/config/scan_settings.toml`

If no dates are supplied, the CLI ends on today and starts
`scan_defaults.lookback_days` before that. The current default config uses
`lookback_days = 365`.

## Common Runs

Run a specific date range:

```bash
uv run security-scan \
  --start-date 2026-01-01 \
  --end-date 2026-03-31
```

Write artifacts to a specific directory:

```bash
uv run security-scan \
  --output ./scan-reports
```

Use a custom config directory:

```bash
uv run security-scan \
  --config-dir ./tmp/security-scan-config
```

The custom directory must contain both files:

- `securities.toml`
- `scan_settings.toml`

Use another market data provider for one run:

```bash
uv run security-scan \
  --provider yfinance
```

Backfill aggregate history for charting:

```bash
uv run security-scan \
  --start-date 2026-01-01 \
  --end-date 2026-03-31 \
  --backfill-aggregates
```

Run without HTML artifacts when you only need JSON and Markdown:

```bash
uv run security-scan \
  --no-html \
  --no-dispersion-html
```

Enable intraday nowcast mode:

```bash
uv run security-scan \
  --intraday \
  --intraday-interval 5m \
  --intraday-min-bars 30
```

Without `--intraday`, scans use daily bars.

## CLI Flags

Run `uv run security-scan --help` for the authoritative option list.

| Flag | Purpose |
| --- | --- |
| `--config-dir PATH` | Load `securities.toml` and `scan_settings.toml` from another directory. Relative paths resolve from the current working directory. |
| `--start-date YYYY-MM-DD` | Override the scan start date. |
| `--end-date YYYY-MM-DD` | Override the scan end date. Defaults to today when omitted. |
| `--output PATH` | Write reports to a directory or use a file prefix. |
| `--provider NAME` | Override the market data provider for this run, for example `yfinance` or `polygon`. |
| `--use-cache` | Enable provider caching through the backend cache/database path. |
| `--no-cache` | Disable provider caching. This is the default. |
| `--intraday` | Build a synthetic current-session bar from intraday data. |
| `--intraday-interval INTERVAL` | Override the intraday interval, for example `1m`, `5m`, `15m`, or `60m`. |
| `--intraday-min-bars N` | Require at least `N` intraday bars before using the synthetic current-session bar. |
| `--no-html` | Skip the main HTML report. JSON and Markdown are still written. |
| `--no-dispersion-html` | Skip dispersion Markdown and HTML reports. |
| `--backfill-aggregates` | Compute and persist daily aggregate records across the backfill date range. |
| `--backfill-start-date YYYY-MM-DD` | Override the aggregate backfill start date. Defaults to `--start-date`. |
| `--backfill-end-date YYYY-MM-DD` | Override the aggregate backfill end date. Defaults to `--end-date`. |

## Output

By default, artifacts are written to `scan-reports/` at the repo root:

- `security_scan_<run_id>.json`
- `security_scan_<run_id>.md`
- `security_scan_<run_id>.html` when report HTML is enabled
- `security_scan_<run_id>_dispersion.md` when dispersion reporting is enabled
- `security_scan_<run_id>_dispersion.html` when dispersion reporting is enabled

The CLI also prints the JSON payload to stdout, followed by the artifact paths.

If `--output` points to an existing directory, the CLI writes the standard
filenames into that directory. If `--output` points to a file path, that path is
used for JSON and the same stem is reused for `.md`, `.html`, and dispersion
artifacts.

Top-level JSON fields include:

- `run_metadata`
- `market_stats`
- `ticker_summaries`
- `signals`
- `aggregates`
- `aggregate_universes`
- `issues`
- `storage_usage`

## Changing Settings

The default config lives in `src/backend/app/security_scan/config/`. For local
experiments, prefer copying that directory and passing `--config-dir` instead of
editing the checked-in defaults:

```bash
mkdir -p ./tmp/security-scan-config
cp src/backend/app/security_scan/config/*.toml ./tmp/security-scan-config/
uv run security-scan --config-dir ./tmp/security-scan-config
```

This keeps experimental ticker lists and thresholds out of the shared defaults.

### `securities.toml`

Use this file for universe membership and date/interval defaults.

| Setting | Meaning |
| --- | --- |
| `[tickers].list` | Main scan universe. Must be a non-empty list of ticker strings. |
| `[nasdaq_tickers].list` | Optional NASDAQ sub-universe used for aggregate/report sections. |
| `[sp100_tickers].list` | Optional S&P 100 sub-universe used for aggregate/report sections. |
| `[scan_defaults].lookback_days` | Default scan window length when `--start-date` is omitted. Must be greater than zero. |
| `[scan_defaults].interval` | Daily scan interval. The runner currently uses `day` in the default config. |
| `[scan_defaults.intraday].interval` | Default intraday bar interval when `--intraday` is used and `--intraday-interval` is omitted. |
| `[scan_defaults.intraday].regular_hours_only` | Whether intraday nowcast data should be limited to regular trading hours. |
| `[scan_defaults.intraday].min_bars_required` | Default minimum intraday bar count when `--intraday-min-bars` is omitted. |

Example:

```toml
[tickers]
list = ["AAPL", "MSFT", "NVDA"]

[nasdaq_tickers]
list = ["AAPL", "MSFT", "NVDA"]

[sp100_tickers]
list = ["AAPL", "MSFT", "NVDA"]

[scan_defaults]
lookback_days = 120
interval = "day"

[scan_defaults.intraday]
interval = "5m"
regular_hours_only = true
min_bars_required = 30
```

### `scan_settings.toml`

Use this file for indicator instances, aggregate metrics, dispersion settings,
and report settings.

Each `[[indicators.instances]]` block enables one indicator configuration:

```toml
[[indicators.instances]]
id = "roc_aggregate"
instance_id = "roc_aggregate_1"
roc_lookbacks = [5, 10, 20]
roc_change_lookbacks = [1, 3, 5]
ma_short = 5
ma_long = 20
```

Rules:

- `id` selects the indicator implementation. Current config uses
  `roc_aggregate`, `qrs_consist_excess`, and
  `scl_ma2_qrs_ma1_breakout`.
- `instance_id` is optional but useful when the same indicator is configured
  more than once.
- Any other keys in the block are passed to that indicator as settings.
- `criteria` may be a single TOML table or a list of tables; the loader
  normalizes it to a list.

Aggregate settings:

```toml
[aggregates]
advance_decline_lookbacks = [1, 5, 10]
```

`advance_decline_lookbacks` must be a non-empty list of positive integers. The
loader removes duplicate lookbacks while preserving order.

Dispersion settings:

```toml
[aggregates.dispersion]
enabled = true
return_horizons = [1]
windows = [5, 21, 63]
window_weights = { w5 = 0.45, w21 = 0.35, w63 = 0.20 }
method_weights = { corr = 0.40, xs = 0.25, pca = 0.25, sign = 0.10 }
min_tickers = 20
min_observations = 15
min_pair_coverage = 0.60
use_robust_xs_dispersion = true
xs_lockstep_decay = 1.0
volatility_gate_enabled = false
volatility_gate_lookback = 20
volatility_gate_percentile = 0.60
segment_up_down = false
segment_threshold_sigma = 0.0
segment_min_events = 8
```

Important validation rules:

- `return_horizons`, `windows`, and integer thresholds must be positive.
- `window_weights` must include a weight for every configured window. Keys can
  be written as `w5` or `"5"`.
- `window_weights` must sum to `1.0`.
- `method_weights` must include `corr`, `xs`, `pca`, and `sign`, and must sum
  to `1.0`.
- Unit values such as `min_pair_coverage` and
  `volatility_gate_percentile` must be between `0.0` and `1.0`.

Report settings:

```toml
[report]
html = true
aggregate_lookback_days = 90
chart_universes = ["all", "nasdaq", "sp100"]
net_advances_ma_days = 26
net_advances_secondary_ma_days = 8
advance_pct_avg_smoothing_days = 4
roc_breadth_avg_smoothing_days = 4
dispersion_html = true
dispersion_lookback_days = 252
dispersion_show_components = true
dispersion_show_diagnostics = true
dispersion_smoothing_days = 3
```

Useful report fields:

- `html`: enables the main HTML report unless `--no-html` is passed.
- `aggregate_lookback_days`: controls how many days of stored aggregate history
  charts include. This is independent of the scan date range.
- `plot_lookbacks`: optionally restricts plotted advance/decline lookbacks.
- `chart_universes`: can include `all`, `nasdaq`, and `sp100`.
- `max_points`: optionally caps chart point count.
- `dispersion_html`: enables dispersion Markdown/HTML reports unless
  `--no-dispersion-html` is passed.
- `dispersion_lookback_days`: controls how many days of stored dispersion
  history charts include.
- `dispersion_show_components`, `dispersion_show_diagnostics`, and
  `dispersion_smoothing_days`: control dispersion chart detail.

## Providers and Cache

If `--provider` is omitted, `MarketDataService` uses its configured default,
which can be influenced by `MARKET_DATA_PROVIDER`. The default practical path is
`yfinance`.

Caching is disabled by default for scan runs. Pass `--use-cache` only when the
backend cache/database dependencies are available and you want provider caching
for the run.

Do not put provider secrets in these TOML files. Keep provider credentials in
the environment used by the backend.

## Troubleshooting

- `Error loading config: Config file not found`: the `--config-dir` directory
  must contain both `securities.toml` and `scan_settings.toml`.
- `start-date must be on or before end-date`: check CLI date order and use
  `YYYY-MM-DD`.
- `intraday-min-bars must be > 0`: pass a positive integer or update
  `scan_defaults.intraday.min_bars_required`.
- Missing or sparse charts usually mean there is not enough aggregate history in
  `src/backend/security_scan.db`; run with `--backfill-aggregates` over the
  desired chart window.
- Provider errors are surfaced in `issues` when the scan can continue; hard
  provider/config failures are printed to stderr and the CLI exits non-zero.
