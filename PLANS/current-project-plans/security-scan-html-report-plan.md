# Security Scan HTML Report + Timeseries Plots Plan

## Goal
Automatically emit an HTML-rendered version of the security scan Markdown report, and include timeseries plots for the main aggregates (advance/decline and MA/ROC breadth) in that HTML output.

## Status (Updated 2026-01-31)
- Phase 1 complete: HTML renderer added, CLI writes `.html`, and Markdown report links HTML output.
- Phase 2 complete: aggregate series fetch helper and plot metric definitions + assembler added.
- Phase 3 complete: Plotly chart renderer added with grouped aggregate charts and inline JS embedding.
- Phase 4 complete: `report` config support (html toggle, plot_lookbacks, max_points) + CLI `--no-html`.
- Phase 5 complete: tests for aggregate series definitions/order, chart HTML embed, and HTML chart section.
- Findings: `markdown-it-py` added for Markdown -> HTML conversion; HTML uses a minimal offline CSS shell. Added `fetch_security_aggregate_series` plus `reporting/aggregate_series.py` for metric definitions + series assembly. Added `plotly` dependency and `reporting/aggregate_charts.py` to build Plotly figures; CLI now supports `--no-html` and uses report config for chart lookbacks and max points.

## Non-goals
- No frontend UI or web server; this is an offline HTML artifact alongside JSON/Markdown.
- No new API endpoints.
- No live data streaming or auto-refresh; charts are static renderings of stored series.

## Current Context
- CLI writes JSON + Markdown to `task-logs/` (`security_scan_<run_id>.json/.md`).
- Aggregates are persisted in `security_scan.db` (table `security_aggregate_values`).
- Markdown report is generated in `src/backend/app/security_scan/reporting/markdown_report.py`.
- Notebook `indicator_sanity_check.py` already reads aggregate series for plotting (proof that data is available).

## Requirements (Functional)
1. Generate an HTML report automatically whenever the CLI runs.
2. HTML should include the content of the Markdown report.
3. HTML should include timeseries charts for a selected set of aggregate metrics:
   - Advances/declines/net advances/advance % (t-1 base)
   - Configured advance/decline lookbacks (ad_<N>_advance_pct as available)
   - MA breadth % above (SMA 13/28/46/8 shift 5)
   - ROC breadth % gt (ROC 17 vs 5, ROC 27 vs 4)
4. Output paths should mirror existing outputs, e.g. `security_scan_<run_id>.html` in `task-logs/` (or alongside user-specified `--output`).
5. Must remain offline-friendly (no CDN). Plotly JS should be embedded in the HTML.

## Proposed Output Contract
Add new artifacts:
- `run_metadata.html_path`: absolute or relative path to HTML output.
- HTML file written in the same directory as JSON/MD.
- Optionally `run_metadata.set_hash` for easier series lookup in the HTML report pipeline.

## Data Sources
- Use `security_scan.db` aggregate series:
  - `security_aggregate_values` keyed by `set_hash`, `interval`, `as_of_date`, `metric_key`.
- The `set_hash` for the current run is already computed in `scan_runner` for aggregate storage but is not currently exposed in the payload.

## Design Options

### Option A — Static HTML + Inline SVG/Canvas
- Use Markdown -> HTML conversion (e.g., `markdown-it-py` or Python `markdown` library).
- Generate charts as inline SVG from Python (no JS dependencies).
- Pros: fully offline, minimal dependencies, deterministic output.
- Cons: more custom chart code; less interactivity.

### Option B — Static HTML + Embedded Plotly (offline bundle) (preferred)
- Use `plotly` to generate HTML snippets with embedded JS (no CDN) and embed into report.
- Pros: rich charts, zoom/hover; minimal manual charting logic.
- Cons: larger HTML size; adds dependency.

## Decision
Proceed with **Option B** using Plotly with embedded JS (`include_plotlyjs="inline"` once, then `include_plotlyjs=False` for subsequent charts).

## Implementation Plan

### Phase 1 — HTML report output (no charts yet)
1. Add a new report renderer (done 2026-01-31):
   - `render_html_report(payload: dict[str, Any], charts_html: str | None = None) -> str`
   - Uses `markdown-it-py` for Markdown -> HTML conversion.
   - Wraps content in a basic HTML shell with minimal CSS.
2. Update CLI to write `security_scan_<run_id>.html` alongside `.md` and `.json` (done 2026-01-31).
3. Add `run_metadata.html_path` and include it in the Markdown report summary (done 2026-01-31).
4. Add `run_metadata.set_hash` so HTML generation can look up aggregate series without recomputing (done 2026-01-31).
5. Unit tests: HTML contains title and key sections (done 2026-01-31).

### Phase 2 — Aggregate series retrieval
6. Add a storage helper to fetch aggregate series by `set_hash`, `metric_key`, and date range.
   - Prefer a single query for all metric keys in the chart set, then group in Python.
7. Define the plot metric set (base + config-driven lookbacks):
   - Advance/Decline counts: `advances`, `declines`, `unchanged` (t-1 only)
   - Advance/Decline net: `net_advances` (t-1 only)
   - Advance %: `advance_pct` + `ad_<N>_advance_pct` for configured lookbacks
   - MA above %: `ma_13_above_pct`, `ma_28_above_pct`, `ma_46_above_pct`, `ma_8_shift_5_above_pct`
   - ROC gt %: `roc_17_vs_5_gt_pct`, `roc_27_vs_4_gt_pct`
8. Series assembler returns:
   ```json
   {
     "metric_key": "advance_pct",
     "label": "Advance % (t-1)",
     "points": [{"date": "2025-01-01", "value": 0.58}, ...]
   }
   ```

### Phase 3 — Plotly chart rendering
9. Implement a chart factory:
   - `build_timeseries_figure(title: str, series: list[Series], y_label: str | None) -> plotly.graph_objects.Figure`
   - Each series becomes a `go.Scatter` line.
   - Missing values should render gaps (Plotly handles `None`).
10. Generate chart HTML snippets via `plotly.io.to_html`:
   - First chart: `include_plotlyjs="inline"`, `full_html=False`.
   - Subsequent charts: `include_plotlyjs=False`, `full_html=False`.
11. Insert charts into the HTML report under a new section:
    - “Aggregate Timeseries” with subheadings per chart group.

### Phase 4 — Config/Customization
12. Add optional config section to `scan_settings.toml`:
    ```toml
    [report]
    html = true
    plot_lookbacks = [1, 5, 10]
    ```
13. Default to `html = true` and plot all configured advance/decline lookbacks if `plot_lookbacks` is missing.

### Phase 5 — Tests & Validation
14. Unit tests for:
    - HTML renderer outputs a valid HTML skeleton.
    - Plotly chart HTML is embedded (presence of div + plotly JS).
    - Aggregate series fetch returns ordered points for multiple metrics.
15. Manual validation:
    - Run scan and open HTML in browser; verify charts render offline.

## Dependencies
- Add `plotly`.
- Add a Markdown -> HTML library (`markdown-it-py` preferred, or `markdown`).
- Keep dependencies optional if `report.html = false`.

## Risks / Blast Radius
- **Low**: HTML generation and report changes are additive.
- **Medium**: `plotly` increases artifact size; HTML could be large.
- **Mitigation**: include Plotly JS once; keep chart count reasonable; allow `report.html=false`.

## Open Questions
- Should HTML output be optional via CLI flag (e.g., `--html` / `--no-html`) in addition to config? Decision: it should be produced by default but can be disabled via CLI flag `--no-html`.
- Do we want to plot additional metrics (below/gt/lt) beyond the initial set? Decision: Yes, but optional and configurable in the config.
- Do we need a max window for timeseries length to keep HTML size bounded? Yes this will also be part of the config setting.
