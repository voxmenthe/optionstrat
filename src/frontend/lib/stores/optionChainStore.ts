/**
 * Option Chain Store
 * Manages state for option chains, expirations, and selection
 * Serves as the central store for the option chain selector functionality
 */

import { create } from 'zustand';
import { optionsApi, OptionContract, OptionExpiration } from '../api/optionsApi';
import { cacheManager, getOptionChainCacheKey, clearOptionChainCache, getMarketAwareTTL } from '../utils/cacheUtils';

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
  clearCache: (ticker?: string) => void;
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
      // Try to get expirations from cache first
      const cacheKey = `expirations:${ticker}`;
      const expirations = await cacheManager.getOrFetch(
        cacheKey,
        async () => await optionsApi.getExpirationDates(ticker),
        getMarketAwareTTL()
      );
      
      // If we have expirations, select the first one by default and ensure it's in YYYY-MM-DD format
      let selectedExpiration = null;
      if (expirations.length > 0) {
        const dateStr = expirations[0].date;
        // Format the date to ensure it's in YYYY-MM-DD format
        selectedExpiration = dateStr.includes('T')
          ? dateStr.split('T')[0]  // Extract just the date part if it has a timestamp
          : dateStr;
      }
      
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
    const { ticker, filters, expirations } = get();
    
    if (!ticker || !date) {
      return;
    }
    
    // Format the date to ensure it's in YYYY-MM-DD format
    // This handles cases where date might be in ISO format (with time component)
    const formattedDate = date.includes('T') 
      ? date.split('T')[0]  // Extract just the date part if it has a timestamp
      : date;
    
    // Check if the expiration date exists in our list of available expirations
    const expirationExists = expirations.some(exp => {
      const expDate = exp.date.includes('T') 
        ? exp.date.split('T')[0]
        : exp.date;
      return expDate === formattedDate;
    });
    
    if (!expirationExists) {
      set({ 
        error: `Expiration date ${formattedDate} is not available for ${ticker}. Please select from the available dates.`,
        isLoading: false
      });
      return;
    }
    
    set({ 
      selectedExpiration: formattedDate, 
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
      
      // Generate cache key based on ticker, expiration, and filters
      const cacheKey = getOptionChainCacheKey(ticker, formattedDate, params);
      
      // Try to get option chain from cache first, or fetch if not available
      const chain = await cacheManager.getOrFetch(
        cacheKey,
        async () => await optionsApi.getOptionsForExpiration(ticker, formattedDate, params),
        getMarketAwareTTL()
      );
      
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
  },
  
  // Clear cache for a specific ticker or all option chain data
  clearCache: (ticker?: string) => {
    clearOptionChainCache(ticker);
  }
})); 