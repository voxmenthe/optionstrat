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
export const calculateMarkPrice = (bid?: number | null, ask?: number | null): number | undefined => {
  console.log('calculateMarkPrice called with:', { bid, ask, bidType: typeof bid, askType: typeof ask });
  
  // Convert inputs to numbers or undefined to handle various input types
  const numericBid = bid !== undefined && bid !== null ? Number(bid) : undefined;
  const numericAsk = ask !== undefined && ask !== null ? Number(ask) : undefined;
  
  console.log('calculateMarkPrice converted values:', { numericBid, numericAsk });
  
  // If both bid and ask are available and valid numbers, return the mid price
  if (numericBid !== undefined && numericAsk !== undefined && 
      !isNaN(numericBid) && !isNaN(numericAsk) && 
      numericBid > 0 && numericAsk > 0) {
    const markPrice = (numericBid + numericAsk) / 2;
    console.log('calculateMarkPrice: Using mid price:', markPrice);
    return markPrice;
  }
  
  // If only bid is available and a valid number, return that price
  if (numericBid !== undefined && !isNaN(numericBid) && numericBid > 0) {
    console.log('calculateMarkPrice: Using bid price:', numericBid);
    return numericBid;
  }
  
  // If only ask is available and a valid number, return that price
  if (numericAsk !== undefined && !isNaN(numericAsk) && numericAsk > 0) {
    console.log('calculateMarkPrice: Using ask price:', numericAsk);
    return numericAsk;
  }
  
  // If neither is available or valid, return undefined
  console.log('calculateMarkPrice: No valid prices available, returning undefined');
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

/**
 * Calculate the current value of an option position
 * 
 * @param quantity - Number of contracts
 * @param markPrice - Current mark price of the option
 * @returns Current value of the position or undefined if markPrice is undefined
 */
export const calculateCurrentValue = (
  quantity: number, 
  markPrice?: number
): number | undefined => {
  if (markPrice === undefined) return undefined;
  
  const contractSize = 100; // Standard contract size is 100 shares
  return Math.abs(quantity) * markPrice * contractSize;
};

/**
 * Calculate the cost basis of an option position
 * 
 * @param quantity - Number of contracts
 * @param premium - Premium paid/received per share
 * @param action - 'buy' or 'sell'
 * @returns Cost basis of the position (positive for buy, negative for sell)
 */
export const calculateCostBasis = (
  quantity: number,
  premium: number,
  action: 'buy' | 'sell'
): number => {
  const contractSize = 100; // Standard contract size is 100 shares
  const sign = action === 'buy' ? 1 : -1;
  return sign * Math.abs(quantity) * premium * contractSize;
};

/**
 * Calculate P&L for an option position
 * 
 * @param quantity - Number of contracts
 * @param premium - Premium paid/received per share
 * @param markPrice - Current mark price of the option
 * @param action - 'buy' or 'sell'
 * @returns Object containing P&L amount and percentage
 */
export const calculatePnL = (
  quantity: number,
  premium: number,
  markPrice: number,
  action: 'buy' | 'sell'
): { pnlAmount: number; pnlPercent: number } => {
  const contractSize = 100; // Standard contract size is 100 shares
  const costBasis = calculateCostBasis(quantity, premium, action);
  const currentValue = Math.abs(quantity) * markPrice * contractSize;
  
  // For buy positions: currentValue - costBasis
  // For sell positions: -currentValue - costBasis (which is already negative)
  const pnlAmount = action === 'buy' 
    ? currentValue - costBasis 
    : -currentValue - costBasis;
  
  // Calculate percentage based on the absolute value of cost basis to avoid division by zero
  // and to handle the sign correctly
  const absCostBasis = Math.abs(costBasis);
  const pnlPercent = absCostBasis > 0 ? (pnlAmount / absCostBasis) * 100 : 0;
  
  return { pnlAmount, pnlPercent };
};
