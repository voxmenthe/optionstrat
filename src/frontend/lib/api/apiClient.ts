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
   * Make a GET request to the API
   * @param endpoint - API endpoint
   * @param params - Query parameters
   * @returns Promise with the response data
   */
  async get<T>(endpoint: string, params?: Record<string, unknown>): Promise<T> {
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
    console.log(`Browser location: ${window.location.href}`);
    
    try {
      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
        credentials: 'include',
      });
      
      console.log(`API connection successful to: ${url.toString()}`);
      return this.handleResponse<T>(response);
    } catch (error) {
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
  async post<T>(endpoint: string, data: any): Promise<T> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(data),
        credentials: 'include',
      });
      
      return this.handleResponse<T>(response);
    } catch (error) {
      // Handle network errors like CORS, server unavailable, etc.
      console.error(`Network error when posting to ${this.baseUrl}${endpoint}:`, error);
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
   * @returns Promise with the response data
   */
  async put<T>(endpoint: string, data: any): Promise<T> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(data),
        credentials: 'include',
      });
      
      return this.handleResponse<T>(response);
    } catch (error) {
      // Handle network errors like CORS, server unavailable, etc.
      console.error(`Network error when putting to ${this.baseUrl}${endpoint}:`, error);
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
   * @returns Promise with the response data
   */
  async delete<T>(endpoint: string): Promise<T> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'DELETE',
        headers: {
          'Accept': 'application/json',
        },
        credentials: 'include',
      });
      
      return this.handleResponse<T>(response);
    } catch (error) {
      // Handle network errors like CORS, server unavailable, etc.
      console.error(`Network error when deleting ${this.baseUrl}${endpoint}:`, error);
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
      
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorMessage = errorData.detail;
        }
      } catch (e) {
        // If we can't parse the error response, just use the default message
      }
      
      throw new ApiError(response.status, response.statusText, errorMessage);
    }
    
    // For 204 No Content responses, return empty object
    if (response.status === 204) {
      return {} as T;
    }
    
    return response.json() as Promise<T>;
  }
}

// Export a singleton instance of the API client
const apiClient = new ApiClient();
export default apiClient; 