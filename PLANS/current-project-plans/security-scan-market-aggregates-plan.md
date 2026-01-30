# Security Scan Market Aggregates + Storage Plan (Expanded)

## Goal
Extend the security scan to:
- Add new market aggregates (MA breadth + ROC-vs-prior ROC breadth).
- Persist commonly used derived values (ROC/SMA) per security to avoid recomputation.
- Persist aggregate series over time (for plotting).
- Show storage usage in the scan report (by storage type).

## Status (Updated 2026-01-29)
- Decision made: use a dedicated `security_scan.db` (separate from `options.db`).
- Phase 1 progress: scan models moved into a scan-specific DB module at `src/backend/app/security_scan/db.py`.
- Phase 1 progress: storage helpers updated to use the scan DB session.
- Phase 2 in progress: metric computation helpers added (`series_math.py`) and scan runner now caches per‑security metrics into `security_scan.db`.
- Phase 3 progress: MA/ROC breadth aggregates computed in `compute_breadth`, and aggregate values persist by set hash.
- Phase 4 progress: report now includes MA/ROC breadth tables + storage usage line.
- Phase 5 progress: tests added for MA/ROC aggregates + storage usage rendering.
- Docs updated: `security_scan/README.md` now documents `storage_usage` in JSON output.
- Notebook updated: aggregate series plotting added to `indicator_sanity_check.py`.
- Next: consider adding DB upsert tests (optional).

## Non-goals
- No API endpoints or UI changes beyond the Markdown report.
- No new providers (assume `yfinance` only; polygon can be ignored).
- No redesign of indicators or criteria engine.

## Current Storage Context (from investigation)
- Database is SQLite via SQLAlchemy (`src/backend/app/models/database.py`), stored at `sqlite:///./options.db`.
  - Tables: positions/legs, legacy positions, cache entries, PnL results.
  - No security scan storage tables yet.
- Scan storage now lives in a separate `security_scan.db` (created in `src/backend/` via `src/backend/app/security_scan/db.py`).
- Provider caching (Redis + DB fallback) stores short-lived values in `CacheEntry` only.
- Security scan outputs are written to `task-logs/` as JSON + Markdown; no persistence of aggregates or indicator series.
- **Risk**: `./options.db` is relative to the current working directory; this repo already contains two `options.db` files, so storage can silently split depending on CWD.

## Requested Metrics (definitions)
### Moving Average Breadth
For each ticker with sufficient data:
- Compute SMA(N) using the most recent N closes and compare `last_close` to that SMA.
- Track % above and % below (and optionally % equal / missing).

Start with:
- SMA(13), SMA(28), SMA(46)
- SMA(8) shifted by 5 (see Open Decisions below)

### ROC vs Prior ROC Breadth
For each ticker with sufficient data:
- Compute ROC(N) at the most recent close: `(close_t - close_{t-N}) / close_{t-N}`
- Compute ROC(N) at `lookback` days ago: `(close_{t-lookback} - close_{t-lookback-N}) / close_{t-lookback-N}`
- Compare current ROC vs prior ROC: greater / less / equal

Start with:
- ROC(17) vs ROC 5 days ago
- ROC(27) vs ROC 4 days ago

## Assumptions + Open Decisions
1. **“8‑day shifted by 5” meaning (resolved)**
   - Confirmed: compare *current* close to SMA(8) computed **ending 5 bars ago** (window `[t-5-7 … t-5]`).
2. **Equality handling**
   - Default: equality counts as neither above nor below; track as `equal`/`unchanged` so totals reconcile.
3. **Percent denominator**
   - Use metric‑specific valid count (tickers with enough data and non‑zero denominators).
4. **Series alignment**
   - Use ordered close series by date (already done in `_summarize_prices`).
5. **Provider dimension (resolved)**
   - Assume `yfinance` only; do not include provider in storage keys.

## Storage Design (new)
We will persist two kinds of data:

### 1) Per‑security derived values (ROC/SMA cache)
Purpose: Avoid recomputation and enable re-use by aggregates/indicators.

**Table: `security_metric_values`**
- `id` (PK)
- `ticker` (indexed)
- `as_of_date` (indexed; date for the metric value)
- `interval` (e.g., `day`)
- `metric_key` (e.g., `sma:13`, `sma:8:shift=5`, `roc:17`, `roc:27`)
- `value` (float)
- `computed_at`
- Unique index: `(ticker, as_of_date, interval, metric_key)`

### 2) Aggregate time series (per ticker‑set hash)
Purpose: Plot aggregate values over time and tie them to the exact security set used.

**Table: `security_sets`** (optional but recommended)
- `set_hash` (PK)
- `tickers_json` (canonical sorted list)
- `ticker_count`
- `created_at`

**Table: `security_aggregate_values`**
- `id` (PK)
- `set_hash` (FK to `security_sets`)
- `as_of_date`
- `interval`
- `metric_key` (e.g., `pct_above_sma:13`, `pct_below_sma:13`, `roc:17:vs_shift=5:gt_pct`)
- `value`
- `valid_count`
- `missing_count`
- `computed_at`
- Unique index: `(set_hash, as_of_date, interval, metric_key)`

### Security‑set hash
```
set_hash = sha256(",".join(sorted(unique_tickers))).hexdigest()
```
If you want interval baked in, append `|interval=day`.

## Storage Separation Options (new)
You asked about separating scan storage from options/positions. Here are viable paths:

### Option 1 — Separate SQLite DB for scan data (recommended)
**Idea**: Keep `options.db` for positions/options; add a dedicated `security_scan.db` for scan metrics + aggregates.
- **Pros**: Clear size isolation; avoids scan growth impacting core DB; easy backup/cleanup.
- **Cons**: Requires a second SQLAlchemy engine/session + moving scan models out of `models/database.py`.
- **Implementation impact**:
  - Create `src/backend/app/security_scan/db.py` with its own `Base`, engine, `SessionLocal`.
  - Move scan models (`SecuritySet`, `SecurityMetricValue`, `SecurityAggregateValue`) into a scan-specific models module (e.g., `security_scan/storage_models.py`).
  - Update `security_scan/storage.py` to use the scan DB session.

### Option 2 — Same DB file, namespaced tables
**Idea**: Keep everything in `options.db` but use `security_*` tables (already done).
- **Pros**: Minimal code changes; no extra engine/session.
- **Cons**: Scan data growth can bloat `options.db`; harder to prune without touching core data.

### Option 3 — File-based time series (CSV/Parquet) + DB metadata
**Idea**: Store aggregates/metrics as files under `task-logs/` or `data/`, keep only run metadata in DB.
- **Pros**: Easy to inspect; large series are cheap to store.
- **Cons**: Harder to query; requires more file management and consistency checks.

**Decision**: Proceed with Option 1 (separate `security_scan.db`) and relocate the scan models out of `models/database.py`.

## Storage Usage Reporting (new)
Add a line to the Markdown report that shows size by storage type, e.g.:

```
Storage: DB=42.3MB | task-logs=18.1MB | total=60.4MB
```

Implementation details:
- Compute file sizes at scan time and add to payload (e.g., `payload["storage_usage"]`).
- Categories:
  - `scan_db`: size of `security_scan.db`.
  - `options_db`: size of `options.db` (still useful for overall footprint).
  - `task_logs`: total size of `task-logs/` directory (JSON + MD).
  - `total`: sum of the above.
- Keep this as a **single line** in the report to minimize clutter.

## Design Direction (updated)
Use a hybrid of Option A + Option C:
- **Option A** for report aggregates (use summary values to compute breadth).
- **Option C** for shared metric computation + persistence (avoid re-running SMA/ROC for every scan).

This gives persistence and reuse without introducing heavy abstraction.

## Concrete Implementation Plan
### Phase 1 — Schema & Storage primitives
1. **Add SQLAlchemy models** in `src/backend/app/security_scan/db.py` (done 2026-01-29):
   - `SecuritySet`
   - `SecurityMetricValue`
   - `SecurityAggregateValue`
2. **Create indexes/unique constraints** for `(ticker, as_of_date, interval, metric_key)` and `(set_hash, as_of_date, interval, metric_key)` (done 2026-01-29).
3. **Create a small storage module** (e.g., `src/backend/app/security_scan/storage.py`) with (done 2026-01-29):
   - `get_or_create_security_set(tickers) -> set_hash`
   - `upsert_security_metric_values(...)`
   - `fetch_security_metric_values(...)`
   - `upsert_aggregate_values(...)`
4. **DB path clarity** (done 2026-01-29): move scan models to dedicated `security_scan.db` with an absolute path anchored to `src/backend/`.
5. **Scan DB module** (done 2026-01-29):
   - New `src/backend/app/security_scan/db.py` with separate engine/base/session.
   - Scan storage helpers now use the scan DB session.

### Phase 2 — Metric computation & caching
5. Add a small helper module (e.g., `series_math.py`) with **pure functions** (done 2026-01-29):
   - `compute_sma(close_series, window, shift=0)`
   - `compute_roc(close_series, lookback, shift=0)`
6. Compute SMA/ROC values for the **most recent date** and persist (done 2026-01-29):
   - Scan runner now computes metric values and stores them in `security_metric_values`.
   - Cached values are reused on subsequent runs for the same ticker/date.

### Phase 3 — Aggregates stored by set hash
7. Extend `compute_breadth` (or rename to `compute_market_aggregates`) to:
   - Calculate new MA/ROC breadth metrics from per‑ticker summary values.
   - Return aggregate counts + percentages. (done 2026-01-29)
8. After aggregates are computed, **persist** them (done 2026-01-29):
   - `set_hash = get_or_create_security_set(config.tickers)`
   - `upsert_security_aggregate_values(...)` now called in `scan_runner`.
   - Aggregates stored using `as_of_date = resolved_end`.

### Phase 4 — Report updates
9. Add storage usage to payload (done 2026-01-29):
   - Compute sizes for `security_scan.db`, `options.db`, and `task-logs/`.
   - Attach `storage_usage` in CLI before rendering the report.
10. Update Markdown report to include a **single storage summary line** (done 2026-01-29).
11. Add new aggregate rows to the Summary table (grouped sections for MA breadth & ROC breadth) (done 2026-01-29).

## Implementation Context (added)
- Aggregate keys for MA breadth:
  - `ma_13_*`, `ma_28_*`, `ma_46_*`, `ma_8_shift_5_*` with `above|below|equal` counts + pct.
- Aggregate keys for ROC breadth:
  - `roc_17_vs_5_*`, `roc_27_vs_4_*` with `gt|lt|eq` counts + pct.
- Storage usage is computed in `cli.py` and rendered in the report from `payload["storage_usage"]`.
- `security_scan/README.md` now lists `storage_usage` as a top-level JSON field.
- Notebook aggregate plotting:
  - Uses `security_scan.db` via `SecurityAggregateValue`.
  - Configure tickers + metric keys in the notebook config section.

### Phase 5 — Tests
12. Add tests in `src/backend/tests/test_security_scan.py`:
   - SMA/ROC derived value correctness for a deterministic series.
   - Aggregate calculations (gt/lt/eq + valid counts).
   - Storage usage summary rendering (stub sizes). (done 2026-01-29)
   - DB upsert path (optional; can mock storage module for unit tests).

## Validation
- `python -m pytest src/backend/tests/test_security_scan.py`
- Run `security_scan` once and verify:
  - `security_scan.db` grows by new tables.
  - Aggregate series are stored.
  - Report includes storage line + new breadth rows.

## Risks & Mitigations
- **DB path ambiguity**: pin DB path or clearly document CWD to avoid split storage.
- **Off‑by‑one errors**: use fixed, synthetic test series with known SMA/ROC values.
- **Growth over time**: consider retention policy or compaction if DB grows too fast.
- **Write amplification**: upsert only for dates that are missing to avoid duplicates.
