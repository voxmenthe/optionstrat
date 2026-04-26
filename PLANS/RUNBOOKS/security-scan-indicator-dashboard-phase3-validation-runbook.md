# Security Scan Indicator Dashboard Phase 3 Validation Runbook

## Purpose

Use this runbook to validate the current state of the dynamic security-scan
indicator dashboard after Phase 3 completion. At this point the supported
dashboard indicators are:

- `roc`
- `roc_aggregate`
- `scl_v4_x5`
- `qrs_consist_excess`
- `scl_ma2_qrs_ma1_breakout`

This runbook separates:

- fast preflight checks
- backend test suites
- frontend type checks
- live API smoke checks
- browser sanity checks
- expected failures and known blockers

It is written for the current checkout state as of 2026-04-26.

## Current Expectations

These are the expected validation boundaries right now:

- The focused and extended backend dashboard suites should pass.
- The scoped frontend TypeScript check for the dashboard files should pass.
- Full frontend `npm run build` is still expected to fail on the unrelated
  `OptionContract.last` type issue in `src/frontend/app/options/page.tsx`.
- Frontend lint is still expected to be blocked because the repo has ESLint 9
  but no `eslint.config.(js|mjs|cjs)` flat config.
- Backend tests and live backend runs may modify tracked runtime artifacts such
  as `src/backend/.coverage`, `src/backend/logs/backend.log`, and sometimes
  `src/backend/options.db`.

## Prerequisites

From the repo root:

```bash
cd /Volumes/cdrive/repos/optionstrat
```

Backend dependencies:

```bash
uv sync
```

Frontend dependencies, if `node_modules` is missing or stale:

```bash
cd src/frontend
npm ci
cd ../..
```

Optional preflight status check:

```bash
git status --short
```

## Ports and Startup Commands

Use these ports for dashboard validation:

- Backend: `8003`
- Frontend: `3003`

The backend README still mentions `8000` in one place, but the live backend
code in `src/backend/app/main.py` defaults to `8003`, and the dashboard plan and
tests are grounded on `8003`.

Recommended backend startup from `src/backend`:

```bash
cd src/backend
uv run uvicorn app.main:app --reload --port 8003
```

Alternative backend startup from `src/backend`:

```bash
cd src/backend
uv run python -m app.main
```

Recommended frontend startup from `src/frontend`:

```bash
cd src/frontend
npm run dev
```

## Fastest Useful Checks

If you only want a quick answer to "did the dashboard regress badly?", run
these two checks first.

### 1. Focused backend dashboard regression

Run from `src/backend`:

```bash
cd src/backend
uv run pytest \
  tests/test_scl_ma2_qrs_ma1_breakout.py \
  tests/security_scan/test_indicator_workbench.py \
  tests/test_security_scan_api.py
```

What this covers:

- composite breakout helper behavior
- dashboard metadata shape
- backend workbench response assembly
- dashboard API route behavior
- negative cases such as bad settings and no-common-date failures

### 2. Scoped frontend dashboard type check

Run from `src/frontend`:

```bash
cd src/frontend
node_modules/.bin/tsc --noEmit --pretty false --jsx preserve --module esnext --moduleResolution bundler --target es5 --lib dom,dom.iterable,esnext --strict --esModuleInterop --skipLibCheck app/security-scan/indicators/page.tsx components/security-scan/IndicatorDashboardChart.tsx lib/api/securityScanApi.ts lib/security-scan/indicatorMru.ts lib/security-scan/indicatorParameterInputs.ts
```

Why this exact command:

- it uses the frontend-local compiler that actually matches this repo
- `npx tsc` from the repo root has previously hit the wrong package
- this command is scoped to the dashboard files rather than the unrelated
  frontend baseline failures

## Full Dashboard Backend Regression Set

If you want the broader backend coverage for the current dashboard surface, run
this verified suite from `src/backend`:

```bash
cd src/backend
uv run pytest \
  tests/test_qrs_consist_excess.py \
  tests/test_scl_v4_x5.py \
  tests/test_scl_ma2_qrs_ma1_breakout.py \
  tests/security_scan/test_indicator_workbench.py \
  tests/test_security_scan_api.py
```

What this adds beyond the fast suite:

- standalone QRS signal and alignment helper tests
- standalone SCL helper tests
- broader helper-level coverage around shared public compute seams

Expected result:

- this suite passed on 2026-04-26 with `47 passed`

## Optional Narrow Test Slices

Use these when you only changed one area and want a tighter loop.

### QRS helper slice

```bash
cd src/backend
uv run pytest tests/test_qrs_consist_excess.py
```

### SCL helper slice

```bash
cd src/backend
uv run pytest tests/test_scl_v4_x5.py
```

### Composite helper slice

```bash
cd src/backend
uv run pytest tests/test_scl_ma2_qrs_ma1_breakout.py
```

### Workbench and route slice

```bash
cd src/backend
uv run pytest \
  tests/security_scan/test_indicator_workbench.py \
  tests/test_security_scan_api.py
```

## Live API Smoke Checks

Start both dev servers first:

- backend on `http://localhost:8003`
- frontend on `http://localhost:3003`

### 1. Metadata endpoint

```bash
curl -s http://localhost:8003/security-scan/indicators | jq '.indicators[].id'
```

Expected output should include:

- `roc`
- `roc_aggregate`
- `scl_v4_x5`
- `qrs_consist_excess`
- `scl_ma2_qrs_ma1_breakout`

### 2. Frontend route is up

```bash
curl -I http://localhost:3003/security-scan/indicators
```

Expected:

- HTTP `200 OK`

### 3. ROC compute smoke

```bash
curl -s http://localhost:8003/security-scan/indicator-dashboard/compute \
  -H 'Content-Type: application/json' \
  -d '{
    "ticker": "AAPL",
    "indicator_id": "roc",
    "settings": {"roc_lookback": 12},
    "start_date": "2025-01-01",
    "end_date": "2025-03-31",
    "interval": "day",
    "benchmark_tickers": ["SPY", "QQQ", "IWM"]
  }' | jq '{indicator_id, signals: (.signals | length), price_points: .diagnostics.price_points, indicator_points: .diagnostics.indicator_points}'
```

Expected:

- `indicator_id` is `roc`
- non-empty `price_points`
- `signals` may be zero or more depending on the data window

### 4. QRS benchmark-aware compute smoke

```bash
curl -s http://localhost:8003/security-scan/indicator-dashboard/compute \
  -H 'Content-Type: application/json' \
  -d '{
    "ticker": "AAPL",
    "indicator_id": "qrs_consist_excess",
    "settings": {},
    "start_date": "2025-01-01",
    "end_date": "2025-06-30",
    "interval": "day",
    "benchmark_tickers": ["SPY", "QQQ", "IWM"]
  }' | jq '{indicator_id, trace_keys: [.indicator.panels[0].traces[].key], benchmark_tickers_used: .diagnostics.benchmark_tickers_used, warnings: .diagnostics.warnings}'
```

Expected:

- `indicator_id` is `qrs_consist_excess`
- lower-panel traces include `qrs`, `ma1`, `ma2`, `ma3`
- `benchmark_tickers_used` shows `SPY`, `QQQ`, `IWM`

### 5. Composite breakout compute smoke

```bash
curl -s http://localhost:8003/security-scan/indicator-dashboard/compute \
  -H 'Content-Type: application/json' \
  -d '{
    "ticker": "AAPL",
    "indicator_id": "scl_ma2_qrs_ma1_breakout",
    "settings": {
      "scl_ma2_window": 12,
      "qrs_ma1_window": 5
    },
    "start_date": "2025-01-01",
    "end_date": "2025-06-30",
    "interval": "day",
    "benchmark_tickers": ["SPY", "QQQ", "IWM"]
  }' | jq '{indicator_id, trace_keys: [.indicator.panels[0].traces[].key], signal_count: (.signals | length), signal_targets: [.signals[].target_trace] | unique, warnings: .diagnostics.warnings}'
```

Expected:

- `indicator_id` is `scl_ma2_qrs_ma1_breakout`
- lower-panel traces include `scl_ma2` and `qrs_ma1`
- signal targets, when signals are present, should land on those two trace keys

## Negative API Checks

These are useful because Phase 3 made benchmark and alignment errors explicit.

### Wrong benchmark count should fail clearly

```bash
curl -s http://localhost:8003/security-scan/indicator-dashboard/compute \
  -H 'Content-Type: application/json' \
  -d '{
    "ticker": "AAPL",
    "indicator_id": "qrs_consist_excess",
    "settings": {},
    "start_date": "2025-01-01",
    "end_date": "2025-06-30",
    "interval": "day",
    "benchmark_tickers": ["SPY", "QQQ"]
  }' | jq
```

Expected:

- HTTP `422`
- error text mentioning exactly three benchmark tickers

### Invalid breakout setting should fail clearly

```bash
curl -s http://localhost:8003/security-scan/indicator-dashboard/compute \
  -H 'Content-Type: application/json' \
  -d '{
    "ticker": "AAPL",
    "indicator_id": "scl_ma2_qrs_ma1_breakout",
    "settings": {
      "scl_ma2_window": 0,
      "qrs_ma1_window": 5
    },
    "start_date": "2025-01-01",
    "end_date": "2025-06-30",
    "interval": "day",
    "benchmark_tickers": ["SPY", "QQQ", "IWM"]
  }' | jq
```

Expected:

- HTTP `422`
- error text mentioning `scl_ma2_window must be >= 1`

### Missing benchmark data should fail clearly

Use a bogus benchmark symbol:

```bash
curl -s http://localhost:8003/security-scan/indicator-dashboard/compute \
  -H 'Content-Type: application/json' \
  -d '{
    "ticker": "AAPL",
    "indicator_id": "qrs_consist_excess",
    "settings": {},
    "start_date": "2025-01-01",
    "end_date": "2025-06-30",
    "interval": "day",
    "benchmark_tickers": ["SPY", "QQQ", "ZZZZ_NOT_REAL"]
  }' | jq
```

Expected:

- HTTP `404` or a clear no-data error for the missing benchmark series

## Browser Sanity Checks

Open:

- `http://localhost:3003/security-scan/indicators`

Work through these checks in order.

### Dashboard loads

- The page should render without a blank screen.
- The indicator dropdown should populate.
- The default indicator should still be `roc`, because metadata order follows
  adapter registration order.

### ROC sanity

- Select `roc`.
- Change `roc_lookback`.
- Click `Recompute`.
- Confirm the top panel shows close price and the bottom panel shows ROC.
- Confirm signal markers, when present, land on the ROC trace.

### ROC aggregate sanity

- Select `roc_aggregate`.
- Confirm the lower panel shows `score`, `ma_short`, and `ma_long`.
- Try list parameter edits such as changing `roc_lookbacks`.
- Recompute and confirm the chart updates instead of failing silently.

### SCL sanity

- Select `scl_v4_x5`.
- Confirm the lower panel shows `countdown`, `ma1`, and `ma2`.
- Confirm warnings appear if you test data with missing `high` or `low` fields.

### QRS sanity

- Select `qrs_consist_excess`.
- Confirm benchmark hint text appears under the benchmark input.
- Confirm the lower panel shows `qrs`, `ma1`, `ma2`, and `ma3`.
- Confirm warnings appear when benchmark overlap drops rows.

### Composite breakout sanity

- Select `scl_ma2_qrs_ma1_breakout`.
- Confirm the lower panel shows `scl_ma2` and `qrs_ma1`.
- Recompute and inspect any dual breakout markers.
- Hover a dual breakout marker and confirm the metadata exposes the current
  value, lookback, and prior threshold context for that trace.

### Error and persistence sanity

- Enter an invalid parameter such as `0` for a required positive integer field.
- Confirm the page shows a visible actionable error instead of silently doing
  nothing.
- Successfully compute a few different indicators.
- Reload the page.
- Confirm the MRU strip still shows the most recently used successful
  indicators.

## Known Blocked Checks

These are worth knowing about so users do not misread them as dashboard
regressions.

### Full frontend build

Run from `src/frontend`:

```bash
cd src/frontend
npm run build
```

Current expectation:

- blocked by the unrelated `OptionContract.last` type issue in
  `src/frontend/app/options/page.tsx`

### Frontend lint

Run from `src/frontend`:

```bash
cd src/frontend
npm run lint
```

Current expectation:

- blocked because ESLint 9 expects flat config and the repo does not currently
  provide `eslint.config.(js|mjs|cjs)`

## Cleanup Notes

After backend tests or live backend runs, check for tracked runtime file noise:

```bash
git status --short
```

Common artifacts:

- `src/backend/.coverage`
- `src/backend/logs/backend.log`
- `src/backend/options.db`

If you are only validating and not making code changes, review those diffs
before deciding whether to keep or discard them.

## Recommended Order

For most users, the best sequence is:

1. preflight with `git status --short`
2. focused backend dashboard regression
3. scoped frontend dashboard `tsc`
4. live metadata endpoint check
5. live `roc`, `qrs_consist_excess`, and `scl_ma2_qrs_ma1_breakout` compute
   smokes
6. browser sanity pass
7. optional extended backend suite

That order gives fast failure signals first, keeps the most stable checks early,
and leaves the slower manual visual checks for the point where the contract and
type surfaces already look healthy.
