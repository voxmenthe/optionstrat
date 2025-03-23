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
    
    // Handle numeric fields specifically
    if (key === 'bid' || key === 'ask' || camelKey === 'bid' || camelKey === 'ask') {
      const value = option[key];
      console.log(`Processing ${camelKey} value:`, { 
        value, 
        type: typeof value, 
        isNull: value === null, 
        isUndefined: value === undefined,
        isEmptyString: value === ''
      });
      
      // Convert string values to numbers, handle null/undefined/empty string
      if (value !== null && value !== undefined && value !== '') {
        const numValue = typeof value === 'number' ? value : Number(value);
        
        // Check if conversion resulted in a valid number
        if (!isNaN(numValue)) {
          mappedOption[camelKey] = numValue;
          console.log(`Successfully converted ${camelKey} from ${typeof value} (${value}) to number: ${numValue}`);
        } else {
          console.warn(`Failed to convert ${camelKey} value '${value}' to a valid number, got NaN`);
          mappedOption[camelKey] = undefined;
        }
      } else {
        // If null/undefined/empty string, set to undefined to ensure consistent handling
        mappedOption[camelKey] = undefined;
        console.log(`${camelKey} is ${value === null ? 'null' : value === '' ? 'empty string' : 'undefined'}, setting to undefined`);
      }
    } else {
      // Use the camelCase key for other properties
      mappedOption[camelKey] = option[key];
    }
  });
  
  // Add debug logging for the final bid/ask values
  console.log(`Option ${mappedOption.optionType} ${mappedOption.strike} mapped bid/ask:`, {
    bid: mappedOption.bid,
    bidType: typeof mappedOption.bid,
    bidIsNaN: typeof mappedOption.bid === 'number' && isNaN(mappedOption.bid),
    ask: mappedOption.ask,
    askType: typeof mappedOption.ask,
    askIsNaN: typeof mappedOption.ask === 'number' && isNaN(mappedOption.ask)
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
    // Format the expiration date to YYYY-MM-DD (backend requirement)
    const formattedDate = expirationDate.split('T')[0]; // Remove the time part if present
    try {
      logger.info('OPTIONS_API: Getting options for expiration', { 
        ticker, 
        expirationDate, 
        formattedDate,
        params 
      });
      
      console.log(`Fetching options for ${ticker} expiring ${expirationDate} (formatted as ${formattedDate})...`);
      
      const response = await optionsClient.get(
        `/options/chains/${ticker}/${formattedDate}`, 
        { 
          params,
          signal 
        }
      );
      
      logger.info('OPTIONS_API: Received options', { 
        ticker, 
        expirationDate, 
        formattedDate,
        count: response.data.length 
      });
      
      console.log(`Received ${response.data.length} options for ${ticker} expiring ${expirationDate}`);
      
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
        
        // Log detailed bid/ask information for debugging
        console.log('Sample option data before mapping:', {
          strike: sampleOption.strike,
          type: sampleOption.option_type || sampleOption.optionType,
          bid: sampleOption.bid,
          bidType: typeof sampleOption.bid,
          ask: sampleOption.ask,
          askType: typeof sampleOption.ask
        });
      } else {
        logger.warn('OPTIONS_API: Unexpected response data format', {
          isArray: Array.isArray(response.data),
          length: response.data?.length,
          data: response.data ? JSON.stringify(response.data).substring(0, 200) + '...' : 'null'
        });
        console.warn('Unexpected options data format:', {
          isArray: Array.isArray(response.data),
          length: response.data?.length
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
        
        console.log('Sample mapped option data:', {
          strike: mappedOptions[0].strike,
          type: mappedOptions[0].optionType,
          bid: mappedOptions[0].bid,
          bidType: typeof mappedOptions[0].bid,
          ask: mappedOptions[0].ask,
          askType: typeof mappedOptions[0].ask
        });
      }
      
      return mappedOptions;
    } catch (error) {
      // Don't log aborted requests as errors
      if (error.name === 'CanceledError' || error.name === 'AbortError') {
        logger.info('OPTIONS_API: Request was cancelled', { 
          ticker, 
          expirationDate,
          formattedDate 
        });
      } else {
        logger.error('OPTIONS_API: Error getting options for expiration', { 
          ticker, 
          expirationDate, 
          formattedDate,
          error: error instanceof Error ? error.message : String(error) 
        });
      }
      throw error;
    }
  },

  /**
   * Get option data for a specific position
   * This is useful for fetching current market data (bid/ask) for an existing position
   * 
   * @param position - The option position to get data for
   * @param signal - Optional AbortSignal for cancellation
   * @returns The option contract data or undefined if not found
   */
  async getOptionDataForPosition(
    position: { ticker: string; expiration: string; strike: number; type: 'call' | 'put' },
    signal?: AbortSignal
  ): Promise<any | undefined> {
    try {
      // Get all options for this expiration
      const options = await this.getOptionsForExpiration(
        position.ticker,
        position.expiration,
        {},
        signal
      );
      
      // Format the expiration date for logging
      const formattedPositionDate = position.expiration.split('T')[0];
      console.log(`Searching for option match in ${options.length} options for ${position.ticker} ${position.type} ${position.strike} expiring ${position.expiration} (formatted as ${formattedPositionDate})`);
      
      // Log a sample of the options to verify data structure
      if (options.length > 0) {
        console.log('Sample option data:', {
          strike: options[0].strike,
          type: options[0].optionType,
          bid: options[0].bid,
          bidType: typeof options[0].bid,
          ask: options[0].ask,
          askType: typeof options[0].ask
        });
      }
      
      // Find the specific option that matches our position
      const optionData = options.find(option => {
        const strikeMatch = option.strike === position.strike;
        const typeMatch = option.optionType.toLowerCase() === position.type.toLowerCase();
        
        if (strikeMatch && !typeMatch) {
          console.log(`Found strike match (${option.strike}) but type mismatch: ${option.optionType} vs ${position.type}`);
        }
        
        return strikeMatch && typeMatch;
      });
      
      if (!optionData) {
        console.warn(`Could not find option data for ${position.ticker} ${position.type} ${position.strike} expiring ${position.expiration}`);
        logger.warn('OPTIONS_API: Could not find option data for position', {
          ticker: position.ticker,
          expiration: position.expiration,
          strike: position.strike,
          type: position.type
        });
        return undefined;
      }
      
      console.log(`Found option data for ${position.ticker} ${position.type} ${position.strike}:`, {
        bid: optionData.bid,
        bidType: typeof optionData.bid,
        ask: optionData.ask,
        askType: typeof optionData.ask
      });
      
      logger.info('OPTIONS_API: Found option data for position', {
        ticker: position.ticker,
        expiration: position.expiration,
        strike: position.strike,
        type: position.type,
        bid: optionData.bid,
        ask: optionData.ask
      });
      
      return optionData;
    } catch (error: unknown) {
      // Don't log aborted requests as errors
      if (error instanceof Error && 
          (error.name === 'CanceledError' || error.name === 'AbortError')) {
        logger.info('OPTIONS_API: Request was cancelled for option data', { 
          position 
        });
      } else {
        logger.error('OPTIONS_API: Error getting option data for position', { 
          position,
          error: error instanceof Error ? error.message : String(error) 
        });
      }
      
      // Return undefined instead of throwing to make this more resilient
      return undefined;
    }
  }
};
