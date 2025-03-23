/**
 * Scenarios Store
 * Manages state for scenario analysis including price, volatility, and time decay scenarios
 */

import { create } from 'zustand';
import { 
  scenariosApi, 
  PricePoint, 
  VolatilityPoint, 
  TimePoint, 
  PriceVsVolatilityPoint,
  PnLScenarioPoint
} from '../api';
import { OptionPosition } from './positionStore';

export interface ScenarioSettings {
  // Price scenario settings
  minPrice: number;
  maxPrice: number;
  priceSteps: number;
  
  // Volatility scenario settings
  minVolatility: number;
  maxVolatility: number;
  volatilitySteps: number;
  
  // Time decay scenario settings
  minDays: number;
  maxDays: number;
  daysSteps: number;
  
  // P&L scenario settings
  daysForward: number;
  priceChangePercent: number;
  
  // Common settings
  basePrice?: number;
  baseVolatility?: number;
  riskFreeRate?: number;
  dividendYield?: number;
}

export interface ScenariosStore {
  // State
  settings: ScenarioSettings;
  priceScenario: PricePoint[];
  volatilityScenario: VolatilityPoint[];
  timeDecayScenario: TimePoint[];
  priceVsVolatilitySurface: PriceVsVolatilityPoint[];
  pnlScenario: PnLScenarioPoint | null;
  loading: boolean;
  error: string | null;
  
  // Actions
  updateSettings: (settings: Partial<ScenarioSettings>) => void;
  analyzePriceScenario: (positions: OptionPosition[]) => Promise<void>;
  analyzeVolatilityScenario: (positions: OptionPosition[]) => Promise<void>;
  analyzeTimeDecayScenario: (positions: OptionPosition[]) => Promise<void>;
  analyzePriceVsVolatilitySurface: (positions: OptionPosition[]) => Promise<void>;
  analyzePnLScenario: (positions: OptionPosition[]) => Promise<void>;
  clearScenarios: () => void;
  clearError: () => void;
}

// Default settings
const DEFAULT_SETTINGS: ScenarioSettings = {
  minPrice: 0.8,  // 80% of current price
  maxPrice: 1.2,  // 120% of current price
  priceSteps: 50,
  
  minVolatility: 0.1,  // 10% volatility
  maxVolatility: 0.5,  // 50% volatility
  volatilitySteps: 20,
  
  minDays: 0,     // Today
  maxDays: 30,    // 30 days from now
  daysSteps: 30,
  
  daysForward: 7,       // Default 7 days forward for P&L
  priceChangePercent: 0, // Default 0% price change for P&L
  
  basePrice: undefined,
  baseVolatility: 0.3,  // 30% volatility
  riskFreeRate: 0.05,   // 5% risk-free rate
  dividendYield: 0,     // 0% dividend yield
};

export const useScenariosStore = create<ScenariosStore>((set, get) => ({
  // Initial state
  settings: DEFAULT_SETTINGS,
  priceScenario: [],
  volatilityScenario: [],
  timeDecayScenario: [],
  priceVsVolatilitySurface: [],
  pnlScenario: null,
  loading: false,
  error: null,
  
  // Update scenario settings
  updateSettings: (settings: Partial<ScenarioSettings>) => {
    set(state => ({
      settings: {
        ...state.settings,
        ...settings
      }
    }));
  },
  
  // Analyze price scenario
  analyzePriceScenario: async (positions: OptionPosition[]) => {
    const { settings } = get();
    
    set({ loading: true, error: null });
    try {
      // Calculate dynamic price range based on option type and strike price
      let minPrice = 0;
      let maxPrice = 0;
      let steps = 100; // Always use higher resolution for smoother curves
      
      if (positions.length > 0) {
        const avgStrike = positions.reduce((sum, pos) => sum + pos.strike, 0) / positions.length;
        const isPut = positions[0].type === 'put';
        
        // Use appropriate ranges based on option type
        if (isPut) {
          // For PUT options - critical to show range below strike
          minPrice = avgStrike * 0.4;  // 60% below strike
          maxPrice = avgStrike * 1.4;  // 40% above strike
          steps = 150; // Extra resolution for PUT
        } else {
          // For CALL options - critical to show range above strike
          minPrice = avgStrike * 0.6;  // 40% below strike
          maxPrice = avgStrike * 1.8;  // 80% above strike
        }
      } else {
        // Default fallback if no positions
        minPrice = settings.minPrice;
        maxPrice = settings.maxPrice;
      }
      
      try {
        const priceScenario = await scenariosApi.analyzePriceScenario(
          positions,
          {
            min_price: minPrice,
            max_price: maxPrice,
            steps: steps,
            base_volatility: settings.baseVolatility,
            risk_free_rate: settings.riskFreeRate,
            dividend_yield: settings.dividendYield
          }
        );
        
        set({ priceScenario, loading: false });
      } catch (apiError) {
        console.error("API error, using fallback data generation:", apiError);
        
        // If API call fails, generate fallback data directly
        if (positions.length > 0) {
          // Import the fallback data generator
          const { generateSamplePayoffData } = require('../../app/visualizations/[id]/page');
          
          if (typeof generateSamplePayoffData === 'function') {
            const fallbackData = generateSamplePayoffData(positions[0]);
            const priceScenario = fallbackData.underlyingPrices.map((price: number, index: number) => ({
              price,
              value: fallbackData.payoffValues[index],
              delta: 0,
              gamma: 0,
              theta: 0,
              vega: 0,
              rho: 0
            }));
            
            set({ priceScenario, loading: false });
            return;
          }
        }
        
        // If fallback fails, re-throw the original error
        throw apiError;
      }
    } catch (error) {
      set({ 
        error: `Failed to analyze price scenario: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Analyze volatility scenario
  analyzeVolatilityScenario: async (positions: OptionPosition[]) => {
    const { settings } = get();
    
    set({ loading: true, error: null });
    try {
      const volatilityScenario = await scenariosApi.analyzeVolatilityScenario(
        positions,
        {
          min_volatility: settings.minVolatility,
          max_volatility: settings.maxVolatility,
          steps: settings.volatilitySteps,
          base_price: settings.basePrice,
          risk_free_rate: settings.riskFreeRate,
          dividend_yield: settings.dividendYield
        }
      );
      
      set({ volatilityScenario, loading: false });
    } catch (error) {
      set({ 
        error: `Failed to analyze volatility scenario: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Analyze time decay scenario
  analyzeTimeDecayScenario: async (positions: OptionPosition[]) => {
    const { settings } = get();
    
    set({ loading: true, error: null });
    try {
      const timeDecayScenario = await scenariosApi.analyzeTimeDecayScenario(
        positions,
        {
          min_days: settings.minDays,
          max_days: settings.maxDays,
          steps: settings.daysSteps,
          base_price: settings.basePrice,
          base_volatility: settings.baseVolatility,
          risk_free_rate: settings.riskFreeRate,
          dividend_yield: settings.dividendYield
        }
      );
      
      set({ timeDecayScenario, loading: false });
    } catch (error) {
      set({ 
        error: `Failed to analyze time decay scenario: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Analyze price vs volatility surface
  analyzePriceVsVolatilitySurface: async (positions: OptionPosition[]) => {
    const { settings } = get();
    
    set({ loading: true, error: null });
    try {
      const priceVsVolatilitySurface = await scenariosApi.analyzePriceVsVolatilitySurface(
        positions,
        {
          min_price: settings.minPrice,
          max_price: settings.maxPrice,
          price_steps: settings.priceSteps,
          min_volatility: settings.minVolatility,
          max_volatility: settings.maxVolatility,
          volatility_steps: settings.volatilitySteps,
          risk_free_rate: settings.riskFreeRate,
          dividend_yield: settings.dividendYield
        }
      );
      
      set({ priceVsVolatilitySurface, loading: false });
    } catch (error) {
      set({ 
        error: `Failed to analyze price vs volatility surface: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Analyze P&L scenario
  analyzePnLScenario: async (positions: OptionPosition[]) => {
    const { settings } = get();
    
    set({ loading: true, error: null });
    try {
      const pnlScenario = await scenariosApi.analyzePnLScenario(
        positions,
        {
          days_forward: settings.daysForward,
          price_change_percent: settings.priceChangePercent
        }
      );
      
      set({ pnlScenario, loading: false });
    } catch (error) {
      set({ 
        error: `Failed to analyze P&L scenario: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false 
      });
    }
  },
  
  // Clear all scenarios
  clearScenarios: () => {
    set({
      priceScenario: [],
      volatilityScenario: [],
      timeDecayScenario: [],
      priceVsVolatilitySurface: [],
      pnlScenario: null
    });
  },
  
  // Clear error
  clearError: () => {
    set({ error: null });
  }
})); 