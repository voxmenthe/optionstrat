# Security Scan Configurable Advance/Decline Aggregations Plan

## Goal
Add configurable advance/decline breadth aggregations so the scan can compare `C_t` vs `C_{t-N}` for arbitrary, user-defined `N` values (multiple lookbacks supported), driven by `scan_settings.toml`.

## Non-goals
- No changes to indicator logic or criteria evaluation.
- No schema changes (reuse existing aggregate storage table/metric keys).
- No API or UI work beyond the existing Markdown report.

## Current Context (relevant code)
- `src/backend/app/security_scan/aggregates.py` computes a single advance/decline set using `last_close` vs `prior_close` (t-1).
- `src/backend/app/security_scan/scan_runner.py` builds ticker summaries and calls `compute_breadth`, then persists aggregates keyed by `metric_key`.
- `src/backend/app/security_scan/reporting/markdown_report.py` renders a fixed Summary (Breadth) section using the existing single-lookback metrics.
- `src/backend/app/security_scan/config_loader.py` currently loads tickers + indicator instances only; no aggregate config.

## Assumptions (explicit)
- "t-N" means N bars back in the ordered price series, not calendar days.
- Config lives in `scan_settings.toml` alongside indicator instances.
- If no config is provided, default behavior remains the current t-1 breadth.
- Aggregate storage uses the existing `security_aggregate_values.metric_key` field; no DB schema changes.

## Hardest Parts (and why)
1. **Backward compatibility**: preserve existing `advances/declines/...` fields for downstream consumers while adding multiple lookbacks.
2. **Data flow**: `compute_breadth` currently only sees summary fields; it needs per-lookback prior closes without bloating payloads.
3. **Report rendering**: Markdown report currently assumes fixed breadth metrics; needs to render a variable set cleanly.

## Options Considered

### Option A — Simple lookback list (recommended)
**Config**
```toml
[aggregates]
advance_decline_lookbacks = [1, 5, 10]
```
**Behavior**
- Always compute base metrics (t-1) for existing keys: `advances`, `declines`, `advance_pct`, etc.
- Additionally compute per-lookback metrics with prefix `ad_<N>_*` for each configured `N` (excluding 1 to avoid duplication).

**Pros**
- Minimal config surface; easy to reason about.
- Keeps backward compatibility.
- Low implementation risk.

**Cons**
- Base metrics are always t-1; cannot redefine "primary" via config.
- Labels are derived from `N` (no custom naming).

**Friction check**
- Low: config is a single list, no extra abstraction.

---

### Option B — List of labeled definitions (more flexible)
**Config**
```toml
[[aggregates.advance_decline]]
id = "t_1"
lookback = 1
label = "1d"

[[aggregates.advance_decline]]
id = "t_5"
lookback = 5
label = "5d"
primary = true
```
**Pros**
- Custom labels and a configurable "primary" lookback.
- Clear naming in output/report.

**Cons**
- Larger config surface; more validation.
- More code paths in loader + report.

**Friction check**
- Medium: more branching/validation and larger config surface.

---

### Option C — Replace existing breadth summary entirely
- Compute only configured lookbacks; remove base `advances/declines` keys.

**Pros**
- Clean, uniform model.

**Cons**
- Breaking change to report/tests/downstream consumers.
- Higher blast radius.

**Friction check**
- High: forced downstream changes.

## Decision
**Choose Option A** for minimal change, low risk, and backward compatibility. Option B can be added later if custom labels become necessary.

## Proposed Design

### Config
- Add to `scan_settings.toml`:
  ```toml
  [aggregates]
  advance_decline_lookbacks = [1, 5, 10]
  ```
- `advance_decline_lookbacks` is optional; default to `[1]` if missing.
- Validate list is non-empty, integers > 0.

### Data Flow
- **Summaries**: extend `_summarize_prices_from_series` to compute a small `close_by_offset` dict for the configured lookbacks (only for requested N values).
  - Example: `{ "1": 125.0, "5": 118.0 }`
- **Aggregates**: update `compute_breadth` to accept:
  - `advance_decline_lookbacks: list[int]`
  - Use `last_close` vs `close_by_offset[N]` for each lookback.
  - Keep existing base metrics for `N=1` using existing keys.
  - Add per-lookback metrics for `N != 1` with a prefix:
    - `ad_<N>_advances`, `ad_<N>_declines`, `ad_<N>_unchanged`
    - `ad_<N>_valid_count`, `ad_<N>_missing_count`
    - `ad_<N>_advance_decline_ratio`, `ad_<N>_net_advances`, `ad_<N>_advance_pct`

### Storage
- No schema changes.
- Update `AGGREGATE_GROUP_PREFIXES` to include `ad_<N>` prefixes so pct records include `valid_count`/`missing_count`.
- Persist all new aggregate metrics via existing `upsert_security_aggregate_values`.

### Report
- Add a new table in Markdown:
  - **Summary (Advance/Decline Lookbacks)** listing `N`, advances, declines, ratio, net, advance %.
- Use `run_metadata.advance_decline_lookbacks` (or default to `[1]` if missing).
- Keep the existing "Summary (Breadth)" section for legacy t-1 metrics.

### Run Metadata
- Include `advance_decline_lookbacks` in `run_metadata` so reports and downstream consumers can introspect configuration.

## Implementation Steps
1. **Config loader**
   - Add `advance_decline_lookbacks` to `SecurityScanConfig`.
   - Parse/validate `[aggregates].advance_decline_lookbacks` from `scan_settings.toml`.
   - Default to `[1]` if missing.
2. **Scan runner summary**
   - Pass `config.advance_decline_lookbacks` into `_summarize_prices_from_series`.
   - Add a `close_by_offset` map to ticker summaries for requested lookbacks.
3. **Aggregate computation**
   - Update `compute_breadth` signature to accept the lookback list.
   - Compute base (t-1) metrics as now.
   - Compute per-lookback metrics for additional N values using `close_by_offset`.
4. **Aggregate persistence**
   - Add `ad_<N>` prefixes to `AGGREGATE_GROUP_PREFIXES`.
   - Ensure `_build_aggregate_records` attaches valid/missing counts for the new pct keys.
5. **Report rendering**
   - Render a variable lookback table using `run_metadata.advance_decline_lookbacks`.
   - Keep the existing "Summary (Breadth)" section for backward compatibility.
6. **Docs + config**
   - Update `security_scan/README.md` config section.
   - Add example `advance_decline_lookbacks` to default `scan_settings.toml`.
7. **Tests**
   - Extend `test_load_security_scan_config_instances` to parse the new config.
   - Add breadth tests for multiple lookbacks, validating counts + pct for `ad_<N>_*` keys.
   - Update Markdown report test to assert the new lookback table is present (if needed).

## Validation Plan
- `uv run python -m pytest src/backend/tests/test_security_scan.py`
- Run a local scan and confirm:
  - Output JSON includes `advance_decline_lookbacks` in `run_metadata`.
  - New `ad_<N>_*` metrics appear in aggregates and are persisted.
  - Markdown report renders the new lookback summary table.

## Risks / Blast Radius
- **Low**: Config parsing + reporting changes; storage uses existing schema.
- **Medium**: `compute_breadth` signature change requires updating all call sites/tests.
- **Mitigation**: Default to `[1]` to keep existing behaviors; maintain legacy keys.

## Open Questions
- Should the report show *only* configured lookbacks, or show base t-1 plus configured extras? (Plan assumes base + extras.)
- Should we skip computing extra lookbacks for tickers with insufficient history, or count them as missing? (Plan assumes missing.)
