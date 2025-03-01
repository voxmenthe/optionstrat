/**
 * Positions API service
 * Handles all API calls related to option positions
 */

import apiClient from './apiClient';
import { OptionPosition, Greeks, PnLResult } from '../stores/positionStore';

// Backend model types may differ from frontend types
// These interfaces represent the backend models
export interface BackendPosition {
  id: string;
  ticker: string;
  expiration: string;
  strike: number;
  option_type: 'call' | 'put';
  action: 'buy' | 'sell';
  quantity: number;
  premium?: number;
  greeks?: {
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
    rho: number;
  };
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface BackendPositionCreate {
  ticker: string;
  expiration: string;
  strike: number;
  option_type: 'call' | 'put';
  action: 'buy' | 'sell';
  quantity: number;
  premium?: number;
}

export interface BackendPositionWithLegs {
  id: string;
  strategy_type: string;
  ticker: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  legs: BackendPosition[];
}

// Conversion functions between frontend and backend models
const toBackendPosition = (position: Omit<OptionPosition, 'id'>): BackendPositionCreate => ({
  ticker: position.ticker,
  expiration: new Date(position.expiration).toISOString(),
  strike: position.strike,
  option_type: position.type,
  action: position.action,
  quantity: position.quantity,
  premium: position.premium,
});

const toFrontendPosition = (position: BackendPosition): OptionPosition => {
  // Create the base position object
  const frontendPosition: OptionPosition = {
    id: position.id,
    ticker: position.ticker,
    expiration: position.expiration,
    strike: position.strike,
    type: position.option_type,
    action: position.action,
    quantity: position.quantity,
    premium: position.premium,
  };
  
  // Include Greeks if they exist in the backend response
  if (position.greeks) {
    frontendPosition.greeks = position.greeks;
  }
  
  // Include any pnl or theoreticalPnl properties if they exist
  // (These would be included if we extend the API to return them in the future)
  if ((position as any).pnl) {
    frontendPosition.pnl = (position as any).pnl;
  }
  
  if ((position as any).theoretical_pnl) {
    frontendPosition.theoreticalPnl = (position as any).theoretical_pnl;
  }
  
  return frontendPosition;
};

/**
 * Positions API service
 */
export interface PnLCalculationParams {
  days_forward?: number;
  price_change_percent?: number;
  volatility_days?: number;
}

export interface BackendPnLResult {
  position_id: string;
  pnl_amount: number;
  pnl_percent?: number;
  initial_value: number;
  current_value: number;
  implied_volatility?: number;
  underlying_price?: number;
  calculation_timestamp?: string;
}

export const positionsApi = {
  /**
   * Get all positions
   * @param params - Query parameters
   * @returns Promise with positions
   */
  getPositions: async (params?: { 
    skip?: number; 
    limit?: number; 
    active_only?: boolean;
    ticker?: string;
  }): Promise<OptionPosition[]> => {
    console.log('API: Fetching positions with params:', params);
    const response = await apiClient.get<BackendPosition[]>('/positions/', params);
    console.log('API: Received positions response:', response);
    return response.map(toFrontendPosition);
  },
  
  /**
   * Get a position by ID
   * @param id - Position ID
   * @returns Promise with position
   */
  getPosition: async (id: string): Promise<OptionPosition> => {
    const response = await apiClient.get<BackendPosition>(`/positions/${id}`);
    return toFrontendPosition(response);
  },
  
  /**
   * Create a new position
   * @param position - Position data
   * @returns Promise with created position
   */
  createPosition: async (position: Omit<OptionPosition, 'id'>): Promise<OptionPosition> => {
    const backendPosition = toBackendPosition(position);
    console.log('API: Creating position with data:', backendPosition);
    const response = await apiClient.post<BackendPosition>('/positions/', backendPosition);
    console.log('API: Created position response:', response);
    return toFrontendPosition(response);
  },
  
  /**
   * Update a position
   * @param id - Position ID
   * @param position - Position data to update
   * @returns Promise with updated position
   */
  updatePosition: async (id: string, position: Partial<OptionPosition>): Promise<OptionPosition> => {
    // Convert partial frontend position to partial backend position
    const backendUpdate: Partial<BackendPosition> = {};
    
    if (position.ticker !== undefined) backendUpdate.ticker = position.ticker;
    if (position.expiration !== undefined) backendUpdate.expiration = position.expiration;
    if (position.strike !== undefined) backendUpdate.strike = position.strike;
    if (position.type !== undefined) backendUpdate.option_type = position.type;
    if (position.action !== undefined) backendUpdate.action = position.action;
    if (position.quantity !== undefined) backendUpdate.quantity = position.quantity;
    if (position.premium !== undefined) backendUpdate.premium = position.premium;
    
    console.log(`API: Updating position ${id} with data:`, backendUpdate);
    const response = await apiClient.put<BackendPosition>(`/positions/${id}/`, backendUpdate);
    console.log('API: Updated position response:', response);
    return toFrontendPosition(response);
  },
  
  /**
   * Delete a position
   * @param id - Position ID
   * @returns Promise with deleted position
   */
  deletePosition: async (id: string): Promise<OptionPosition> => {
    console.log(`API: Deleting position ${id}`);
    const response = await apiClient.delete<BackendPosition>(`/positions/${id}/`);
    console.log('API: Deleted position response:', response);
    return toFrontendPosition(response);
  },

  /**
   * Calculate current P&L for a position
   * @param id - Position ID
   * @param recalculate - Force recalculation instead of using saved values
   * @returns Promise with P&L calculation result
   */
  calculatePnL: async (id: string, recalculate: boolean = false): Promise<PnLResult> => {
    console.log(`API: Calculating P&L for position ${id}, recalculate=${recalculate}`);
    const response = await apiClient.get<BackendPnLResult>(`/positions/${id}/pnl?recalculate=${recalculate}`);
    console.log('API: P&L calculation response:', response);
    
    return {
      positionId: response.position_id,
      pnlAmount: response.pnl_amount,
      pnlPercent: response.pnl_percent || 0,
      initialValue: response.initial_value,
      currentValue: response.current_value,
      impliedVolatility: response.implied_volatility,
      underlyingPrice: response.underlying_price,
      calculationTimestamp: response.calculation_timestamp,
    };
  },

  /**
   * Calculate theoretical P&L for a position based on days forward and price change percentage
   * @param id - Position ID
   * @param params - P&L calculation parameters (days forward, price change %)
   * @param recalculate - Force recalculation instead of using saved values
   * @returns Promise with P&L calculation result
   */
  calculateTheoreticalPnL: async (id: string, params: PnLCalculationParams, recalculate: boolean = false): Promise<PnLResult> => {
    console.log(`API: Calculating theoretical P&L for position ${id} with params:`, params, `recalculate=${recalculate}`);
    const response = await apiClient.post<BackendPnLResult>(`/positions/${id}/theoretical-pnl?recalculate=${recalculate}`, params);
    console.log('API: Theoretical P&L calculation response:', response);
    
    return {
      positionId: response.position_id,
      pnlAmount: response.pnl_amount,
      pnlPercent: response.pnl_percent || 0,
      initialValue: response.initial_value,
      currentValue: response.current_value,
      impliedVolatility: response.implied_volatility,
      underlyingPrice: response.underlying_price,
      calculationTimestamp: response.calculation_timestamp,
    };
  },

  /**
   * Calculate theoretical P&L for multiple positions based on days forward and price change percentage
   * @param ids - Array of position IDs
   * @param params - P&L calculation parameters (days forward, price change %)
   * @param recalculate - Force recalculation instead of using saved values
   * @returns Promise with P&L calculation results keyed by position ID
   */
  calculateBulkTheoreticalPnL: async (ids: string[], params: PnLCalculationParams, recalculate: boolean = false): Promise<Record<string, PnLResult>> => {
    console.log(`API: Calculating bulk theoretical P&L for ${ids.length} positions with params:`, params, `recalculate=${recalculate}`);
    const response = await apiClient.post<BackendPnLResult[]>(`/positions/bulk-theoretical-pnl?recalculate=${recalculate}`, {
      position_ids: ids,
      ...params
    });
    console.log('API: Bulk theoretical P&L calculation response:', response);
    
    // Convert the array to a record keyed by position ID
    const results: Record<string, PnLResult> = {};
    response.forEach(item => {
      results[item.position_id] = {
        positionId: item.position_id,
        pnlAmount: item.pnl_amount,
        pnlPercent: item.pnl_percent || 0,
        initialValue: item.initial_value,
        currentValue: item.current_value,
        impliedVolatility: item.implied_volatility,
        underlyingPrice: item.underlying_price,
        calculationTimestamp: item.calculation_timestamp,
      };
    });
    
    return results;
  },
};

export default positionsApi; 