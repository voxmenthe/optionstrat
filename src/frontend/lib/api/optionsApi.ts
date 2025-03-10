/**
 * Options API service
 * Handles all API calls related to option chains and market data
 */

import apiClient from './apiClient';
import logger from '../utils/logger';

export interface OptionContract {
  ticker: string;
  expiration: string;
  strike: number;
  optionType: 'call' | 'put';
  bid: number;
  ask: number;
  last?: number;
  volume?: number;
  openInterest?: number;
  impliedVolatility?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  inTheMoney?: boolean;
  underlyingPrice?: number;
}

export interface OptionExpiration {
  date: string;
  formattedDate: string;
}

// Backend model interfaces
interface BackendOptionContract {
  ticker: string;
  expiration: string;
  strike: number;
  option_type: 'call' | 'put';
  bid: number;
  ask: number;
  last?: number;
  volume?: number;
  open_interest?: number;
  implied_volatility?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  in_the_money?: boolean;
  underlying_price?: number;
}

interface BackendOptionExpiration {
  date: string;
  formatted_date: string;
}

// Converter functions
const toFrontendOptionContract = (option: BackendOptionContract): OptionContract => ({
  ticker: option.ticker,
  expiration: option.expiration,
  strike: option.strike,
  optionType: option.option_type,
  bid: option.bid,
  ask: option.ask,
  last: option.last,
  volume: option.volume,
  openInterest: option.open_interest,
  impliedVolatility: option.implied_volatility,
  delta: option.delta,
  gamma: option.gamma,
  theta: option.theta,
  vega: option.vega,
  rho: option.rho,
  inTheMoney: option.in_the_money,
  underlyingPrice: option.underlying_price
});

const toFrontendOptionExpiration = (expiration: BackendOptionExpiration): OptionExpiration => ({
  date: expiration.date,
  formattedDate: expiration.formatted_date
});

/**
 * Options API service
 */
export const optionsApi = {
  /**
   * Get options chain for a ticker
   * @param ticker - Ticker symbol
   * @param params - Optional parameters
   * @returns Promise with option chain data
   */
  getOptionsChain: async (
    ticker: string, 
    params?: { 
      expiration_date?: string; 
      option_type?: 'call' | 'put';
      min_strike?: number;
      max_strike?: number;
    }
  ): Promise<OptionContract[]> => {
    try {
      logger.info(`OPTION_CHAIN_DEBUG: Fetching options chain for ${ticker}`, params);
      const response = await apiClient.get<BackendOptionContract[]>(
        `/options/chains/${ticker}`, 
        params
      );
      logger.info(`OPTION_CHAIN_DEBUG: Received ${response.length} options for ${ticker}`);
      
      // Log the first option for debugging
      if (response.length > 0) {
        logger.debug(`OPTION_CHAIN_DEBUG: Sample option data:`, response[0]);
      }
      
      return response.map(toFrontendOptionContract);
    } catch (error: any) {
      logger.error(`OPTION_CHAIN_DEBUG: Error fetching options chain for ${ticker}`, {
        error: error.message,
        status: error.response?.status,
        data: error.response?.data
      });
      throw error;
    }
  },
  
  /**
   * Get available expiration dates for options on a ticker
   * @param ticker - Ticker symbol
   * @returns Promise with expiration dates
   */
  getExpirationDates: async (ticker: string): Promise<OptionExpiration[]> => {
    try {
      logger.info(`OPTION_CHAIN_DEBUG: Fetching expiration dates for ${ticker}`);
      const response = await apiClient.get<BackendOptionExpiration[]>(
        `/options/chains/${ticker}/expirations`
      );
      logger.info(`OPTION_CHAIN_DEBUG: Received ${response.length} expiration dates for ${ticker}`);
      
      // Log all expiration dates for debugging
      logger.debug(`OPTION_CHAIN_DEBUG: Expiration dates:`, response);
      
      return response.map(toFrontendOptionExpiration);
    } catch (error: any) {
      logger.error(`OPTION_CHAIN_DEBUG: Error fetching expiration dates for ${ticker}`, {
        error: error.message,
        status: error.response?.status,
        data: error.response?.data
      });
      throw error;
    }
  },
  
  /**
   * Get options for a specific ticker and expiration date
   * @param ticker - Ticker symbol
   * @param expirationDate - Expiration date
   * @param params - Optional parameters
   * @param signal - Optional AbortController signal for request cancellation
   * @returns Promise with option data
   */
  getOptionsForExpiration: async (
    ticker: string, 
    expirationDate: string,
    params?: { 
      option_type?: 'call' | 'put';
      min_strike?: number;
      max_strike?: number;
    },
    signal?: AbortSignal
  ): Promise<OptionContract[]> => {
    try {
      logger.info(
        `OPTION_CHAIN_DEBUG: Fetching options for ${ticker} with expiration ${expirationDate}`, 
        params
      );
      
      // Add the request configuration with the abort signal
      const config: any = { params };
      if (signal) {
        config.signal = signal;
        logger.info('OPTION_CHAIN_DEBUG: Request configured with AbortSignal');
      }
      
      const response = await apiClient.get<BackendOptionContract[]>(
        `/options/chains/${ticker}/${expirationDate}`, 
        config
      );
      
      logger.info(
        `OPTION_CHAIN_DEBUG: Received ${response.length} options for ${ticker} with expiration ${expirationDate}`
      );
      
      // Log underlying price and first option for debugging
      if (response.length > 0) {
        const underlyingPrice = response[0].underlying_price;
        logger.info(`OPTION_CHAIN_DEBUG: Underlying price for ${ticker}: ${underlyingPrice}`);
        logger.debug(`OPTION_CHAIN_DEBUG: Sample option data:`, response[0]);
      } else {
        logger.warn(`OPTION_CHAIN_DEBUG: No options received for ${ticker} with expiration ${expirationDate}`);
      }
      
      return response.map(toFrontendOptionContract);
    } catch (error: any) {
      // Check if this is an abort error
      if (error.name === 'AbortError' || error.code === 'ECONNABORTED') {
        logger.warn(`OPTION_CHAIN_DEBUG: Request aborted for ${ticker} with expiration ${expirationDate}`);
        throw new Error('Request timed out or was aborted');
      }
      
      logger.error(
        `OPTION_CHAIN_DEBUG: Error fetching options for ${ticker} with expiration ${expirationDate}`, 
        {
          error: error.message,
          status: error.response?.status,
          data: error.response?.data
        }
      );
      
      // Check for 404 error specifically, which would indicate the expiration date doesn't exist
      if (error.response && error.response.status === 404) {
        const errorDetail = error.response.data.detail || '';
        logger.warn(`OPTION_CHAIN_DEBUG: Invalid expiration date: ${errorDetail}`);
        throw new Error(`Invalid expiration date: ${errorDetail}`);
      }
      
      throw error;
    }
  },
  
  /**
   * Search for ticker symbols matching a query
   * @param query - Search query
   * @param limit - Maximum number of results to return
   * @param signal - AbortController signal for cancelling the request
   * @returns Promise with matching ticker symbols
   */
  searchTickers: async (query: string, limit: number = 10, signal?: AbortSignal): Promise<string[]> => {
    try {
      console.log(`API: Searching tickers with query: ${query}, limit: ${limit}`);
      const startTime = performance.now();
      
      const response = await apiClient.get<string[]>(
        `/options/search/${query}`, 
        { limit },
        signal
      );
      
      const endTime = performance.now();
      console.log(`API: Received ticker search results in ${Math.round(endTime - startTime)}ms:`, response);
      
      // Ensure we always return an array, even if the API returns null or undefined
      return Array.isArray(response) ? response : [];
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        console.warn(`API: Search request for ${query} was aborted`);
        return []; // Return empty array on timeout
      }
      console.error(`API: Error searching tickers with query: ${query}:`, error);
      return []; // Return empty array on error instead of throwing
    }
  },
};

export default optionsApi;
