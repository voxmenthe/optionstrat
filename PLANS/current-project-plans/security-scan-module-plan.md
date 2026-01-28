# Security Scan Utilities Module Plan

## Goal
Create a new, separate Python module under `src/` that provides utility scripts to scan a configurable set of securities using Yahoo Finance data. The module will:
- Load a configurable ticker list from a dedicated config file (initially AAPL/MSFT/AMZN/TSLA/GOOG)
- Fetch historical price data from YFinance via the existing `MarketDataService`
- Compute aggregate breadth/depth metrics (advances/declines, etc.)
- Run indicator checks and surface triggered signals (start with ROC crossover criteria)
- Produce a nicely formatted Markdown report for human review
- Be easy to extend with new indicators (each indicator in its own Python file)

## Non-goals (for this initial module)
- No API endpoints or frontend integration yet
- No database persistence
- No real-time streaming or scheduling (run on demand via scripts)
- No new market data provider integration beyond existing YFinance path
- No interactive UI (future phase only)

## Status (Updated 2026-01-28)
- Phase 1 completed: module skeleton, configs, config loader, signals dataclass, CLI stub.
- Phase 2 completed: data fetcher, scan runner, structured logging, CLI scan wiring.
- Phase 3 completed: indicator registry + ROC indicator + criteria rules + breadth aggregates.
- Phase 4 completed: JSON schema + Markdown report renderer + CLI output wiring + unit tests.
- Follow-up completed: criteria evaluation scans the full window and emits multiple hits.

## Current Context (relevant code)
- Market data is already abstracted behind `MarketDataService` and `MarketDataProvider`.
- YFinance provider supports `get_historical_prices` returning a list of OHLCV dicts with `date`, `open`, `high`, `low`, `close`, `volume`.
- No existing indicator framework or scanning utilities exist.

## Proposed Module Location
Place the new module inside the backend Python package to reuse existing market data services:
- `src/backend/app/security_scan/`

Rationale:
- Reuses `MarketDataService` without duplicating provider logic
- Keeps scanning logic separate from API routes and existing services
- Minimal blast radius: new package, minimal changes to existing code

## High-Level Architecture
**Edge (I/O)**
- Config loader (tickers + scan options)
- Market data fetcher (calls `MarketDataService`)
- CLI entrypoint (invokes scans, prints/writes results)

**Core (pure logic)**
- Indicator evaluation functions
- Aggregate breadth/depth calculations
- Signal formatting

This keeps side effects at boundaries and core logic referentially transparent.

## Proposed Module Layout
```
src/backend/app/security_scan/
  __init__.py
  config/
    securities.toml           # ticker list + scan defaults
    scan_settings.toml         # indicator enablement + params
  config_loader.py             # parse config files
  data_fetcher.py              # MarketDataService wrapper
  aggregates.py                # breadth/depth metrics
  criteria.py                  # reusable criteria evaluation helpers
  signals.py                   # dataclasses for Signal/IndicatorSignal
  scan_runner.py               # orchestrates scan per ticker
  cli.py                       # entrypoint: python -m app.security_scan.cli
  indicators/
    __init__.py                # registry/discovery
    roc.py                     # first indicator (ROC series)
  reporting/
    __init__.py
    markdown_report.py         # human-friendly report renderer
```

## Configuration Plan
Use TOML (built-in `tomllib` in Python 3.13; no new deps).

**`securities.toml`**
```
[tickers]
list = ["AAPL", "MSFT", "AMZN", "TSLA", "GOOG"]

[scan_defaults]
lookback_days = 90
interval = "day"
```

**`scan_settings.toml`**
```
[indicators]
# Each entry is an indicator instance. `id` maps to the indicator file.
# All other keys are indicator-specific settings (including `criteria`).
# `criteria` is a list of structured rules (type + params).
instances = [
  { id = "roc", roc_lookback = 12, criteria = [{ type = "crossover", series = "roc", level = 0, direction = "both" }] },
  { id = "roc", roc_lookback = 24, criteria = [{ type = "crossover", series = "roc", level = 0, direction = "both" }] },
  { id = "ma_direction", ma_period = 49, criteria = [{ type = "direction", series = "ma", lookback = 5 }] }
]
```

Config loader should:
- Resolve config paths relative to module location
- Allow CLI override `--config-dir` without changing code
- Parse indicator instances from `scan_settings.toml` (see below)
- Normalize `criteria` to a list of structured rules (accept single rule or list)

## Indicator Interface (minimal, file-per-indicator)
Avoid heavy abstractions. Use a simple contract:
- Each indicator file exports:
  - `INDICATOR_ID: str`
  - `evaluate(prices: list[dict], settings: dict) -> list[IndicatorSignal]`
    - `settings` includes `criteria` (list of structured rules)
    - runner wraps results with `ticker`, `indicator_id`, `indicator_type`

**IndicatorSignal** (indicator-local):
- `signal_date`, `signal_type`, `metadata`

**Signal** (scan output):
- `ticker`, `indicator_id`, `indicator_type`, `signal_date`, `signal_type`, `metadata`

This avoids special-case handling and keeps extension simple.

## Aggregate Calculations (initial)
Start with daily advances/declines breadth on the most recent day in the lookback range:
- For each ticker, compare last close vs prior close
- Count advances, declines, unchanged
- Compute advance/decline ratio and net advances

Future extension: moving breadth time series, new-declines/new-highs, volume breadth, etc.

## Data Flow (End-to-End)
1. CLI invoked with optional `--config-dir`, `--start-date`, `--end-date`
2. Load ticker list + scan settings
3. For each ticker:
   - Fetch historical prices via `MarketDataService.get_historical_prices`
   - Normalize data to expected list-of-dicts format
4. Run indicators against each ticker’s data
5. Compute aggregates across all tickers
6. Output results (stdout JSON + optional file path)

## Implementation Phases

### Phase 1: Module Skeleton + Config
- Create `security_scan/` package and config files
- Implement `config_loader.py`
- Implement `signals.py` dataclasses
- Add CLI stub with `--config-dir` and `--output` options

### Phase 2: Data Fetch + Core Scan
- Implement `data_fetcher.py` to wrap `MarketDataService`
- Implement `scan_runner.py` orchestration (sequential loop for v1)
- Add structured logging at the module boundary

### Phase 3: Indicators + Aggregates
- Implement `roc.py`
- Implement `macd.py`
- Implement indicator registry in `indicators/__init__.py`
- Implement `aggregates.py` for advances/declines breadth

### Phase 4: Output + Tests
- Define JSON output schema for:
  - `signals`
  - `aggregates`
  - `run_metadata` (timestamp, lookback, tickers, indicators)
- Add Markdown report renderer:
  - summary table (breadth stats + totals)
  - per-indicator sections with triggered tickers
  - per-ticker mini-summaries (last close, indicator status, etc.)
- Unit tests:
  - ROC crossover criteria on synthetic data
  - Breadth calculations on deterministic inputs
  - Config loader parsing

## Detailed Plan Additions (Fill-In)

### Data Contracts (Explicit Shapes)
**Normalized price row**
- `date`: `YYYY-MM-DD` string (or `None` if missing)
- `open`, `high`, `low`, `close`, `volume`: numeric or `None`

**Signal**
- `ticker: str`
- `indicator_id: str` (unique instance id for reporting)
- `indicator_type: str` (matches indicator file `INDICATOR_ID`)
- `signal_date: str`
- `signal_type: str`
- `metadata: dict[str, Any]`

**IndicatorSignal (indicator-local)**
- `signal_date: str`
- `signal_type: str`
- `metadata: dict[str, Any]`

**Indicator instance (from config)**
- `id`: indicator type (maps to `INDICATOR_ID` in the indicator file)
- `instance_id`: optional; auto-generated when needed for reporting/logging
- `settings`: dict of indicator-specific parameters (includes `criteria`)

**Ticker summary**
- `ticker`
- `series_length`
- `first_date`
- `last_date`
- `last_close`
- `prior_close`
- `close_change`
- `close_change_pct`
- `issues: list[str]`

**Run payload**
- `run_metadata`
- `ticker_summaries`
- `signals`
- `aggregates`
- `issues`

### Indicator Framework (Minimal Registry)
- Maintain a plain dict registry:
  - `INDICATOR_REGISTRY: dict[str, Callable[[prices, settings], list[Signal]]]`
- Parse `indicators.instances` as a list of indicator instances:
  - Reserved keys: `id`, `instance_id`
  - All other keys are passed into the indicator as `settings`
  - Missing `instance_id` → auto-generate for output (stable order):
    `f"{id}_{index}"` where index is config order.
- Registry resolve behavior:
  - Unknown indicator ID → warning + issue entry, continue run.
  - Indicator evaluation error → warning + issue entry, continue run.
- No classes/inheritance; file-per-indicator with a simple function contract.

### Settings Contract (Low-Friction)
- No mapping layer between config and indicator settings.
- Config keys are passed verbatim to the indicator’s `settings` dict.
- Each indicator owns:
  - its **canonical setting names**
  - **defaults** (via `settings.get(...)`)
  - **validation** (raise or skip with issue)
- This keeps config ergonomic and avoids global coupling for 100s of indicators.

### Indicator Instances + Criteria (Scalable, Data-First)
- Each indicator instance is fully described by config (id + settings).
- `criteria` is a list of structured rules; each rule is a dict with:
  - `type`: rule type (e.g., `crossover`, `threshold`, `direction`)
  - rule-specific params (see below)
- Indicators can either:
  - use a shared criteria helper for common rule types, or
  - implement custom rule types locally.
- Signals should include both:
  - `indicator_id` (instance identity for reporting), and
  - `indicator_type` (shared type for grouping).
- Criteria are evaluated across the **full lookback window**; emit a signal
  for each hit (per ticker, per rule) with the matching `signal_date`.
- This allows hundreds of instances per indicator without code changes.

**Series naming contract**
- Indicators define the series names they emit (e.g., `roc`, `ma`).
- A rule with `series` applies only to that series; if `series` is omitted,
  it applies to the indicator’s default series.

### Criteria Schema (Generic, Reusable)
**Crossover**
- `{ type = "crossover", series = "roc", level = 0, direction = "both" }`
- General form for any series crossing any numeric level.
- Optional: `series_b` for series-vs-series crossover (future).
- Evaluate across consecutive points in the series and emit a signal on
  each crossing that matches `direction`.

**Threshold**
- `{ type = "threshold", series = "rsi", op = ">=", level = 70 }`
- Simple comparisons against a level (>, >=, <, <=).
- Evaluate at each point; emit a signal for each point meeting the condition.

**Direction**
- `{ type = "direction", series = "ma", lookback = 5 }`
- Compares last value vs value `lookback` periods ago.
- Emits signal metadata indicating `up` / `flat` / `down`.
- Evaluate across the series with the rolling `lookback` window; emit a signal
  for each evaluated point.

**Labeling**
- Optional `label` per criterion for report readability.
- If missing, auto-generate from type + key params.

**Note**
- “Zero crossover” is just `crossover` with `level = 0` (no sign-special-casing).

### Indicator Example (Non-Normative): ROC with Generic Crossover
**Definition**
- ROC = `(close[t] - close[t-lookback]) / close[t-lookback]`

**Settings (from TOML)**
- `roc_lookback`: int, default `12`
- `criteria`: list of structured rules (e.g., crossover at any level)

**Signal emission**
- Emit whenever the ROC meets configured rules across the window.
- Include `criteria` label/type in signal metadata.

### Aggregates (Breadth)
**Per-ticker inputs**
- Require at least two valid closes (last + prior).

**Outputs**
- `advances`, `declines`, `unchanged`
- `valid_ticker_count`, `missing_ticker_count`
- `advance_decline_ratio` (None if declines == 0)
- `net_advances` = advances − declines
- `advance_pct` = advances / valid_ticker_count

**Issue tracking**
- Missing last/prior close → add issue per ticker.

### Scan Runner Enhancements
- Fetch + normalize + sort prices.
- Build per-ticker summaries (last/prior close, change, pct).
- Evaluate indicators for each ticker.
- Collect signals for every rule hit across the configured window.
- Compute aggregates across all tickers.
- Include issues in payload without aborting the run.

### Markdown Report Renderer
File: `src/backend/app/security_scan/reporting/markdown_report.py`

**Sections**
- Title + run metadata (run_id, timestamp, range, interval, ticker count).
- Summary table (breadth metrics).
- Indicator overview (per instance: settings + total signals + most recent hit).
- Indicator rollups (readability-first):
  - by date + signal type + count + tickers (truncate long lists with “+N more”).
  - separate blocks for `up` vs `down` style signals when present.
- “Recent window” rollup (default last N trading days; older hits summarized).
- Latest-day highlight (most recent trading day only).
- Per-criteria grouping (use rule label/type to group signals).
- Signal streaks (tickers with consecutive direction signals).
- Signal density by date (simple counts table or sparkline-like row).
- Top tickers by signal count (overall + per indicator).
- Per-ticker summary table (last close, change, signals count, issues).
- Detailed signals table (appendix) with **flattened metadata** columns.
- Issues section (if non-empty).

**Formatting**
- Markdown tables with fixed column ordering.
- Sort tickers alphabetically; signals by signal_date desc.
- Flatten common metadata keys into columns (e.g., `prev_value`, `current_value`,
  `level`, `direction`, `label`) instead of JSON blobs.
- Keep raw metadata JSON only in the appendix if needed.

### JSON Output Schema
Top-level keys:
- `run_metadata`
- `ticker_summaries`
- `signals`
- `aggregates`
- `issues`

### CLI Output Behavior
- Default: write JSON and Markdown to `task-logs/` with shared run_id.
- `--output` accepts file or directory:
  - If file provided, write JSON there and place Markdown alongside with `.md`.
  - If directory provided, use `security_scan_<run_id>.json` and `.md`.
- Stdout stays JSON (non-breaking).

### Tests (Deterministic + Lightweight)
- ROC crossover criteria:
  - Up-cross, down-cross, no-cross, insufficient data, zeros.
  - Multiple hits across a window (emit multiple signals).
- Aggregates:
  - Deterministic last/prior close sets (adv/dec/unch, missing data).
- Config loader:
  - Valid TOML, invalid types, empty tickers.
- Markdown renderer:
  - Snapshot or string-contains for sections/tables.

### Observability + Issues
- Log warnings for missing data and indicator failures.
- Include structured `issues` list; avoid hard failures when possible.
- Criteria validation errors should surface as issues and skip that rule.

## Testing Plan (Real Data + Phase Gates)
The goal is to validate behavior under 100% realistic conditions after **each** phase. This means running scans against live YFinance data and manually inspecting outputs for plausibility.

Note that to run tests, you'll need to activate the local venv in src/backend/.venv

**After Phase 1 (Module Skeleton + Config)**
- Run the CLI with the default ticker list and verify config resolution and CLI wiring.
- Confirm it loads tickers and emits a minimal run metadata structure.
  - Completed 2026-01-27: `cd src/backend && .venv/bin/python -m app.security_scan.cli`
    - Result: run metadata emitted with config_dir, tickers, lookback_days, interval, and output_path.

**After Phase 2 (Data Fetch + Core Scan)**
- Run scans against the default ticker list using real market data.
- Manually inspect:
  - Data completeness (no empty series unless genuinely unavailable)
  - Dates align and most recent day matches expectations
  - Sensible last-close values (spot check 1–2 tickers)
  - Completed 2026-01-27: `cd src/backend && .venv/bin/python -m app.security_scan.cli`
    - Result: 5 tickers scanned, no issues, series_length=60 each, last_date=2026-01-26, sample last_close values looked plausible.

**After Phase 3 (Indicators + Aggregates)**
- Run scans on real data and verify indicator outputs are plausible.
- Manually inspect:
  - ROC crossover signals align with configured level + direction criteria
  - Multiple signals appear when criteria hits occur across the window
  - Breadth counts (adv/decl/unch) align with last-close vs prior-close deltas
  - Pending (2026-01-28): re-run after new criteria-based config/outputs.

**After Phase 4 (Output + Reporting)**
- Generate JSON + Markdown reports and inspect:
  - Summary table matches computed aggregates
  - Triggered ticker lists match raw outputs
  - Per-ticker summaries are internally consistent (dates, prices, signal labels)
  - Pending (2026-01-28): validate Markdown output after schema update.

**Automated checks (lightweight, optional)**
- Keep focused unit tests for indicator math and aggregate logic using deterministic fixtures.
- These are secondary to real-data validation and are intended to catch regressions in pure logic.

## Risks & Mitigations
- **Data gaps / missing days**: handle empty or 1-row series gracefully, skip with warning
- **Indicator parameter drift**: validate settings on load; fallback to defaults
- **Large ticker sets** (future): plan for bounded concurrency and caching; keep sequential for v1

## Hardest Parts (and why they should be easy with this design)
1. **Indicator extensibility**: file-per-indicator + simple function contract avoids registry complexity.
2. **Config-driven ticker sets**: TOML files + path override keeps config isolated and deterministic.
3. **Data alignment for breadth**: using last-two closes per ticker keeps initial breadth simple; future time-series breadth can be layered without refactoring core.

## Blast Radius Assessment
- New module only; no changes to existing API routes
- Reuses existing `MarketDataService` without modification
- Optional: add lightweight tests only; no database or schema impact

## Open Questions
- Should the scan results be written to disk under `task-logs/` by default? Resloved: Yes and stdout as well.
- Do we want to run scans inside the existing Docker setup, or keep as local dev utility only? Resolved: Local dev utility only.
- Should the Markdown report be saved by default (and JSON optional), or vice versa? Resolved: Markdown report by default, json optional for now, but may be required once we build the UI components.

## Proposed Next Step
Confirm module location (`src/backend/app/security_scan/`) and config format (TOML). Once confirmed, implement Phase 1.

## Future Phase (Penciled In)
### UI Explorer for Scan Results (Later)
- Add a frontend view to browse surfaced securities with filters by indicator/trigger type
- Click-through drill-down to security detail analysis (option chains, volatility curves, term structure)
- Backend API endpoints to fetch scan results and on-demand drill-down data
- Persist scan runs (metadata + signals) for historical comparison
