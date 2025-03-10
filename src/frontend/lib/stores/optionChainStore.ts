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
  
  // Set selected expiration and fetch option chain
  setSelectedExpiration: async (date: string) => {
    const { ticker, filters, expirations } = get();
    
    if (!ticker || !date) {
      logger.warn('OPTION_CHAIN_DEBUG: Missing ticker or date in setSelectedExpiration', { ticker, date });
      return;
    }
    
    // Format the date to ensure it's in YYYY-MM-DD format
    // This handles cases where date might be in ISO format (with time component)
    const formattedDate = date.includes('T') 
      ? date.split('T')[0]  // Extract just the date part if it has a timestamp
      : date;
    
    logger.info('OPTION_CHAIN_DEBUG: Formatting date', { original: date, formatted: formattedDate });
    
    // Check if the expiration date exists in our list of available expirations
    logger.info('OPTION_CHAIN_DEBUG: Checking if expiration exists', { formattedDate, availableExpirations: expirations });
    const expirationExists = expirations.some(exp => {
      const expDate = exp.date.includes('T') 
        ? exp.date.split('T')[0]
        : exp.date;
      return expDate === formattedDate;
    });
    logger.info('OPTION_CHAIN_DEBUG: Expiration exists?', expirationExists);
    
    if (!expirationExists) {
      set({ 
        error: `Expiration date ${formattedDate} is not available for ${ticker}. Please select from the available dates.`,
        isLoading: false
      });
      return;
    }
    
    // IMPORTANT: Update the UI state immediately before starting the async operation
    // This prevents the UI from freezing while waiting for the chain to load
    set({ 
      selectedExpiration: formattedDate, 
      isLoading: true, 
      error: null,
      // Clear chain when changing expiration
      chain: [],
      selectedOption: null
    });
    
    // Use requestAnimationFrame to ensure the UI updates before starting the heavy operation
    // This is crucial for preventing UI freezing
    requestAnimationFrame(async () => {
      // Create an AbortController to handle timeouts and cancellations
      const abortController = new AbortController();
      const timeoutId = setTimeout(() => {
        logger.warn('OPTION_CHAIN_DEBUG: Request timeout after 8 seconds', { ticker, formattedDate });
        abortController.abort();
        // Important: Reset loading state when timeout occurs
        set({ 
          isLoading: false,
          error: 'Request timed out. Please try again.'
        });
      }, 8000); // 8 second timeout - reduced from 10s for better responsiveness
      
      try {
        logger.info('OPTION_CHAIN_DEBUG: Starting to fetch option chain', { ticker, formattedDate });
        
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
        logger.info('OPTION_CHAIN_DEBUG: Generated cache key', cacheKey);
        
        // Try to get option chain from cache first, or fetch if not available
        logger.info('OPTION_CHAIN_DEBUG: Attempting to fetch option chain from cache or API');
        
        // Improved fetch with timeout handling
        const fetchWithTimeout = async () => {
          try {
            // Use a shorter timeout for the Promise.race to ensure responsiveness
            const timeoutPromise = new Promise<OptionContract[]>((_, reject) => {
              setTimeout(() => {
                reject(new Error('Request timed out. Please try again.'));
              }, 10000); // 10 second backup timeout
            });
            
            // Race between the actual fetch and the timeout
            return await Promise.race([
              cacheManager.getOrFetch(
                cacheKey,
                async () => {
                  logger.info('OPTION_CHAIN_DEBUG: Cache miss, fetching from API');
                  
                  // Add a progress update to improve perceived performance
                  setTimeout(() => {
                    if (get().isLoading) {
                      set(state => ({
                        ...state,
                        error: 'Still loading option chain data...'
                      }));
                    }
                  }, 3000);
                  
                  return await optionsApi.getOptionsForExpiration(ticker, formattedDate, params, abortController.signal);
                },
                getMarketAwareTTL()
              ),
              timeoutPromise
            ]);
          } catch (error) {
            if (error && typeof error === 'object' && 'name' in error && error.name === 'AbortError') {
              logger.error('OPTION_CHAIN_DEBUG: Request aborted due to timeout', { ticker, formattedDate });
              throw new Error('Request timed out. Please try again.');
            }
            throw error;
          }
        };
        
        // Execute the fetch operation
        const chain = await fetchWithTimeout();
        
        // Clear the timeout since we got a response
        clearTimeout(timeoutId);
        
        // Check if we still have a valid state (user hasn't navigated away or changed selection)
        if (get().selectedExpiration !== formattedDate) {
          logger.info('OPTION_CHAIN_DEBUG: Expiration changed during fetch, discarding results');
          return;
        }
        
        logger.info(`OPTION_CHAIN_DEBUG: Received chain data with ${chain.length} options`, { chainLength: chain.length });
        
        // Update the state with the chain data
        // Use requestAnimationFrame again to ensure smooth UI updates
        requestAnimationFrame(() => {
          set({ chain, isLoading: false, error: null });
        });
      } catch (error) {
        // Clear the timeout in case of error
        clearTimeout(timeoutId);
        
        logger.error('OPTION_CHAIN_DEBUG: Error fetching option chain', error instanceof Error ? { message: error.message, stack: error.stack } : error);
        
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