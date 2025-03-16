/**
 * Utility functions for option price calculations
 */

/**
 * Calculate the mark price (mid price) from bid and ask
 * 
 * @param bid - The bid price
 * @param ask - The ask price
 * @returns The calculated mark price or undefined if no valid prices are available
 */
export const calculateMarkPrice = (bid?: number, ask?: number): number | undefined => {
  // If both bid and ask are available, return the mid price
  if (bid !== undefined && ask !== undefined && bid > 0 && ask > 0) {
    return (bid + ask) / 2;
  }
  
  // If only one is available, return that price
  if (bid !== undefined && bid > 0) return bid;
  if (ask !== undefined && ask > 0) return ask;
  
  // If neither is available, return undefined
  return undefined;
};

/**
 * Format a price value for display
 * 
 * @param price - The price to format
 * @param fallback - Optional fallback string to display when price is undefined
 * @returns Formatted price string
 */
export const formatPrice = (price?: number, fallback: string = 'N/A'): string => {
  if (price === undefined || isNaN(price)) return fallback;
  return price.toFixed(2);
};
