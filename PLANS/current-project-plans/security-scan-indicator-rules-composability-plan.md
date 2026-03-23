# Security Scan: Composable Indicators, Aggregates, and Scans (Proposal + Plan)

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
- There is no first-class config concept for reusable **indicator aggregates** or named **scans**, so users duplicate wiring and cannot compose scan setups cleanly.

## Goals
- Make scan criteria **fully composable across indicators**:
  - Any rule can reference **any output series** from **any computation/indicator instance**
  - Composite criteria can combine **any set of series** from **any set of indicators** (e.g. `all_of` / `any_of` / gates), without writing a new Python indicator for each combination
- Avoid recomputation: compute each indicator’s series once per ticker, then evaluate many rules against that cached output.
- Keep the **narrow waist** small and stable: core data types + a minimal rule evaluation interface.
- Preserve **change agility**: add/modify signals via config rather than code for common cases.
- Make **indicator aggregates** and **scans** first-class config objects so users can declare, reuse, and adjust scan setups without Python changes.
- Keep the run/report contract stable enough for existing consumers during migration (explicit compatibility layer for v2 metadata + signal attribution).
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
- Config loading: `src/backend/app/security_scan/config_loader.py`
  - Today loads `[indicators].instances`, `[aggregates]`, `[report]`; no schema-v2/scan selection model yet.
- CLI + reporting are indicator-instance centric today:
  - `src/backend/app/security_scan/cli.py` runs one pass over all indicator instances (no `scan_id` selector).
  - `src/backend/app/security_scan/reporting/markdown_report.py` renders an “Indicator Instances” table and criteria from instance settings.

## Proposal (Recommended): Split Into “Computations”, “Rules”, “Indicator Aggregates”, and “Scans”
### New Conceptual Model
1. **Computation (Series Provider)**
   - Input: prices + settings + context
   - Output: a `SeriesBundle` of named series (e.g. `roc`, `QRSConsistExcess`, `MA1`, `MA2`, `MA3`), plus optional metadata (warmup bars, dependencies).

2. **Rule (Signal Generator)**
   - Input: one or more series (by reference) + rule params
   - Output: `IndicatorSignal` events with `signal_date`, `signal_type`, `metadata`.

3. **Indicator Aggregate (Reusable Wiring Unit)**
   - Input: references to computation outputs + optional rule refs
   - Output: a reusable named bundle (series aliases + default rules) for scan composition.

4. **Scan Spec**
   - A configuration that declares:
     - which indicator aggregates to include
     - which rule(s) define the scan “hit” (`root_rule_ref`)
     - which rules to emit (`emit_rule_refs`, defaulting to `[root_rule_ref]`)
     - optional composition (`all_of` / `any_of`) for multi-criteria scans
   - Computations are derived from the referenced `SeriesRef`s in the scan’s rule closure (no duplicated `computation_refs` lists).

### Composability Guarantee (The Main Requirement)
For schema v2, “criteria” is not owned by any one indicator.

- Every computation instance exports one or more **named series**.
- Every rule references series by an explicit **series address**: `{ instance_id, series_name }`.
- Indicator aggregates are config-only bundles that can alias those series and attach reusable rule refs.
- Composite rules can combine sub-rules that reference **different instances** and **different series**.
- Composite rules can nest arbitrarily (`all_of`/`any_of`/gates), enabling any combination of any number of series across any number of indicators.
- Scans can include any number of rule refs plus aggregate refs, so scan setup remains config-only.

If a series exists in the catalog, it is eligible input to any supported rule primitive, regardless of which indicator produced it.

### Why This Flows Better
- Indicators stop being “special”: they compute series; everything else is rules.
- Rules become reusable across indicators (crossover/threshold/direction, etc.).
- Cross-indicator scans become config-level composition instead of a new Python indicator that imports others.
- The config unit becomes explicit and stable: `computations` -> `indicator_aggregates` -> `scans`.

## Core Interfaces (Interface-First Sketch)
These are intentionally small; if they feel heavy at usage sites, redesign before implementing.

### Types
- `SeriesPoint { date: str, value: float }` (already exists)
- `Series { name: str, points: list[SeriesPoint] }`
- `SeriesBundle { by_name: dict[str, list[SeriesPoint]] }`
- `SeriesRef { instance_id: str, series: str }` (config should also accept shorthand `"instance_id.series"`)
- `SeriesCatalog { by_instance_id: dict[str, SeriesBundle] }` (per ticker)
- `ComputationManifest { computation_id: str, output_series: list[str], required_context_keys: list[str] }`
- `RuleSpec` (primitive or composite; composites may include `{ ref: "rule_id" }` children)
- `IndicatorAggregateSpec { id: str, series_aliases: dict[str, SeriesRef], rule_refs: list[str] }`
- `ScanSpec { id: str, aggregate_refs: list[str], root_rule_ref?: str, emit_rule_refs?: list[str], default?: bool }`
- `RuleResult = list[IndicatorSignal]`

### Computation Contract (v2)
- `compute_series(prices: list[dict[str, Any]], settings: dict[str, Any]) -> SeriesBundle`
  - Must be pure (no I/O); context is passed in `settings["_context"]` as today.
  - Must produce stable, documented series names.
- `get_manifest() -> ComputationManifest`
  - Declares output series names + required context keys so config refs can be validated before runtime.

### Rule Contract (v2)
- `evaluate_rule(series_catalog: SeriesCatalog, rule: RuleSpec) -> RuleResult`
  - Rules reference series by `SeriesRef` (series address).

## Rule Semantics (Make Composition Practical)
Composable scans need two things that v1 never had to make explicit:

1. **A rule can be used for gating without being emitted**
   - Example: `pos_regime = all_of(MA1>0, MA2>0, MA3>0)` is a *useful predicate* but extremely noisy as an emitted signal.
   - Schema v2 should treat “evaluate” and “emit” as separate concerns:
     - the engine evaluates the full closure of rules needed to decide scan hits
     - the scan chooses which rule ids are actually emitted as `signals`

2. **Rules are events, some are “state-like”**
   - Some primitives are “event-like” (e.g. `crossover_*` emits on the crossing bar).
   - Some primitives are “state-like” (e.g. `threshold` emits on every bar that satisfies it).
   - This is OK *as long as* scan configs can avoid emitting the noisy state rules and use them only as inputs to composites.

### Emission Model (Pit of Success Defaults)
- Each `[[scans]]` declares a **root rule** (`root_rule_ref`) that represents the scan’s “hit”.
- Each `[[scans]]` may optionally declare `emit_rule_refs`:
  - If omitted: default to emitting only `root_rule_ref` (single, high-signal output)
  - If present: emit exactly those rule ids (useful for debugging / richer reports)
- Indicator aggregates may contribute *default rule refs* (reusable building blocks), but **emission remains scan-controlled** to keep output intentional.

## v2 Config Shape (Draft, Config-First for Aggregates + Scans)
This is a proposal; it should be versioned to keep the old shape working.

```toml
[schema]
version = 2
# If multiple scans exist and CLI doesn't specify `--scan-id`, require exactly one default.
default_scan_id = "trend_breakout_scan"

[aggregates]
# Existing market breadth config remains first-class.
advance_decline_lookbacks = [1, 5, 10]

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
id = "trend_breakout_hit"
type = "all_of"
children = [
  { ref = "roc_cross_zero" },
  { ref = "dual_breakout_up" },
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

[[indicator_aggregates]]
id = "qrs_trend_pack"
series_aliases = [
  { alias = "qrs_main", source = { instance_id = "qrs_1", series = "QRSConsistExcess" } },
  { alias = "qrs_fast", source = { instance_id = "qrs_1", series = "MA1" } },
  { alias = "qrs_slow", source = { instance_id = "qrs_1", series = "MA2" } },
]
rule_refs = ["qrs_ma1_cross_ma2"]

[[indicator_aggregates]]
id = "scl_breakout_pack"
series_aliases = [
  { alias = "scl_ma2", source = { instance_id = "scl_1", series = "MA2" } },
]
rule_refs = ["dual_breakout_up"]

[[scans]]
id = "trend_breakout_scan"
description = "Reusable scan composed from indicator aggregates + rule refs"
aggregate_refs = ["qrs_trend_pack", "scl_breakout_pack"]
root_rule_ref = "trend_breakout_hit"
# Optional: emit more than just the scan hit (useful for debugging / richer reports).
emit_rule_refs = ["trend_breakout_hit", "roc_cross_zero", "dual_breakout_up"]

[[scans]]
id = "momentum_only_scan"
aggregate_refs = []
root_rule_ref = "roc_cross_zero"
# emit_rule_refs omitted => emit only the root rule by default.
```

Notes:
- Keep rule types deliberately small and table-driven (no expression language).
- Composition uses `all_of` / `any_of` with child rule specs.
- `[aggregates]` keeps market-breadth settings; `[[indicator_aggregates]]` is for indicator-series/rule bundles.
- `[[scans]]` is the runnable unit so adding or changing scans is config-only.
- `indicator_aggregates[*].rule_refs` should be treated as “recommended building blocks” (useful for reports/docs); they are not automatically emitted unless the scan includes them in `emit_rule_refs` (directly or via the scan’s root rule closure).

### Config Invariants (Must Validate at Load Time)
- Config mode must be unambiguous:
  - schema v1 accepts `[indicators].instances` + optional `settings.criteria`
  - schema v2 accepts `[[computations]]`/`[[rules]]`/`[[indicator_aggregates]]`/`[[scans]]`
  - mixed-mode config should fail validation with a clear migration error.
- In schema v2, `computations[*].instance_id` must be present and unique (no auto-generated ids; it’s the stable reference key).
- `rule.id`, `indicator_aggregates.id`, and `scans.id` must each be unique in their namespace.
- Every reference (`aggregate_refs`, `root_rule_ref`, `emit_rule_refs`, aggregate/rule refs, `SeriesRef`) must resolve.
- Every referenced `series` must exist in the referenced computation’s manifest.
- Any recursive composition (`rule refs`, `root_rule refs`) must be cycle-free.
- If more than one scan is defined, runtime selection must be explicit (CLI arg or configured default), never implicit.
- Context-dependent computations (e.g. benchmark-dependent QRS) must declare required context keys and fail fast if missing.
- Each scan must have a single unambiguous “hit”:
  - either `root_rule_ref` is set, or `emit_rule_refs` is non-empty (recommend `root_rule_ref` always).
  - if multiple scans exist and no `--scan-id` is provided: exactly one must be marked as default (`[schema].default_scan_id` or `scan.default=true`).

## v2 Config Compilation (Data-First, Low Glue)
To keep blast radius small and behavior predictable, schema v2 should introduce one “narrow waist” object: a compiled, fully-resolved scan plan.

### Compiler Output: `CompiledScanPlan`
At minimum:
- `schema_version`
- `scan_id`
- `scan_description`
- `emitted_rule_ids` (after defaulting)
- `evaluated_rule_ids` (closure of root + emitted + dependencies)
- `required_computation_instance_ids` (derived from `SeriesRef`s referenced by evaluated rules)
- `required_context_keys` (union from computation manifests)

Optional but useful:
- `resolved_rules_by_id` (normalized `RuleSpec` trees with refs resolved to ids)
- `resolved_aggregates` (expanded series aliases + rule refs)
- `validation_warnings` (non-fatal, e.g., unused computations/rules)

### Compile Algorithm (Deterministic)
1. **Select scan**
   - Resolve `scan_id` from CLI `--scan-id` or `[schema].default_scan_id` / `scan.default`.
2. **Validate uniqueness**
   - Enforce unique `instance_id`, `rule.id`, `indicator_aggregates.id`, `scans.id`.
3. **Resolve computation manifests**
   - Load registry of computations (initially from `indicators/`) and fetch `get_manifest()` for each `computations[*].id`.
   - Fail fast on unknown computation ids.
4. **Validate rules (local)**
   - Validate `rule.type` is supported.
   - Validate every `SeriesRef` points at a declared computation instance and a manifest-declared series name.
   - Validate `ref` children point at existing `[[rules]].id`.
5. **Validate rule graph**
   - Build dependency graph from `{ ref = "..." }` edges.
   - Detect cycles and report the cycle path (actionable error).
6. **Default emission**
   - `emit_rule_refs = scan.emit_rule_refs or [scan.root_rule_ref]`.
   - If both are empty, fail config validation (scan has no output).
7. **Compute rule closure**
   - Compute `evaluated_rule_ids` as the transitive closure of emitted rule ids and their dependencies.
8. **Derive required computations**
   - Walk all evaluated rules and collect referenced `SeriesRef.instance_id`.
   - Add any implicitly-required base computation (e.g., `bars`) if referenced.
9. **Context requirements**
   - Union `required_context_keys` from manifests for required computations.
   - Fail fast if runner cannot provide required keys (or if config cannot provide required context policy).

This compilation step is also the natural place to produce human-friendly errors:
`rule_id`, config path, available series names, and a clear “how to fix” suggestion.

## Execution Semantics (Must Lock Before Build)
- **Scan selection**:
  - If exactly one `[[scans]]` entry exists, run it by default.
  - If multiple scans exist, require explicit selection (`--scan-id`) unless a default is configured.
- **Compile/validate before fetch**:
  - Parse and validate the full config graph (`scan -> aggregate -> rule -> series`) before fetching market data.
  - Misconfiguration is a hard error; data gaps remain per-ticker issues.
- **Evaluate vs emit**:
  - Evaluate the full closure of rules needed by the selected scan (root + emitted + their dependencies).
  - Emit `signals` for `emit_rule_refs` only (defaulting to `[root_rule_ref]`).
- **Signal attribution compatibility**:
  - v2 signals must include stable source identity (`scan_id`, `rule_id`) while preserving backwards-compatible fields for existing report/JSON consumers.
- **Duplicate + ordering policy**:
  - Define and enforce deterministic ordering (date asc, then source id, then signal type).
  - Define dedupe key explicitly (recommended: `ticker + signal_date + scan_id + rule_id + signal_type`).
- **Failure containment**:
  - Config/rule graph errors fail the run early.
  - Per-ticker compute errors are recorded in `issues` and do not stop other tickers.

## Rule Primitives to Support (Minimal Set)
All rule primitives must accept `SeriesRef` inputs so they can be wired to outputs
from any computation instance (cross-indicator by design).

Start with primitives that remove today’s biggest pain (composition + reuse):
- `crossover_level` (existing `criteria.crossover`)
- `threshold` (existing)
- `direction` (existing)
- `crossover_series` (needed for MA1 vs MA2, etc.)
- `above_all` / `below_all` (needed for “main vs all MAs” regimes; often used as non-emitted gating rules)
- `breakout_extreme` (needed for “prior N-bar high/low (excluding current)”)
- `crossover_level` should support an optional confirmation window (e.g. `confirm_bars=3`) to express QRS’s “3-day zero-cross” without introducing a generic streak DSL prematurely.
- `all_of` / `any_of` composition

## Migration Plan (Incremental, Low Blast Radius)
### Phase 0: Clarify Reporting (Low Risk)
- Rename report column from “Criteria” to “Configured Criteria (DSL)” on the v1 path.
- Add a second column “Built-in Signals” listing emitted `signal_type`s for indicators that don’t use DSL (derived from observed signals in the run payload).
- Add baseline snapshot tests for current JSON/markdown fields so v2 compatibility changes are intentional.

### Phase 1: Introduce v2 Data Structures (No Behavior Change)
- Add `series_bundle.py` with:
  - `SeriesPoint` reuse
  - helper to align series by date intersection
- Add a small `series_catalog` helper (per ticker) to store outputs by `instance_id`,
  so rule evaluation can reference any series across any computation instance.
- Add `rules/` module with parsing + skeleton evaluators.
- Add config parsing + validation for `[schema.version=2]`, `[[computations]]`, `[[rules]]`,
  `[[indicator_aggregates]]`, and `[[scans]]` without enabling execution by default.
- Add a config compile step that resolves refs, checks uniqueness, validates series names via computation manifests, and fails fast on unresolved refs/cycles.
  - Compiler should also derive:
    - which computation instances are required by the selected scan (from `SeriesRef`s in the rule closure)
    - which rule ids are evaluated vs emitted (per scan `emit_rule_refs` defaulting rules)

### Phase 2: Implement Rule Engine + Unit Tests
- Implement the minimal primitive set listed above.
- Unit tests should be table-driven:
  - date alignment edge cases
  - missing dates
  - warmup behavior (rules must simply “not emit” when required prior points are missing)
  - cross-indicator composition: a single composite rule referencing series from 2+ different instances
  - config graph validation: `scan -> aggregate -> rule -> series` references resolve with clear errors when invalid
  - deterministic ordering + dedupe behavior for overlapping rule emissions

### Phase 3: Runner + CLI Wiring for Scan Selection
- Add scan execution path in `scan_runner` for schema v2:
  - compute required computation instances once per ticker
  - evaluate the scan’s rule closure, then emit only `emit_rule_refs`
- Add CLI selection support (e.g., `--scan-id`) and default-scan behavior.
- Emit explicit v2 run metadata:
  - `schema_version`, `scan_id`, derived `computation_instance_ids`, `aggregate_refs`, `evaluated_rule_ids`, `emitted_rule_ids`
  - compatibility metadata needed by existing reports/consumers.

### Phase 4: Add “compute_series” to Existing Indicators (Parallel to v1)
For each indicator:
- Add `compute_series(...)` (pure) that returns its series bundle.
- Add `get_manifest()` declaring stable output series names and required context keys.
- Keep `evaluate(...)` working by calling either:
  - v1 built-in logic (unchanged), or
  - v2 rules, if v2 is enabled for that run.

Start with `roc` (already has a clean series + rule flow).

### Phase 5: Port QRS to Rules (Maintain Signal Parity)
- Ensure `qrs_consist_excess.compute_series` exports stable names:
  - `QRSConsistExcess`, `MA1`, `MA2`, `MA3`
- Re-express existing signals as rules:
  - 3-day zero-cross (via `crossover_level` with `confirm_bars=3`)
  - MA1/MA2 crossover (crossover_series)
  - regime transitions (above_all/below_all + optional regime predicate)
- Add golden tests that compare v1 vs v2 emitted `signal_type`s on synthetic series.

### Phase 6: Replace Cross-Indicator “Breakout” Indicator With Composite Rules
- Introduce separate computations for SCL + QRS series.
- Implement breakout via `breakout_extreme` + `all_of`.
- Provide a default `indicator_aggregate` + `scan` config example that replaces current breakout indicator instances.
- Keep the old `scl_ma2_qrs_ma1_breakout` indicator for a deprecation window:
  - mark as legacy in docs
  - optionally auto-map v1 config to v2 composite config to reduce manual migration

### Phase 7: Report/Docs Migration + Deprecate v1 Indicator-Only Wiring
- Update markdown/html report sections to render scan-centric metadata when `schema.version=2`, while preserving v1 indicator-instance rendering.
- Update CLI/README examples to show `[[indicator_aggregates]]` + `[[scans]]` and scan selection.
- For schema v2:
  - move rules out of `settings.criteria` into top-level `[[rules]]`
  - declare reusable wiring in `[[indicator_aggregates]]`
  - declare runnable scans in `[[scans]]`
- For schema v1:
  - continue to support `settings.criteria` as-is.

## Hard Parts (Harshest Constraints First)
1. **Date alignment across series and computations**
   - Must be deterministic and explicit: rules operate on the *intersection* of dates for referenced series.
2. **Warmup and missing data**
   - Rules must handle “insufficient history” by emitting nothing (not errors) unless misconfigured.
3. **Config ergonomics**
   - Avoid forcing users to duplicate instance ids/series names everywhere; consider short refs like `"qrs_1.MA1"`.
   - Avoid noisy configs: scan must make it easy to use rules for gating without emitting them.
4. **Reference graph correctness**
   - `scan -> aggregate -> rule -> series` validation must fail fast with actionable errors (missing id, unknown series, cycles).
5. **Signal attribution + compatibility**
   - Need explicit mapping from rule/scan identity to existing `signals` payload fields to avoid breaking downstream consumers.
6. **Execution selection semantics**
   - Multiple scans per config require deterministic/default selection rules and CLI UX (`--scan-id`).

## Blast Radius and Risk Controls
- Version-gate v2 via `[schema.version]`.
- Maintain v1 path untouched until v2 parity is proven.
- Keep current `[aggregates]` semantics for market metrics unchanged while introducing `[[indicator_aggregates]]`.
- Preserve top-level output shape (`run_metadata`, `signals`, `issues`, aggregates payloads) while adding v2 fields.
- Add a “dual-run” validation mode:
  - run v1 and v2 for the same inputs and diff signals (dev-only).

## Validation Checklist
- Unit tests for each primitive rule type.
- Config parsing/validation tests for `[[indicator_aggregates]]` and `[[scans]]`.
- Config compile tests for uniqueness, unresolved refs, unknown series names, and cycle detection.
- Golden tests for QRS and ROC parity (signal types + dates on synthetic data).
- End-to-end scan selection tests:
  - one-scan config auto-select
  - multi-scan config requires explicit/default selection
- Output compatibility tests:
  - existing report sections still render for v1
  - v2 run metadata includes selected scan + rule provenance
- Run a real scan on a small ticker set and compare:
  - total signal count
  - per-indicator signal distribution
  - report metadata correctness (what scan ran, which aggregates/rules/computations were active)

## Open Questions
- Should we rename the directory `indicators/` to `computations/` in v2, or keep the name and change semantics?
- Should we keep `[aggregates]` for market breadth and add `[[indicator_aggregates]]`, or rename market settings to `[market_aggregates]` in v2 for clarity?
- Do we want rule definitions to support “named rulesets” reusable across scans, or keep everything inline initially?
- For composite rules, do we require same-day alignment by default (recommended), or allow windows (“within N days”)?
- For v2 signal rows, should compatibility fields map as `indicator_id=scan_id` and `indicator_type=rule`, or keep legacy indicator naming with additional provenance fields?

### Recommended Defaults (to reduce friction + blast radius)
- Keep the directory name `indicators/` for now and evolve the contract in-place (`compute_series` + `get_manifest`) to avoid a wide rename rippling through imports/tests.
- Keep `[aggregates]` as market breadth settings (unchanged) and introduce `[[indicator_aggregates]]` for the new concept; avoid renaming existing config tables during the v2 rollout.
- Prefer same-day alignment only; “within N days” turns this into a higher-density temporal query engine and can be added later as a separate, explicit feature.
- For v2 signals, map compatibility fields as:
  - `Signal.indicator_type = scan_id`
  - `Signal.indicator_id = rule_id`
  - and include `scan_id`, `rule_id`, `rule_type`, `schema_version` in `metadata` for explicit provenance and easy migration of downstream consumers.
