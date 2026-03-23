# Security Scan Dispersion Aggregate Score Plan

## Motivation
The security scan already tracks breadth and trend-style aggregates, but it does not yet summarize co-movement across the universe. A dispersion aggregate fills that gap by answering:
- Are names moving in lockstep (high co-movement)?
- Are moves idiosyncratic and spread out (high dispersion)?
- Is co-movement behavior changing by horizon or market regime?

This plan defines a principled, extensible way to produce:
- A single daily aggregate score suitable for HTML charting.
- Optional companion component metrics for diagnostics.
- Multi-timeframe and regime-aware variants (up/down and volatility-gated).

## Terminology and Score Orientation
To remove ambiguity, we track both orientations:
- `lockstep_score` in `[0, 100]`: higher means stronger co-movement.
- `dispersion_score` in `[0, 100]`: higher means weaker co-movement (more dispersed).

Contract:
- `dispersion_score = 100 - lockstep_score`.
- Report headline can show either one; storage keeps both for clarity.

## Scope
In scope:
- Aggregate metric computation at scan runtime.
- Persistence in `security_aggregate_values`.
- HTML chart panel and markdown summary section.
- Configurable timeframes, methods, segmentation, and volatility gating.

Out of scope:
- Intraday-only dispersion modeling.
- External factor model dependencies.
- Changing existing indicator signal logic.

## Hard Parts First
The design must directly handle three hard problems:
1. Noise control: short windows can be unstable; low-vol days can produce misleading correlation estimates.
2. Missing/uneven data: not all symbols have full history each date.
3. Sign ambiguity: users may interpret “dispersion” as either spread or lockstep, so output orientation must be explicit.

If any implementation starts accumulating ad hoc exceptions for these, the model boundary is wrong and should be revisited.

## Candidate Measures (Standard + Heterodox)
Each measure produces `lockstep_component in [0, 1]` after normalization.

### 1. Pairwise Correlation Cohesion (Standard)
Definition:
- Build return matrix `R` for aligned symbols over window `W`.
- Compute pairwise correlations across symbols.
- `corr_mean = mean(corr_ij)` over valid pairs.
- Normalize: `lockstep_corr = (corr_mean + 1) / 2`.

Strengths:
- Direct measure of synchronized movement.
- Intuitive and well-known.

Weaknesses:
- Sensitive to outliers and low-vol regimes.
- Pairwise matrix can be noisy with few observations.

### 2. Cross-Sectional Return Dispersion (Standard)
Definition:
- For each date `t`, compute cross-sectional spread of same-day returns (prefer robust MAD).
- `disp_t = MAD_i(r_{i,t})` or `std_i(r_{i,t})`.
- Aggregate over window `W`: `disp_window = median_t(disp_t)`.
- Normalize against trailing baseline/percentile:
  - `disp_norm = clip(disp_window / disp_ref, 0, 1)`.
  - `lockstep_xs = 1 - disp_norm`.

Strengths:
- Captures breadth of idiosyncratic moves directly.
- Complements correlation (different failure mode).

Weaknesses:
- Needs robust baseline normalization to be comparable over time.

### 3. PCA First-Component Dominance (Standard)
Definition:
- On standardized returns in window `W`, compute PCA.
- `pc1_share = explained_variance_ratio_of_first_component`.
- `lockstep_pca = pc1_share`.

Strengths:
- Measures concentration into one “market mode”.
- Good structural complement to pairwise correlation.

Weaknesses:
- Can be unstable for tiny sample sizes.
- Requires minimum ticker/observation counts.

### 4. Directional Consensus / Entropy (Standard-Lightweight)
Definition:
- For each date, compute sign agreement:
  - `p_up = fraction(r_{i,t} > 0)`, `p_down = fraction(r_{i,t} < 0)`.
  - Binary entropy `H = -p_up log2 p_up - p_down log2 p_down` (ignore zeros).
- `lockstep_sign = 1 - H` (after scaling so max entropy maps near 0).

Strengths:
- Robust to magnitude outliers.
- Useful in turbulent sessions where direction dominates interpretation.

Weaknesses:
- Ignores return magnitude by design.

### 5. Tail Co-Movement / Exceedance Dependence (Heterodox)
Definition:
- Condition on market move days where `|r_mkt| > threshold`.
- Compute fraction of symbols moving same sign as market and/or tail correlation.
- `lockstep_tail` from exceedance agreement.

Strengths:
- Detects “everything moves together” stress episodes.

Weaknesses:
- Sparse samples; must enforce minimum event counts.

### 6. Correlation-Network Connectivity (Heterodox)
Definition:
- Build graph from pairwise correlations above threshold.
- Use giant-component ratio or average weighted degree as lockstep proxy.

Strengths:
- Captures nonlinear structural shifts in co-movement clusters.

Weaknesses:
- More parameters, harder to calibrate/explain.

## Recommended Baseline (Implement First)
Use a composite of Measures 1-4, then stage 5-6 as optional extensions.

Per-window lockstep:
- `L_W = 0.40 * lockstep_corr + 0.25 * lockstep_xs + 0.25 * lockstep_pca + 0.10 * lockstep_sign`.

Window mix:
- Windows: `W = {5, 21, 63}` trading days.
- Weights: `{0.45, 0.35, 0.20}` (short/medium/long).

Reliability weighting:
- For each window apply `reliability_W in [0,1]` based on:
  - valid ticker count coverage
  - valid pair coverage
  - available observations vs required window
- Final:
  - `lockstep_score_raw = sum(W_weight * reliability_W * L_W) / sum(W_weight * reliability_W)`.
  - `lockstep_score = round(100 * lockstep_score_raw, 2)`.
  - `dispersion_score = round(100 - lockstep_score, 2)`.

Fallback rule:
- If denominator is zero (insufficient data), emit `None` and set diagnostic counts.

## Timeframe Variations
All methods support multiple return horizons:
- Base daily horizon: `h=1`.
- Optional swing horizon: `h=5` non-overlapping or stepped returns.

Plan:
- Start with `h=1` for stability and lower complexity.
- Add `h=5` variant as optional `dispersion_h5_*` keys after baseline validation.

## Regime Segmentation and Volatility Gating
### Up/Down Segmentation
Compute optional segmented scores:
- Up days: `r_mkt_t > +theta`.
- Down days: `r_mkt_t < -theta`.
- `theta` default: `0` or volatility-scaled `k * sigma_mkt`.

Outputs:
- `disp_lockstep_up_score`
- `disp_lockstep_down_score`
- `disp_up_event_count`
- `disp_down_event_count`

Guardrail:
- Require `min_events` per segment; otherwise emit `None`.

### Volatility Gate
Optional gate so dispersion contributes only when movement is meaningful:
- Gate on rolling realized market volatility percentile or `|r_mkt| > k*sigma`.
- If gate is closed:
  - keep raw component diagnostics,
  - but freeze/exclude gated score from final composite.

This prevents quiet, micro-noise days from dominating co-movement interpretation.

## Output Contract (Aggregate Metric Keys)
Minimum baseline keys per universe/date:
- `disp_lockstep_score`
- `disp_dispersion_score`
- `disp_lockstep_5d`
- `disp_lockstep_21d`
- `disp_lockstep_63d`
- `disp_corr_mean_21d`
- `disp_xs_mad_21d`
- `disp_pca_pc1_share_21d`
- `disp_sign_consensus_21d`
- `disp_valid_ticker_count`
- `disp_valid_pair_count`
- `disp_observation_count`

Optional segmented/gated keys:
- `disp_lockstep_up_score`
- `disp_lockstep_down_score`
- `disp_gate_open` (1/0)
- `disp_gate_metric`

`valid_count`/`missing_count` semantics in storage:
- For score keys, `valid_count = disp_valid_ticker_count`.
- `missing_count = universe_ticker_count - disp_valid_ticker_count`.

## Config Design (`scan_settings.toml`)
Add a dedicated section:

```toml
[aggregates.dispersion]
enabled = true
return_horizons = [1]
windows = [5, 21, 63]
method_weights = { corr = 0.40, xs = 0.25, pca = 0.25, sign = 0.10 }
window_weights = { w5 = 0.45, w21 = 0.35, w63 = 0.20 }
min_tickers = 20
min_pair_coverage = 0.60
use_robust_xs_dispersion = true
volatility_gate_enabled = false
volatility_gate_lookback = 20
volatility_gate_percentile = 0.60
segment_up_down = true
segment_threshold_sigma = 0.0
segment_min_events = 8
```

Report tuning (optional):

```toml
[report]
dispersion_smoothing_days = 3
dispersion_show_components = true
```

## Implementation Architecture (File-Level)
### 1. New pure computation module
Add `src/backend/app/security_scan/dispersion.py`:
- `build_aligned_return_matrix(...)`
- `compute_dispersion_components(...)`
- `compute_dispersion_snapshot(...)`
- `to_aggregate_metrics(...)`

Design rules:
- Pure functions only; no DB/report imports.
- Input is close-series map by ticker and config.
- Output is plain dict metrics + diagnostics.

### 2. Scan runner integration
Update `src/backend/app/security_scan/scan_runner.py`:
- Collect per-ticker close series once during fetch loop.
- For each aggregate universe (`all`, `nasdaq`, `sp100`), compute dispersion metrics using that universe’s tickers.
- Merge dispersion metrics into existing `aggregates` dict before persistence.
- Extend history fetch metric set so dispersion history is included in payload refresh.

### 3. Config loader integration
Update `src/backend/app/security_scan/config_loader.py`:
- Add typed fields for dispersion config and defaults.
- Validate weights, windows, and thresholds.
- Keep backward compatibility when section is absent.

### 4. Chart series + Plotly group
Update `src/backend/app/security_scan/reporting/aggregate_series.py`:
- Add dispersion metric definitions to the series list.

Update `src/backend/app/security_scan/reporting/aggregate_charts.py`:
- Add new chart group, e.g. `dispersion_lockstep`.
- Plot `disp_lockstep_score` as primary line.
- Optionally overlay `disp_lockstep_5d/21d/63d` and up/down segmented lines.
- Reference line at `50` for visual regime split.

### 5. Markdown summary
Update `src/backend/app/security_scan/reporting/markdown_report.py`:
- Add `## Summary (Dispersion)` table with current, t-1, t-2, 10d avg.
- Include both lockstep and dispersion headline values to avoid interpretation drift.

### 6. History refresh path
Update `src/backend/app/security_scan/cli.py` and constants used for history refresh:
- Include dispersion metric keys in history retrieval (`BREADTH_HISTORY_METRICS` successor should cover breadth + dispersion).

## Backfill Strategy
Two rollout-compatible options:
- Option A (fast): no special backfill logic; historical lines build as scans run daily.
- Option B (complete): extend `build_backfill_aggregate_records` to compute dispersion per date from historical price windows.

Recommendation:
- Start with Option A to de-risk baseline implementation.
- Add Option B after baseline correctness tests pass.

## Testing Plan
### Unit tests (`src/backend/tests/test_security_scan.py`)
Add deterministic synthetic cases:
1. Perfect lockstep: all symbols identical returns -> high lockstep, low dispersion.
2. Perfect anti-lockstep mix: half up/half down with similar magnitude -> low lockstep, high dispersion.
3. Missing data: partial symbols/history -> score computed with reduced reliability, no crash.
4. Gate behavior: with volatility gate enabled, quiet window does not update gated score.
5. Up/down segmentation: up-only sample populates up score, down score stays `None` with correct event counts.

### Report/chart tests
Update tests to assert:
- New markdown summary section exists.
- Dispersion chart heading appears in HTML chart output.
- Series definitions include `disp_lockstep_score`.

### Property-style checks (low overhead)
For random return matrices:
- `0 <= lockstep_score <= 100`.
- `dispersion_score = 100 - lockstep_score`.
- Increasing common-factor strength should not decrease lockstep_score on average.

## Calibration and Validation
Calibration process:
- Run on a long historical sample.
- Inspect score behavior during known high-co-movement stress periods vs calmer rotational periods.
- Tune method/window weights only after observing stability and interpretability.

Acceptance criteria:
- Score is stable enough not to whipsaw on single noisy days.
- Score rises in broad risk-on/risk-off lockstep episodes.
- Score falls during cross-sectional rotation regimes.

## Risk and Blast Radius
Break blast radius:
- Low for core scan execution (additive aggregate keys).
- Medium for report/chart code paths (new sections and series groups).

Change blast radius:
- `scan_runner.py`, reporting modules, config loader, and tests will all change.
- Minimize risk by isolating math in one new pure module and keeping storage schema unchanged.

Reversibility:
- Fully reversible at code level; no destructive schema migration required.
- If needed, disable via config flag `aggregates.dispersion.enabled = false`.

## Rollout Options
1. Baseline only: composite (corr + xs + pca + sign), windows 5/21/63, no gating.
2. Baseline + segmentation: add up/down scores and event counts.
3. Full model: add volatility gate and one heterodox measure (`tail`), then evaluate.

Recommended order:
1. Implement Option 1.
2. Validate behavior and chart readability.
3. Add Option 2.
4. Add Option 3 only if incremental signal value is clear.

## Definition of Done
- Daily scan payload includes dispersion aggregate keys per universe.
- HTML report includes a dispersion chart panel with historical series.
- Markdown report includes a dispersion summary table.
- Tests cover computation, gating/segmentation logic, and report rendering.
- Config toggles allow enabling/disabling and tuning without code edits.
