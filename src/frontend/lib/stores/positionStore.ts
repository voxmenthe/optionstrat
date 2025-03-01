import { create } from 'zustand';
import { positionsApi, greeksApi } from '../api';

// Types for our store
export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface OptionPosition {
  id: string;
  ticker: string;
  expiration: string;
  strike: number;
  type: 'call' | 'put';
  action: 'buy' | 'sell';
  quantity: number;
  premium?: number;
  greeks?: Greeks;
}

// Interface for grouped positions
export interface GroupedPosition {
  underlying: string;
  positions: OptionPosition[];
  totalGreeks?: Greeks;
}

interface PositionStore {
  positions: OptionPosition[];
  loading: boolean;
  error: string | null;
  groupByUnderlying: boolean;
  calculatingAllGreeks: boolean;
  
  // Actions
  fetchPositions: () => Promise<void>;
  addPosition: (position: Omit<OptionPosition, 'id'>) => Promise<void>;
  updatePosition: (id: string, position: Partial<OptionPosition>) => Promise<void>;
  removePosition: (id: string) => Promise<void>;
  calculateGreeks: (position: OptionPosition) => Promise<Greeks | void>;
  recalculateAllGreeks: () => Promise<void>;
  
  // Grouped positions
  toggleGrouping: () => void;
  getGroupedPositions: () => GroupedPosition[];
}

// Create the store with real API calls
export const usePositionStore = create<PositionStore>((set, get) => ({
  positions: [],
  loading: false,
  error: null,
  groupByUnderlying: false,
  calculatingAllGreeks: false,
  
  fetchPositions: async () => {
    set({ loading: true, error: null });
    try {
      console.log('Fetching positions from API...');
      const positions = await positionsApi.getPositions();
      console.log('Received positions:', positions);
      set({ positions, loading: false });
    } catch (error) {
      console.error('Error fetching positions:', error);
      set({ error: `Failed to fetch positions: ${error instanceof Error ? error.message : String(error)}`, loading: false });
    }
  },
  
  addPosition: async (position) => {
    set({ loading: true, error: null });
    try {
      console.log('Creating new position:', position);
      const newPosition = await positionsApi.createPosition(position);
      console.log('Position created successfully:', newPosition);
      
      set(state => {
        console.log('Updating state with new position');
        return {
          positions: [...state.positions, newPosition],
          loading: false
        };
      });
      
      // Automatically calculate Greeks for the new position
      try {
        console.log('Calculating Greeks for new position');
        await get().calculateGreeks(newPosition);
      } catch (error) {
        console.error('Failed to automatically calculate Greeks:', error);
        // Don't set error state here to avoid disrupting the UI flow
      }
    } catch (error) {
      console.error('Error adding position:', error);
      set({ error: `Failed to add position: ${error instanceof Error ? error.message : String(error)}`, loading: false });
    }
  },
  
  updatePosition: async (id, position) => {
    set({ loading: true, error: null });
    try {
      const updatedPosition = await positionsApi.updatePosition(id, position);
      
      set(state => ({
        positions: state.positions.map(pos => 
          pos.id === id ? updatedPosition : pos
        ),
        loading: false
      }));
    } catch (error) {
      set({ error: `Failed to update position: ${error instanceof Error ? error.message : String(error)}`, loading: false });
    }
  },
  
  removePosition: async (id) => {
    set({ loading: true, error: null });
    try {
      await positionsApi.deletePosition(id);
      
      set(state => ({
        positions: state.positions.filter(pos => pos.id !== id),
        loading: false
      }));
    } catch (error) {
      set({ error: `Failed to remove position: ${error instanceof Error ? error.message : String(error)}`, loading: false });
    }
  },
  
  calculateGreeks: async (position) => {
    try {
      console.log(`Calculating Greeks for position ${position.id}:`, position.ticker, position.strike, position.type);
      const greeks = await greeksApi.calculateGreeks(position);
      console.log(`Received Greeks for position ${position.id}:`, greeks);
      
      // Store the updated position with Greeks in local state only (don't save to DB)
      set(state => {
        const updatedPositions = state.positions.map(pos => 
          pos.id === position.id ? { ...pos, greeks } : pos
        );
        
        // No longer save Greeks to database to prevent double application of scaling
        console.log(`Updated Greeks for position ${position.id} in state only`);
        
        return { positions: updatedPositions };
      });
      
      return greeks;
    } catch (error) {
      console.error(`Failed to calculate Greeks for position ${position.id}:`, error);
      set({ error: `Failed to calculate Greeks: ${error instanceof Error ? error.message : String(error)}` });
      throw error;
    }
  },
  
  recalculateAllGreeks: async () => {
    const { positions } = get();
    
    if (positions.length === 0) {
      console.log('No positions to calculate Greeks for');
      return;
    }
    
    console.log(`Recalculating Greeks for all ${positions.length} positions`);
    set({ calculatingAllGreeks: true, error: null });
    
    try {
      // Process positions in parallel using Promise.all
      const results = await Promise.allSettled(
        positions.map(async (position) => {
          try {
            // Use the direct position endpoint instead of calculate endpoint
            // This ensures the Greeks are properly adjusted for short positions
            const greeks = await greeksApi.getPositionGreeks(position.id);
            console.log(`Retrieved Greeks for position ${position.id}:`, greeks);
            
            // Update the position with the calculated Greeks
            return { position, greeks, success: true };
          } catch (error) {
            console.error(`Failed to calculate Greeks for position ${position.id}:`, error);
            return { position, error, success: false };
          }
        })
      );
      
      // Update the positions with calculated Greeks
      const updatedPositions = [...positions];
      let updatedCount = 0;
      
      for (const result of results) {
        if (result.status === 'fulfilled' && result.value.success) {
          const { position, greeks } = result.value;
          const posIndex = updatedPositions.findIndex(p => p.id === position.id);
          
          if (posIndex >= 0) {
            updatedPositions[posIndex] = { ...updatedPositions[posIndex], greeks };
            updatedCount++;
            
            // We no longer save Greeks to the database as they should be calculated fresh each time
            // This prevents double-application of sign and quantity
            console.log(`Updated Greeks for position ${position.id} in frontend state only`);
          }
        }
      }
      
      console.log(`Updated Greeks for ${updatedCount} out of ${positions.length} positions`);
      set({ positions: updatedPositions });
    } catch (error) {
      console.error('Failed to recalculate all Greeks:', error);
      set({ error: `Failed to recalculate all Greeks: ${error instanceof Error ? error.message : String(error)}` });
    } finally {
      set({ calculatingAllGreeks: false });
    }
  },
  
  toggleGrouping: () => {
    set(state => ({
      groupByUnderlying: !state.groupByUnderlying
    }));
  },
  
  getGroupedPositions: () => {
    const { positions } = get();
    const groupedByTicker: Record<string, OptionPosition[]> = {};
    
    // Group positions by ticker
    positions.forEach(position => {
      if (!groupedByTicker[position.ticker]) {
        groupedByTicker[position.ticker] = [];
      }
      groupedByTicker[position.ticker].push(position);
    });
    
    // Create array of grouped positions with aggregated Greeks
    return Object.entries(groupedByTicker).map(([ticker, positionsList]) => {
      // Calculate aggregated Greeks if all positions have Greeks
      let totalGreeks: Greeks | undefined = undefined;
      
      const allPositionsHaveGreeks = positionsList.every(pos => !!pos.greeks);
      
      if (allPositionsHaveGreeks) {
        totalGreeks = {
          delta: 0,
          gamma: 0,
          theta: 0,
          vega: 0,
          rho: 0
        };
        
        // Simply sum the Greeks since they are already adjusted by the API
        // for position direction (buy/sell) and quantity
        positionsList.forEach(position => {
          if (position.greeks) {
            totalGreeks!.delta += position.greeks.delta;
            totalGreeks!.gamma += position.greeks.gamma;
            totalGreeks!.theta += position.greeks.theta;
            totalGreeks!.vega += position.greeks.vega;
            totalGreeks!.rho += position.greeks.rho;
          }
        });
      }
      
      return {
        underlying: ticker,
        positions: positionsList,
        totalGreeks
      };
    });
  }
}));