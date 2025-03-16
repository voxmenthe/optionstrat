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

// Helper function to convert snake_case API response to camelCase
const mapOptionResponseToCamelCase = (option: any): OptionContract => {
  // Create a new object with camelCase keys
  const mappedOption: any = {};
  
  // Map known snake_case keys to camelCase
  if (option.option_type !== undefined) mappedOption.optionType = option.option_type;
  else if (option.optionType !== undefined) mappedOption.optionType = option.optionType;
  
  // Copy all other properties, preferring camelCase if both exist
  Object.keys(option).forEach(key => {
    // Skip already mapped properties
    if (key === 'option_type' && mappedOption.optionType !== undefined) return;
    
    // Convert snake_case to camelCase
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    
    // Use the camelCase key
    mappedOption[camelKey] = option[key];
  });
  
  return mappedOption as OptionContract;
};

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
      
      // Map the backend's snake_case fields to the frontend's camelCase fields
      const mappedExpirations = response.data.map((exp: any) => ({
        date: exp.formatted_date,
        daysToExpiration: exp.days_to_expiration
      }));
      
      return mappedExpirations;
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
      
      // Enhanced logging to debug the response structure
      if (response.data && Array.isArray(response.data) && response.data.length > 0) {
        const sampleOption = response.data[0];
        logger.info('OPTIONS_API: Sample option data structure', {
          keys: Object.keys(sampleOption),
          sample: JSON.stringify(sampleOption).substring(0, 200) + '...'
        });
        
        // Check for snake_case vs camelCase property names
        const hasSnakeCaseProps = sampleOption.option_type !== undefined;
        logger.info('OPTIONS_API: Property format detection', {
          hasSnakeCaseProps,
          optionType: sampleOption.optionType,
          option_type: sampleOption.option_type
        });
      } else {
        logger.warn('OPTIONS_API: Unexpected response data format', {
          isArray: Array.isArray(response.data),
          length: response.data?.length,
          data: response.data ? JSON.stringify(response.data).substring(0, 200) + '...' : 'null'
        });
      }
      
      // Convert snake_case to camelCase if needed
      const mappedOptions = response.data.map(mapOptionResponseToCamelCase);
      
      // Log the mapped data
      if (mappedOptions.length > 0) {
        logger.info('OPTIONS_API: Mapped option data sample', {
          keys: Object.keys(mappedOptions[0]),
          sample: JSON.stringify(mappedOptions[0]).substring(0, 200) + '...'
        });
      }
      
      return mappedOptions;
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
