/**
 * Greeks API service
 * Handles all API calls related to option Greeks calculations
 */

import apiClient from './apiClient';
import { OptionPosition, Greeks } from '../stores/positionStore';

// Backend model types
export interface GreeksRequest {
  ticker: string;
  expiration: string;
  strike: number;
  option_type: 'call' | 'put';
  underlying_price?: number;
  volatility?: number;
  risk_free_rate?: number;
  dividend_yield?: number;
  action?: 'buy' | 'sell';
  quantity?: number;
}

export interface GreeksResponse {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  implied_volatility?: number;
  price?: number;
}

// Convert frontend position to Greeks request
const toGreeksRequest = (position: OptionPosition, params?: {
  underlying_price?: number;
  volatility?: number;
  risk_free_rate?: number;
  dividend_yield?: number;
}): GreeksRequest => ({
  ticker: position.ticker,
  expiration: position.expiration,
  strike: position.strike,
  option_type: position.type,
  action: position.action,
  quantity: position.quantity,
  ...params
});

/**
 * Greeks API service
 */
export const greeksApi = {
  /**
   * Calculate Greeks for a position
   * @param position - Option position
   * @param params - Optional parameters for calculation
   * @returns Promise with Greeks
   */
  calculateGreeks: async (
    position: OptionPosition,
    params?: {
      underlying_price?: number;
      volatility?: number;
      risk_free_rate?: number;
      dividend_yield?: number;
    }
  ): Promise<Greeks> => {
    // Make sure we include action and quantity in the request
    // to ensure the backend can properly adjust for short positions
    const request = toGreeksRequest(position, params);
    
    // Ensure action and quantity are explicitly set
    if (!request.action) {
      request.action = position.action;
    }
    
    if (!request.quantity) {
      request.quantity = position.quantity;
    }
    
    const response = await apiClient.post<GreeksResponse>('/greeks/calculate', request);
    
    return {
      delta: response.delta,
      gamma: response.gamma,
      theta: response.theta,
      vega: response.vega,
      rho: response.rho
    };
  },
  
  /**
   * Get Greeks for a position directly from the backend using position ID
   * This is preferred when the position already exists in the database
   * @param positionId - ID of the position
   * @param forceRecalculate - Whether to force recalculation of Greeks
   * @returns Promise with Greeks
   */
  getPositionGreeks: async (positionId: string, forceRecalculate: boolean = true): Promise<Greeks> => {
    // Always force recalculation to ensure fresh values
    const response = await apiClient.get<GreeksResponse>(`/greeks/position/${positionId}?force_recalculate=${forceRecalculate}`);
    
    return {
      delta: response.delta,
      gamma: response.gamma,
      theta: response.theta,
      vega: response.vega,
      rho: response.rho
    };
  },
  
  /**
   * Calculate implied volatility for a position
   * @param position - Option position
   * @param marketPrice - Market price of the option
   * @param params - Optional parameters for calculation
   * @returns Promise with implied volatility
   */
  calculateImpliedVolatility: async (
    position: OptionPosition,
    marketPrice: number,
    params?: {
      underlying_price?: number;
      risk_free_rate?: number;
      dividend_yield?: number;
    }
  ): Promise<number> => {
    const request = {
      ...toGreeksRequest(position, params),
      market_price: marketPrice
    };
    
    const response = await apiClient.post<{ implied_volatility: number }>('/greeks/implied-volatility', request);
    return response.implied_volatility;
  },
  
  /**
   * Calculate option price
   * @param position - Option position
   * @param params - Optional parameters for calculation
   * @returns Promise with option price
   */
  calculatePrice: async (
    position: OptionPosition,
    params?: {
      underlying_price?: number;
      volatility?: number;
      risk_free_rate?: number;
      dividend_yield?: number;
    }
  ): Promise<number> => {
    const request = toGreeksRequest(position, params);
    const response = await apiClient.post<{ price: number }>('/greeks/price', request);
    return response.price;
  }
};

export default greeksApi; 