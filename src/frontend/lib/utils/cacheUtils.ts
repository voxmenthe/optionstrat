/**
 * Cache utilities for client-side caching
 * Provides functions for caching and retrieving data with TTL support
 */

interface CacheItem<T> {
  data: T;
  timestamp: number;
  expiresAt: number;
}

/**
 * Cache manager for client-side caching with TTL support
 */
export class CacheManager {
  private static instance: CacheManager;
  public cache: Map<string, CacheItem<any>>;
  private defaultTTL: number; // TTL in milliseconds
  
  private constructor(defaultTTL: number = 5 * 60 * 1000) { // Default 5 minutes
    this.cache = new Map();
    this.defaultTTL = defaultTTL;
  }
  
  /**
   * Get singleton instance of CacheManager
   */
  public static getInstance(): CacheManager {
    if (!CacheManager.instance) {
      CacheManager.instance = new CacheManager();
    }
    return CacheManager.instance;
  }
  
  /**
   * Set cache item with optional TTL
   * @param key - Cache key
   * @param data - Data to cache
   * @param ttl - Time to live in milliseconds (optional)
   */
  public set<T>(key: string, data: T, ttl?: number): void {
    console.log(`CACHE_DEBUG: set called for key: ${key}`);
    const timestamp = Date.now();
    const expiresAt = timestamp + (ttl || this.defaultTTL);
    const actualTtl = ttl || this.defaultTTL;
    
    console.log(`CACHE_DEBUG: Setting cache with TTL: ${actualTtl}ms, expires at: ${new Date(expiresAt).toISOString()}`);
    
    this.cache.set(key, {
      data,
      timestamp,
      expiresAt
    });
    
    // Log cache size after adding item
    console.log(`CACHE_DEBUG: Cache now contains ${this.cache.size} items`);
  }
  
  /**
   * Get cache item if it exists and is not expired
   * @param key - Cache key
   * @returns Cached data or null if not found or expired
   */
  public get<T>(key: string): T | null {
    console.log(`CACHE_DEBUG: get called for key: ${key}`);
    const item = this.cache.get(key);
    
    if (!item) {
      console.log(`CACHE_DEBUG: No item found in cache for key: ${key}`);
      return null;
    }
    
    // Check if item is expired
    if (Date.now() > item.expiresAt) {
      console.log(`CACHE_DEBUG: Item expired for key: ${key}, deleting from cache`);
      this.cache.delete(key);
      return null;
    }
    
    console.log(`CACHE_DEBUG: Returning cached item for key: ${key}`);
    return item.data as T;
  }
  
  /**
   * Check if cache has a valid (not expired) item for the key
   * @param key - Cache key
   * @returns True if cache has valid item, false otherwise
   */
  public has(key: string): boolean {
    const item = this.cache.get(key);
    
    if (!item) {
      return false;
    }
    
    // Check if item is expired
    if (Date.now() > item.expiresAt) {
      this.cache.delete(key);
      return false;
    }
    
    return true;
  }
  
  /**
   * Delete cache item
   * @param key - Cache key
   */
  public delete(key: string): void {
    this.cache.delete(key);
  }
  
  /**
   * Clear all cache items
   */
  public clear(): void {
    this.cache.clear();
  }
  
  /**
   * Clear expired cache items
   */
  public clearExpired(): void {
    const now = Date.now();
    
    // Using forEach instead of for...of to avoid TypeScript downlevelIteration issues
    this.cache.forEach((item, key) => {
      if (now > item.expiresAt) {
        this.cache.delete(key);
      }
    });
  }
  
  /**
   * Get cache item if it exists and is not expired, otherwise fetch and cache
   * @param key - Cache key
   * @param fetchFn - Function to fetch data if not in cache
   * @param ttl - Time to live in milliseconds (optional)
   * @returns Cached or fetched data
   */
  public async getOrFetch<T>(
    key: string, 
    fetchFn: () => Promise<T>, 
    ttl?: number
  ): Promise<T> {
    console.log(`CACHE_DEBUG: getOrFetch called for key: ${key}`);
    const cachedData = this.get<T>(key);
    
    if (cachedData !== null) {
      console.log(`CACHE_DEBUG: Cache hit for key: ${key}`);
      return cachedData;
    }
    
    console.log(`CACHE_DEBUG: Cache miss for key: ${key}, fetching data...`);
    
    // Use a local variable to track if the request was aborted
    let wasAborted = false;
    
    try {
      // Fetch data with timeout protection
      const data = await fetchFn();
      
      // Only cache if the request wasn't aborted
      if (!wasAborted) {
        console.log(`CACHE_DEBUG: Successfully fetched data for key: ${key}`);
        
        // Cache data
        this.set(key, data, ttl);
      }
      
      return data;
    } catch (error) {
      // Check if this is an abort error
      if (error && typeof error === 'object') {
        const err = error as any;
        if (err.name === 'AbortError' || err.code === 'ECONNABORTED') {
          console.warn(`CACHE_DEBUG: Request aborted for key: ${key}`);
          wasAborted = true;
        }
      }
      
      console.error(`CACHE_DEBUG: Error fetching data for key: ${key}`, error);
      throw error;
    }
  }
  
  /**
   * Get cache statistics
   * @returns Cache statistics
   */
  public getStats(): { totalItems: number; size: number } {
    // Clear expired items first
    this.clearExpired();
    
    // Calculate size in bytes (approximate)
    let size = 0;
    
    // Using forEach instead of for...of to avoid TypeScript downlevelIteration issues
    this.cache.forEach((item, key) => {
      // Key size
      size += key.length * 2;
      
      // Data size (approximate)
      size += JSON.stringify(item.data).length * 2;
      
      // Metadata size
      size += 16; // timestamp and expiresAt (8 bytes each)
    });
    
    return {
      totalItems: this.cache.size,
      size
    };
  }
}

/**
 * Get singleton instance of CacheManager
 */
export const cacheManager = CacheManager.getInstance();

/**
 * Generate a cache key for option chain data
 * @param ticker - Ticker symbol
 * @param expiration - Expiration date (optional)
 * @param filters - Filters (optional)
 * @returns Cache key
 */
export const getOptionChainCacheKey = (
  ticker: string,
  expiration?: string | null,
  filters?: Record<string, any>
): string => {
  let key = `option_chain:${ticker}`;
  
  if (expiration) {
    key += `:${expiration}`;
  }
  
  if (filters) {
    key += `:${JSON.stringify(filters)}`;
  }
  
  return key;
};

/**
 * Clear cache for a specific ticker or all option chain data
 * @param specificTicker - Optional ticker to clear cache for
 */
export const clearOptionChainCache = (specificTicker?: string): void => {
  if (specificTicker) {
    // Clear cache for specific ticker
    const cacheKeys = [
      `expirations:${specificTicker}`,
      `price:${specificTicker}`
    ];
    
    cacheKeys.forEach(key => cacheManager.delete(key));
    
    // Get all keys as an array first
    const allKeys: string[] = [];
    cacheManager.cache.forEach((_, key) => allKeys.push(key));
    
    // Clear option chain cache for this ticker (all variations)
    allKeys.forEach(key => {
      if (key.startsWith(`option_chain:${specificTicker}:`)) {
        cacheManager.delete(key);
      }
    });
  } else {
    // Get all keys as an array first
    const allKeys: string[] = [];
    cacheManager.cache.forEach((_, key) => allKeys.push(key));
    
    // Clear all option chain related cache
    allKeys.forEach(key => {
      if (key.startsWith('option_chain:') || 
          key.startsWith('expirations:') || 
          key.startsWith('price:')) {
        cacheManager.delete(key);
      }
    });
  }
};

/**
 * Calculate TTL based on market hours
 * Returns shorter TTL during market hours, longer TTL outside market hours
 * @returns TTL in milliseconds
 */
export const getMarketAwareTTL = (): number => {
  const now = new Date();
  const day = now.getDay();
  const hour = now.getHours();
  
  // Weekend (Saturday = 6, Sunday = 0)
  if (day === 0 || day === 6) {
    return 30 * 60 * 1000; // 30 minutes
  }
  
  // Market hours (9:30 AM - 4:00 PM Eastern Time)
  // Simplified check - not accounting for time zones
  if (hour >= 9 && hour < 16) {
    return 1 * 60 * 1000; // 1 minute during market hours
  }
  
  // Extended hours
  if ((hour >= 4 && hour < 9) || (hour >= 16 && hour < 20)) {
    return 5 * 60 * 1000; // 5 minutes during extended hours
  }
  
  // Outside market hours
  return 15 * 60 * 1000; // 15 minutes
};
