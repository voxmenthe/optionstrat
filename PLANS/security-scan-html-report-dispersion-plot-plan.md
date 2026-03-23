# Security Scan: Dispersion Suite HTML Report (Separate Artifact) — Plan

This document supersedes the earlier “single plot in the main report” direction and incorporates the strongest ideas from `PLANS/security-scan-dispersion-aggregate-plan.md`, while reshaping them into a **dedicated dispersion/co-movement HTML report** that:
- is **separate** from the main Security Scan report (different `.html` file),
- is **similar in style** (Plotly timeseries blocks, offline/self-contained), and
- **shares helpers** (series fetching/assembly, Plotly figure builder, HTML shell) where that reduces duplication and blast radius.

## Goal (What We’re Building)
Produce a **single, interpretable daily score** per universe (“how much the universe moves in lockstep”) and a companion suite of diagnostic dispersion measures, then render them into **one dedicated HTML report**:
- `security_scan_<run_id>_dispersion.html` (name bikeshed below)
- optionally a markdown companion `security_scan_<run_id>_dispersion.md` for diffability

The main Security Scan report remains focused on breadth/trend aggregates and indicator rollups; it may include a simple link to the dispersion report artifact.

## Non-Goals (For Safety + Change Agility)
- No schema migrations (reuse `security_scan.db` + `security_aggregate_values`).
- No frontend app / server; this is an offline artifact like the existing HTML report.
- No “heatmap of NxN correlations” in the report by default (too heavy / high density).
- No intraday-only dispersion modeling in v1 (we can compute an intraday snapshot, but persistence stays consistent with current intraday-synthetic skip rules).

## Terminology (Make Orientation Unambiguous)
“Dispersion” is ambiguous; “lockstep” is what we actually want to quantify.

We will store *both* orientations in the DB and report:
- `lockstep_score ∈ [0, 100]`: higher = more co-movement.
- `dispersion_score ∈ [0, 100]`: higher = more idiosyncratic movement.

Contract:
- `dispersion_score = 100 - lockstep_score`.

The dispersion report will headline `lockstep_score` (the “single aggregate number”), and also show `dispersion_score` to prevent interpretation drift.

## Current State (Relevant Code + Data Flows)
- Aggregates are persisted in `security_scan.db` (`security_aggregate_values`) keyed by:
  - `set_hash` (ticker universe hash), `as_of_date`, `interval`, `metric_key`.
- The Security Scan CLI already:
  - computes and persists breadth aggregates per universe (`all`, `nasdaq`, `sp100`),
  - supports a backfill path (`--backfill-aggregates`) that writes historical series,
  - renders an offline Plotly-based HTML report using:
    - `reporting/aggregate_series.py` (series definitions + assembly),
    - `reporting/aggregate_charts.py` (Plotly rendering),
    - `reporting/html_report.py` (HTML shell + markdown rendering).

Implication: dispersion metrics should be treated as **first-class aggregates** (like breadth), persisted into the same table and plotted from the same storage primitives.

## Hard Parts (And How We Make Them Natural)
1. **Noise + stability**: co-movement estimates are unstable in short windows and on low-volatility days.
   - Solution: multi-window design (5/21/63) + reliability weighting + optional volatility gating.
2. **Missing/uneven data**: IPOs, delistings, data gaps.
   - Solution: strict window eligibility per ticker + explicit `valid_count/missing_count` + minimum thresholds.
3. **Performance**: naive pairwise correlation is O(N²) and will explode for large universes.
   - Solution: compute key measures in **O(T·N)** (or O(T·N·iters) for PCA top-1) without materializing NxN matrices.

If implementation starts adding special cases around any of these, that’s architectural friction: we should revisit the data model and boundaries (pure math module + explicit eligibility rules).

## Measures (Principled Options) — What We’ll Compute
We want one daily score, but also enough “component” measures to explain *why* it moved.

### Core Components (v1 baseline)
Each component is normalized to a `lockstep_component ∈ [0, 1]` (higher = more lockstep).

1) **Average Pairwise Correlation (Cohesion)**
- Compute mean off-diagonal correlation of returns in window `W`.
- Normalize: `lockstep_corr = (corr_mean + 1) / 2`.
- Efficient formula (no NxN matrix):
  - Standardize return matrix by column within window → `Z` (T×N).
  - Let `s_t = Σ_i Z_{t,i}`.
  - `sum(C) = (1/(T-1)) * Σ_t s_t²` (includes diagonals).
  - `corr_mean = (sum(C) - N) / (N*(N-1))`.

2) **“Market Mode” Dominance (PCA PC1 share)**
- On the correlation matrix implied by `Z`, compute the top eigenvalue `λ1` (via power iteration using `Z` multiplications).
- Since `trace(C) = N` for a correlation matrix, `pc1_share = λ1 / N`.
- Normalize: `lockstep_pca = pc1_share` (already in [0,1]).

3) **Directional Consensus (Entropy / Sign Agreement)**
- For each day in window: `p_up = frac(r_i > 0)`, `p_down = frac(r_i < 0)` (ignore exact zeros).
- Compute binary entropy `H`, scale to [0,1], then:
  - `lockstep_sign = 1 - H_scaled`.
- Window aggregate: median/mean across days in window.

4) **Cross-Sectional Dispersion of Standardized Returns (Robust)**
- For each day, compute robust spread across tickers (MAD) on standardized returns:
  - `xs_mad_z_t = MAD_i(Z_{t,i})`.
- Map to lockstep via a monotone transform:
  - default: `lockstep_xs = exp(-k * median_t(xs_mad_z_t))` with configurable `k`.
  - (Alternative: percentile-rank mapping once we have enough history.)

Rationale: this captures “everyone is doing the same thing” vs “moves are idiosyncratic” without being dominated by overall market volatility.

### Extensions (v2+; behind config flags)
5) **Tail co-movement / exceedance dependence**
- Condition on “big market move” days (|r_mkt| > threshold) and measure agreement with market sign.

6) **Correlation-network connectivity**
- Build a graph by corr threshold and measure giant-component ratio / average degree.
- High density + more parameters ⇒ keep optional; only ship after we have calibration evidence.

## The Score (Single Number) — Composite With Reliability

### Per-window composite (W ∈ {5, 21, 63})
Compute each component in window `W`, then:
- `L_W = Σ_method (method_weight * lockstep_method_W)` where weights sum to 1.

Default method weights (configurable):
- corr: 0.40
- xs: 0.25
- pca: 0.25
- sign: 0.10

### Multi-window blend
Default windows + weights:
- W=5: 0.45
- W=21: 0.35
- W=63: 0.20

### Reliability weighting (prevents garbage scores)
For each window, compute `reliability_W ∈ [0,1]` based on:
- eligible ticker count ≥ `min_tickers`
- observations in window ≥ `min_observations`
- (optional) pair coverage ≥ `min_pair_coverage`

Then:
- `lockstep_score_raw = Σ(W_weight * reliability_W * L_W) / Σ(W_weight * reliability_W)`
- `lockstep_score = round(100 * lockstep_score_raw, 2)` or `None` if denominator is 0.
- `dispersion_score = 100 - lockstep_score` (when lockstep_score is not None).

### Optional volatility gate (keeps quiet days from dominating)
If enabled, score contributions can be gated by a market-vol measure (e.g., realized vol percentile).
If the gate is closed, we still store components/diagnostics but:
- either freeze the composite score (carry forward),
- or mark composite score as None for that day.

This is high policy-impact; default off until we observe behavior.

## Timeframe Variations (Return Horizons)
All measures above assume **1-day returns** (`h=1`), which is the best baseline for stability and backfill cost.

We should design the computation API to support additional horizons without rewriting the model:
- `h=1` (daily) — baseline
- `h=5` (weekly-ish) — optional extension, computed as 5-trading-day returns

Suggested rollout:
1. Ship `h=1` only.
2. Add `h=5` metrics as a second “view” once the baseline score is trusted (helps detect slower regime shifts).

Storage key convention for horizons:
- No suffix = `h=1` (default).
- `_h5_...` prefix segment or suffix for `h=5` (pick one and keep consistent), e.g.:
  - `disp_h5_lockstep_score`
  - `disp_h5_corr_mean_21d`

## Output Contract (Metric Keys in `security_aggregate_values`)
We keep the key set intentionally stable and versionable. Baseline keys per universe/date:

Headline:
- `disp_lockstep_score` (0–100)
- `disp_dispersion_score` (0–100)

Per-window lockstep (0–100):
- `disp_lockstep_5d`
- `disp_lockstep_21d`
- `disp_lockstep_63d`

Primary-window component metrics (keep components to 21d initially):
- `disp_corr_mean_21d` ([-1,1] or [0,1] depending on stored form; choose and document)
- `disp_pca_pc1_share_21d` ([0,1])
- `disp_sign_consensus_21d` ([0,1])
- `disp_xs_mad_z_21d` ([0,∞), robust spread diagnostic)

Diagnostics:
- `disp_valid_ticker_count`
- `disp_valid_pair_count` (optional; used for pair coverage + debugging)
- `disp_observation_count`
- `disp_reliability_5d` / `disp_reliability_21d` / `disp_reliability_63d` (optional)
- `disp_gate_open` (0/1, optional)
- `disp_gate_metric` (optional; e.g., realized vol percentile)

Optional segmented keys (only when segmentation is enabled + event counts are sufficient):
- `disp_lockstep_up_score`
- `disp_lockstep_down_score`
- `disp_up_event_count`
- `disp_down_event_count`

`valid_count` / `missing_count` storage semantics:
- For all dispersion keys, set `valid_count = disp_valid_ticker_count`.
- Set `missing_count = universe_ticker_count - valid_count`.

## Report Direction Change: Separate Dispersion HTML Report
Instead of injecting dispersion charts into the main HTML report, we generate a separate artifact:

### New artifact(s)
- `security_scan_<run_id>_dispersion.html` (offline self-contained)
- optional: `security_scan_<run_id>_dispersion.md`

### Link from main report (small, low-risk)
- Add a line in the main report “Artifacts” list:
  - Dispersion HTML Output: `/path/to/security_scan_<run_id>_dispersion.html`

This keeps the main report stable while making the dispersion suite discoverable.

## Dispersion Report UX (What’s In The HTML)
The dispersion report should “feel” like the existing aggregate plots:
- same Plotly look-and-feel (white template, unified hover, crosshair),
- same chart grouping pattern (multiple blocks with `<h3>` titles),
- same multi-universe panels (All / NASDAQ / SP100) where useful.

### Proposed sections (v1)
1) **Headline**
   - A small summary table per universe: lockstep_score, dispersion_score, valid_tickers.
2) **Lockstep Score (Timeseries)**
   - Plot `disp_lockstep_score` plus optional per-window overlays.
   - Reference lines at 25/50/75 or just 50.
3) **Components (Timeseries)**
   - Corr mean, PC1 share, sign consensus (21d).
4) **Cross-Sectional Dispersion (Timeseries)**
   - `disp_xs_mad_z_21d` (diagnostic; include explanation).
5) **Data Quality**
   - valid_ticker_count and observation_count; optionally reliability and gate_open.
6) (Optional) **Regime Segments**
   - up/down lockstep scores + event counts when enabled.

The report is a “one stop” page for all dispersion measures.

## Architecture (File-Level Plan) — Share Helpers, Keep Math Pure

### 1) Pure dispersion computation module (core logic; no I/O)
Create `src/backend/app/security_scan/dispersion.py` (or `dispersion/` package if it grows):
- Build aligned return matrices from `prices_by_ticker`.
- Compute each component for a given window/horizon.
- Compute composite score + reliability.
- Output a plain dict of metric_key → value plus diagnostics.

Design rules:
- Pure functions; deterministic (same input → same output).
- No imports from storage or reporting.
- Explicit eligibility and failure modes (`None` when insufficient data).

### 2) Scan runner integration (current-day snapshot)
Update `src/backend/app/security_scan/scan_runner.py`:
- Collect `price_series_by_ticker` while fetching prices (already present in backfill; add for normal run).
- For each universe (`all`, `nasdaq`, `sp100`):
  - compute dispersion metrics for `resolved_end` from `price_series_by_ticker`
  - merge into `universe_entry["aggregates"]` so persistence piggybacks on `_build_aggregate_records(...)`.
- Respect current intraday synthetic persistence skip rules:
  - compute for reporting, but do not persist when `intraday_synthetic_scan_tickers` is non-empty.

### 3) Backfill integration (creates timeseries for charts)
Extend `build_backfill_aggregate_records(...)` to also compute dispersion metrics for each `as_of_date`.
Performance containment:
- Only compute the key subset needed for the report (headline + primary-window components).
- Use O(T·N) formulas; avoid any NxN materialization by default.

### 4) Reporting: new dispersion report renderer (separate from main)
Add `src/backend/app/security_scan/reporting/dispersion_markdown_report.py`:
- Build markdown sections/tables for dispersion metrics.

Add `src/backend/app/security_scan/reporting/dispersion_html_report.py`:
- Render markdown → HTML and inject charts_html, using the same HTML shell styling.

### 5) Charting: share Plotly + multi-universe helpers
We should avoid copy/pasting `aggregate_charts.py`.

Proposed refactor (small, pays for itself with 2 report types):
- Extract a generic helper in `src/backend/app/security_scan/reporting/timeseries_charts.py`:
  - generic “render chart groups” given:
    - group definitions (title, y-label, tickformat, reference lines),
    - a `group_series(series_payloads) -> dict[group_key, list[series]]` function,
    - optional benchmark context series.
- Update existing `aggregate_charts.py` to call the generic helper (no behavior change).
- Add `dispersion_charts.py` to define:
  - dispersion series definitions (metric keys to fetch),
  - dispersion chart group definitions + grouping function,
  - a `build_dispersion_report_charts_html(...)` entrypoint.

This keeps the “narrow waist” stable: one generic chart renderer; multiple report-specific definitions.

### 6) CLI changes: write dispersion report artifact
Update `src/backend/app/security_scan/cli.py`:
- Extend output path resolution:
  - `security_scan_<run_id>.{json,md,html}` (existing)
  - `security_scan_<run_id>_dispersion.html` (new)
  - optionally `_dispersion.md`
- Add config/flag:
  - config: `[report] dispersion_html = true` (default true once implemented)
  - CLI: `--no-dispersion-html` (mirror `--no-html`)
- Write the dispersion report after aggregates are available/backfilled:
  - fetch the required dispersion series from DB (same set_hashes)
  - build charts HTML
  - render dispersion markdown + html
- Add `run_metadata.dispersion_html_path` to payload and list it in main report artifacts.

## Config Design (TOML; Backward Compatible)

### Dispersion computation config
Add to `scan_settings.toml`:
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
volatility_gate_enabled = false
volatility_gate_lookback = 20
volatility_gate_percentile = 0.60
segment_up_down = false
segment_threshold_sigma = 0.0
segment_min_events = 8
```
Parsing rules:
- Absent section ⇒ dispersion disabled by default (or enabled; pick one and document).
- Validate weights sum to ~1 (within epsilon) and windows are positive ints.

### Dispersion report config
Add to `[report]`:
```toml
[report]
dispersion_html = true
dispersion_lookback_days = 252
dispersion_show_components = true
dispersion_show_diagnostics = true
dispersion_smoothing_days = 3
```

## Testing Plan (Proportional to Density)

### Unit tests (pure math)
Deterministic synthetic cases:
1) Perfect lockstep: identical return series ⇒ lockstep near 100.
2) Two-cluster anti-lockstep: half up / half down ⇒ lockstep low, dispersion high.
3) Missing data: insufficient tickers/observations ⇒ scores become None, diagnostics correct.
4) PCA sanity: increasing common-factor strength increases `pc1_share`.

Property checks:
- `0 <= lockstep_score <= 100` when not None.
- `dispersion_score = 100 - lockstep_score`.

### Backfill + persistence tests
- Backfill writes dispersion metric keys alongside breadth keys.
- DB rows have correct `valid_count/missing_count`.

### Report tests
- Dispersion HTML includes the title + a known chart heading once.
- Main report includes a link/path to dispersion report when enabled.

## Calibration / Validation (How We Know It’s Not Nonsense)
Run a multi-year backfill and inspect:
- lockstep spikes during broad risk-off episodes and macro shock windows,
- lockstep drops during rotation/regime-change periods,
- component charts “explain” moves (corr_mean rises when lockstep rises; sign consensus correlates on directional days),
- data-quality charts explain gaps (valid_ticker_count dips around missing data).

Only after this do we enable advanced features (vol gate, tail, network).

## Rollout Plan (Minimize Blast Radius)
1) Compute + persist baseline dispersion headline + components (no new report yet).
2) Add backfill support so history exists.
3) Add dispersion HTML report artifact generation (separate file).
4) Add optional segmentation + volatility gating (behind config flags).
5) Add heterodox measures only with demonstrated incremental value.

## Open Questions (Decide Before Implementation)
1) Artifact naming: `security_scan_<run_id>_dispersion.html` vs `security_scan_dispersion_<run_id>.html`?
2) Should dispersion be enabled by default, or opt-in via `[aggregates.dispersion].enabled`?
3) For `disp_corr_mean_21d`, do we store raw `corr_mean` in [-1,1] or normalized [0,1]? (Report tickformat depends on this.)
4) Do we want “All / NASDAQ / SP100” for dispersion by default, or only “All” unless configured?
