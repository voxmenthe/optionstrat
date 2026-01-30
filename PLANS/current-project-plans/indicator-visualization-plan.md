# Indicator Sanity Plotter Plan

## Goal
Provide a notebook-style Python script that fetches historical prices, recomputes any configured security-scan indicator, and renders a dual pane chart (price + indicator) to visually sanity-check behavior before shipping indicator changes.

## Non-goals
- No UI/Next.js integration or backend API route.
- No refactor of the indicator registry/evaluator contract.
- No persistence of generated plots.

## Current Context
- Security scan indicators live in `src/backend/app/security_scan/indicators` and are invoked via the registry.
- Indicator evaluation currently returns only signals; intermediate series data is private to each indicator module.
- Analysts/debuggers need a fast way to compare indicator curves against price history without touching the full scan runner.

## Approach
1. **Notebook-style script**: Create `src/backend/notebooks/indicator_sanity_check.py` with `# %%` cell markers so it can run as either a plain Python script or a Jupyter notebook via `jupytext`/VS Code.
2. **Config-aware indicator selection**: Allow selecting an indicator instance from `scan_settings.toml` (by `instance_id` or `id`) with optional overrides defined in the script.
3. **Shared market data path**: Reuse `MarketDataService` + `MarketDataFetcher.normalize_prices` to guarantee parity with production scans.
4. **Indicator adapters**: For each supported indicator (starting with `roc` and `roc_aggregate`), create a lightweight adapter that exposes:
   - How to build the indicator series (reusing module helpers where possible).
   - Optional auxiliary series (e.g., moving averages) and metadata for plotting.
   - Signal generation via the indicator’s existing `evaluate` function for overlay markers.
   New indicators can register adapters in the same file to keep blast radius local.
5. **Visualization**: Use `matplotlib` (already a standard dependency for notebooks) to render:
   - Top axis: close prices over the requested date range.
   - Bottom axis: indicator series + auxiliary lines, with signal markers and hoverable labels.
6. **Usage ergonomics**: Add helper functions to list available indicator instances, display resolved settings, and summarize fetched data so the notebook remains self-explanatory.

## Key Decisions & Risks
- **Dependency**: Add `matplotlib` to backend dependencies so the notebook works out-of-the-box (`pandas` already present). Risk is minor since it is dev-only usage.
- **Indicator internals**: Script will import private helper functions (e.g., `_compute_indicator_series`) to avoid duplicating math. Document this in code comments and keep adapters narrow to limit breakage.
- **Extensibility**: Register adapters in a dict so future indicators are a one-function addition. If an indicator lacks an adapter, script should fail with a clear message instead of silently plotting nothing.

## Implementation Steps
1. **Project scaffolding**
   - Create `src/backend/notebooks/` if it does not exist.
   - Add the new notebook-style script skeleton with markdown intro + config cells.
2. **Config + data plumbing**
   - Load scan config via `load_security_scan_config` and expose helper functions to select indicator settings by instance or type.
   - Fetch normalized prices for the chosen ticker/period by reusing `MarketDataFetcher`.
3. **Indicator adapters**
   - Implement adapter for `roc` (close series + ROC series + signals).
   - Implement adapter for `roc_aggregate` (close series + indicator + SMA overlays + signals).
   - Expose registry/dict for adapters and helper to compute `pandas.DataFrame` objects for plotting.
4. **Plotting + display**
   - Build dual-subplot visualization with shared x-axis, formatting, and signal annotations.
   - Show tabular previews of indicator series + signals for quick inspection.
5. **Dependencies + docs**
   - Add `matplotlib` to `src/backend/pyproject.toml` dependencies and lockfile.
   - Update README or inline docstring with run instructions (`uv run python src/backend/notebooks/indicator_sanity_check.py`).

## Validation
- Run the notebook script for a known ticker + indicator (e.g., `AAPL` with `roc`). Ensure plots render and no exceptions occur.
- Repeat for `roc_aggregate` to verify adapter wiring.
- Sanity-check signal markers appear at reasonable locations by cross-referencing `signals` output.

## Blast Radius & Reversibility
- **Blast radius**: Low. Changes limited to a new notebook script and a dependency addition.
- **Reversibility**: Remove the notebook file and dependency entry if needed.
