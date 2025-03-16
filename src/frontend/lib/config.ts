// API configuration
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003';

// Other configuration constants
export const DEFAULT_TIMEOUT = 10000; // 10 seconds
export const MAX_RETRIES = 3;
export const CACHE_TTL = 60 * 5; // 5 minutes in seconds

// Feature flags
export const FEATURES = {
  ENABLE_OPTION_CHAIN: true,
  ENABLE_GREEKS_CALCULATION: true,
  ENABLE_SCENARIO_ANALYSIS: true,
};