import axios from 'axios';
import { API_BASE_URL } from '../config';
import logger from '../utils/logger';

export interface OptionContract {
  ticker: string;
  expiration: string;
  strike: number;
  optionType: string;
  bid: number;
  ask: number;
  lastPrice: number;
  volume: number;
  openInterest: number;
  impliedVolatility: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
}

export interface OptionExpiration {
  date: string;
  daysToExpiration: number;
}

// Create a dedicated axios instance for options API
const optionsClient = axios.create({
  baseURL: `${API_BASE_URL}`,
  timeout: 10000,
});

// Add request/response logging
optionsClient.interceptors.request.use(
  (config) => {
    logger.info(`OPTIONS_API_REQUEST: ${config.method?.toUpperCase()} ${config.url}`, {
      params: config.params
    });
    return config;
  },
  (error) => {
    logger.error('OPTIONS_API_REQUEST_ERROR:', error);
    return Promise.reject(error);
  }
);

optionsClient.interceptors.response.use(
  (response) => {
    logger.info(`OPTIONS_API_RESPONSE: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    logger.error('OPTIONS_API_RESPONSE_ERROR:', {
      url: error.config?.url,
      status: error.response?.status,
      message: error.message
    });
    return Promise.reject(error);
  }
);

export const optionsApi = {
  // Search for ticker symbols
  async searchTicker(query: string, limit: number = 10): Promise<string[]> {
    try {
      logger.info('OPTIONS_API: Searching for ticker', { query, limit });
      const response = await optionsClient.get(`/options/search/${query}`, {
        params: { limit }
      });
      return response.data;
    } catch (error) {
      logger.error('OPTIONS_API: Error searching ticker', { 
        query, 
        error: error instanceof Error ? error.message : String(error) 
      });
      throw error;
    }
  },

  // Get available expiration dates for a ticker
  async getExpirations(ticker: string): Promise<OptionExpiration[]> {
    try {
      logger.info('OPTIONS_API: Getting expirations for ticker', { ticker });
      const response = await optionsClient.get(`/options/chains/${ticker}/expirations`);
      logger.info('OPTIONS_API: Received expirations', { 
        ticker, 
        count: response.data.length 
      });
      return response.data;
    } catch (error) {
      logger.error('OPTIONS_API: Error getting expirations', { 
        ticker, 
        error: error instanceof Error ? error.message : String(error) 
      });
      throw error;
    }
  },

  // Get options for a specific expiration date
  async getOptionsForExpiration(
    ticker: string, 
    expirationDate: string, 
    params: any = {},
    signal?: AbortSignal
  ): Promise<OptionContract[]> {
    try {
      logger.info('OPTIONS_API: Getting options for expiration', { 
        ticker, 
        expirationDate, 
        params 
      });
      
      const response = await optionsClient.get(
        `/options/chains/${ticker}/${expirationDate}`, 
        { 
          params,
          signal 
        }
      );
      
      logger.info('OPTIONS_API: Received options', { 
        ticker, 
        expirationDate, 
        count: response.data.length 
      });
      
      return response.data;
    } catch (error) {
      // Don't log aborted requests as errors
      if (error.name === 'CanceledError' || error.name === 'AbortError') {
        logger.info('OPTIONS_API: Request was cancelled', { 
          ticker, 
          expirationDate 
        });
      } else {
        logger.error('OPTIONS_API: Error getting options for expiration', { 
          ticker, 
          expirationDate, 
          error: error instanceof Error ? error.message : String(error) 
        });
      }
      throw error;
    }
  }
};
