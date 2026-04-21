# Security Scan Indicator Dashboard Plan

## Goal
Build a dynamic local web dashboard for testing security-scan indicators against an underlying ticker's price history. The first version should let a user choose an indicator type, edit its hyperparameters, recompute on demand, and inspect a two-panel chart with close price on top and one or more indicator traces below.

This is a development and research workbench, not a static scan report. It should establish the frontend/backend path we can later reuse for a dynamic screener dashboard.

## Requirements
- Serve the dashboard through the existing local web app stack rather than generating static HTML.
- Add a new frontend page under the existing Next.js app.
- Add backend API endpoints under the existing FastAPI app.
- Recompute indicator series from fetched historical market data using the same normalized price path as the security scan.
- Start with a smaller set of indicators, then expand to all current indicators.
- Allow indicator type selection, not only configured scan instances.
- Allow live hyperparameter edits and recompute.
- Persist top-5 most recently used indicator selections in browser `localStorage`.
- Include controls for ticker, date range/lookback, interval, benchmark tickers, indicator type, and indicator hyperparameters.
- Plot close price in the top panel.
- Plot one or more indicator traces in the bottom panel.
- Keep exactly two chart panels for the initial implementation; later versions may support 1-3 extra indicator panels.
- Overlay signal markers where meaningful:
  - shared vertical markers across panels by signal date
  - colored marker symbols on indicator traces
  - hover metadata for signal details
- Defer candlestick/OHLC price display to a later enhancement.

## Assumptions
- The frontend remains `src/frontend`, currently a Next.js 15 + React 19 app using client-side API calls and `react-plotly.js`.
- The backend remains `src/backend/app`, currently a FastAPI app on port `8003`.
- The dashboard route can be added as a normal app page, for example `src/frontend/app/security-scan/indicators/page.tsx`.
- The first backend endpoints can live under a new router such as `src/backend/app/routes/security_scan.py`, included by `app.main`.
- The first implementation uses daily historical bars. The API should keep `interval` in the request contract so intraday can be added later without a breaking change.
- Browser `localStorage` is acceptable for per-browser MRU state. There is no need for server-side user/session state.
- The initial indicator set should prioritize indicators that expose or can cleanly expose full series with low blast radius: `roc`, `roc_aggregate`, and `scl_v4_x5`.
- QRS-based indicators require benchmark context (`SPY`, `QQQ`, `IWM` by default). They should be planned in phase 2 unless the first implementation explicitly needs them.
- Hyperparameter editing should be schema-driven by backend metadata, not manually duplicated in frontend components per indicator.

## Current Context
- Indicator modules live in `src/backend/app/security_scan/indicators`.
- The production registry in `indicators/__init__.py` discovers modules with `INDICATOR_ID` and `evaluate(prices, settings)`.
- The production indicator contract returns `list[IndicatorSignal]`, which is sufficient for scans but not enough for charting full series.
- Several modules already have reusable compute helpers:
  - `roc` has private close extraction and ROC series helpers.
  - `roc_aggregate` has private ROC, aggregate score, and SMA helpers.
  - `scl_v4_x5` exposes `scl_v4_x5()` and `compute_countdown_series()`.
  - `qrs_consist_excess` computes rich output traces but requires benchmark price context.
  - `scl_ma2_qrs_ma1_breakout` composes SCL and QRS series and also requires benchmark context.
- The existing frontend already uses `react-plotly.js` dynamically to avoid SSR issues.
- Existing API calls use `src/frontend/lib/api/apiClient.ts`.
- Existing pages use Tailwind utility classes and client components.

## Hardest Parts
1. **Series contract gap**
   Production indicators emit signals, not the full series needed by charts. Pushing chart behavior into `evaluate()` would overload the scan contract and increase production blast radius.

2. **Editable hyperparameters**
   The frontend needs to render controls safely for each indicator. Hand-building fields in React for each indicator would duplicate backend defaults and drift quickly.

3. **Context-sensitive indicators**
   QRS and composite indicators need benchmark prices aligned with the ticker dates. This is a real data dependency, not a UI special case.

4. **Future screener reuse**
   The indicator dashboard should not become a one-off tool. The API shape should be suitable for a future dynamic screener page that reuses metadata, fetch/recompute services, and chart payload contracts.

## Friction Assessment
The natural shape is a small backend workbench layer beside the scan runner:

- **Production scan path** keeps `evaluate(prices, settings) -> signals`.
- **Dashboard path** uses explicit visualization adapters that return trace data, signals, defaults, and parameter schemas.
- **Frontend** stays generic: it asks for available indicators, renders fields from metadata, posts a compute request, and charts returned traces.

This avoids three friction signals:

- no special-case React forms per indicator
- no leaking dashboard concerns into production scan evaluation
- no duplicated indicator math in TypeScript

The cost is one new adapter contract. That cost is justified because it handles at least three concrete cases immediately: indicator metadata, editable parameter fields, and multi-trace chart payload assembly.

## Design Options

### Option A - Add a Dynamic Page that Calls Existing `evaluate()` Only
Use existing indicators as-is, call `evaluate()`, and plot only signals plus price.

Pros:
- Lowest backend code.
- Minimal effect on current scan modules.

Cons:
- Does not satisfy the main visualization need because full indicator traces are unavailable.
- Forces awkward frontend/chart special cases.
- Makes hyperparameters discoverability weak.

Friction:
- High. The current contract is signal-oriented, and the dashboard needs series-oriented output.

### Option B - Expand Every Indicator `evaluate()` Return Value
Change indicator evaluation to return both signals and visualization series.

Pros:
- One indicator contract.
- No separate adapter registry.

Cons:
- High production blast radius.
- Requires touching every scan caller and test that assumes signal-only output.
- Couples report/debug visualization behavior to the load-bearing scan path.

Friction:
- High. This turns a narrow production command into a mixed command/query API.

### Option C - Add Indicator Dashboard Adapters Beside the Scan Contract
Create a new backend adapter layer for dashboard usage. Each adapter declares:

- indicator id and label
- parameter schema and defaults
- required price fields
- benchmark requirements
- function to compute chart traces and signals from normalized prices

Pros:
- Keeps scan behavior stable.
- Gives frontend a schema-driven control surface.
- Lets indicators be added incrementally.
- Supports future screener dashboard APIs without forcing static report conventions.

Cons:
- Adds one new contract to maintain.
- Some indicators may temporarily use private helper functions until shared pure compute functions are extracted.

Friction:
- Low. This matches the data needs directly and isolates dynamic dashboard concerns.

Decision: proceed with Option C.

## Proposed Architecture

### Backend Modules
Add a small dashboard/workbench layer under security scan:

- `src/backend/app/security_scan/indicator_workbench.py`
  - Public service functions for listing indicators and computing dashboard payloads.
  - Owns input validation, fetch orchestration, benchmark context assembly, and adapter dispatch.

- `src/backend/app/security_scan/indicator_adapters.py`
  - Registry of visualization adapters.
  - Starts with `roc`, `roc_aggregate`, and `scl_v4_x5`.
  - Later adds `qrs_consist_excess` and `scl_ma2_qrs_ma1_breakout`.

- `src/backend/app/routes/security_scan.py`
  - FastAPI router for dashboard endpoints.
  - Included from `src/backend/app/main.py`.

Potential later split:
- If `indicator_adapters.py` grows beyond a cohesive file, move adapters into `src/backend/app/security_scan/indicator_adapters/`.
- Do not split prematurely. Start with one module until the adapter shape proves itself across at least three indicators.

### Backend API
Add two initial endpoints:

#### `GET /security-scan/indicators`
Returns metadata for available dashboard-supported indicator types.

Example response shape:

```json
{
  "indicators": [
    {
      "id": "roc",
      "label": "Rate of Change",
      "description": "Close-to-close rate of change over N bars.",
      "default_settings": {
        "roc_lookback": 12,
        "criteria": []
      },
      "parameters": [
        {
          "key": "roc_lookback",
          "label": "ROC Lookback",
          "type": "integer",
          "default": 12,
          "min": 1,
          "required": true
        }
      ],
      "requires_benchmarks": false,
      "supported_intervals": ["day"]
    }
  ]
}
```

#### `POST /security-scan/indicator-dashboard/compute`
Computes price, indicator traces, and signals for one ticker/indicator/settings request.

Example request shape:

```json
{
  "ticker": "AAPL",
  "indicator_id": "roc_aggregate",
  "settings": {
    "roc_lookbacks": [5, 10, 20],
    "roc_change_lookbacks": [1, 3, 5],
    "ma_short": 5,
    "ma_long": 20
  },
  "start_date": "2025-01-01",
  "end_date": "2026-04-18",
  "interval": "day",
  "benchmark_tickers": ["SPY", "QQQ", "IWM"]
}
```

Example response shape:

```json
{
  "ticker": "AAPL",
  "indicator_id": "roc_aggregate",
  "resolved_settings": {
    "roc_lookbacks": [5, 10, 20],
    "roc_change_lookbacks": [1, 3, 5],
    "ma_short": 5,
    "ma_long": 20
  },
  "date_range": {
    "start_date": "2025-01-01",
    "end_date": "2026-04-18",
    "interval": "day"
  },
  "price": {
    "label": "AAPL Close",
    "points": [
      {"date": "2025-01-02", "value": 243.85}
    ]
  },
  "indicator": {
    "panels": [
      {
        "id": "main",
        "label": "ROC Aggregate",
        "traces": [
          {
            "key": "score",
            "label": "Score",
            "points": [{"date": "2025-01-02", "value": 3.0}]
          }
        ],
        "reference_lines": [0.0]
      }
    ]
  },
  "signals": [
    {
      "date": "2025-02-03",
      "type": "cross_above_both",
      "label": "cross_above_both",
      "target_trace": "score",
      "metadata": {}
    }
  ],
  "diagnostics": {
    "price_points": 320,
    "indicator_points": 288,
    "benchmark_tickers_used": []
  }
}
```

The `indicator.panels` array is intentionally future-compatible. Phase 1 returns one indicator panel, but later versions can add more panels without changing the top-level response shape.

### Adapter Contract
Use a simple data-first adapter structure rather than classes unless behavior demands it.

Conceptual shape:

```python
@dataclass(frozen=True)
class IndicatorDashboardAdapter:
    id: str
    label: str
    description: str
    parameters: list[IndicatorParameter]
    default_settings: dict[str, Any]
    requires_benchmarks: bool
    compute: Callable[[IndicatorDashboardInput], IndicatorDashboardOutput]
```

Validation rules:
- Required parameters must be present after defaults are applied.
- Numeric parameters must be parsed and range-checked before compute.
- List parameters must be parsed as typed lists, not comma-split ad hoc in indicator code.
- Unknown parameter keys should be rejected in strict mode, or returned as warnings in permissive mode. Phase 1 should prefer strict rejection for clarity.

### Frontend Modules
Add the dashboard page and local API wrapper:

- `src/frontend/app/security-scan/indicators/page.tsx`
  - Client page for the workbench.

- `src/frontend/lib/api/securityScanApi.ts`
  - `getIndicatorMetadata()`
  - `computeIndicatorDashboard(request)`

- Optional component split after the first concrete page works:
  - `src/frontend/components/security-scan/IndicatorSelector.tsx`
  - `src/frontend/components/security-scan/IndicatorParameterForm.tsx`
  - `src/frontend/components/security-scan/IndicatorDashboardChart.tsx`
  - `src/frontend/components/security-scan/MruIndicatorStrip.tsx`

Keep the first implementation cohesive. Split components when the page starts carrying separate concerns, not before.

### Frontend UX
Target audience: indicator/screener development. The dashboard should prioritize dense, fast comparison over marketing-style presentation.

Initial layout:
- Top control band:
  - ticker input
  - start/end date or lookback preset
  - interval selector, daily only enabled initially
  - benchmark tickers input
  - recompute button
- Indicator selection row:
  - top-5 MRU buttons from `localStorage`
  - full indicator dropdown
- Hyperparameter panel:
  - schema-driven fields
  - numeric inputs for ints/floats
  - list input for integer lists
  - checkbox/toggle for booleans when needed
  - reset-to-defaults action
- Chart area:
  - Plotly subplot with shared x-axis
  - top row: close price
  - bottom row: indicator traces
  - vertical signal markers spanning both rows
  - indicator trace signal markers with hover metadata
- Diagnostics strip:
  - price point count
  - indicator point count
  - benchmark tickers used
  - warnings/errors

Use a restrained data-terminal aesthetic consistent with a research dashboard:
- high information density
- clear hierarchy
- low visual noise
- strong hover states and readable legends
- no landing page or explanatory marketing sections

### MRU Behavior
Persist MRU in browser `localStorage`.

Suggested key:

```text
optionstrat.securityScan.indicatorDashboard.mru.v1
```

Value:

```json
[
  {
    "indicator_id": "roc_aggregate",
    "label": "ROC Aggregate",
    "last_used_at": "2026-04-18T12:00:00.000Z"
  }
]
```

Rules:
- Update after successful compute, not merely selection.
- Deduplicate by `indicator_id`.
- Keep most recent 5.
- If metadata no longer contains an MRU indicator, hide it rather than showing a broken button.

## Implementation Phases

### Phase 0 - Contract Spike
Purpose: prove the backend response shape and chart data model before building broad UI.

Status: complete as of 2026-04-19 00:10 PDT for the initial `roc` adapter.

Tasks:
1. Complete - define Pydantic request/response models for indicator metadata and compute payloads.
2. Complete - implement the adapter dataclasses/types.
3. Complete - add metadata and compute adapters for `roc`.
4. Complete - add `GET /security-scan/indicators`.
5. Complete - add `POST /security-scan/indicator-dashboard/compute`.
6. Complete - add backend tests using a fake `MarketDataService` and route dependency override.

Exit criteria:
- `roc` metadata returns defaults and parameter schema.
- `roc` compute returns close price, one ROC trace, signal payloads, and diagnostics.
- Invalid settings return clear `4xx` errors with parameter-specific messages.

Implementation notes:
- The workbench uses `MarketDataFetcher.fetch_historical_prices()` so dashboard prices pass through the same normalization path as the security scan runner.
- The production indicator contract remains unchanged: `evaluate(prices, settings) -> list[IndicatorSignal]`.
- The first adapter uses `roc`'s existing close extraction and ROC series helpers. This is acceptable for the contract spike, but if more adapters need underscore helpers, promote the shared pure series functions explicitly instead of deepening private imports.
- Dashboard `roc` signals are visualization-level zero-cross markers generated by the adapter. They do not change scan criteria behavior.
- Settings are strict: unknown keys are rejected and `roc_lookback` must be an integer `>= 1`.

### Phase 1 - Minimal Dynamic Dashboard
Purpose: make the first end-to-end workbench useful.

Status: initial `roc` page implemented as of 2026-04-19 00:10 PDT.

Tasks:
1. Complete - add `securityScanApi.ts`.
2. Complete - add the new Next.js page at `src/frontend/app/security-scan/indicators/page.tsx`.
3. Complete - render ticker/date/indicator controls plus daily interval and benchmark tickers inputs.
4. Complete - render schema-driven parameter fields for `roc`.
5. Complete - add explicit recompute flow with loading, error, and empty states.
6. Complete - render a two-row Plotly chart with shared x-axis, reference line, vertical signal markers, and trace-level signal markers.
7. Complete - add `localStorage` MRU strip, updated only after successful compute.

Exit criteria:
- User can open the local frontend, select `roc`, edit `roc_lookback`, recompute, and see price + ROC traces.
- MRU persists across reloads.
- Empty or malformed requests produce visible, actionable errors.

Implementation notes:
- Frontend state remains local to the page. The first slice did not introduce a global store because no other page consumes this dashboard state yet.
- Chart construction lives in `src/frontend/components/security-scan/IndicatorDashboardChart.tsx` so the page remains a coordinator rather than mixing form, storage, and Plotly shaping.
- Parameter serialization lives in `src/frontend/lib/security-scan/indicatorParameterInputs.ts`; MRU parsing/storage lives in `src/frontend/lib/security-scan/indicatorMru.ts`.
- `benchmark_tickers` is included in the request contract and UI now, but `roc` does not consume it. Benchmark fetching remains gated by adapter requirements in the backend.

### Phase 2 - Add Multi-Trace Indicators
Purpose: validate the adapter shape across multiple indicator forms.

Tasks:
1. Add `roc_aggregate` adapter:
   - score trace
   - short MA trace
   - long MA trace
   - signal markers for crosses
2. Add `scl_v4_x5` adapter:
   - `CountdownDisplay`
   - `MA1`
   - `MA2`
   - zero/reference line
   - seven-bar high/low signal markers
3. Add tests for metadata schemas and compute payloads for each adapter.
4. Improve frontend parameter rendering for integer lists and grouped controls.

Exit criteria:
- Dashboard can switch among `roc`, `roc_aggregate`, and `scl_v4_x5`.
- Each indicator can be recomputed with edited parameters.
- Multi-trace legends and marker overlays remain readable.

Next detailed slice:
1. Add a backend `roc_aggregate` dashboard adapter before `scl_v4_x5`; it is the closest structural extension from `roc` because it adds multiple traces without benchmark context.
2. Promote only the helper functions needed for `roc_aggregate` if private imports start to pile up. The friction signal to watch is adapter code duplicating `_to_positive_int_list`, score construction, or SMA alignment logic.
3. Extend the adapter metadata with `integer_list` parameters for `roc_lookbacks` and `roc_change_lookbacks`, plus integer parameters for `ma_short` and `ma_long`.
4. Add tests that assert score, short MA, long MA, signal markers, diagnostics, and strict validation for list inputs.
5. Re-run the existing dashboard page against `roc_aggregate` without adding indicator-specific React branches. If the generic form cannot render this cleanly, fix the parameter schema/rendering contract rather than special-casing the page.
6. Add `scl_v4_x5` only after `roc_aggregate` proves the multi-trace shape; it will validate structurally different OHLC requirements and countdown/MA naming.

### Phase 3 - Benchmark-Aware Indicators
Purpose: support QRS and composite indicators without special-casing in the frontend.

Tasks:
1. Add benchmark ticker controls in the frontend.
2. Add backend benchmark fetch/alignment support in `indicator_workbench.py`.
3. Add `qrs_consist_excess` adapter:
   - main QRS trace
   - `MA1`, `MA2`, `MA3`
   - zero line
   - existing signal types
4. Add `scl_ma2_qrs_ma1_breakout` adapter:
   - SCL `MA2`
   - QRS `MA1`
   - prior high/low context where useful
   - dual breakout markers
5. Add diagnostics for missing benchmark data and date alignment losses.

Exit criteria:
- QRS-based indicators compute with default benchmarks.
- Users can override benchmark tickers.
- Missing benchmark data fails clearly without silent partial output.

### Phase 4 - Screener Dashboard Foundation
Purpose: make the indicator workbench reusable for a future dynamic screener page.

Tasks:
1. Extract shared frontend chart payload types.
2. Add a backend endpoint for configured scan instances if needed:
   - `GET /security-scan/indicator-instances`
3. Add an API for running one indicator across many tickers with bounded concurrency and explicit limits.
4. Add request cancellation/debouncing strategy on frontend.
5. Define cache behavior for expensive recomputes.

Exit criteria:
- The single-ticker dashboard and future screener can share indicator metadata and compute contracts.
- Multi-ticker compute has explicit guardrails for request size, timeout, and provider failures.

## Data and Validation Rules
- Ticker symbols are normalized to uppercase.
- `start_date` and `end_date` must be valid `YYYY-MM-DD` dates.
- `start_date` must be before or equal to `end_date`.
- `interval` must be one of the backend-supported values; phase 1 enables only `day`.
- Integer parameters must be whole numbers and satisfy min/max rules.
- Float parameters must be finite numbers.
- List parameters must validate each element and reject empty lists when the indicator requires non-empty input.
- Benchmark tickers must be exactly three symbols for current QRS logic.
- If fetched prices are empty, return a clear no-data response or `422`/`404` style error; do not emit a blank chart as success.
- If indicator output length does not align with dates, return diagnostics or fail fast depending on the adapter.

## Testing Plan

### Backend Unit Tests
- Metadata endpoint returns supported indicators in stable order.
- Parameter defaults and schemas match adapter definitions.
- Invalid indicator id returns `404` or `422`.
- Invalid hyperparameters return clear validation errors.
- Empty price data returns clear error.
- `roc` compute returns expected ROC values for synthetic prices.
- `roc_aggregate` compute returns score and MA traces for synthetic prices.
- `scl_v4_x5` compute returns countdown and MA traces for synthetic OHLC prices.
- Benchmark-aware adapters report missing benchmark data clearly.

### Frontend Tests
If the project has or adds frontend test tooling:
- Parameter form renders fields from metadata.
- Numeric/list inputs serialize into the backend request shape.
- MRU update logic deduplicates and limits to 5.
- Compute errors render in the dashboard.

### Manual Validation
- Start backend on `localhost:8003`.
- Start frontend on `localhost:3003`.
- Open the new dashboard page.
- Test `AAPL` over a recent 1-year range.
- Change `roc_lookback` and verify the chart changes.
- Switch to `roc_aggregate` and verify multiple traces render.
- Reload page and verify MRU persists.

Latest validation:
- Passed: `uv run pytest src/backend/tests/security_scan/test_indicator_workbench.py src/backend/tests/test_security_scan_api.py`.
- Passed: scoped TypeScript check for the new dashboard frontend files with `npx tsc --noEmit ...`.
- Passed: `GET http://localhost:8003/security-scan/indicators`.
- Passed: `POST http://localhost:8003/security-scan/indicator-dashboard/compute` for `AAPL`, `roc`, `roc_lookback=1`, `2025-01-01` through `2025-01-10`.
- Passed: `HEAD http://localhost:3003/security-scan/indicators` returned `200 OK`.
- Blocked: full `npm run build` currently fails on an existing unrelated type error in `src/frontend/app/options/page.tsx` where `OptionContract.last` is referenced but not defined on the type.
- Blocked: direct `npx eslint ...` cannot run because the frontend uses ESLint 9 but has no `eslint.config.(js|mjs|cjs)` file.

## Blast Radius and Reversibility

Break blast radius:
- Low for phase 0/1 if the workbench service is additive and scan runner contracts are unchanged.
- Medium when adding benchmark-aware indicators because provider calls and date alignment can fail in more ways.

Change blast radius:
- Low if the frontend consumes metadata generically.
- Medium if parameter schemas are duplicated manually in frontend. Avoid duplication.

Reversibility:
- The new router can be removed from `app.main`.
- The new frontend route can be removed without affecting existing app pages.
- Adapter modules can be deleted without touching production scan indicator evaluation if we keep contracts separate.

## Open Questions
- Resolved for this slice: the frontend route is `/security-scan/indicators`, with backend metadata at `GET /security-scan/indicators` and compute at `POST /security-scan/indicator-dashboard/compute`.
- Should the first supported set include `scl_v4_x5`, even though it is not currently configured as a top-level scan instance in `scan_settings.toml`?
- Resolved for this slice: parameter edits require an explicit recompute button.
- Should the frontend support saving named parameter presets in `localStorage`, separate from MRU indicator types?
- Should future multi-panel support be per-indicator-defined or user-configurable?
- Should `roc` zero-cross visualization markers remain dashboard-owned defaults, or should future `roc` signal markers come only from explicit criteria metadata?
- Should the tracked runtime artifacts `.coverage`, `src/backend/logs/backend.log`, and `src/backend/options.db` be removed from version control or moved to ignored local paths? Tests and local smoke runs modify them.

## Initial File Targets
- Backend:
  - `src/backend/app/security_scan/indicator_adapters.py`
  - `src/backend/app/security_scan/indicator_workbench.py`
  - `src/backend/app/routes/security_scan.py`
  - `src/backend/app/main.py`
  - `src/backend/tests/security_scan/test_indicator_workbench.py`
  - `src/backend/tests/test_security_scan_api.py`
- Frontend:
  - `src/frontend/app/security-scan/indicators/page.tsx`
  - `src/frontend/lib/api/securityScanApi.ts`
  - optionally `src/frontend/components/security-scan/*`
  - optionally shared frontend types under `src/frontend/types/securityScan.ts`

## Recommended First Slice
Build the narrowest useful end-to-end path:

1. Complete - backend metadata + compute for `roc`.
2. Complete - frontend page that can edit `roc_lookback`.
3. Complete - plot close + ROC with signal markers.
4. Complete - MRU in `localStorage`.
5. Complete for backend - tests for the backend compute contract and API route. Frontend test tooling is not currently available.

Do not start by implementing all indicators. The adapter contract should earn its shape by supporting `roc`, then `roc_aggregate`, then one structurally different indicator.
