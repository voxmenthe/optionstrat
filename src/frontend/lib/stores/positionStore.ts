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

interface PositionStore {
  positions: OptionPosition[];
  loading: boolean;
  error: string | null;
  
  fetchPositions: () => Promise<void>;
  addPosition: (position: Omit<OptionPosition, 'id'>) => Promise<void>;
  updatePosition: (id: string, position: Partial<OptionPosition>) => Promise<void>;
  removePosition: (id: string) => Promise<void>;
  calculateGreeks: (position: OptionPosition) => Promise<Greeks | void>;
}

// Create the store with real API calls
export const usePositionStore = create<PositionStore>((set, get) => ({
  positions: [],
  loading: false,
  error: null,
  
  fetchPositions: async () => {
    set({ loading: true, error: null });
    try {
      const positions = await positionsApi.getPositions();
      set({ positions, loading: false });
    } catch (error) {
      set({ error: `Failed to fetch positions: ${error instanceof Error ? error.message : String(error)}`, loading: false });
    }
  },
  
  addPosition: async (position) => {
    set({ loading: true, error: null });
    try {
      const newPosition = await positionsApi.createPosition(position);
      
      set(state => ({
        positions: [...state.positions, newPosition],
        loading: false
      }));
    } catch (error) {
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
      const greeks = await greeksApi.calculateGreeks(position);
      
      set(state => ({
        positions: state.positions.map(pos => 
          pos.id === position.id ? { ...pos, greeks } : pos
        )
      }));
      
      return greeks;
    } catch (error) {
      set({ error: `Failed to calculate Greeks: ${error instanceof Error ? error.message : String(error)}` });
      throw error;
    }
  }
})); 