/**
 * Scenarios API service
 * Handles all API calls related to scenario analysis
 */

import apiClient from './apiClient';
import { OptionPosition } from '../stores/positionStore';
import { BackendPosition } from './positionsApi';

// Backend model types
export interface ScenarioParams {
  positions: {
    ticker: string;
    expiration: string;
    strike: number;
    option_type: 'call' | 'put';
    action: 'buy' | 'sell';
    quantity: number;
    premium?: number;
  }[];
  price_range?: {
    min: number;
    max: number;
    steps: number;
  };
  volatility_range?: {
    min: number;
    max: number;
    steps: number;
  };
  days_range?: {
    min: number;
    max: number;
    steps: number;
  };
  base_price?: number;
  base_volatility?: number;
  risk_free_rate?: number;
  dividend_yield?: number;
}

export interface PricePoint {
  price: number;
  value: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface VolatilityPoint {
  volatility: number;
  value: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface TimePoint {
  days: number;
  value: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface PriceVsVolatilityPoint {
  price: number;
  volatility: number;
  value: number;
}

export interface ScenarioResult {
  price_points?: PricePoint[];
  volatility_points?: VolatilityPoint[];
  time_points?: TimePoint[];
  price_vs_volatility?: PriceVsVolatilityPoint[];
}

// Convert frontend positions to backend format for scenarios
const toScenarioPositions = (positions: OptionPosition[]) => {
  return positions.map(position => ({
    ticker: position.ticker,
    expiration: position.expiration,
    strike: position.strike,
    option_type: position.type,
    action: position.action,
    quantity: position.quantity,
    premium: position.premium
  }));
};

/**
 * Scenarios API service
 */
export const scenariosApi = {
  /**
   * Analyze price scenarios
   * @param positions - Option positions
   * @param params - Scenario parameters
   * @returns Promise with price scenario results
   */
  analyzePriceScenario: async (
    positions: OptionPosition[],
    params: {
      min_price: number;
      max_price: number;
      steps: number;
      base_volatility?: number;
      days_to_expiration?: number;
      risk_free_rate?: number;
      dividend_yield?: number;
    }
  ): Promise<PricePoint[]> => {
    const request: ScenarioParams = {
      positions: toScenarioPositions(positions),
      price_range: {
        min: params.min_price,
        max: params.max_price,
        steps: params.steps
      },
      base_volatility: params.base_volatility,
      risk_free_rate: params.risk_free_rate,
      dividend_yield: params.dividend_yield
    };
    
    const response = await apiClient.post<ScenarioResult>('/scenarios/price', request);
    return response.price_points || [];
  },
  
  /**
   * Analyze volatility scenarios
   * @param positions - Option positions
   * @param params - Scenario parameters
   * @returns Promise with volatility scenario results
   */
  analyzeVolatilityScenario: async (
    positions: OptionPosition[],
    params: {
      min_volatility: number;
      max_volatility: number;
      steps: number;
      base_price?: number;
      days_to_expiration?: number;
      risk_free_rate?: number;
      dividend_yield?: number;
    }
  ): Promise<VolatilityPoint[]> => {
    const request: ScenarioParams = {
      positions: toScenarioPositions(positions),
      volatility_range: {
        min: params.min_volatility,
        max: params.max_volatility,
        steps: params.steps
      },
      base_price: params.base_price,
      risk_free_rate: params.risk_free_rate,
      dividend_yield: params.dividend_yield
    };
    
    const response = await apiClient.post<ScenarioResult>('/scenarios/volatility', request);
    return response.volatility_points || [];
  },
  
  /**
   * Analyze time decay scenarios
   * @param positions - Option positions
   * @param params - Scenario parameters
   * @returns Promise with time decay scenario results
   */
  analyzeTimeDecayScenario: async (
    positions: OptionPosition[],
    params: {
      min_days: number;
      max_days: number;
      steps: number;
      base_price?: number;
      base_volatility?: number;
      risk_free_rate?: number;
      dividend_yield?: number;
    }
  ): Promise<TimePoint[]> => {
    const request: ScenarioParams = {
      positions: toScenarioPositions(positions),
      days_range: {
        min: params.min_days,
        max: params.max_days,
        steps: params.steps
      },
      base_price: params.base_price,
      base_volatility: params.base_volatility,
      risk_free_rate: params.risk_free_rate,
      dividend_yield: params.dividend_yield
    };
    
    const response = await apiClient.post<ScenarioResult>('/scenarios/time-decay', request);
    return response.time_points || [];
  },
  
  /**
   * Analyze price vs volatility surface
   * @param positions - Option positions
   * @param params - Scenario parameters
   * @returns Promise with price vs volatility surface results
   */
  analyzePriceVsVolatilitySurface: async (
    positions: OptionPosition[],
    params: {
      min_price: number;
      max_price: number;
      price_steps: number;
      min_volatility: number;
      max_volatility: number;
      volatility_steps: number;
      days_to_expiration?: number;
      risk_free_rate?: number;
      dividend_yield?: number;
    }
  ): Promise<PriceVsVolatilityPoint[]> => {
    const request: ScenarioParams = {
      positions: toScenarioPositions(positions),
      price_range: {
        min: params.min_price,
        max: params.max_price,
        steps: params.price_steps
      },
      volatility_range: {
        min: params.min_volatility,
        max: params.max_volatility,
        steps: params.volatility_steps
      },
      risk_free_rate: params.risk_free_rate,
      dividend_yield: params.dividend_yield
    };
    
    const response = await apiClient.post<ScenarioResult>('/scenarios/price-vs-volatility', request);
    return response.price_vs_volatility || [];
  }
};

export default scenariosApi; 