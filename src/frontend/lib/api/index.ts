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