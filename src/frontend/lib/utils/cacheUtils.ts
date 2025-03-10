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
    const timestamp = Date.now();
    const expiresAt = timestamp + (ttl || this.defaultTTL);
    
    this.cache.set(key, {
      data,
      timestamp,
      expiresAt
    });
  }
  
  /**
   * Get cache item if it exists and is not expired
   * @param key - Cache key
   * @returns Cached data or null if not found or expired
   */
  public get<T>(key: string): T | null {
    const item = this.cache.get(key);
    
    if (!item) {
      return null;
    }
    
    // Check if item is expired
    if (Date.now() > item.expiresAt) {
      this.cache.delete(key);
      return null;
    }
    
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
    const cachedData = this.get<T>(key);
    
    if (cachedData !== null) {
      return cachedData;
    }
    
    // Fetch data
    const data = await fetchFn();
    
    // Cache data
    this.set(key, data, ttl);
    
    return data;
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
