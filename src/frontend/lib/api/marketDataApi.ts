/**
 * Market Data API service
 * Handles all API calls related to market data
 */

import apiClient from './apiClient';

// Backend model types
export interface TickerInfo {
  ticker: string;
  name: string;
  exchange: string;
  type: string;
  currency: string;
  last_price?: number;
  change_percent?: number;
  volume?: number;
}

export interface OptionChainItem {
  ticker: string;
  expiration: string;
  strike: number;
  option_type: 'call' | 'put';
  bid: number;
  ask: number;
  last: number;
  volume: number;
  open_interest: number;
  implied_volatility: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
}

export interface ExpirationDate {
  date: string;
  days_to_expiration: number;
}

/**
 * Market Data API service
 */
export const marketDataApi = {
  /**
   * Search for a ticker
   * @param query - Search query
   * @returns Promise with ticker information
   */
  searchTicker: async (query: string): Promise<TickerInfo[]> => {
    return apiClient.get<TickerInfo[]>('/market-data/search', { query });
  },
  
  /**
   * Get ticker information
   * @param ticker - Ticker symbol
   * @returns Promise with ticker information
   */
  getTickerInfo: async (ticker: string): Promise<TickerInfo> => {
    return apiClient.get<TickerInfo>(`/market-data/ticker/${ticker}`);
  },
  
  /**
   * Get current stock price
   * @param ticker - Ticker symbol
   * @returns Promise with stock price
   */
  getStockPrice: async (ticker: string): Promise<number> => {
    const response = await apiClient.get<{ price: number }>(`/market-data/price/${ticker}`);
    return response.price;
  },
  
  /**
   * Get available expiration dates for options
   * @param ticker - Ticker symbol
   * @returns Promise with expiration dates
   */
  getExpirationDates: async (ticker: string): Promise<ExpirationDate[]> => {
    return apiClient.get<ExpirationDate[]>(`/market-data/expirations/${ticker}`);
  },
  
  /**
   * Get option chain for a ticker and expiration date
   * @param ticker - Ticker symbol
   * @param expiration - Expiration date (YYYY-MM-DD)
   * @returns Promise with option chain
   */
  getOptionChain: async (ticker: string, expiration: string): Promise<OptionChainItem[]> => {
    return apiClient.get<OptionChainItem[]>(`/market-data/option-chain/${ticker}`, { expiration });
  },
  
  /**
   * Get historical volatility
   * @param ticker - Ticker symbol
   * @param days - Number of days for calculation (default: 30)
   * @returns Promise with historical volatility
   */
  getHistoricalVolatility: async (ticker: string, days: number = 30): Promise<number> => {
    const response = await apiClient.get<{ volatility: number }>(`/market-data/historical-volatility/${ticker}`, { days });
    return response.volatility;
  },
  
  /**
   * Get volatility surface
   * @param ticker - Ticker symbol
   * @returns Promise with volatility surface data
   */
  getVolatilitySurface: async (ticker: string): Promise<any> => {
    return apiClient.get<any>(`/market-data/volatility-surface/${ticker}`);
  }
};

export default marketDataApi; 