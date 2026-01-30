# Composite ROC Aggregate Indicator Plan

## Goal
Add a new indicator under `src/backend/app/security_scan/indicators/` that:
- Computes multiple ROC series with configurable lookbacks.
- Scores each ROC as +1/0/-1 based on whether it increased/flat/decreased vs configurable comparison lookbacks.
- Aggregates scores into a single indicator series.
- Computes short and long moving averages of the indicator.
- Emits scan signals when the indicator transitions to being above both MAs or below both MAs.

## Non-goals
- Do not redesign the indicator registry or criteria engine.
- Do not introduce a new shared math/TA framework unless clearly necessary.
- No API/DB changes; scope is local to `security_scan`.

## Current Context
- Indicators live in `src/backend/app/security_scan/indicators/` and expose `INDICATOR_ID` + `evaluate(prices, settings)`.
- Criteria evaluation only supports single-series rules (crossover vs fixed level, threshold, direction). It does not support crossovers between two series.
- The scan runner expects `IndicatorSignal` values from each indicator and reports them; no extra wiring needed.

## Assumptions + Open Decisions
1. **ROC lookbacks config**: A list (e.g., `[5, 10, 20]`) under `roc_lookbacks`.
2. **Comparison lookbacks config**: A list (e.g., `[1, 3, 5]`) under `roc_change_lookbacks` that compares current ROC to ROC `N` periods ago within the same ROC series.
3. **Moving average type**: Simple moving average (SMA) unless explicitly requested otherwise.
4. **Cross logic**: A signal fires on the date when the indicator transitions to above both MAs or below both MAs:
   - Up: `prev_above_both == False` AND `current_above_both == True`.
   - Down: `prev_below_both == False` AND `current_below_both == True`.
   This captures the “already above one MA, then cross the other” requirement.
5. **Equality handling**: Treat `>` as above and `<` as below; equality does not count as above/below to avoid ambiguous signals.
6. **Minimum data**: No signals emitted until indicator values and both MAs are available for at least two consecutive points.

If any of these assumptions are wrong, update settings/logic before coding.

## Design Options
### Option A (Recommended): Indicator-local signal detection
**Overview**: Implement all series building + crossover detection inside the new indicator file. No changes to `criteria.py`.
- **Pros**: Minimal blast radius; avoids expanding criteria engine for cross-series logic.
- **Cons**: Slightly more code in the indicator; cannot reuse generic criteria rules.
- **Risks**: Off-by-one/date-alignment mistakes; mitigate with unit tests.
- **Friction**: Low; fits current architecture without forcing cross-series rules into criteria.

### Option B: Extend criteria engine to support series-to-series crossover
**Overview**: Add a new criteria type (e.g., `series_crossover`) that compares two named series.
- **Pros**: Reusable for future indicators with cross-series logic.
- **Cons**: Requires new interface for multi-series criteria, additional data plumbing, larger blast radius.
- **Risks**: Interface design complexity; risk of over-abstraction for a single use.
- **Friction**: Medium/high; criteria engine currently assumes single series.

**Recommendation**: Option A. It aligns with existing indicator contract and avoids premature abstraction.

## Data Flow (Option A)
1. Extract close series ordered by date (reuse pattern from `roc.py`).
2. For each configured ROC lookback `L`:
   - Compute ROC series `roc_L` aligned to close series index.
3. For each date where ROC values exist:
   - For each ROC series and each change lookback `K`, compare current ROC vs ROC from `K` periods ago.
   - Score +1/0/-1 and aggregate across all comparisons into a single indicator value.
4. Compute short and long SMA series on the indicator values.
5. Emit signals when indicator transitions to above/below both MAs.

## Proposed Settings (scan_settings.toml)
```toml
[indicators]
instances = [
  {
    id = "roc_aggregate",
    roc_lookbacks = [5, 10, 20],
    roc_change_lookbacks = [1, 3, 5],
    ma_short = 5,
    ma_long = 20
  }
]
```

## Signals + Metadata
Signal types:
- `cross_above_both`
- `cross_below_both`

Metadata to include:
- `indicator_value`
- `ma_short_value`
- `ma_long_value`
- `roc_lookbacks`
- `roc_change_lookbacks`
- (optional) `score_breakdown` summary (e.g., total comparisons, counts of +1/0/-1)

## Tests (Add to `src/backend/tests/test_security_scan.py`)
- **Score construction**: Synthetic price series where ROC deltas are known; assert aggregated indicator value on specific dates.
- **MA crossover signal**: Controlled indicator sequence to verify one up and one down signal; assert dates and signal types.
- **Insufficient data**: Ensure empty signals when not enough data for ROC/MA windows.

## Implementation Steps
1. Create new indicator file `src/backend/app/security_scan/indicators/roc_aggregate.py`.
2. Implement helpers: extract closes, compute ROC per lookback, compute score series, compute SMA series, detect cross-above/below-both events.
3. Add tests for the new indicator behavior.
4. Update `scan_settings.toml` example (and `README.md` if needed) to show configuration.

## Validation
- Run `python -m pytest src/backend/tests/test_security_scan.py` from `src/backend`.
- Run the security scan CLI on a small ticker list to confirm signals appear and report formatting remains stable.

## Blast Radius / Reversibility
- **Blast radius**: Low. New indicator + tests + config example; no changes to core scan runner.
- **Reversibility**: Remove the new indicator file and config entry; no migrations or data changes.
