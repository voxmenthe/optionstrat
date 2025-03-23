/**
 * Visualization Types
 * Type definitions for visualization components and data structures
 */

import { 
  PricePoint, 
  VolatilityPoint, 
  TimePoint, 
  PriceVsVolatilityPoint,
  PnLScenarioPoint 
} from '../lib/api/scenariosApi';
import { OptionPosition } from '../lib/stores/positionStore';

/**
 * Common chart configuration options
 */
export interface ChartConfiguration {
  title?: string;
  showLegend: boolean;
  colorScale: 'profits' | 'greeks' | 'custom';
  customColors?: string[];
  showGridLines: boolean;
  showTooltips: boolean;
  height?: number;
  width?: number;
  responsiveResize: boolean;
  margin?: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
}

/**
 * Base props interface for all chart components
 */
export interface BaseChartProps {
  config: ChartConfiguration;
  isLoading?: boolean;
  error?: string | null;
  onConfigChange?: (newConfig: Partial<ChartConfiguration>) => void;
  className?: string;
}

/**
 * Payoff diagram data structure
 */
export interface PayoffDiagramData {
  underlyingPrices: number[];
  payoffValues: number[];
  breakEvenPoints: number[];
  maxProfit?: number;
  maxLoss?: number;
  currentPrice?: number;
  positions?: OptionPosition[];
}

/**
 * Payoff diagram props
 */
export interface PayoffDiagramProps extends BaseChartProps {
  data: PayoffDiagramData;
}

/**
 * Price vs Time data structure
 */
export interface PriceTimeData {
  dates: string[];
  scenarios: {
    name: string;
    values: number[];
    price?: number;
    color?: string;
  }[];
  currentPrice?: number;
  positions?: OptionPosition[];
}

/**
 * Price vs Time chart props
 */
export interface PriceTimeChartProps extends BaseChartProps {
  data: PriceTimeData;
}

/**
 * Price vs Volatility Surface data structure
 */
export interface PriceVolatilitySurfaceData {
  points: PriceVsVolatilityPoint[];
  currentPrice?: number;
  currentVolatility?: number;
  positions?: OptionPosition[];
}

/**
 * Price vs Volatility Surface props
 */
export interface PriceVolatilitySurfaceProps extends BaseChartProps {
  data: PriceVolatilitySurfaceData;
  viewOptions?: {
    rotation?: { x: number; y: number; z: number };
    showContour?: boolean;
    showAxes?: boolean;
    showLabels?: boolean;
  };
}

/**
 * Greeks chart data structure
 */
export interface GreeksChartData {
  points: PricePoint[] | VolatilityPoint[] | TimePoint[];
  greek: 'delta' | 'gamma' | 'theta' | 'vega' | 'rho';
  xAxis: 'price' | 'volatility' | 'days';
  currentValue?: number;
  positions?: OptionPosition[];
}

/**
 * Greeks chart props
 */
export interface GreeksChartProps extends BaseChartProps {
  data: GreeksChartData;
}

/**
 * Visualization export options
 */
export interface ExportOptions {
  format: 'png' | 'jpg' | 'svg' | 'csv' | 'json';
  quality?: number;
  width?: number;
  height?: number;
  filename?: string;
} 