/**
 * API services index
 * Export all API services for easy importing
 */

export { default as apiClient, ApiError, ApiClient } from './apiClient';
export { default as positionsApi } from './positionsApi';
export { default as greeksApi } from './greeksApi';
export { default as marketDataApi } from './marketDataApi';
export { default as scenariosApi } from './scenariosApi';
export { optionsApi } from './optionsApi';
export { default as securityScanApi } from './securityScanApi';

// Re-export types
export type { 
  BackendPosition, 
  BackendPositionCreate,
  BackendPositionWithLegs 
} from './positionsApi';

export type { 
  GreeksRequest, 
  GreeksResponse 
} from './greeksApi';

export type { 
  TickerInfo, 
  OptionChainItem, 
  ExpirationDate 
} from './marketDataApi';

export type { 
  ScenarioParams,
  PricePoint,
  VolatilityPoint,
  TimePoint,
  PriceVsVolatilityPoint,
  PnLScenarioPoint,
  ScenarioResult
} from './scenariosApi'; 

export type {
  IndicatorDashboardComputeRequest,
  IndicatorDashboardComputeResponse,
  IndicatorDashboardDiagnostics,
  IndicatorDashboardSignal,
  IndicatorMetadata,
  IndicatorMetadataListResponse,
  IndicatorParameterMetadata,
  IndicatorPanel,
  IndicatorTrace,
  PriceSeries,
  SeriesPoint,
} from './securityScanApi';
