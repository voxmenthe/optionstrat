/**
 * Options API service
 * Handles all API calls related to option chains and market data
 */

import apiClient from './apiClient';

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
      console.log(`API: Fetching options chain for ${ticker} with params:`, params);
      const response = await apiClient.get<BackendOptionContract[]>(
        `/options/chains/${ticker}`, 
        params
      );
      console.log(`API: Received options chain for ${ticker}:`, response);
      return response.map(toFrontendOptionContract);
    } catch (error) {
      console.error(`API: Error fetching options chain for ${ticker}:`, error);
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
      console.log(`API: Fetching expiration dates for ${ticker}`);
      const response = await apiClient.get<BackendOptionExpiration[]>(
        `/options/chains/${ticker}/expirations`
      );
      console.log(`API: Received expiration dates for ${ticker}:`, response);
      return response.map(toFrontendOptionExpiration);
    } catch (error) {
      console.error(`API: Error fetching expiration dates for ${ticker}:`, error);
      throw error;
    }
  },
  
  /**
   * Get options for a specific ticker and expiration date
   * @param ticker - Ticker symbol
   * @param expirationDate - Expiration date
   * @param params - Optional parameters
   * @returns Promise with option data
   */
  getOptionsForExpiration: async (
    ticker: string, 
    expirationDate: string,
    params?: { 
      option_type?: 'call' | 'put';
      min_strike?: number;
      max_strike?: number;
    }
  ): Promise<OptionContract[]> => {
    try {
      console.log(
        `API: Fetching options for ${ticker} with expiration ${expirationDate} and params:`, 
        params
      );
      const response = await apiClient.get<BackendOptionContract[]>(
        `/options/chains/${ticker}/${expirationDate}`, 
        params
      );
      console.log(
        `API: Received options for ${ticker} with expiration ${expirationDate}:`, 
        response
      );
      return response.map(toFrontendOptionContract);
    } catch (error: any) {
      console.error(
        `API: Error fetching options for ${ticker} with expiration ${expirationDate}:`, 
        error
      );
      
      // Check for 404 error specifically, which would indicate the expiration date doesn't exist
      if (error.response && error.response.status === 404) {
        const errorDetail = error.response.data.detail || '';
        throw new Error(`Invalid expiration date: ${errorDetail}`);
      }
      
      throw error;
    }
  },
  
  /**
   * Search for ticker symbols matching a query
   * @param query - Search query
   * @param limit - Maximum number of results to return
   * @returns Promise with matching ticker symbols
   */
  searchTickers: async (query: string, limit: number = 10): Promise<string[]> => {
    try {
      console.log(`API: Searching tickers with query: ${query}, limit: ${limit}`);
      const response = await apiClient.get<string[]>(
        `/options/search/${query}`, 
        { limit }
      );
      console.log(`API: Received ticker search results:`, response);
      return response;
    } catch (error) {
      console.error(`API: Error searching tickers with query: ${query}:`, error);
      throw error;
    }
  },
};

export default optionsApi;
