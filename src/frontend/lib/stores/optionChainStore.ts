/**
 * Option Chain Store
 * Manages state for option chains, expirations, and selection
 * Serves as the central store for the option chain selector functionality
 */

import { create } from 'zustand';
import { optionsApi, OptionContract, OptionExpiration } from '../api/optionsApi';
import { cacheManager, getOptionChainCacheKey, clearOptionChainCache, getMarketAwareTTL } from '../utils/cacheUtils';
import logger, { LogLevel } from '../utils/logger';

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
    logger.info('OPTION_CHAIN_DEBUG: setTicker called with', { ticker });
    if (!ticker || ticker.trim() === '') {
      logger.info('OPTION_CHAIN_DEBUG: Empty ticker, clearing state');
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
      logger.info('OPTION_CHAIN_DEBUG: Fetching expirations for ticker', { ticker });
      // Try to get expirations from cache first
      const cacheKey = `expirations:${ticker}`;
      logger.info('OPTION_CHAIN_DEBUG: Using cache key for expirations', { cacheKey });
      const expirations = await cacheManager.getOrFetch(
        cacheKey,
        async () => {
          logger.info('OPTION_CHAIN_DEBUG: Cache miss for expirations, fetching from API');
          return await optionsApi.getExpirationDates(ticker);
        },
        getMarketAwareTTL()
      );
      
      logger.info(`OPTION_CHAIN_DEBUG: Received ${expirations.length} expirations for ${ticker}`, { expirations, count: expirations.length });
      
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
      logger.error('OPTION_CHAIN_DEBUG: Error fetching expirations', error instanceof Error ? 
        { message: error.message, stack: error.stack } : error);
      
      // Provide detailed error information for debugging
      const errorMessage = error instanceof Error ? error.message : String(error);
      const errorDetails = error instanceof Error && error.stack ? error.stack : 'No stack trace available';
      
      logger.debug('OPTION_CHAIN_DEBUG: Error details', { errorMessage, errorDetails });
      
      set({ 
        error: `Failed to fetch expirations: ${errorMessage}`, 
        isLoading: false 
      });
    }
  },
  
  // Set selected expiration and fetch the chain for that date
  setSelectedExpiration: async (date: string) => {
    const { ticker, filters } = get();
    const currentSelection = get().selectedExpiration;
    
    logger.info('OPTION_CHAIN_DEBUG: setSelectedExpiration called with', { 
      date, 
      currentSelection,
      previouslySelectedDate: currentSelection,
      ticker
    });
    
    if (!ticker) {
      logger.warn('OPTION_CHAIN_DEBUG: setSelectedExpiration called with no ticker set');
      return;
    }
    
    if (!date) {
      logger.warn('OPTION_CHAIN_DEBUG: setSelectedExpiration called with empty date');
      return;
    }
    
    // Format the date to ensure it's in YYYY-MM-DD format
    const formattedDate = date.includes('T')
      ? date.split('T')[0]  // Extract just the date part if it has a timestamp
      : date;
    
    logger.info('OPTION_CHAIN_DEBUG: Formatted date', { 
      originalDate: date, 
      formattedDate 
    });
    
    // Update the selected expiration immediately
    set({ 
      selectedExpiration: formattedDate, 
      isLoading: true, 
      error: null
    });
    
    // Use requestAnimationFrame to not block the UI
    requestAnimationFrame(async () => {
      // Create an AbortController to handle timeouts and cancellations
      const abortController = new AbortController();
      const signal = abortController.signal;
      
      // Set a timeout for the request
      const timeoutMs = 8000; // 8 second timeout - reduced from 10s for better responsiveness
      const timeoutId = setTimeout(() => {
        logger.warn(`OPTION_CHAIN_DEBUG: Request timeout after ${timeoutMs}ms for ${ticker} at ${formattedDate}`);
        abortController.abort();
      }, timeoutMs);
      
      try {
        logger.info('OPTION_CHAIN_DEBUG: Starting to fetch option chain', { 
          ticker, 
          formattedDate,
          baseApiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003'
        });
        
        // Convert our filter format to API parameters
        const params: {
          option_type?: 'call' | 'put';
          min_strike?: number;
          max_strike?: number;
        } = {};
        
        logger.info('OPTION_CHAIN_DEBUG: Current filters', filters);
        
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
        logger.info('OPTION_CHAIN_DEBUG: Generated cache key', { cacheKey });
        
        // Try to get option chain from cache first, or fetch if not available
        logger.info('OPTION_CHAIN_DEBUG: Attempting to fetch option chain from cache or API');
        
        // Log the full API endpoint being used 
        const apiUrl = `/options/chains/${ticker}/${formattedDate}`;
        logger.info('OPTION_CHAIN_DEBUG: API endpoint target', { 
          apiUrl,
          params
        });

        // Debug: Print the current state of request for debugging
        console.log('OPTION_CHAIN_STATE_DEBUG:', { 
          ticker, 
          formattedDate, 
          params,
          filters,
          isLoading: get().isLoading
        });
        
        // Attempt to fetch from cache or API
        const chain = await cacheManager.getOrFetch(
          cacheKey,
          async () => {
            logger.info('OPTION_CHAIN_DEBUG: Cache miss for option chain, fetching from API');
            try {
              logger.info('OPTION_CHAIN_DEBUG: About to call API.getOptionsForExpiration', {
                ticker,
                formattedDate,
                params
              });
              
              // Make the API call with the abort signal
              const result = await optionsApi.getOptionsForExpiration(
                ticker, 
                formattedDate, 
                params,
                signal
              );
              
              logger.info(`OPTION_CHAIN_DEBUG: API call successful. Received ${result.length} options`);
              
              // Return the result, or empty array if undefined (shouldn't happen)
              return result || [];
            } catch (fetchError) {
              logger.error('OPTION_CHAIN_DEBUG: Error during API fetch', 
                fetchError instanceof Error 
                  ? { message: fetchError.message, stack: fetchError.stack } 
                  : fetchError
              );
              
              // Re-throw to be handled by the main catch block
              throw fetchError;
            }
          },
          getMarketAwareTTL()
        );
        
        // Clear the timeout since the request completed
        clearTimeout(timeoutId);
        
        // Check if we still have a valid state (user hasn't navigated away or changed selection)
        if (get().selectedExpiration !== formattedDate) {
          logger.info('OPTION_CHAIN_DEBUG: Expiration changed during fetch, discarding results');
          return;
        }
        
        logger.info(`OPTION_CHAIN_DEBUG: Received chain data with ${chain.length} options`, { 
          chainLength: chain.length,
          sampleOption: chain.length > 0 ? JSON.stringify(chain[0]).substring(0, 200) + '...' : 'none'
        });
        
        // Update the state with the chain data
        // Use requestAnimationFrame again to ensure smooth UI updates
        requestAnimationFrame(() => {
          set({ chain, isLoading: false, error: null });
          
          // Debug log of first option data for verification
          if (chain.length > 0) {
            logger.info('OPTION_CHAIN_DEBUG: First option in chain:', chain[0]);
          }
        });
      } catch (error) {
        // Clear the timeout in case of error
        clearTimeout(timeoutId);
        
        logger.error('OPTION_CHAIN_DEBUG: Error fetching option chain', 
          error instanceof Error 
            ? { 
                message: error.message, 
                stack: error.stack,
                name: error.name,
                type: error.constructor.name
              } 
            : error
        );
        
        // Provide a more user-friendly error message
        let errorMessage = 'Failed to fetch option chain';
        
        // Safely check if error is an Error object
        if (error instanceof Error) {
          if (error.message.includes('timeout') || error.message.includes('aborted')) {
            errorMessage = 'Request timed out. Please try again.';
          } else {
            errorMessage = `${errorMessage}: ${error.message}`;
          }
        } else if (error && typeof error === 'object') {
          // Handle object-like errors
          const errObj = error as any;
          if (errObj.message) {
            errorMessage = `${errorMessage}: ${errObj.message}`;
          } else if (errObj.toString && typeof errObj.toString === 'function') {
            errorMessage = `${errorMessage}: ${errObj.toString()}`;
          }
        } else {
          // Fallback for primitive error types
          errorMessage = `${errorMessage}: ${String(error)}`;
        }
        
        // Update the state with the error
        // Use requestAnimationFrame to ensure smooth UI updates
        requestAnimationFrame(() => {
          set({ 
            error: errorMessage, 
            isLoading: false 
          });
        });
      }
    });
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
    if (ticker) {
      logger.info(`OPTION_CHAIN_DEBUG: Clearing cache for ticker ${ticker}`);
    } else {
      logger.info('OPTION_CHAIN_DEBUG: Clearing all option chain cache data');
    }
    
    clearOptionChainCache(ticker);
  }
})); 