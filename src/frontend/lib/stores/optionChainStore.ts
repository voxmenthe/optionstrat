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
      logger.info('OPTION_CHAIN_DEBUG: Fetching expirations for', { ticker });
      const expirations = await optionsApi.getExpirations(ticker);
      
      // Check if ticker is still the same (user might have changed it while loading)
      if (get().ticker === ticker) {
        logger.info('OPTION_CHAIN_DEBUG: Received expirations', { 
          ticker, 
          count: expirations.length 
        });
        set({ expirations, isLoading: false });
        
        // Auto-select first expiration if available
        if (expirations.length > 0) {
          const firstExpiration = expirations[0].date;
          logger.info('OPTION_CHAIN_DEBUG: Auto-selecting first expiration', { 
            firstExpiration 
          });
          // Call the setSelectedExpiration action
          get().setSelectedExpiration(firstExpiration);
        } else {
          logger.warn('OPTION_CHAIN_DEBUG: No expirations available for', { ticker });
          set({ isLoading: false });
        }
      } else {
        logger.info('OPTION_CHAIN_DEBUG: Ticker changed during expirations fetch, discarding results');
      }
    } catch (error) {
      logger.error('OPTION_CHAIN_DEBUG: Error fetching expirations', { 
        ticker, 
        error: error instanceof Error ? error.message : String(error) 
      });
      
      // Only update state if ticker is still the same
      if (get().ticker === ticker) {
        set({ 
          error: `Failed to fetch expirations: ${error instanceof Error ? error.message : String(error)}`,
          isLoading: false
        });
      }
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
              
              // Log the raw response data for debugging
              logger.info('OPTION_CHAIN_DEBUG: Raw API response sample', {
                sample: result.length > 0 ? JSON.stringify(result[0]).substring(0, 200) + '...' : 'empty',
                count: result.length
              });
              
              // Check if we have any data at all
              if (!result || !Array.isArray(result) || result.length === 0) {
                logger.warn('OPTION_CHAIN_DEBUG: Empty or invalid result from API');
                return [];
              }
              
              // Less strict validation - only log warnings but don't filter out options
              // This ensures we don't lose data due to validation issues
              result.forEach((option, index) => {
                if (!option || typeof option !== 'object') {
                  logger.warn(`OPTION_CHAIN_DEBUG: Invalid option at index ${index}:`, option);
                } else {
                  // Check for missing required fields but don't filter
                  const missingFields = [];
                  if (!option.ticker) missingFields.push('ticker');
                  if (!option.optionType) missingFields.push('optionType');
                  if (!option.strike) missingFields.push('strike');
                  if (!option.expiration) missingFields.push('expiration');
                  
                  if (missingFields.length > 0) {
                    logger.warn(`OPTION_CHAIN_DEBUG: Option at index ${index} missing fields:`, {
                      missingFields,
                      option
                    });
                  }
                }
              });
              
              // Return the original results without filtering
              return result;
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
          // Log the chain data for debugging
          logger.info('OPTION_CHAIN_DEBUG: Chain data received', {
            length: chain.length,
            sample: chain.length > 0 ? JSON.stringify(chain[0]).substring(0, 200) + '...' : 'none'
          });
          
          // Check if we have any data
          if (chain.length === 0) {
            logger.warn('OPTION_CHAIN_DEBUG: Empty chain data received');
            set({
              chain: [],
              isLoading: false,
              error: 'No option data available for this date. Try another expiration date.'
            });
          } else {
            // We have data, update the state
            set({ chain, isLoading: false, error: null });
            
            // Debug log of first option data for verification
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