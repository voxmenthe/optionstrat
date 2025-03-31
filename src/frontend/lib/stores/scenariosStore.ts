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
      // Skip API call if no positions provided
      if (!positions.length) {
        set({ priceScenario: [], loading: false });
        return;
      }
      
      // Calculate price ranges based on option type
      const avgStrike = positions.reduce((sum, pos) => sum + pos.strike, 0) / positions.length;
      const isPut = positions[0].type === 'put';
      
      // Customize price range and steps based on option type
      let minPrice, maxPrice, steps;
      
      if (isPut) {
        // For PUT options: focus on downside
        minPrice = Math.max(1, avgStrike * 0.5); // 50% below strike, min $1
        maxPrice = avgStrike * 1.5; // 50% above strike
        steps = 200; // More steps for smoother PUT curves
      } else {
        // For CALL options: focus on upside
        minPrice = Math.max(1, avgStrike * 0.6); // 40% below strike, min $1
        maxPrice = avgStrike * 2.0; // 100% above strike
        steps = 150; // Fewer steps needed for CALL
      }
      
      try {
        // Use a default matching the backend position API's reliable default
        const DEFAULT_VOLATILITY = 0.3; // 30%, match positions.py behavior
        
        // Enhanced volatility validation chain with complete fallbacks
        let volatilityToSend;
        
        // First check if we have a valid value in settings
        if (settings.baseVolatility !== undefined && settings.baseVolatility > 0) {
          volatilityToSend = settings.baseVolatility;
          
          // If it's in percentage form (>1), convert to decimal
          if (volatilityToSend > 1) {
            console.log(`Converting percentage volatility ${volatilityToSend} to decimal form`);
            volatilityToSend = volatilityToSend / 100;
          }
          
          // Ensure it's in a safe range for QuantLib
          if (volatilityToSend < 0.01) {
            console.log(`Volatility too low (${volatilityToSend}), using minimum 0.01`);
            volatilityToSend = 0.01;
          } else if (volatilityToSend > 2.0) {
            console.log(`Volatility too high (${volatilityToSend}), using maximum 2.0`);
            volatilityToSend = 2.0;
          }
        } else {
          // No valid setting - use reliable default that works in position API
          console.log(`No valid volatility in settings, using default ${DEFAULT_VOLATILITY}`);
          volatilityToSend = DEFAULT_VOLATILITY;
        }
        
        // Special handling for PUT options - they need higher minimum volatility
        if (isPut) {
          const PUT_MIN_VOLATILITY = 0.1; // Higher minimum for PUT options
          if (volatilityToSend < PUT_MIN_VOLATILITY) {
            console.log(`PUT option detected - increasing volatility from ${volatilityToSend} to minimum ${PUT_MIN_VOLATILITY}`);
            volatilityToSend = PUT_MIN_VOLATILITY;
          }
          
          console.log(`Using volatility ${volatilityToSend} for PUT option`);
        }
        
        const priceScenario = await scenariosApi.analyzePriceScenario(
          positions,
          {
            min_price: minPrice,
            max_price: maxPrice,
            steps: steps,
            base_volatility: volatilityToSend,
            risk_free_rate: settings.riskFreeRate || 0.05, // Ensure risk-free rate is always provided
            dividend_yield: settings.dividendYield || 0.0 // Ensure dividend yield is always provided
          }
        );
        
        // If API returns data with points, use it
        if (priceScenario && priceScenario.length > 0) {
          set({ priceScenario, loading: false });
          return;
        }
        
        // Empty response - fall through to use fallback
        console.warn("API returned empty price scenario data, using fallback");
        throw new Error("Empty price scenario data");
        
      } catch (apiError) {
        console.error("API error, using client-side data generation:", apiError);
        
        // Generate fallback data directly without dynamic import
        if (positions.length) {
          // Get the generateSamplePayoffData function
          const position = positions[0];
          
          // Import helper functions
          const generatePayoffData = (position: OptionPosition) => {
            // Basic implementation matching the one in visualization page
            const strike = position.strike;
            // Ensure premium is non-negative, default if necessary
            const premium = position.premium !== undefined && position.premium >= 0 
                          ? position.premium 
                          : (strike * (position.type === 'put' ? 0.05 : 0.06));
            const isCall = position.type === 'call';
            const isBuy = position.action === 'buy';
            const quantity = position.quantity; // Get quantity for payoff calculation
            
            // Generate price points with special handling for PUT options
            let prices: number[] = []; // Use let for reassignment
            let values: number[] = []; // Use let for reassignment
            
            const numPoints = 101; // Generate 101 points for smoother curves
            
            // Create different price distributions based on option type
            if (isCall) {
              // For calls: focus on area above strike
              const minPrice = Math.max(1, strike * 0.6); // 40% below strike, min $1
              const maxPrice = strike * 2.0; // 100% above strike
              const aboveStrikeDensity = 0.6; // 60% points above strike
              
              for (let i = 0; i < numPoints; i++) {
                let price;
                const proportion = i / (numPoints - 1); // 0 to 1

                if (proportion < (1 - aboveStrikeDensity)) {
                  // Points below strike: minPrice to strike
                  const belowStrikeProportion = proportion / (1 - aboveStrikeDensity);
                  price = minPrice + (strike - minPrice) * belowStrikeProportion;
                } else {
                  // Points above strike: strike to maxPrice
                  const aboveStrikeProportion = (proportion - (1 - aboveStrikeDensity)) / aboveStrikeDensity;
                  price = strike + (maxPrice - strike) * aboveStrikeProportion;
                }
                prices.push(price);
                
                // Calculate CALL payoff
                let payoff = isBuy 
                  ? Math.max(0, price - strike) - premium 
                  : premium - Math.max(0, price - strike);
                values.push(payoff * quantity); // Use position quantity
              }

            } else { // isPut
              // For puts: focus on area below strike
              const minPrice = Math.max(1, strike * 0.5); // 50% below strike, min $1
              const maxPrice = strike * 1.5; // 50% above strike
              const belowStrikeDensity = 0.7; // 70% of points below strike

              for (let i = 0; i < numPoints; i++) {
                  let price;
                  const proportion = i / (numPoints - 1); // 0 to 1

                  if (proportion < belowStrikeDensity) {
                      // Concentrate points below strike: minPrice to strike
                      const belowStrikeProportion = proportion / belowStrikeDensity;
                      price = minPrice + (strike - minPrice) * belowStrikeProportion;
                  } else {
                      // Distribute remaining points above strike: strike to maxPrice
                      const aboveStrikeProportion = (proportion - belowStrikeDensity) / (1 - belowStrikeDensity);
                      price = strike + (maxPrice - strike) * aboveStrikeProportion;
                  }
                  prices.push(price);

                  // Calculate PUT payoff
                  let payoff = isBuy
                    ? Math.max(0, strike - price) - premium
                    : premium - Math.max(0, strike - price);
                  values.push(payoff * quantity); // Use position quantity
              }
              
              // Sort points by price to ensure correct plotting order for PUTs
              // This is crucial for Plotly to draw the line correctly
              const points = prices.map((p, idx) => ({ price: p, value: values[idx] }));
              points.sort((a, b) => a.price - b.price);
              prices = points.map(p => p.price);
              values = points.map(p => p.value);

              // Log PUT data for validation
              console.log("Generated PUT Fallback Data:", {
                strike: strike,
                premium: premium,
                quantity: quantity,
                action: position.action,
                prices: prices.map(p => p.toFixed(2)), // Format for readability
                values: values.map(v => v.toFixed(2))  // Format for readability
              });
            }
            
            return { prices, values };
          };
          
          // Generate data and convert to API format
          const data = generatePayoffData(position);
          const priceScenario = data.prices.map((price, index) => ({
            price,
            value: data.values[index],
            delta: 0,
            gamma: 0,
            theta: 0,
            vega: 0,
            rho: 0
          }));
          
          set({ priceScenario, loading: false });
          return;
        }
        
        // If fallback fails, re-throw the original error
        throw apiError;
      }
    } catch (error) {
      console.error("Failed to analyze price scenario:", error);
      
      set({ 
        error: `Failed to analyze price scenario: ${error instanceof Error ? error.message : String(error)}`, 
        loading: false,
        priceScenario: [] // Clear any existing data on error
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
      // Use a default matching the backend position API's reliable default
      const DEFAULT_VOLATILITY = 0.3; // 30%, match positions.py behavior
      
      // Enhanced volatility validation chain with complete fallbacks
      let volatilityToSend;
      
      // Check if we're dealing with a PUT option
      const isPut = positions.length > 0 && positions[0].type === 'put';
      
      // First check if we have a valid value in settings
      if (settings.baseVolatility !== undefined && settings.baseVolatility > 0) {
        volatilityToSend = settings.baseVolatility;
        
        // If it's in percentage form (>1), convert to decimal
        if (volatilityToSend > 1) {
          console.log(`Converting percentage volatility ${volatilityToSend} to decimal form`);
          volatilityToSend = volatilityToSend / 100;
        }
        
        // Ensure it's in a safe range for QuantLib
        if (volatilityToSend < 0.01) {
          console.log(`Volatility too low (${volatilityToSend}), using minimum 0.01`);
          volatilityToSend = 0.01;
        } else if (volatilityToSend > 2.0) {
          console.log(`Volatility too high (${volatilityToSend}), using maximum 2.0`);
          volatilityToSend = 2.0;
        }
      } else {
        // No valid setting - use reliable default that works in position API
        console.log(`No valid volatility in settings, using default ${DEFAULT_VOLATILITY}`);
        volatilityToSend = DEFAULT_VOLATILITY;
      }
      
      // Special handling for PUT options - they need higher minimum volatility
      if (isPut) {
        const PUT_MIN_VOLATILITY = 0.1; // Higher minimum for PUT options
        if (volatilityToSend < PUT_MIN_VOLATILITY) {
          console.log(`PUT option detected - increasing volatility from ${volatilityToSend} to minimum ${PUT_MIN_VOLATILITY}`);
          volatilityToSend = PUT_MIN_VOLATILITY;
        }
        
        console.log(`Using volatility ${volatilityToSend} for PUT option`);
      }
      
      const timeDecayScenario = await scenariosApi.analyzeTimeDecayScenario(
        positions,
        {
          min_days: settings.minDays,
          max_days: settings.maxDays,
          steps: settings.daysSteps,
          base_price: settings.basePrice,
          base_volatility: volatilityToSend,
          risk_free_rate: settings.riskFreeRate || 0.05,
          dividend_yield: settings.dividendYield || 0.0
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