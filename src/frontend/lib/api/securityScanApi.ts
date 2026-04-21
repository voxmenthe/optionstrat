import apiClient from './apiClient';

export type IndicatorParameterType =
  | 'integer'
  | 'float'
  | 'integer_list'
  | 'boolean'
  | 'string';

export interface IndicatorParameterMetadata {
  key: string;
  label: string;
  type: IndicatorParameterType;
  default: unknown;
  required: boolean;
  min?: number | null;
  max?: number | null;
  description?: string | null;
  item_type?: string | null;
}

export interface IndicatorMetadata {
  id: string;
  label: string;
  description: string;
  default_settings: Record<string, unknown>;
  parameters: IndicatorParameterMetadata[];
  requires_benchmarks: boolean;
  supported_intervals: string[];
}

export interface IndicatorMetadataListResponse {
  indicators: IndicatorMetadata[];
}

export interface IndicatorDashboardComputeRequest {
  ticker: string;
  indicator_id: string;
  settings: Record<string, unknown>;
  start_date: string;
  end_date: string;
  interval: 'day';
  benchmark_tickers: string[];
}

export interface SeriesPoint {
  date: string;
  value: number;
}

export interface PriceSeries {
  label: string;
  points: SeriesPoint[];
}

export interface IndicatorTrace {
  key: string;
  label: string;
  points: SeriesPoint[];
  color?: string | null;
}

export interface IndicatorPanel {
  id: string;
  label: string;
  traces: IndicatorTrace[];
  reference_lines: number[];
}

export interface IndicatorPanelGroup {
  panels: IndicatorPanel[];
}

export interface IndicatorDashboardSignal {
  date: string;
  type: string;
  label: string;
  target_trace: string;
  metadata: Record<string, unknown>;
}

export interface IndicatorDashboardDiagnostics {
  price_points: number;
  indicator_points: number;
  benchmark_tickers_used: string[];
  warnings: string[];
}

export interface IndicatorDashboardComputeResponse {
  ticker: string;
  indicator_id: string;
  resolved_settings: Record<string, unknown>;
  date_range: {
    start_date: string;
    end_date: string;
    interval: string;
  };
  price: PriceSeries;
  indicator: IndicatorPanelGroup;
  signals: IndicatorDashboardSignal[];
  diagnostics: IndicatorDashboardDiagnostics;
}

export const securityScanApi = {
  getIndicatorMetadata: async (): Promise<IndicatorMetadataListResponse> => {
    return apiClient.get<IndicatorMetadataListResponse>('/security-scan/indicators');
  },

  computeIndicatorDashboard: async (
    request: IndicatorDashboardComputeRequest,
    signal?: AbortSignal
  ): Promise<IndicatorDashboardComputeResponse> => {
    return apiClient.post<IndicatorDashboardComputeResponse>(
      '/security-scan/indicator-dashboard/compute',
      request,
      undefined,
      signal,
      30000
    );
  },
};

export default securityScanApi;
