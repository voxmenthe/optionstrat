import { create } from 'zustand';

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

// Create the store with mock functionality for now
// Later we'll connect to the backend API
export const usePositionStore = create<PositionStore>((set, get) => ({
  positions: [],
  loading: false,
  error: null,
  
  fetchPositions: async () => {
    set({ loading: true, error: null });
    try {
      // Mock API call for now
      // Will be replaced with real API call later
      const mockPositions: OptionPosition[] = [
        {
          id: '1',
          ticker: 'AAPL',
          expiration: '2023-12-15',
          strike: 175,
          type: 'call',
          action: 'buy',
          quantity: 1,
          premium: 5.65,
          greeks: {
            delta: 0.52,
            gamma: 0.03,
            theta: -0.05,
            vega: 0.12,
            rho: 0.03
          }
        },
        {
          id: '2',
          ticker: 'MSFT',
          expiration: '2023-12-15',
          strike: 350,
          type: 'put',
          action: 'sell',
          quantity: 2,
          premium: 3.25,
          greeks: {
            delta: -0.35,
            gamma: 0.02,
            theta: 0.07,
            vega: 0.10,
            rho: -0.02
          }
        }
      ];
      
      // Simulate network delay
      await new Promise(resolve => setTimeout(resolve, 500));
      
      set({ positions: mockPositions, loading: false });
    } catch (error) {
      set({ error: `Failed to fetch positions: ${error instanceof Error ? error.message : String(error)}`, loading: false });
    }
  },
  
  addPosition: async (position) => {
    set({ loading: true, error: null });
    try {
      // Mock API call for now
      // Will be replaced with real API call later
      const newPosition: OptionPosition = {
        ...position,
        id: Math.random().toString(36).substring(2, 9) // Simple ID generation without uuid
      };
      
      // Simulate network delay
      await new Promise(resolve => setTimeout(resolve, 500));
      
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
      // Mock API call for now
      // Will be replaced with real API call later
      
      // Simulate network delay
      await new Promise(resolve => setTimeout(resolve, 500));
      
      set(state => ({
        positions: state.positions.map(pos => 
          pos.id === id ? { ...pos, ...position } : pos
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
      // Mock API call for now
      // Will be replaced with real API call later
      
      // Simulate network delay
      await new Promise(resolve => setTimeout(resolve, 500));
      
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
      // Mock API call for now
      // Will be replaced with real API call later
      
      // Simulate network delay and random values for Greeks
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const mockGreeks: Greeks = {
        delta: position.type === 'call' ? Math.random() * 0.7 : -Math.random() * 0.7,
        gamma: Math.random() * 0.05,
        theta: position.type === 'call' ? -Math.random() * 0.1 : Math.random() * 0.1,
        vega: Math.random() * 0.2,
        rho: position.type === 'call' ? Math.random() * 0.05 : -Math.random() * 0.05
      };
      
      set(state => ({
        positions: state.positions.map(pos => 
          pos.id === position.id ? { ...pos, greeks: mockGreeks } : pos
        )
      }));
      
      return mockGreeks;
    } catch (error) {
      set({ error: `Failed to calculate Greeks: ${error instanceof Error ? error.message : String(error)}` });
      throw error;
    }
  }
})); 