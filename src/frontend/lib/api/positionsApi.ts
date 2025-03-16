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
   * @param signal - AbortController signal for cancelling the request
   * @returns Promise with positions
   */
  getPositions: async (params?: { 
    skip?: number; 
    limit?: number; 
    active_only?: boolean;
    ticker?: string;
  }, signal?: AbortSignal): Promise<OptionPosition[]> => {
    console.log('API: Fetching positions with params:', params);
    try {
      const startTime = performance.now();
      const response = await apiClient.get<BackendPosition[]>('/positions/', params, signal);
      const endTime = performance.now();
      console.log(`API: Received positions response in ${Math.round(endTime - startTime)}ms:`, response);
      return Array.isArray(response) ? response.map(toFrontendPosition) : [];
    } catch (error) {
      console.error('API: Error fetching positions:', error);
      // Return empty array instead of throwing to prevent UI from breaking
      return [];
    }
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
    const response = await apiClient.put<BackendPosition>(`/positions/${id}/`, backendUpdate, undefined, undefined, 30000);
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
    const response = await apiClient.delete<BackendPosition>(`/positions/${id}/`, undefined, undefined, 30000);
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
    // Check if we're in development mode to reduce console noise
    const isDev = process.env.NODE_ENV === 'development';
    
    if (isDev) {
      // In development, log with lower severity
      console.debug(`API: Calculating P&L for position ${id}, recalculate=${recalculate}`);
    }
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        if (isDev) {
          console.debug(`API: P&L calculation timed out for position ${id}`);
        }
        controller.abort();
      }, 5000); // 5 second timeout
      
      const response = await apiClient.get<BackendPnLResult>(
        `/positions/${id}/pnl?recalculate=${recalculate}`,
        undefined,
        controller.signal,
        5000
      );
      
      clearTimeout(timeoutId);
      
      if (isDev) {
        console.debug('API: P&L calculation response:', response);
      }
      
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
    } catch (error) {
      // For network errors (status 0), don't log to console as these are expected
      // until the backend endpoints are implemented
      if ((error as any)?.status !== 0) {
        console.warn(`API: Error calculating P&L for position ${id}:`, error);
      }
      
      // Return a default PnL result to prevent UI from breaking
      return {
        positionId: id,
        pnlAmount: 0,
        pnlPercent: 0,
        initialValue: 0,
        currentValue: 0,
        calculationTimestamp: new Date().toISOString(),
        error: error instanceof Error ? error.message : String(error),
        endpointNotImplemented: (error as any)?.status === 0 || (error as any)?.status === 404 || (error as any)?.status === 501
      };
    }
  },

  /**
   * Calculate theoretical P&L for a position based on days forward and price change percentage
   * @param id - Position ID
   * @param params - P&L calculation parameters (days forward, price change %)
   * @param recalculate - Force recalculation instead of using saved values
   * @returns Promise with P&L calculation result
   */
  calculateTheoreticalPnL: async (id: string, params: PnLCalculationParams, recalculate: boolean = false): Promise<PnLResult> => {
    // Check if we're in development mode to reduce console noise
    const isDev = process.env.NODE_ENV === 'development';
    
    if (isDev) {
      // In development, log with lower severity
      console.debug(`API: Calculating theoretical P&L for position ${id} with params:`, params, `recalculate=${recalculate}`);
    }
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        if (isDev) {
          console.debug(`API: Theoretical P&L calculation timed out for position ${id}`);
        }
        controller.abort();
      }, 5000); // 5 second timeout
      
      const response = await apiClient.post<BackendPnLResult>(
        `/positions/${id}/theoretical-pnl?recalculate=${recalculate}`,
        params,
        undefined,
        controller.signal,
        5000
      );
      
      clearTimeout(timeoutId);
      
      if (isDev) {
        console.debug('API: Theoretical P&L calculation response:', response);
      }
      
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
    } catch (error) {
      // For network errors (status 0), don't log to console as these are expected
      // until the backend endpoints are implemented
      if ((error as any)?.status !== 0) {
        console.warn(`API: Error calculating theoretical P&L for position ${id}:`, error);
      }
      
      // Return a default PnL result to prevent UI from breaking
      return {
        positionId: id,
        pnlAmount: 0,
        pnlPercent: 0,
        initialValue: 0,
        currentValue: 0,
        calculationTimestamp: new Date().toISOString(),
        error: error instanceof Error ? error.message : String(error),
        endpointNotImplemented: (error as any)?.status === 0 || (error as any)?.status === 404 || (error as any)?.status === 501
      };
    }
  },

  /**
   * Calculate theoretical P&L for multiple positions based on days forward and price change percentage
   * @param ids - Array of position IDs
   * @param params - P&L calculation parameters (days forward, price change %)
   * @param recalculate - Force recalculation instead of using saved values
   * @returns Promise with P&L calculation results keyed by position ID
   */
  calculateBulkTheoreticalPnL: async (ids: string[], params: PnLCalculationParams, recalculate: boolean = false): Promise<Record<string, PnLResult>> => {
    // Check if we're in development mode to reduce console noise
    const isDev = process.env.NODE_ENV === 'development';
    
    if (isDev) {
      // In development, log with lower severity
      console.debug(`API: Calculating bulk theoretical P&L for ${ids.length} positions with params:`, params, `recalculate=${recalculate}`);
    }
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        if (isDev) {
          console.debug(`API: Bulk theoretical P&L calculation timed out for ${ids.length} positions`);
        }
        controller.abort();
      }, 8000); // 8 second timeout for bulk operations
      
      const response = await apiClient.post<BackendPnLResult[]>(
        `/positions/bulk-theoretical-pnl?recalculate=${recalculate}`,
        {
          position_ids: ids,
          ...params
        },
        undefined,
        controller.signal,
        8000
      );
      
      clearTimeout(timeoutId);
      
      if (isDev) {
        console.debug('API: Bulk theoretical P&L calculation response:', response);
      }
      
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
    } catch (error) {
      // For network errors (status 0), don't log to console as these are expected
      // until the backend endpoints are implemented
      if ((error as any)?.status !== 0) {
        console.warn(`API: Error calculating bulk theoretical P&L for ${ids.length} positions:`, error);
      }
      
      // Return a default PnL result for each position to prevent UI from breaking
      const results: Record<string, PnLResult> = {};
      ids.forEach(id => {
        results[id] = {
          positionId: id,
          pnlAmount: 0,
          pnlPercent: 0,
          initialValue: 0,
          currentValue: 0,
          calculationTimestamp: new Date().toISOString(),
          error: error instanceof Error ? error.message : String(error),
          endpointNotImplemented: (error as any)?.status === 0 || (error as any)?.status === 404 || (error as any)?.status === 501
        };
      });
      return results;
    }
  },
};

export default positionsApi; 