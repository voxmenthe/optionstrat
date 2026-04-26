'use client';

import React, {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { IndicatorDashboardChart } from '../../../components/security-scan/IndicatorDashboardChart';
import { ApiError } from '../../../lib/api/apiClient';
import securityScanApi from '../../../lib/api/securityScanApi';
import type {
  IndicatorDashboardComputeResponse,
  IndicatorMetadata,
  IndicatorParameterMetadata,
} from '../../../lib/api/securityScanApi';
import {
  filterMruByMetadata,
  IndicatorMruItem,
  readIndicatorMruItems,
  updateIndicatorMruItems,
  writeIndicatorMruItems,
} from '../../../lib/security-scan/indicatorMru';
import {
  buildParameterInputs,
  buildSettingsFromInputs,
  defaultEndDate,
  defaultStartDate,
  ParameterInputMap,
  ParameterInputValue,
  parseBenchmarkTickers,
} from '../../../lib/security-scan/indicatorParameterInputs';

function errorMessageFromUnknown(error: unknown): string {
  if (error instanceof ApiError) {
    return `API Error ${error.status}: ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unexpected dashboard error';
}

export default function SecurityScanIndicatorsPage() {
  const [indicators, setIndicators] = useState<IndicatorMetadata[]>([]);
  const [selectedIndicatorId, setSelectedIndicatorId] = useState('');
  const [parameterInputs, setParameterInputs] = useState<ParameterInputMap>({});
  const [ticker, setTicker] = useState('AAPL');
  const [startDate, setStartDate] = useState(defaultStartDate);
  const [endDate, setEndDate] = useState(defaultEndDate);
  const [benchmarkTickers, setBenchmarkTickers] = useState('SPY, QQQ, IWM');
  const [metadataLoading, setMetadataLoading] = useState(true);
  const [computeLoading, setComputeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IndicatorDashboardComputeResponse | null>(null);
  const [mruItems, setMruItems] = useState<IndicatorMruItem[]>([]);
  const activeCompute = useRef<AbortController | null>(null);

  const selectedIndicator = useMemo(
    () => indicators.find((indicator) => indicator.id === selectedIndicatorId) || null,
    [indicators, selectedIndicatorId]
  );

  useEffect(() => {
    setMruItems(readIndicatorMruItems());
  }, []);

  useEffect(() => {
    let mounted = true;
    async function loadMetadata() {
      setMetadataLoading(true);
      setError(null);
      try {
        const response = await securityScanApi.getIndicatorMetadata();
        if (!mounted) {
          return;
        }
        setIndicators(response.indicators);
        setMruItems((items) => filterMruByMetadata(items, response.indicators));
        if (response.indicators.length > 0) {
          setSelectedIndicatorId(response.indicators[0].id);
          setParameterInputs(buildParameterInputs(response.indicators[0]));
        }
      } catch (err) {
        if (mounted) {
          setError(errorMessageFromUnknown(err));
        }
      } finally {
        if (mounted) {
          setMetadataLoading(false);
        }
      }
    }

    loadMetadata();
    return () => {
      mounted = false;
      activeCompute.current?.abort();
    };
  }, []);

  const applySelectedIndicator = useCallback(
    (indicatorId: string) => {
      const indicator = indicators.find((item) => item.id === indicatorId);
      if (!indicator) {
        return;
      }
      setSelectedIndicatorId(indicator.id);
      setParameterInputs(buildParameterInputs(indicator));
      setResult(null);
      setError(null);
    },
    [indicators]
  );

  const handleParameterChange = (
    parameter: IndicatorParameterMetadata,
    value: ParameterInputValue
  ) => {
    setParameterInputs((current) => ({
      ...current,
      [parameter.key]: value,
    }));
  };

  const handleResetParameters = () => {
    if (!selectedIndicator) {
      return;
    }
    setParameterInputs(buildParameterInputs(selectedIndicator));
    setError(null);
  };

  const handleCompute = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (!selectedIndicator) {
      setError('Select an indicator before recomputing');
      return;
    }

    let settings: Record<string, unknown>;
    try {
      settings = buildSettingsFromInputs(selectedIndicator, parameterInputs);
    } catch (err) {
      setError(errorMessageFromUnknown(err));
      return;
    }

    activeCompute.current?.abort();
    const controller = new AbortController();
    activeCompute.current = controller;
    setComputeLoading(true);
    setError(null);

    try {
      const response = await securityScanApi.computeIndicatorDashboard(
        {
          ticker,
          indicator_id: selectedIndicator.id,
          settings,
          start_date: startDate,
          end_date: endDate,
          interval: 'day',
          benchmark_tickers: parseBenchmarkTickers(benchmarkTickers),
        },
        controller.signal
      );
      setResult(response);
      const updatedMru = updateIndicatorMruItems(mruItems, selectedIndicator);
      setMruItems(updatedMru);
      writeIndicatorMruItems(updatedMru);
    } catch (err) {
      setError(errorMessageFromUnknown(err));
    } finally {
      if (activeCompute.current === controller) {
        activeCompute.current = null;
      }
      setComputeLoading(false);
    }
  };

  return (
    <div className="space-y-5 px-2">
      <div className="flex flex-col gap-2 border-b border-gray-200 pb-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-950">
            Security Scan Indicator Workbench
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            {result
              ? `${result.ticker} ${result.indicator_id} from ${result.date_range.start_date} to ${result.date_range.end_date}`
              : 'No computation yet'}
          </p>
        </div>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div>
            <div className="text-gray-500">Price Points</div>
            <div className="font-semibold text-gray-950">
              {result?.diagnostics.price_points ?? '-'}
            </div>
          </div>
          <div>
            <div className="text-gray-500">Indicator Points</div>
            <div className="font-semibold text-gray-950">
              {result?.diagnostics.indicator_points ?? '-'}
            </div>
          </div>
          <div>
            <div className="text-gray-500">Signals</div>
            <div className="font-semibold text-gray-950">
              {result?.signals.length ?? '-'}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form
        className="space-y-4 rounded-md border border-gray-200 bg-white p-4 shadow-sm"
        onSubmit={handleCompute}
      >
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-6">
          <label className="block">
            <span className="form-label">Ticker</span>
            <input
              className="form-input uppercase"
              value={ticker}
              onChange={(event) => setTicker(event.target.value.toUpperCase())}
            />
          </label>
          <label className="block">
            <span className="form-label">Start Date</span>
            <input
              className="form-input"
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="form-label">End Date</span>
            <input
              className="form-input"
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="form-label">Interval</span>
            <select className="form-select" value="day" disabled>
              <option value="day">Day</option>
            </select>
          </label>
          <label className="block lg:col-span-2">
            <span className="form-label">Benchmarks</span>
            <input
              className="form-input"
              value={benchmarkTickers}
              onChange={(event) => setBenchmarkTickers(event.target.value)}
            />
            {selectedIndicator?.requires_benchmarks && (
              <span className="mt-1 block text-xs text-gray-500">
                Required for benchmark-relative indicators. Separate tickers with
                commas.
              </span>
            )}
          </label>
        </div>

        <div className="grid grid-cols-1 gap-4 border-t border-gray-100 pt-4 lg:grid-cols-[minmax(240px,320px)_1fr]">
          <div>
            <label className="block">
              <span className="form-label">Indicator</span>
              <select
                className="form-select"
                value={selectedIndicatorId}
                onChange={(event) => applySelectedIndicator(event.target.value)}
                disabled={metadataLoading || indicators.length === 0}
              >
                {indicators.map((indicator) => (
                  <option key={indicator.id} value={indicator.id}>
                    {indicator.label}
                  </option>
                ))}
              </select>
            </label>
            {mruItems.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {mruItems.map((item) => (
                  <button
                    key={item.indicator_id}
                    type="button"
                    className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:border-cyan-600 hover:text-cyan-700"
                    onClick={() => applySelectedIndicator(item.indicator_id)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {selectedIndicator?.parameters.map((parameter) => (
              <label key={parameter.key} className="block">
                <span className="form-label">{parameter.label}</span>
                {parameter.type === 'boolean' ? (
                  <input
                    type="checkbox"
                    checked={Boolean(parameterInputs[parameter.key])}
                    onChange={(event) =>
                      handleParameterChange(parameter, event.target.checked)
                    }
                    className="mt-3 h-5 w-5 rounded border-gray-300 text-cyan-700"
                  />
                ) : (
                  <input
                    className="form-input"
                    type={
                      parameter.type === 'integer' || parameter.type === 'float'
                        ? 'number'
                        : 'text'
                    }
                    min={parameter.min ?? undefined}
                    max={parameter.max ?? undefined}
                    step={parameter.type === 'integer' ? 1 : undefined}
                    value={String(parameterInputs[parameter.key] ?? '')}
                    onChange={(event) =>
                      handleParameterChange(parameter, event.target.value)
                    }
                  />
                )}
                {parameter.description && (
                  <span className="mt-1 block text-xs text-gray-500">
                    {parameter.description}
                  </span>
                )}
              </label>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-gray-100 pt-4">
          <button
            type="submit"
            className="rounded-md bg-cyan-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-cyan-800 disabled:cursor-not-allowed disabled:bg-gray-400"
            disabled={metadataLoading || computeLoading || !selectedIndicator}
          >
            {computeLoading ? 'Recomputing...' : 'Recompute'}
          </button>
          <button
            type="button"
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
            onClick={handleResetParameters}
            disabled={!selectedIndicator}
          >
            Reset Parameters
          </button>
          {selectedIndicator && (
            <span className="text-sm text-gray-600">
              {selectedIndicator.description}
            </span>
          )}
        </div>
      </form>

      <div className="rounded-md border border-gray-200 bg-white p-3 shadow-sm">
        {metadataLoading ? (
          <div className="flex h-[520px] items-center justify-center text-gray-600">
            Loading indicators...
          </div>
        ) : result ? (
          <IndicatorDashboardChart result={result} />
        ) : (
          <div className="flex h-[520px] items-center justify-center text-gray-600">
            No computation yet.
          </div>
        )}
      </div>

      {result && (
        <div className="space-y-3">
          {result.diagnostics.warnings.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {result.diagnostics.warnings.map((warning) => (
                <div key={warning}>{warning}</div>
              ))}
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
            <div className="rounded-md border border-gray-200 bg-white p-3">
              <div className="font-semibold text-gray-900">Resolved Settings</div>
              <pre className="mt-2 max-h-48 overflow-auto rounded bg-gray-950 p-3 text-xs text-gray-100">
                {JSON.stringify(result.resolved_settings, null, 2)}
              </pre>
            </div>
            <div className="rounded-md border border-gray-200 bg-white p-3">
              <div className="font-semibold text-gray-900">Diagnostics</div>
              <pre className="mt-2 max-h-48 overflow-auto rounded bg-gray-950 p-3 text-xs text-gray-100">
                {JSON.stringify(result.diagnostics, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
