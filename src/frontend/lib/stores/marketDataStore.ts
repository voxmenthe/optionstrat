/**
 * Market Data Store
 * Manages state for market data including ticker search, stock prices, and option chains
 */

import { create } from 'zustand';
import { marketDataApi, TickerInfo, OptionChainItem, ExpirationDate } from '../api';

export interface MarketDataStore {
  // State
  tickerInfo: TickerInfo | null;
  searchResults: TickerInfo[];
  stockPrice: number | null;
  optionChain: OptionChainItem[];
  expirationDates: ExpirationDate[];
  selectedExpiration: string | null;
  loading: boolean;
  error: string | null;
  
  // Actions
  searchTicker: (query: string) => Promise<void>;
  getTickerInfo: (ticker: string) => Promise<void>;
  getStockPrice: (ticker: string) => Promise<void>;
  getExpirationDates: (ticker: string) => Promise<void>;
  getOptionChain: (ticker: string, expiration: string) => Promise<void>;
  setSelectedExpiration: (expiration: string | null) => void;
  clearSearchResults: () => void;
  clearError: () => void;
}

export const useMarketDataStore = create<MarketDataStore>((set, get) => ({
  // Initial state
  tickerInfo: null,
  searchResults: [],
  stockPrice: null,
  optionChain: [],
  expirationDates: [],
  selectedExpiration: null,
  loading: false,
  error: null,
  
  // Search for a ticker
  searchTicker: async (query: string) => {
    if (!query || query.trim() === '') {
      set({ searchResults: [] });
      return;
    }
    
    set({ loading: true, error: null });
    try {
      const results = await marketDataApi.searchTicker(query);
      set({ searchResults: results, loading: false });
    } catch (error) {
      set({ 
        error: `Failed to search ticker: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Get ticker information
  getTickerInfo: async (ticker: string) => {
    set({ loading: true, error: null });
    try {
      const tickerInfo = await marketDataApi.getTickerInfo(ticker);
      set({ tickerInfo, loading: false });
    } catch (error) {
      set({ 
        error: `Failed to get ticker info: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Get current stock price
  getStockPrice: async (ticker: string) => {
    set({ loading: true, error: null });
    try {
      const stockPrice = await marketDataApi.getStockPrice(ticker);
      set({ stockPrice, loading: false });
    } catch (error) {
      set({ 
        error: `Failed to get stock price: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Get available expiration dates
  getExpirationDates: async (ticker: string) => {
    set({ loading: true, error: null });
    try {
      const expirationDates = await marketDataApi.getExpirationDates(ticker);
      
      // If we have expirations, select the first one by default
      const selectedExpiration = expirationDates.length > 0 ? expirationDates[0].date : null;
      
      set({ 
        expirationDates, 
        selectedExpiration, 
        loading: false 
      });
    } catch (error) {
      set({ 
        error: `Failed to get expiration dates: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Get option chain for a ticker and expiration
  getOptionChain: async (ticker: string, expiration: string) => {
    set({ loading: true, error: null });
    try {
      const optionChain = await marketDataApi.getOptionChain(ticker, expiration);
      set({ 
        optionChain, 
        selectedExpiration: expiration, 
        loading: false 
      });
    } catch (error) {
      set({ 
        error: `Failed to get option chain: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Set selected expiration date
  setSelectedExpiration: (expiration: string | null) => {
    set({ selectedExpiration: expiration });
    
    // If we have a ticker and a new expiration, fetch the option chain
    const { tickerInfo } = get();
    if (tickerInfo && expiration) {
      get().getOptionChain(tickerInfo.ticker, expiration);
    }
  },
  
  // Clear search results
  clearSearchResults: () => {
    set({ searchResults: [] });
  },
  
  // Clear error
  clearError: () => {
    set({ error: null });
  }
})); 