/**
 * Positions API service
 * Handles all API calls related to option positions
 */

import apiClient from './apiClient';
import { OptionPosition, Greeks } from '../stores/positionStore';

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
  expiration: position.expiration,
  strike: position.strike,
  option_type: position.type,
  action: position.action,
  quantity: position.quantity,
  premium: position.premium,
});

const toFrontendPosition = (position: BackendPosition): OptionPosition => ({
  id: position.id,
  ticker: position.ticker,
  expiration: position.expiration,
  strike: position.strike,
  type: position.option_type,
  action: position.action,
  quantity: position.quantity,
  premium: position.premium,
});

/**
 * Positions API service
 */
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
    const response = await apiClient.get<BackendPosition[]>('/positions', params);
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
    const response = await apiClient.post<BackendPosition>('/positions', backendPosition);
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
    
    const response = await apiClient.put<BackendPosition>(`/positions/${id}`, backendUpdate);
    return toFrontendPosition(response);
  },
  
  /**
   * Delete a position
   * @param id - Position ID
   * @returns Promise with deleted position
   */
  deletePosition: async (id: string): Promise<OptionPosition> => {
    const response = await apiClient.delete<BackendPosition>(`/positions/${id}`);
    return toFrontendPosition(response);
  },
};

export default positionsApi; 