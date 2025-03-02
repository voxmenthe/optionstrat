/**
 * Option Chain Store
 * Manages state for option chains, expirations, and selection
 * Serves as the central store for the option chain selector functionality
 */

import { create } from 'zustand';
import { optionsApi, OptionContract, OptionExpiration } from '../api/optionsApi';

export interface OptionChainState {
  // State
  ticker: string;
  expirations: OptionExpiration[];
  selectedExpiration: string | null;
  chain: OptionContract[];
  isLoading: boolean;
  error: string | null;
  filters: {
    optionType: 'all' | 'call' | 'put';
    minStrike: number | null;
    maxStrike: number | null;
    minIV: number | null;
    maxIV: number | null;
  };
  selectedOption: OptionContract | null;

  // Actions
  setTicker: (ticker: string) => Promise<void>;
  setSelectedExpiration: (date: string) => Promise<void>;
  setFilter: (filter: Partial<OptionChainState['filters']>) => void;
  refreshChain: () => Promise<void>;
  selectOption: (option: OptionContract | null) => void;
  clear: () => void;
}

export const useOptionChainStore = create<OptionChainState>((set, get) => ({
  // Initial state
  ticker: '',
  expirations: [],
  selectedExpiration: null,
  chain: [],
  isLoading: false,
  error: null,
  filters: {
    optionType: 'all',
    minStrike: null,
    maxStrike: null,
    minIV: null,
    maxIV: null,
  },
  selectedOption: null,

  // Set ticker and fetch expirations
  setTicker: async (ticker: string) => {
    if (!ticker || ticker.trim() === '') {
      set({ 
        ticker: '',
        expirations: [],
        selectedExpiration: null,
        chain: [],
        error: null
      });
      return;
    }
    
    set({ 
      ticker, 
      isLoading: true, 
      error: null,
      // Clear related state when changing tickers
      expirations: [],
      selectedExpiration: null,
      chain: [],
      selectedOption: null
    });
    
    try {
      const expirations = await optionsApi.getExpirationDates(ticker);
      
      // If we have expirations, select the first one by default
      const selectedExpiration = expirations.length > 0 ? expirations[0].date : null;
      
      set({ 
        expirations, 
        selectedExpiration, 
        isLoading: false 
      });
      
      // If we have a selected expiration, fetch the chain
      if (selectedExpiration) {
        await get().setSelectedExpiration(selectedExpiration);
      }
    } catch (error) {
      set({ 
        error: `Failed to fetch expirations: ${error instanceof Error ? error.message : String(error)}`, 
        isLoading: false 
      });
    }
  },
  
  // Set selected expiration and fetch option chain
  setSelectedExpiration: async (date: string) => {
    const { ticker, filters } = get();
    
    if (!ticker || !date) {
      return;
    }
    
    set({ 
      selectedExpiration: date, 
      isLoading: true, 
      error: null,
      // Clear chain when changing expiration
      chain: [],
      selectedOption: null
    });
    
    try {
      // Convert our filter format to API parameters
      const params: {
        option_type?: 'call' | 'put';
        min_strike?: number;
        max_strike?: number;
      } = {};
      
      if (filters.optionType !== 'all') {
        params.option_type = filters.optionType;
      }
      
      if (filters.minStrike !== null) {
        params.min_strike = filters.minStrike;
      }
      
      if (filters.maxStrike !== null) {
        params.max_strike = filters.maxStrike;
      }
      
      const chain = await optionsApi.getOptionsForExpiration(ticker, date, params);
      set({ chain, isLoading: false });
    } catch (error) {
      set({ 
        error: `Failed to fetch option chain: ${error instanceof Error ? error.message : String(error)}`, 
        isLoading: false 
      });
    }
  },
  
  // Update filters and refresh the chain
  setFilter: (filter: Partial<OptionChainState['filters']>) => {
    const currentFilters = get().filters;
    const newFilters = { ...currentFilters, ...filter };
    set({ filters: newFilters });
    
    // Refresh the chain with the new filters
    get().refreshChain();
  },
  
  // Refresh the current chain with current filters
  refreshChain: async () => {
    const { ticker, selectedExpiration } = get();
    
    if (!ticker || !selectedExpiration) {
      return;
    }
    
    // Use the setSelectedExpiration method to refresh with current filters
    await get().setSelectedExpiration(selectedExpiration);
  },
  
  // Select an option contract
  selectOption: (option: OptionContract | null) => {
    set({ selectedOption: option });
  },
  
  // Clear the store state
  clear: () => {
    set({
      ticker: '',
      expirations: [],
      selectedExpiration: null,
      chain: [],
      isLoading: false,
      error: null,
      filters: {
        optionType: 'all',
        minStrike: null,
        maxStrike: null,
        minIV: null,
        maxIV: null,
      },
      selectedOption: null
    });
  }
})); 