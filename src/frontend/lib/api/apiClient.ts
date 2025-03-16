/**
 * Base API client for making requests to the backend
 */

// Default API URL - can be overridden by environment variables
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003';

/**
 * API response error class
 */
export class ApiError extends Error {
  status: number;
  statusText: string;
  
  constructor(status: number, statusText: string, message: string) {
    super(message);
    this.status = status;
    this.statusText = statusText;
    this.name = 'ApiError';
  }
}

/**
 * Base API client for making requests to the backend
 */
export class ApiClient {
  private baseUrl: string;
  
  constructor(baseUrl = API_BASE_URL) {
    this.baseUrl = baseUrl;
    // Add debug log of API base URL at initialization
    console.log(`API Client initialized with base URL: ${baseUrl}`);
  }
  
  /**
   * Get the base URL for API requests
   * @returns The base URL as a string
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }
  
  /**
   * Make a GET request to the API
   * @param endpoint - API endpoint
   * @param params - Query parameters
   * @param signal - AbortController signal for cancelling the request
   * @param timeout - Optional timeout in milliseconds (defaults to 15000ms)
   * @returns Promise with the response data
   */
  async get<T>(endpoint: string, params?: Record<string, unknown>, signal?: AbortSignal, timeout?: number): Promise<T> {
    const url = new URL(`${this.baseUrl}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    
    // Enhanced debug logging for API requests
    console.log(`API REQUEST: GET ${url.toString()}`);
    console.log(`Request details:`, { 
      baseUrl: this.baseUrl, 
      endpoint, 
      params, 
      fullUrl: url.toString(),
      timeout: timeout || 'default'
    });
    
    // Create a timeout promise if timeout is specified and no signal is provided
    let timeoutId: number | undefined;
    let localAbortController: AbortController | undefined;
    
    // If no signal is provided but timeout is, create our own AbortController
    if (!signal && timeout) {
      localAbortController = new AbortController();
      signal = localAbortController.signal;
      
      // Set up the timeout
      timeoutId = window.setTimeout(() => {
        if (localAbortController) {
          console.warn(`Request to ${url.toString()} timed out after ${timeout}ms`);
          localAbortController.abort();
        }
      }, timeout);
    }
    
    try {
      const startTime = performance.now();
      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
        // Don't specify credentials or mode to let the browser handle CORS properly
        signal, // Add the abort signal
      });
      
      // Clear timeout if it was set
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      
      const endTime = performance.now();
      console.log(`API RESPONSE: ${response.status} ${response.statusText} for ${url.toString()} (${Math.round(endTime - startTime)}ms)`);
      
      // Add logging for the response status
      if (!response.ok) {
        console.error(`API ERROR: ${response.status} ${response.statusText} for ${url.toString()}`);
      }
      
      return this.handleResponse<T>(response);
    } catch (error) {
      // Clear timeout if it was set
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      
      // Check if the request was aborted
      if (error instanceof DOMException && error.name === 'AbortError') {
        console.warn(`Request to ${url.toString()} was aborted`);
        throw new ApiError(
          408, // Request Timeout
          'Request Timeout',
          'The request took too long to complete. Please try again.'
        );
      }
      
      // Enhanced error logging
      console.error(`API NETWORK ERROR for ${url.toString()}:`, error);
      console.error(`Network details:`, { 
        apiUrl: this.baseUrl, 
        endpoint, 
        params,
        fullUrl: url.toString(),
        errorName: error instanceof Error ? error.name : typeof error,
        errorMessage: error instanceof Error ? error.message : String(error)
      });
      
      throw new ApiError(
        0, 
        'Network Error', 
        'Unable to connect to the server. Please check your internet connection and try again.'
      );
    }
  }
  
  /**
   * Make a POST request to the API
   * @param endpoint - API endpoint
   * @param data - Request body data
   * @returns Promise with the response data
   */
  /**
   * Make a POST request to the API
   * @param endpoint - API endpoint
   * @param data - Request body data
   * @param params - Optional query parameters
   * @param signal - AbortController signal for cancelling the request
   * @param timeout - Optional timeout in milliseconds (defaults to 15000ms)
   * @returns Promise with the response data
   */
  async post<T>(endpoint: string, data: any, params?: Record<string, unknown>, signal?: AbortSignal, timeout?: number): Promise<T> {
    // Create a URL with query parameters if provided
    const url = new URL(`${this.baseUrl}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    
    // Create a timeout promise if timeout is specified and no signal is provided
    let timeoutId: number | undefined;
    let localAbortController: AbortController | undefined;
    
    // If no signal is provided but timeout is, create our own AbortController
    if (!signal && timeout) {
      localAbortController = new AbortController();
      signal = localAbortController.signal;
      
      // Set up the timeout
      timeoutId = window.setTimeout(() => {
        if (localAbortController) {
          console.warn(`Request to ${url.toString()} timed out after ${timeout}ms`);
          localAbortController.abort();
        }
      }, timeout);
    }
    
    try {
      const response = await fetch(url.toString(), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: data !== null ? JSON.stringify(data) : undefined,
        signal,
        // Don't specify credentials or mode to let the browser handle CORS properly
      });
      
      // Clear timeout if it was set
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      
      return this.handleResponse<T>(response);
    } catch (error) {
      // Clear timeout if it was set
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      
      // Check if the request was aborted
      if (error instanceof DOMException && error.name === 'AbortError') {
        console.warn(`Request to ${url.toString()} was aborted`);
        throw new ApiError(
          408, // Request Timeout
          'Request Timeout',
          'The request took too long to complete. Please try again.'
        );
      }
      
      // Handle network errors like CORS, server unavailable, etc.
      console.error(`Network error when posting to ${url.toString()}:`, error);
      throw new ApiError(
        0, 
        'Network Error', 
        'Unable to connect to the server. Please check your internet connection and try again.'
      );
    }
  }
  
  /**
   * Make a PUT request to the API
   * @param endpoint - API endpoint
   * @param data - Request body data
   * @param params - Optional query parameters
   * @param signal - AbortController signal for cancelling the request
   * @param timeout - Optional timeout in milliseconds (defaults to 15000ms)
   * @returns Promise with the response data
   */
  async put<T>(endpoint: string, data: any, params?: Record<string, unknown>, signal?: AbortSignal, timeout?: number): Promise<T> {
    // Create a URL with query parameters if provided
    const url = new URL(`${this.baseUrl}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    
    // Create a timeout promise if timeout is specified and no signal is provided
    let timeoutId: number | undefined;
    let localAbortController: AbortController | undefined;
    
    // If no signal is provided but timeout is, create our own AbortController
    if (!signal && timeout) {
      localAbortController = new AbortController();
      signal = localAbortController.signal;
      
      // Set up the timeout
      timeoutId = window.setTimeout(() => {
        if (localAbortController) {
          console.warn(`Request to ${url.toString()} timed out after ${timeout}ms`);
          localAbortController.abort();
        }
      }, timeout);
    }
    
    try {
      const response = await fetch(url.toString(), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: data !== null ? JSON.stringify(data) : undefined,
        signal,
        // Don't specify credentials or mode to let the browser handle CORS properly
      });
      
      // Clear timeout if it was set
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      
      return this.handleResponse<T>(response);
    } catch (error) {
      // Clear timeout if it was set
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      
      // Check if the request was aborted
      if (error instanceof DOMException && error.name === 'AbortError') {
        console.warn(`Request to ${url.toString()} was aborted`);
        throw new ApiError(
          408, // Request Timeout
          'Request Timeout',
          'The request took too long to complete. Please try again.'
        );
      }
      
      // Handle network errors like CORS, server unavailable, etc.
      console.error(`Network error when putting to ${url.toString()}:`, error);
      throw new ApiError(
        0, 
        'Network Error', 
        'Unable to connect to the server. Please check your internet connection and try again.'
      );
    }
  }
  
  /**
   * Make a DELETE request to the API
   * @param endpoint - API endpoint
   * @param params - Optional query parameters
   * @param signal - AbortController signal for cancelling the request
   * @param timeout - Optional timeout in milliseconds (defaults to 15000ms)
   * @returns Promise with the response data
   */
  async delete<T>(endpoint: string, params?: Record<string, unknown>, signal?: AbortSignal, timeout?: number): Promise<T> {
    // Create a URL with query parameters if provided
    const url = new URL(`${this.baseUrl}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    
    // Create a timeout promise if timeout is specified and no signal is provided
    let timeoutId: number | undefined;
    let localAbortController: AbortController | undefined;
    
    // If no signal is provided but timeout is, create our own AbortController
    if (!signal && timeout) {
      localAbortController = new AbortController();
      signal = localAbortController.signal;
      
      // Set up the timeout
      timeoutId = window.setTimeout(() => {
        if (localAbortController) {
          console.warn(`Request to ${url.toString()} timed out after ${timeout}ms`);
          localAbortController.abort();
        }
      }, timeout);
    }
    
    try {
      const response = await fetch(url.toString(), {
        method: 'DELETE',
        headers: {
          'Accept': 'application/json',
        },
        signal,
        // Don't specify credentials or mode to let the browser handle CORS properly
      });
      
      // Clear timeout if it was set
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      
      return this.handleResponse<T>(response);
    } catch (error) {
      // Clear timeout if it was set
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      
      // Check if the request was aborted
      if (error instanceof DOMException && error.name === 'AbortError') {
        console.warn(`Request to ${url.toString()} was aborted`);
        throw new ApiError(
          408, // Request Timeout
          'Request Timeout',
          'The request took too long to complete. Please try again.'
        );
      }
      
      // Handle network errors like CORS, server unavailable, etc.
      console.error(`Network error when deleting ${url.toString()}:`, error);
      throw new ApiError(
        0, 
        'Network Error', 
        'Unable to connect to the server. Please check your internet connection and try again.'
      );
    }
  }
  
  /**
   * Handle the response from the API
   * @param response - Fetch API response object
   * @returns Promise with parsed response data
   * @throws ApiError if response is not OK
   */
  private async handleResponse<T>(response: Response): Promise<T> {
    // Try to parse the response as JSON
    try {
      const data = await response.json();
      
      // Enhanced logging for response data
      console.log(`API PARSED RESPONSE for ${response.url}:`, {
        status: response.status,
        ok: response.ok,
        hasData: !!data,
        dataType: data ? typeof data : 'null'
      });
      
      if (!response.ok) {
        // Extract error message from response if available
        const errorMessage = data?.detail || data?.message || response.statusText;
        console.error(`API ERROR DETAILS:`, { 
          status: response.status, 
          statusText: response.statusText,
          url: response.url,
          errorMessage,
          data
        });
        
        throw new ApiError(
          response.status,
          response.statusText,
          errorMessage
        );
      }
      
      return data as T;
    } catch (error) {
      // If error is already an ApiError, rethrow it
      if (error instanceof ApiError) {
        throw error;
      }
      
      // Otherwise check if the error is from JSON parsing
      if (error instanceof SyntaxError) {
        console.error(`API JSON PARSE ERROR for ${response.url}:`, {
          status: response.status,
          statusText: response.statusText,
          error: error.message
        });
        
        throw new ApiError(
          response.status,
          response.statusText,
          'Invalid response from server'
        );
      }
      
      // Handle other errors
      console.error(`API UNEXPECTED ERROR for ${response.url}:`, error);
      throw new ApiError(
        response.status,
        response.statusText,
        'An unexpected error occurred'
      );
    }
  }
}

// Export a singleton instance of the API client
const apiClient = new ApiClient();
export default apiClient; 