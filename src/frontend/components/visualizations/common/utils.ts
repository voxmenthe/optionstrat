/**
 * Visualization Utilities
 * Helper functions for chart components
 */

import { 
  PricePoint, 
  VolatilityPoint, 
  TimePoint, 
  PriceVsVolatilityPoint 
} from '../../../lib/api/scenariosApi';
import { 
  PayoffDiagramData, 
  PriceTimeData, 
  PriceVolatilitySurfaceData 
} from '../../../types/visualization';
import { OptionPosition } from '../../../lib/stores/positionStore';

/**
 * Color scales for different visualization types
 */
export const COLOR_SCALES = {
  profits: {
    positive: ['#e6f7ff', '#91d5ff', '#1890ff', '#0050b3'],
    negative: ['#fff1f0', '#ffa39e', '#ff4d4f', '#a8071a'],
    neutral: ['#d9d9d9', '#8c8c8c', '#595959', '#262626'],
  },
  greeks: {
    delta: ['#e6f7ff', '#91d5ff', '#1890ff', '#0050b3'],
    gamma: ['#f9f0ff', '#d3adf7', '#9254de', '#531dab'],
    theta: ['#fff1f0', '#ffa39e', '#ff4d4f', '#a8071a'],
    vega: ['#f6ffed', '#b7eb8f', '#52c41a', '#135200'],
    rho: ['#fff7e6', '#ffd591', '#fa8c16', '#ad4e00'],
  },
  custom: [] as string[],
};

/**
 * Gets a color scale based on the type and value
 */
export function getColorScale(
  type: 'profits' | 'greeks' | 'custom',
  value?: number | string,
  customColors?: string[]
): string[] {
  if (type === 'custom' && customColors && customColors.length) {
    return customColors;
  }

  if (type === 'profits' && typeof value === 'number') {
    return value >= 0 ? COLOR_SCALES.profits.positive : COLOR_SCALES.profits.negative;
  }

  if (type === 'greeks' && typeof value === 'string') {
    return COLOR_SCALES.greeks[value as keyof typeof COLOR_SCALES.greeks] || COLOR_SCALES.greeks.delta;
  }

  return COLOR_SCALES.profits.neutral;
}

/**
 * Calculates responsive dimensions based on container size
 */
export function calculateDimensions(
  containerWidth: number,
  containerHeight: number,
  aspectRatio: number = 16/9,
  minHeight: number = 300,
  maxHeight: number = 800
): { width: number; height: number } {
  const calculatedHeight = containerWidth / aspectRatio;
  
  // Ensure height is within bounds
  let height = Math.max(minHeight, Math.min(calculatedHeight, maxHeight, containerHeight));
  
  // Adjust width based on calculated height
  const width = Math.min(containerWidth, height * aspectRatio);
  
  return { width, height };
}

/**
 * Transforms API price scenario data to payoff diagram data format
 */
export function transformToPricePayoffData(
  pricePoints: PricePoint[],
  positions: OptionPosition[],
  currentPrice?: number
): PayoffDiagramData {
  // Extract underlying prices and payoff values
  const underlyingPrices = pricePoints.map(point => point.price);
  const payoffValues = pricePoints.map(point => point.value);
  
  // Calculate break-even points (where value crosses zero)
  const breakEvenPoints: number[] = [];
  for (let i = 1; i < pricePoints.length; i++) {
    const prev = pricePoints[i - 1];
    const curr = pricePoints[i];
    
    // Check if value crosses zero between these points
    if ((prev.value <= 0 && curr.value >= 0) || (prev.value >= 0 && curr.value <= 0)) {
      // Linear interpolation to find the exact break-even price
      const ratio = Math.abs(prev.value) / (Math.abs(prev.value) + Math.abs(curr.value));
      const breakEvenPrice = prev.price + ratio * (curr.price - prev.price);
      breakEvenPoints.push(parseFloat(breakEvenPrice.toFixed(2)));
    }
  }
  
  // Find max profit and max loss
  const maxProfit = Math.max(...payoffValues);
  const maxLoss = Math.min(...payoffValues);
  
  return {
    underlyingPrices,
    payoffValues,
    breakEvenPoints,
    maxProfit: maxProfit > 0 ? maxProfit : undefined,
    maxLoss: maxLoss < 0 ? maxLoss : undefined,
    currentPrice,
    positions
  };
}

/**
 * Transforms API time decay data to price time chart data format
 */
export function transformToPriceTimeData(
  timePoints: TimePoint[],
  positions: OptionPosition[],
  currentPrice?: number
): PriceTimeData {
  // Sort by days to ensure proper sequence
  const sortedPoints = [...timePoints].sort((a, b) => a.days - b.days);
  
  // Extract dates (convert days to actual dates from today)
  const today = new Date();
  const dates = sortedPoints.map(point => {
    const date = new Date(today);
    date.setDate(date.getDate() + point.days);
    return date.toISOString().split('T')[0]; // Format as YYYY-MM-DD
  });
  
  // Create a single scenario for the values over time
  const scenarios = [{
    name: 'Position Value',
    values: sortedPoints.map(point => point.value),
    color: '#1890ff' // Default color
  }];
  
  return {
    dates,
    scenarios,
    currentPrice,
    positions
  };
}

/**
 * Transforms API price vs volatility data to surface data format
 */
export function transformToPriceVolatilitySurfaceData(
  points: PriceVsVolatilityPoint[],
  positions: OptionPosition[],
  currentPrice?: number,
  currentVolatility?: number
): PriceVolatilitySurfaceData {
  return {
    points,
    currentPrice,
    currentVolatility,
    positions
  };
}

/**
 * Formats currency values
 */
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value);
}

/**
 * Formats percentage values
 */
export function formatPercentage(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value / 100);
} 