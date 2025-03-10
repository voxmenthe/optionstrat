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
    
    // Log connection attempt details
    console.log(`Attempting API connection to: ${url.toString()}`);
    console.log(`API base URL: ${this.baseUrl}`);
    
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
      console.log(`API connection successful to: ${url.toString()} in ${Math.round(endTime - startTime)}ms`);
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
      console.error(`Network error when fetching ${url.toString()}:`, error);
      console.error(`Network details - API URL: ${this.baseUrl}, Endpoint: ${endpoint}`);
      
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
   * Handle API response
   * @param response - Fetch response
   * @returns Promise with the response data
   * @throws ApiError if the response is not ok
   */
  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let errorMessage = `API error: ${response.status} ${response.statusText}`;
      let userFriendlyMessage = 'An error occurred while processing your request.';
      
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorMessage = errorData.detail;
          userFriendlyMessage = errorData.detail;
        }
      } catch (e) {
        // If we can't parse the error response, use status-specific messages
        if (response.status === 504 || response.status === 408) {
          userFriendlyMessage = 'The request took too long to complete. Please try again.';
        } else if (response.status === 404) {
          userFriendlyMessage = 'The requested resource was not found.';
        } else if (response.status >= 500) {
          userFriendlyMessage = 'The server encountered an error. Please try again later.';
        }
      }
      
      console.error(`API error: ${response.status} ${response.statusText} - ${errorMessage}`);
      throw new ApiError(response.status, response.statusText, userFriendlyMessage);
    }
    
    // For 204 No Content responses, return empty object
    if (response.status === 204) {
      return {} as T;
    }
    
    try {
      return await response.json() as Promise<T>;
    } catch (e) {
      console.error('Error parsing JSON response:', e);
      throw new ApiError(
        500,
        'Invalid Response',
        'The server returned an invalid response. Please try again.'
      );
    }
  }
}

// Export a singleton instance of the API client
const apiClient = new ApiClient();
export default apiClient; 