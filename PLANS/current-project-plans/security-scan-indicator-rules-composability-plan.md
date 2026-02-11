# Security Scan: Composable Indicators + Rules (Proposal + Plan)

## Problem Statement
The current `security_scan` indicator framework mixes two different concepts:

- **Series computation**: turning OHLCV bars + context (benchmarks, etc.) into one or more named numeric time series.
- **Signal generation**: applying rules/conditions over those series to emit `Signal` rows.

Today:
- Some indicators (e.g. `roc`) compute a series and then use the generic criteria DSL (`criteria.py`) to emit signals.
- Other indicators (e.g. `qrs_consist_excess`) embed signal logic directly in the indicator module.
- Cross-indicator scans (e.g. `scl_ma2_qrs_ma1_breakout`) are implemented as a *new indicator* that imports other indicators and recomputes their series.

This creates architectural friction:
- Reporting/UI needs to explain “criteria” but many indicators do not use criteria at all.
- Composition across indicators requires writing new Python modules (coupling + duplication + recomputation).
- Scan logic that should be config-level (“A AND B AND C across different indicators”) becomes code-level (new indicator module).
- The “unit of configuration” is unclear (indicator instance vs rule set vs composite scan).

## Goals
- Make scan criteria **fully composable across indicators**:
  - Any rule can reference **any output series** from **any computation/indicator instance**
  - Composite criteria can combine **any set of series** from **any set of indicators** (e.g. `all_of` / `any_of` / gates), without writing a new Python indicator for each combination
- Avoid recomputation: compute each indicator’s series once per ticker, then evaluate many rules against that cached output.
- Keep the **narrow waist** small and stable: core data types + a minimal rule evaluation interface.
- Preserve **change agility**: add/modify signals via config rather than code for common cases.
- Constrain **blast radius**: introduce a v2 path behind config versioning; migrate incrementally.

## Non-Goals
- Build a full expression language.
- Rewrite storage/DB schema.
- Replace all custom logic with DSL on day one (some indicators will remain “custom” initially).

## Current State (Key Code)
- Indicator contract: each file in `src/backend/app/security_scan/indicators/` exports:
  - `INDICATOR_ID: str`
  - `evaluate(prices, settings) -> list[IndicatorSignal]`
- Generic criteria engine: `src/backend/app/security_scan/criteria.py`
  - Supports rule types: `crossover` (level), `threshold`, `direction`
- Orchestration: `src/backend/app/security_scan/scan_runner.py`
  - Calls each indicator’s `evaluate(...)` per ticker with a `_context` dict injected.

## Proposal (Recommended): Split Into “Computations” and “Rules”
### New Conceptual Model
1. **Computation (Series Provider)**
   - Input: prices + settings + context
   - Output: a `SeriesBundle` of named series (e.g. `roc`, `QRSConsistExcess`, `MA1`, `MA2`, `MA3`), plus optional metadata (warmup bars, dependencies).

2. **Rule (Signal Generator)**
   - Input: one or more series (by reference) + rule params
   - Output: `IndicatorSignal` events with `signal_date`, `signal_type`, `metadata`.

3. **Scan Spec**
   - A configuration that declares:
     - which computations to run
     - which rules to evaluate
     - optional composition (`all_of` / `any_of`) for multi-criteria scans

### Composability Guarantee (The Main Requirement)
For schema v2, “criteria” is not owned by any one indicator.

- Every computation instance exports one or more **named series**.
- Every rule references series by an explicit **series address**: `{ instance_id, series_name }`.
- Composite rules can combine sub-rules that reference **different instances** and **different series**.
- Composite rules can nest arbitrarily (`all_of`/`any_of`/gates), enabling any combination of any number of series across any number of indicators.

If a series exists in the catalog, it is eligible input to any supported rule primitive, regardless of which indicator produced it.

### Why This Flows Better
- Indicators stop being “special”: they compute series; everything else is rules.
- Rules become reusable across indicators (crossover/threshold/direction, etc.).
- Cross-indicator scans become config-level composition instead of a new Python indicator that imports others.

## Core Interfaces (Interface-First Sketch)
These are intentionally small; if they feel heavy at usage sites, redesign before implementing.

### Types
- `SeriesPoint { date: str, value: float }` (already exists)
- `Series { name: str, points: list[SeriesPoint] }`
- `SeriesBundle { by_name: dict[str, list[SeriesPoint]] }`
- `SeriesRef { instance_id: str, series: str }`
- `SeriesCatalog { by_instance_id: dict[str, SeriesBundle] }` (per ticker)
- `RuleResult = list[IndicatorSignal]`

### Computation Contract (v2)
- `compute_series(prices: list[dict[str, Any]], settings: dict[str, Any]) -> SeriesBundle`
  - Must be pure (no I/O); context is passed in `settings["_context"]` as today.
  - Must produce stable, documented series names.

### Rule Contract (v2)
- `evaluate_rule(series_catalog: SeriesCatalog, rule: RuleSpec) -> RuleResult`
  - Rules reference series by `SeriesRef` (series address).

## v2 Config Shape (Draft)
This is a proposal; it should be versioned to keep the old shape working.

```toml
[schema]
version = 2

# A built-in base computation should always exist (or be auto-injected)
# so rules can reference raw bar data too.
[[computations]]
id = "bars"
instance_id = "bars_1"

[[computations]]
id = "roc"
instance_id = "roc_1"
roc_lookback = 12

[[computations]]
id = "qrs_consist_excess"
instance_id = "qrs_1"
map1 = 7
map2 = 21
map3 = 56

[[computations]]
id = "scl_v4_x5"
instance_id = "scl_1"
lag1 = 2
lag2 = 3
lag3 = 4
lag4 = 5
lag5 = 11
cd_offset1 = 2
cd_offset2 = 3
ma_period1 = 5
ma_period2 = 11

[[rules]]
id = "roc_cross_zero"
source = { instance_id = "roc_1", series = "roc" }
type = "crossover_level"
level = 0
direction = "both"

[[rules]]
id = "qrs_ma1_cross_ma2"
type = "crossover_series"
left  = { instance_id = "qrs_1", series = "MA1" }
right = { instance_id = "qrs_1", series = "MA2" }
direction = "both"

[[rules]]
id = "dual_breakout_up"
type = "all_of"
children = [
  { type = "breakout_extreme", source = { instance_id="scl_1", series="MA2" }, window=12, direction="up" },
  { type = "breakout_extreme", source = { instance_id="qrs_1", series="MA1" }, window=5,  direction="up" },
]

[[rules]]
id = "example_multi_indicator_stack"
type = "all_of"
children = [
  # Uses raw bars:
  { type = "threshold", source = { instance_id="bars_1", series="close" }, op=">", level=50 },
  # Uses ROC output:
  { type = "crossover_level", source = { instance_id="roc_1", series="roc" }, level=0, direction="up" },
  # Uses QRS output:
  { type = "threshold", source = { instance_id="qrs_1", series="MA1" }, op=">", level=0 },
]
```

Notes:
- Keep rule types deliberately small and table-driven (no expression language).
- Composition uses `all_of` / `any_of` with child rule specs.

## Rule Primitives to Support (Minimal Set)
All rule primitives must accept `SeriesRef` inputs so they can be wired to outputs
from any computation instance (cross-indicator by design).

Start with primitives that remove today’s biggest pain (composition + reuse):
- `crossover_level` (existing `criteria.crossover`)
- `threshold` (existing)
- `direction` (existing)
- `crossover_series` (needed for MA1 vs MA2, etc.)
- `above_all` / `below_all` (needed for “main vs all MAs” regimes)
- `breakout_extreme` (needed for “prior N-bar high/low (excluding current)”)
- `streak_gate` or `min_consecutive` wrapper (needed for QRS 3-day zero-cross requirement)
- `all_of` / `any_of` composition

## Migration Plan (Incremental, Low Blast Radius)
### Phase 0: Clarify Reporting (Low Risk)
- Rename report column from “Criteria” to “Configured Criteria (DSL)” on the v1 path.
- Add a second column “Built-in Signals” listing emitted `signal_type`s for indicators that don’t use DSL (derived from observed signals in the run payload).

### Phase 1: Introduce v2 Data Structures (No Behavior Change)
- Add `series_bundle.py` with:
  - `SeriesPoint` reuse
  - helper to align series by date intersection
- Add a small `series_catalog` helper (per ticker) to store outputs by `instance_id`,
  so rule evaluation can reference any series across any computation instance.
- Add `rules/` module with parsing + skeleton evaluators.
- Add config parsing for `[schema.version=2]` without enabling it by default.

### Phase 2: Implement Rule Engine + Unit Tests
- Implement the minimal primitive set listed above.
- Unit tests should be table-driven:
  - date alignment edge cases
  - missing dates
  - warmup behavior (rules must simply “not emit” when required prior points are missing)
  - cross-indicator composition: a single composite rule referencing series from 2+ different instances

### Phase 3: Add “compute_series” to Existing Indicators (Parallel to v1)
For each indicator:
- Add `compute_series(...)` (pure) that returns its series bundle.
- Keep `evaluate(...)` working by calling either:
  - v1 built-in logic (unchanged), or
  - v2 rules, if v2 is enabled for that run.

Start with `roc` (already has a clean series + rule flow).

### Phase 4: Port QRS to Rules (Maintain Signal Parity)
- Ensure `qrs_consist_excess.compute_series` exports stable names:
  - `QRSConsistExcess`, `MA1`, `MA2`, `MA3`
- Re-express existing signals as rules:
  - 3-day zero-cross (as streak gate + crossover_level)
  - MA1/MA2 crossover (crossover_series)
  - regime transitions (above_all/below_all + optional regime predicate)
- Add golden tests that compare v1 vs v2 emitted `signal_type`s on synthetic series.

### Phase 5: Replace Cross-Indicator “Breakout” Indicator With Composite Rules
- Introduce separate computations for SCL + QRS series.
- Implement breakout via `breakout_extreme` + `all_of`.
- Keep the old `scl_ma2_qrs_ma1_breakout` indicator for a deprecation window:
  - mark as legacy in docs
  - optionally auto-map v1 config to v2 composite config to reduce manual migration

### Phase 6: Deprecate v1 “criteria inside indicator settings”
- For schema v2:
  - move rules out of `settings.criteria` into top-level `[[rules]]`
- For schema v1:
  - continue to support `settings.criteria` as-is.

## Hard Parts (Harshest Constraints First)
1. **Date alignment across series and computations**
   - Must be deterministic and explicit: rules operate on the *intersection* of dates for referenced series.
2. **Warmup and missing data**
   - Rules must handle “insufficient history” by emitting nothing (not errors) unless misconfigured.
3. **Config ergonomics**
   - Avoid forcing users to duplicate instance ids/series names everywhere; consider short refs like `"qrs_1.MA1"`.

## Blast Radius and Risk Controls
- Version-gate v2 via `[schema.version]`.
- Maintain v1 path untouched until v2 parity is proven.
- Add a “dual-run” validation mode:
  - run v1 and v2 for the same inputs and diff signals (dev-only).

## Validation Checklist
- Unit tests for each primitive rule type.
- Golden tests for QRS and ROC parity (signal types + dates on synthetic data).
- Run a real scan on a small ticker set and compare:
  - total signal count
  - per-indicator signal distribution
  - report metadata correctness (what ran, with what rules)

## Open Questions
- Should we rename the directory `indicators/` to `computations/` in v2, or keep the name and change semantics?
- Do we want rule definitions to support “named rulesets” reusable across scans, or keep everything inline initially?
- For composite rules, do we require same-day alignment by default (recommended), or allow windows (“within N days”)?
