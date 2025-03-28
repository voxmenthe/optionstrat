import { create } from 'zustand';
import { positionsApi, greeksApi } from '../api';
import { calculateMarkPrice, calculatePnL, calculateCurrentValue } from '../utils/optionPriceUtils';
import { PnLCalculationParams } from '../api/positionsApi';

// Types for our store
export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface PnLResult {
  positionId: string;
  pnlAmount: number;
  pnlPercent: number;
  initialValue: number;
  currentValue: number;
  impliedVolatility?: number;
  underlyingPrice?: number;
  calculationTimestamp?: string;
  error?: string; // Added to handle error cases gracefully
  endpointNotImplemented?: boolean; // Flag to indicate if the endpoint is not implemented yet
  clientCalculated?: boolean; // Flag to indicate if the P&L was calculated client-side
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
  markPrice?: number;  // New field for the mid price
  markPriceOverride?: boolean;  // Flag to indicate if mark price is manually overridden
  greeks?: Greeks;
  pnl?: PnLResult;
  theoreticalPnl?: PnLResult;
}

// Interface for grouped positions
export interface GroupedPosition {
  underlying: string;
  underlyingPrice?: number;
  positions: OptionPosition[];
  totalGreeks?: Greeks;
  totalPnl?: {
    pnlAmount: number;
    pnlPercent: number;
    initialValue: number;
    currentValue: number;
    impliedVolatility?: number;
    underlyingPrice?: number;
    clientCalculated?: boolean;
  };
  totalTheoreticalPnl?: {
    pnlAmount: number;
    pnlPercent: number;
    initialValue: number;
    currentValue: number;
    impliedVolatility?: number;
    clientCalculated?: boolean;
  };
}

export interface TheoreticalPnLSettings {
  daysForward: number;
  priceChangePercent: number;
}

interface PositionStore {
  positions: OptionPosition[];
  loading: boolean;
  error: string | null;
  groupByUnderlying: boolean;
  calculatingAllGreeks: boolean;
  calculatingPnL: boolean;
  calculatingTheoreticalPnL: boolean;
  theoreticalPnLSettings: TheoreticalPnLSettings;
  
  // Actions
  fetchPositions: () => Promise<void>;
  addPosition: (position: Omit<OptionPosition, 'id'>) => Promise<void>;
  updatePosition: (id: string, position: Partial<OptionPosition>) => Promise<void>;
  removePosition: (id: string) => Promise<void>;
  calculateGreeks: (position: OptionPosition) => Promise<Greeks | void>;
  recalculateAllGreeks: () => Promise<void>;
  updatePositionMarkPrice: (position: OptionPosition, optionData?: any) => void;
  fetchAndUpdateMarkPrice: (position: OptionPosition) => Promise<number | undefined>;
  fetchAllMarkPrices: (forceUpdate?: boolean) => Promise<void>;
  
  // P&L calculations
  calculatePnL: (position: OptionPosition, recalculate?: boolean, retryCount?: number) => Promise<PnLResult | void>;
  recalculateAllPnL: (forceRecalculate?: boolean) => Promise<void>;
  calculateTheoreticalPnL: (position: OptionPosition, retryCount?: number) => Promise<PnLResult | void>;
  recalculateAllTheoreticalPnL: (forceRecalculate?: boolean) => Promise<void>;
  updateTheoreticalPnLSettings: (settings: Partial<TheoreticalPnLSettings>) => void;
  
  // Grouped positions
  getGroupedPositions: () => GroupedPosition[];
}

// Create the store with real API calls
export const usePositionStore = create<PositionStore>((set, get) => ({
  // Helper function to update mark price for a position
  updatePositionMarkPrice: (position: OptionPosition, optionData?: any) => {
    // Only update mark price if not manually overridden
    if (position.markPriceOverride) return;
    
    // If option data is provided, calculate mark price from bid/ask
    if (optionData) {
      console.log(`Calculating mark price for position ${position.id} with bid=${optionData.bid}, ask=${optionData.ask}`);
      const markPrice = calculateMarkPrice(optionData.bid, optionData.ask);
      console.log(`Calculated mark price: ${markPrice}`);
      
      // Update the position with the calculated mark price
      set(state => {
        const updatedPositions = state.positions.map(pos => 
          pos.id === position.id ? { ...pos, markPrice } : pos
        );
        return { positions: updatedPositions };
      });
    }
  },
  
  // Function to fetch option data and update mark prices
  fetchAndUpdateMarkPrice: async (position: OptionPosition) => {
    // Skip if position has a manual override
    if (position.markPriceOverride) return;
    
    try {
      console.log(`Fetching option data for position ${position.id}:`, position.ticker, position.expiration, position.strike, position.type);
      
      // Import directly from the file to avoid circular dependencies
      const optionsApi = (await import('../api/optionsApi')).optionsApi;
      
      // Fetch option data for this position
      const optionData = await optionsApi.getOptionDataForPosition(position);
      
      if (optionData) {
        console.log(`Received option data for position ${position.id}:`, {
          bid: optionData.bid,
          ask: optionData.ask,
          lastPrice: optionData.lastPrice
        });
        
        // Calculate and update mark price
        const markPrice = calculateMarkPrice(optionData.bid, optionData.ask);
        console.log(`Calculated mark price for position ${position.id}: ${markPrice}`);
        
        if (markPrice !== undefined) {
          // Update the position with the calculated mark price
          set(state => {
            const updatedPositions = state.positions.map(pos => 
              pos.id === position.id ? { ...pos, markPrice } : pos
            );
            return { positions: updatedPositions };
          });
          
          console.log(`Updated mark price for position ${position.id} to ${markPrice}`);
          return markPrice;
        } else {
          console.warn(`Could not calculate mark price for position ${position.id} - bid/ask unavailable`);
        }
      } else {
        console.warn(`No option data found for position ${position.id}`);
      }
      
      return undefined;
    } catch (error) {
      console.warn(`Failed to fetch option data for position ${position.id}:`, error);
      return undefined;
    }
  },
  
  // Function to fetch mark prices for all positions in a batch
  fetchAllMarkPrices: async (forceUpdate = false) => {
    const { positions } = get();
    
    if (positions.length === 0) {
      console.log('No positions to fetch mark prices for');
      return;
    }
    
    console.log(`Fetching mark prices for all ${positions.length} positions`);
    console.log('Current position mark prices before fetch:', positions.map(p => ({
      id: p.id,
      ticker: p.ticker,
      type: p.type,
      strike: p.strike,
      markPrice: p.markPrice,
      markPriceType: typeof p.markPrice,
      isOverride: p.markPriceOverride
    })));
    
    // Set a timeout to ensure we don't hang indefinitely
    let timeoutId: number | undefined;
    const timeoutPromise = new Promise<void>((_, reject) => {
      timeoutId = window.setTimeout(() => {
        reject(new Error('Mark price fetch timeout - continuing with available data'));
      }, 15000); // 15 second timeout
    });
    
    try {
      // Race the fetch against a timeout
      const fetchPromise = (async () => {
        // Group positions by ticker and expiration to minimize API calls
        const positionsByTickerAndExpiry: Record<string, OptionPosition[]> = {};
        
        positions.forEach(position => {
          // Skip positions with manual overrides unless forceUpdate is true
          if (position.markPriceOverride && !forceUpdate) return;
          
          const key = `${position.ticker}|${position.expiration}`;
          if (!positionsByTickerAndExpiry[key]) {
            positionsByTickerAndExpiry[key] = [];
          }
          positionsByTickerAndExpiry[key].push(position);
        });
        
        return positionsByTickerAndExpiry;
      })();
      
      // Race the fetch against the timeout
      const positionsByTickerAndExpiry = await Promise.race([
        fetchPromise,
        timeoutPromise.then(() => ({} as Record<string, OptionPosition[]>))
      ]);
      
      // Import directly from the file to avoid circular dependencies
      const optionsApi = (await import('../api/optionsApi')).optionsApi;
      
      // Process each group in parallel
      const results = await Promise.allSettled(
        Object.entries(positionsByTickerAndExpiry).map(async ([key, positionGroup]) => {
          const [ticker, expiration] = key.split('|');
          
          try {
            console.log(`Fetching options for ${ticker} expiring ${expiration}...`);
            // Fetch options for this expiration
            const options = await optionsApi.getOptionsForExpiration(ticker, expiration);
            console.log(`Received ${options.length} options for ${ticker} expiring ${expiration}`);
            
            if (options.length > 0) {
              console.log('Sample option data:', {
                strike: options[0].strike,
                type: options[0].optionType,
                bid: options[0].bid,
                ask: options[0].ask
              });
            }
            
            // Match options to positions and update mark prices
            const updates: Array<{position: OptionPosition, markPrice: number}> = [];
            
            positionGroup.forEach(position => {
              console.log(`Looking for matching option for position: ${position.ticker} ${position.type.toUpperCase()} ${position.strike} ${position.expiration}`);
              
              const matchingOption = options.find(option => 
                option.strike === position.strike && 
                option.optionType.toLowerCase() === position.type.toLowerCase()
              );
              
              if (matchingOption) {
                console.log(`Found matching option for position ${position.id}:`, {
                  strike: matchingOption.strike,
                  type: matchingOption.optionType,
                  bid: matchingOption.bid,
                  ask: matchingOption.ask
                });
                
                // Ensure bid and ask are numbers before calculating mark price
                const bid = typeof matchingOption.bid === 'number' ? matchingOption.bid : undefined;
                const ask = typeof matchingOption.ask === 'number' ? matchingOption.ask : undefined;
                
                console.log(`Using bid: ${bid}, ask: ${ask} for mark price calculation`);
                const markPrice = calculateMarkPrice(bid, ask);
                console.log(`Calculated mark price for position ${position.id}: ${markPrice}`);
                
                if (markPrice !== undefined) {
                  updates.push({ position, markPrice });
                  console.log(`Added mark price update for position ${position.id}: ${markPrice}`);
                } else {
                  console.warn(`Could not calculate mark price for position ${position.id} - bid/ask unavailable`);
                }
              } else {
                console.warn(`No matching option found for position ${position.id}`);
              }
            });
            
            console.log(`Created ${updates.length} mark price updates for ${ticker} expiring ${expiration}`);
            return { key, updates };
          } catch (error) {
            console.error(`Failed to fetch options for ${ticker} expiring ${expiration}:`, error);
            return { key, error };
          }
        })
      );
      
      // Apply all updates at once to minimize state updates
      const allUpdates: Array<{position: OptionPosition, markPrice: number}> = [];
      
      results.forEach(result => {
        if (result.status === 'fulfilled' && result.value.updates) {
          allUpdates.push(...result.value.updates);
        }
      });
      
      if (allUpdates.length > 0) {
        // Update all positions with new mark prices in a single state update
        console.log('About to update positions with mark prices:', allUpdates.map(u => ({ id: u.position.id, markPrice: u.markPrice })));
        
        set(state => {
          const updatedPositions = [...state.positions];
          
          allUpdates.forEach(({ position, markPrice }) => {
            const posIndex = updatedPositions.findIndex(p => p.id === position.id);
            if (posIndex >= 0) {
              console.log(`Updating position ${position.id} mark price from ${updatedPositions[posIndex].markPrice} to ${markPrice}`);
              
              // Ensure the mark price is a valid number
              if (markPrice === undefined || markPrice === null) {
                console.error(`Null or undefined mark price for position ${position.id}`);
              } else {
                const numericMarkPrice = typeof markPrice === 'number' ? markPrice : Number(markPrice);
                
                if (!isNaN(numericMarkPrice) && numericMarkPrice >= 0) {
                  console.log(`Setting valid mark price ${numericMarkPrice} for position ${position.id}`);
                  updatedPositions[posIndex] = { 
                    ...updatedPositions[posIndex], 
                    markPrice: numericMarkPrice 
                  };
                } else {
                  console.error(`Invalid mark price value: ${markPrice} (${typeof markPrice}) for position ${position.id}`);
                }
              }
            } else {
              console.warn(`Position ${position.id} not found in state when updating mark price`);
            }
          });
          
          // Debug log the updated positions
          console.log('Updated positions:', updatedPositions.map(p => ({ id: p.id, markPrice: p.markPrice })));
          
          return { positions: updatedPositions };
        });
        
        console.log(`Updated mark prices for ${allUpdates.length} positions`);
      } else {
        console.log('No mark prices were updated');
      }
    } catch (error) {
      // If it's a timeout, we'll still try to use whatever data we have
      if (error instanceof Error && error.message.includes('timeout')) {
        console.warn('Mark price fetch timed out - continuing with available data');
        // Don't set an error state for timeouts, as we'll continue with partial data
      } else {
        console.error('Failed to fetch mark prices:', error);
      }
    } finally {
      // Clear timeout if it was set
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    }
  },
  positions: [],
  loading: false,
  error: null,
  groupByUnderlying: true, // Set grouped view as default
  calculatingAllGreeks: false,
  calculatingPnL: false,
  calculatingTheoreticalPnL: false,
  theoreticalPnLSettings: {
    daysForward: 7,
    priceChangePercent: 0,
  },
  
  fetchPositions: async () => {
    set({ loading: true, error: null });
    
    // Create an AbortController for timeout handling
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
      console.warn('Positions fetch request timed out after 5 seconds');
    }, 5000);
    
    try {
      console.log('Fetching positions from API...');
      const startTime = performance.now();
      const newPositions = await positionsApi.getPositions({}, controller.signal);
      const endTime = performance.now();
      console.log(`Received positions in ${Math.round(endTime - startTime)}ms:`, newPositions);
      
      // Clear the timeout since the request completed successfully
      clearTimeout(timeoutId);
      
      // Preserve PnL data for existing positions
      set(state => {
        // If we got an empty array but have existing positions, keep the existing ones
        // This prevents the UI from flashing empty state during temporary API issues
        if (newPositions.length === 0 && state.positions.length > 0) {
          console.log('No positions returned from API but have existing positions, preserving current state');
          return { loading: false, error: null };
        }
        
        const updatedPositions = newPositions.map(newPos => {
          // Find matching position in current state to preserve PnL data
          const existingPos = state.positions.find(p => p.id === newPos.id);
          if (existingPos) {
            return {
              ...newPos,
              pnl: existingPos.pnl, // Preserve actual PnL if it exists
              theoreticalPnl: existingPos.theoreticalPnl // Preserve theoretical PnL if it exists
            };
          }
          return newPos;
        });
        
        return { positions: updatedPositions, loading: false, error: null };
      });
    } catch (error) {
      // Clear the timeout since the request errored out
      clearTimeout(timeoutId);
      
      console.error('Error fetching positions:', error);
      
      // Check if this was an abort error (timeout)
      if (error instanceof DOMException && error.name === 'AbortError') {
        set({ 
          error: 'Request timed out. The server is taking too long to respond.', 
          loading: false,
          // Keep any existing positions to maintain UI functionality
          // positions: get().positions - no need to set this as we're not changing it
        });
        return;
      }
      
      // More detailed error message to help diagnose issues
      const errorMessage = error instanceof Error ? 
        `${error.name}: ${error.message}` : 
        String(error);
      
      set({ 
        error: `Failed to fetch positions: ${errorMessage}`, 
        loading: false 
        // Keep any existing positions to maintain UI functionality
        // positions: get().positions - no need to set this as we're not changing it
      });
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
      
      // Try to update mark price from option data if available
      try {
        // In a real implementation, we would fetch option data separately or extract it from the Greeks response
        // For now, we'll use the Greeks data as a fallback, assuming it might have bid/ask properties
        // This is just a placeholder - in a real implementation, we'd need to fetch actual option data
        const optionData = {
          bid: (greeks as any).bid,
          ask: (greeks as any).ask
        };
        
        // Calculate and update the mark price if we have valid data
        if (optionData.bid !== undefined || optionData.ask !== undefined) {
          get().updatePositionMarkPrice(position, optionData);
        }
      } catch (markPriceError) {
        // Silently handle mark price calculation errors
        console.warn(`Failed to update mark price for position ${position.id}:`, markPriceError);
      }
      
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
  
  recalculateAllGreeks: async (forceRecalculate = false) => {
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
            
            // If not force recalculating, try to use Greeks data as a fallback
            try {
              const optionData = {
                bid: (greeks as any).bid,
                ask: (greeks as any).ask
              };
              
              // Only update if we have valid data and no override
              if ((optionData.bid !== undefined || optionData.ask !== undefined) && 
                  !updatedPositions[posIndex].markPriceOverride) {
                const markPrice = calculateMarkPrice(optionData.bid, optionData.ask);
                if (markPrice !== undefined) {
                  updatedPositions[posIndex].markPrice = markPrice;
                }
              }
            } catch (markPriceError) {
              // Silently handle mark price calculation errors
              console.warn(`Failed to update mark price from Greeks for position ${position.id}:`, markPriceError);
            }
            
            // We no longer save Greeks to the database as they should be calculated fresh each time
            // This prevents double-application of sign and quantity
            console.log(`Updated Greeks for position ${position.id} in frontend state only`);
          }
        }
      }
      
      console.log(`Updated Greeks for ${updatedCount} out of ${positions.length} positions`);
      set({ positions: updatedPositions });
      
      // If force recalculating, also fetch and update mark prices
      if (forceRecalculate) {
        console.log('Force recalculating mark prices');
        // Don't await - let this happen in the background
        get().fetchAllMarkPrices(false).catch(markPriceError => {
          console.warn('Failed to fetch mark prices:', markPriceError);
        });
      }
    } catch (error) {
      console.error('Failed to recalculate all Greeks:', error);
      set({ error: `Failed to recalculate all Greeks: ${error instanceof Error ? error.message : String(error)}` });
    } finally {
      set({ calculatingAllGreeks: false });
    }
  },
  
  // P&L calculations with retry logic
  calculatePnL: async (position: OptionPosition, recalculate: boolean = false, retryCount: number = 0) => {
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 1000; // 1 second
    
    try {
      console.log(`Calculating P&L for position ${position.id}:`, position.ticker, position.strike, position.type, `recalculate=${recalculate}`);
      
      try {
        const pnl = await positionsApi.calculatePnL(position.id, recalculate);
        console.log(`Received P&L for position ${position.id}:`, pnl);
        
        // Store the updated position with P&L in local state
        set(state => {
          const updatedPositions = state.positions.map(pos => 
            pos.id === position.id ? { ...pos, pnl } : pos
          );
          return { positions: updatedPositions };
        });
        
        return pnl;
      } catch (apiError) {
        // Check if this is a 404 or similar error that might indicate endpoint not implemented
        if (apiError && typeof apiError === 'object' && 'status' in apiError && (apiError.status === 404 || apiError.status === 501)) {
          console.log(`P&L calculation endpoint not implemented for position ${position.id}, using client-side calculation`);
          
          // Use client-side calculation with mark price
          if (position.markPrice !== undefined && position.premium !== undefined && 
              position.quantity !== undefined && position.action !== undefined) {
            
            // Calculate P&L using the mark price
            const { pnlAmount, pnlPercent } = calculatePnL(
              position.quantity,
              position.premium,
              position.markPrice,
              position.action
            );
            
            // Calculate cost basis and current value
            const initialValue = Math.abs(position.quantity * position.premium * 100);
            const currentValue = calculateCurrentValue(position.quantity, position.markPrice) || 0;
            
            // Create a client-calculated PnL result
            const clientPnl: PnLResult = {
              positionId: position.id,
              pnlAmount,
              pnlPercent,
              initialValue,
              currentValue,
              calculationTimestamp: new Date().toISOString(),
              clientCalculated: true
            };
            
            console.log(`Client-side P&L calculation for position ${position.id}:`, clientPnl);
            
            // Store the client-calculated result in local state
            set(state => {
              const updatedPositions = state.positions.map(pos => 
                pos.id === position.id ? { ...pos, pnl: clientPnl } : pos
              );
              return { positions: updatedPositions };
            });
            
            return clientPnl;
          } else {
            // Missing required data for client-side calculation
            console.log(`Cannot calculate P&L for position ${position.id}: missing required data`);
            // Create a placeholder PnL result with error info
            const placeholderPnl: PnLResult = {
              positionId: position.id,
              pnlAmount: 0,
              pnlPercent: 0,
              initialValue: 0,
              currentValue: 0,
              error: 'Missing data for P&L calculation',
              clientCalculated: true
            };
            
            // Store the placeholder in local state
            set(state => {
              const updatedPositions = state.positions.map(pos => 
                pos.id === position.id ? { ...pos, pnl: placeholderPnl } : pos
              );
              return { positions: updatedPositions };
            });
            
            return placeholderPnl;
          }
        }
        
        // For other errors, rethrow to be handled by the retry logic
        throw apiError;
      }
    } catch (error) {
      console.error(`Failed to calculate P&L for position ${position.id} (attempt ${retryCount + 1}/${MAX_RETRIES}):`, error);
      
      // If we haven't exceeded max retries, wait and try again
      if (retryCount < MAX_RETRIES) {
        console.log(`Retrying P&L calculation for position ${position.id} in ${RETRY_DELAY}ms...`);
        // Wait for the specified delay
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
        // Try again with recalculate=true to force a fresh calculation
        return get().calculatePnL(position, true, retryCount + 1);
      }
      
      // We've exhausted our retries - create a placeholder with error info
      const errorPnl: PnLResult = {
        positionId: position.id,
        pnlAmount: 0,
        pnlPercent: 0,
        initialValue: 0,
        currentValue: 0,
        error: `Failed after ${MAX_RETRIES} attempts: ${error instanceof Error ? error.message : String(error)}`,
        clientCalculated: true // Mark as client-calculated since we're handling the error client-side
      };
      
      // Store the error result in local state
      set(state => {
        const updatedPositions = state.positions.map(pos => 
          pos.id === position.id ? { ...pos, pnl: errorPnl } : pos
        );
        return { 
          positions: updatedPositions,
          error: `Failed to calculate P&L after ${MAX_RETRIES} attempts` 
        };
      });
      
      return errorPnl;
    }
  },
  
  recalculateAllPnL: async (forceRecalculate: boolean = false) => {
    const { positions } = get();
    
    if (positions.length === 0) {
      console.log('No positions to calculate P&L for');
      return;
    }
    
    console.log(`Recalculating P&L for all ${positions.length} positions, forceRecalculate=${forceRecalculate}`);
    set({ calculatingPnL: true, error: null });
    
    try {
      // First check if the endpoint is implemented by trying one position
      if (positions.length > 0) {
        try {
          // Try with the first position to see if the endpoint exists
          await positionsApi.calculatePnL(positions[0].id, forceRecalculate);
        } catch (endpointError) {
          // If we get a 404/501 (endpoint not implemented) or a network error (status 0)
          if (endpointError && typeof endpointError === 'object' && 'status' in endpointError && 
              (endpointError.status === 404 || endpointError.status === 501 || endpointError.status === 0)) {
            console.log('P&L calculation endpoint not implemented - using client-side calculations');
            
            // Use client-side calculation with mark prices
            const updatedPositions = positions.map(position => {
              // Only calculate if we have the necessary data
              if (position.markPrice !== undefined && position.premium !== undefined && 
                  position.quantity !== undefined && position.action !== undefined) {
                
                // Calculate P&L using the mark price
                const { pnlAmount, pnlPercent } = calculatePnL(
                  position.quantity,
                  position.premium,
                  position.markPrice,
                  position.action
                );
                
                // Calculate cost basis and current value
                const initialValue = Math.abs(position.quantity * position.premium * 100);
                const currentValue = calculateCurrentValue(position.quantity, position.markPrice) || 0;
                
                return {
                  ...position,
                  pnl: {
                    positionId: position.id,
                    pnlAmount,
                    pnlPercent,
                    initialValue,
                    currentValue,
                    calculationTimestamp: new Date().toISOString(),
                    clientCalculated: true
                  } as PnLResult
                };
              } else {
                // Missing required data
                return {
                  ...position,
                  pnl: {
                    positionId: position.id,
                    pnlAmount: 0,
                    pnlPercent: 0,
                    initialValue: 0,
                    currentValue: 0,
                    error: 'Missing data for P&L calculation',
                    clientCalculated: true
                  } as PnLResult
                };
              }
            });
            
            set({ positions: updatedPositions, calculatingPnL: false });
            return;
          }
        }
      }
      
      // If we get here, the endpoint exists, so proceed with calculations
      // Process positions in parallel using Promise.allSettled
      const results = await Promise.allSettled(
        positions.map(async (position) => {
          try {
            // Use the provided forceRecalculate parameter
            const pnl = await get().calculatePnL(position, forceRecalculate) as PnLResult;
            return { position, pnl, success: true };
          } catch (error) {
            console.error(`Failed to calculate P&L for position ${position.id}:`, error);
            // Create an error PnL result
            const errorPnl: PnLResult = {
              positionId: position.id,
              pnlAmount: 0,
              pnlPercent: 0,
              initialValue: 0,
              currentValue: 0,
              error: error instanceof Error ? error.message : String(error),
              clientCalculated: true // Mark as client-calculated since we're handling the error client-side
            };
            return { position, pnl: errorPnl, success: false };
          }
        })
      );
      
      // Update the positions with calculated P&L
      const updatedPositions = [...positions];
      let updatedCount = 0;
      let errorCount = 0;
      
      for (const result of results) {
        if (result.status === 'fulfilled') {
          const { position, pnl, success } = result.value;
          const posIndex = updatedPositions.findIndex(p => p.id === position.id);
          
          if (posIndex >= 0) {
            updatedPositions[posIndex] = { ...updatedPositions[posIndex], pnl };
            if (success) {
              updatedCount++;
            } else {
              errorCount++;
            }
          }
        }
      }
      
      console.log(`Updated P&L for ${updatedCount} out of ${positions.length} positions (${errorCount} errors)`);
      set({ positions: updatedPositions });
    } catch (error) {
      console.error('Failed to recalculate all P&L:', error);
      set({ error: `Failed to recalculate all P&L: ${error instanceof Error ? error.message : String(error)}` });
    } finally {
      set({ calculatingPnL: false });
    }
  },
  
  calculateTheoreticalPnL: async (position: OptionPosition, retryCount: number = 0) => {
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 1000; // 1 second
    const { theoreticalPnLSettings } = get();
    
    try {
      console.log(`Calculating theoretical P&L for position ${position.id} with settings:`, theoreticalPnLSettings);
      const params: PnLCalculationParams = {
        days_forward: theoreticalPnLSettings.daysForward,
        price_change_percent: theoreticalPnLSettings.priceChangePercent
      };
      
      try {
        // Use recalculate=retryCount>0 to force recalculation on retry attempts
        const pnl = await positionsApi.calculateTheoreticalPnL(position.id, params, retryCount > 0);
        console.log(`Received theoretical P&L for position ${position.id}:`, pnl);
        
        // Store the updated position with theoretical P&L in local state
        set(state => {
          const updatedPositions = state.positions.map(pos => 
            pos.id === position.id ? { ...pos, theoreticalPnl: pnl } : pos
          );
          return { positions: updatedPositions };
        });
        
        return pnl;
      } catch (apiError) {
        // Check if this is a 404/501 error (endpoint not implemented) or a network error (status 0)
        if (apiError && typeof apiError === 'object' && 'status' in apiError && 
            (apiError.status === 404 || apiError.status === 501 || apiError.status === 0)) {
          console.log(`Theoretical P&L calculation endpoint not implemented for position ${position.id}, using client-side calculation`);
          
          // Use client-side calculation with mark price
          if (position.markPrice !== undefined && position.premium !== undefined && 
              position.quantity !== undefined && position.action !== undefined) {
            
            // Simple theoretical calculation based on price change percentage
            const priceChangeMultiplier = 1 + (theoreticalPnLSettings.priceChangePercent / 100);
            
            // For calls, price increases are good for buyers, bad for sellers
            // For puts, price increases are bad for buyers, good for sellers
            let theoreticalMarkPrice = position.markPrice;
            
            if (position.type === 'call') {
              theoreticalMarkPrice = position.markPrice * priceChangeMultiplier;
            } else { // put
              // For puts, price increases reduce value, decreases increase value
              theoreticalMarkPrice = position.markPrice * (2 - priceChangeMultiplier);
            }
            
            // Ensure mark price doesn't go below zero
            theoreticalMarkPrice = Math.max(0, theoreticalMarkPrice);
            
            // Calculate theoretical P&L using the adjusted mark price
            const { pnlAmount, pnlPercent } = calculatePnL(
              position.quantity,
              position.premium,
              theoreticalMarkPrice,
              position.action
            );
            
            // Calculate cost basis and theoretical value
            const initialValue = Math.abs(position.quantity * position.premium * 100);
            const currentValue = calculateCurrentValue(position.quantity, theoreticalMarkPrice) || 0;
            
            // Create a client-calculated theoretical PnL result
            const clientPnl: PnLResult = {
              positionId: position.id,
              pnlAmount,
              pnlPercent,
              initialValue,
              currentValue,
              calculationTimestamp: new Date().toISOString(),
              clientCalculated: true
            };
            
            console.log(`Client-side theoretical P&L calculation for position ${position.id}:`, clientPnl);
            
            // Store the client-calculated result in local state
            set(state => {
              const updatedPositions = state.positions.map(pos => 
                pos.id === position.id ? { ...pos, theoreticalPnl: clientPnl } : pos
              );
              return { positions: updatedPositions };
            });
            
            return clientPnl;
          }
          
          console.log(`Cannot calculate theoretical P&L for position ${position.id}: missing required data`);
          // Create a placeholder PnL result with error info
          const placeholderPnl: PnLResult = {
            positionId: position.id,
            pnlAmount: 0,
            pnlPercent: 0,
            initialValue: 0,
            currentValue: 0,
            error: 'Missing data for theoretical P&L calculation',
            clientCalculated: true
          };
          
          // Store the placeholder in local state
          set(state => {
            const updatedPositions = state.positions.map(pos => 
              pos.id === position.id ? { ...pos, theoreticalPnl: placeholderPnl } : pos
            );
            return { positions: updatedPositions };
          });
          
          return placeholderPnl;
        }
        
        // For other errors, rethrow to be handled by the retry logic
        throw apiError;
      }
    } catch (error) {
      console.error(`Failed to calculate theoretical P&L for position ${position.id} (attempt ${retryCount + 1}/${MAX_RETRIES}):`, error);
      
      // If we haven't exceeded max retries, wait and try again
      if (retryCount < MAX_RETRIES) {
        console.log(`Retrying theoretical P&L calculation for position ${position.id} in ${RETRY_DELAY}ms...`);
        // Wait for the specified delay
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
        // Try again
        return get().calculateTheoreticalPnL(position, retryCount + 1);
      }
      
      // We've exhausted our retries - create a placeholder with error info
      const errorPnl: PnLResult = {
        positionId: position.id,
        pnlAmount: 0,
        pnlPercent: 0,
        initialValue: 0,
        currentValue: 0,
        error: `Failed after ${MAX_RETRIES} attempts: ${error instanceof Error ? error.message : String(error)}`,
        clientCalculated: true // Mark as client-calculated since we're handling the error client-side
      };
      
      // Store the error result in local state
      set(state => {
        const updatedPositions = state.positions.map(pos => 
          pos.id === position.id ? { ...pos, theoreticalPnl: errorPnl } : pos
        );
        return { 
          positions: updatedPositions,
          error: `Failed to calculate theoretical P&L after ${MAX_RETRIES} attempts` 
        };
      });
      
      return errorPnl;
    }
  },
  
  recalculateAllTheoreticalPnL: async (forceRecalculate: boolean = false) => {
    const { positions, theoreticalPnLSettings } = get();
    
    if (positions.length === 0) {
      console.log('No positions to calculate theoretical P&L for');
      return;
    }
    
    console.log(`Recalculating theoretical P&L for all ${positions.length} positions with settings:`, theoreticalPnLSettings, `forceRecalculate=${forceRecalculate}`);
    set({ calculatingTheoreticalPnL: true, error: null });
    
    try {
      // First check if the endpoint is implemented by trying one position
      if (positions.length > 0) {
        try {
          // Try with the first position to see if the endpoint exists
          const params: PnLCalculationParams = {
            days_forward: theoreticalPnLSettings.daysForward,
            price_change_percent: theoreticalPnLSettings.priceChangePercent
          };
          await positionsApi.calculateTheoreticalPnL(positions[0].id, params, forceRecalculate);
        } catch (endpointError) {
          // If we get a 404/501 (endpoint not implemented) or a network error (status 0)
          if (endpointError && typeof endpointError === 'object' && 'status' in endpointError && 
              (endpointError.status === 404 || endpointError.status === 501 || endpointError.status === 0)) {
            console.log('Theoretical P&L calculation endpoint not implemented - using client-side calculations');
            
            // Use client-side calculation with mark prices
            const updatedPositions = positions.map(position => {
              // Only calculate if we have the necessary data
              if (position.markPrice !== undefined && position.premium !== undefined && 
                  position.quantity !== undefined && position.action !== undefined && 
                  position.type !== undefined) {
                
                // Simple theoretical calculation based on price change percentage
                const priceChangeMultiplier = 1 + (theoreticalPnLSettings.priceChangePercent / 100);
                
                // For calls, price increases are good for buyers, bad for sellers
                // For puts, price increases are bad for buyers, good for sellers
                let theoreticalMarkPrice = position.markPrice;
                
                if (position.type === 'call') {
                  theoreticalMarkPrice = position.markPrice * priceChangeMultiplier;
                } else { // put
                  // For puts, price increases reduce value, decreases increase value
                  theoreticalMarkPrice = position.markPrice * (2 - priceChangeMultiplier);
                }
                
                // Ensure mark price doesn't go below zero
                theoreticalMarkPrice = Math.max(0, theoreticalMarkPrice);
                
                // Calculate theoretical P&L using the adjusted mark price
                const { pnlAmount, pnlPercent } = calculatePnL(
                  position.quantity,
                  position.premium,
                  theoreticalMarkPrice,
                  position.action
                );
                
                // Calculate cost basis and theoretical value
                const initialValue = Math.abs(position.quantity * position.premium * 100);
                const currentValue = calculateCurrentValue(position.quantity, theoreticalMarkPrice) || 0;
                
                return {
                  ...position,
                  theoreticalPnl: {
                    positionId: position.id,
                    pnlAmount,
                    pnlPercent,
                    initialValue,
                    currentValue,
                    calculationTimestamp: new Date().toISOString(),
                    clientCalculated: true
                  } as PnLResult
                };
              } else {
                // Missing required data
                return {
                  ...position,
                  theoreticalPnl: {
                    positionId: position.id,
                    pnlAmount: 0,
                    pnlPercent: 0,
                    initialValue: 0,
                    currentValue: 0,
                    error: 'Missing data for theoretical P&L calculation',
                    clientCalculated: true
                  } as PnLResult
                };
              }
            });
            
            set({ positions: updatedPositions, calculatingTheoreticalPnL: false });
            return;
          }
        }
      }
      
      // If we get here, the endpoint exists, so proceed with calculations
      try {
        // Bulk calculate theoretical P&L for all positions
        const positionIds = positions.map(p => p.id);
        const params: PnLCalculationParams = {
          days_forward: theoreticalPnLSettings.daysForward,
          price_change_percent: theoreticalPnLSettings.priceChangePercent
        };
        
        const pnlResults = await positionsApi.calculateBulkTheoreticalPnL(positionIds, params, forceRecalculate);
        console.log('Received bulk theoretical P&L results:', pnlResults);
        
        // Update the positions with calculated theoretical P&L
        const updatedPositions = positions.map(position => {
          const theoreticalPnl = pnlResults[position.id];
          return theoreticalPnl ? { ...position, theoreticalPnl } : position;
        });
        
        console.log(`Updated theoretical P&L for ${Object.keys(pnlResults).length} out of ${positions.length} positions`);
        set({ positions: updatedPositions });
      } catch (bulkError) {
        // If bulk endpoint fails with 404/501 (not implemented) or network error (status 0)
        if (bulkError && typeof bulkError === 'object' && 'status' in bulkError && 
            (bulkError.status === 404 || bulkError.status === 501 || bulkError.status === 0)) {
          console.log('Bulk theoretical P&L endpoint not implemented - trying individual calculations');
          
          // Process positions in parallel using Promise.allSettled
          const results = await Promise.allSettled(
            positions.map(async (position) => {
              try {
                const pnl = await get().calculateTheoreticalPnL(position, 0) as PnLResult;
                return { position, pnl, success: true };
              } catch (error) {
                console.error(`Failed to calculate theoretical P&L for position ${position.id}:`, error);
                // Create an error PnL result
                const errorPnl: PnLResult = {
                  positionId: position.id,
                  pnlAmount: 0,
                  pnlPercent: 0,
                  initialValue: 0,
                  currentValue: 0,
                  error: error instanceof Error ? error.message : String(error),
                  clientCalculated: true // Mark as client-calculated since we're handling the error client-side
                };
                return { position, pnl: errorPnl, success: false };
              }
            })
          );
          
          // Update the positions with calculated theoretical P&L
          const updatedPositions = [...positions];
          let updatedCount = 0;
          let errorCount = 0;
          
          for (const result of results) {
            if (result.status === 'fulfilled') {
              const { position, pnl, success } = result.value;
              const posIndex = updatedPositions.findIndex(p => p.id === position.id);
              
              if (posIndex >= 0) {
                updatedPositions[posIndex] = { ...updatedPositions[posIndex], theoreticalPnl: pnl };
                if (success) {
                  updatedCount++;
                } else {
                  errorCount++;
                }
              }
            }
          }
          
          console.log(`Updated theoretical P&L for ${updatedCount} out of ${positions.length} positions (${errorCount} errors)`);
          set({ positions: updatedPositions });
        } else {
          // For other errors, rethrow
          throw bulkError;
        }
      }
    } catch (error) {
      console.error('Failed to recalculate all theoretical P&L:', error);
      set({ error: `Failed to recalculate all theoretical P&L: ${error instanceof Error ? error.message : String(error)}` });
    } finally {
      set({ calculatingTheoreticalPnL: false });
    }
  },
  
  updateTheoreticalPnLSettings: (settings: Partial<TheoreticalPnLSettings>) => {
    set(state => ({
      theoreticalPnLSettings: {
        ...state.theoreticalPnLSettings,
        ...settings
      }
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
    
    // Create array of grouped positions with aggregated Greeks and P&L
    return Object.entries(groupedByTicker).map(([ticker, positionsList]) => {
      // Calculate aggregated Greeks if all positions have Greeks
      let totalGreeks: Greeks | undefined = undefined;
      let totalPnl: GroupedPosition['totalPnl'] = undefined;
      let totalTheoreticalPnl: GroupedPosition['totalTheoreticalPnl'] = undefined;
      
      const allPositionsHaveGreeks = positionsList.every(pos => !!pos.greeks);
      const allPositionsHavePnL = positionsList.every(pos => !!pos.pnl);
      const allPositionsHaveTheoreticalPnL = positionsList.every(pos => !!pos.theoreticalPnl);
      
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
      
      // Calculate aggregated P&L if all positions have P&L
      if (allPositionsHavePnL) {
        totalPnl = {
          pnlAmount: 0,
          pnlPercent: 0,
          initialValue: 0,
          currentValue: 0,
          impliedVolatility: 0,
          clientCalculated: false // Initialize as false, will set to true if any position has client-calculated P&L
        };
        
        let totalInitialValue = 0;
        
        let totalVolatilityWeight = 0;
        
        positionsList.forEach(position => {
          if (position.pnl) {
            totalPnl!.pnlAmount += position.pnl.pnlAmount;
            totalPnl!.initialValue += position.pnl.initialValue;
            totalPnl!.currentValue += position.pnl.currentValue;
            totalInitialValue += position.pnl.initialValue;
            
            // Calculate weighted implied volatility
            if (position.pnl.impliedVolatility) {
              const weight = position.pnl.initialValue / totalInitialValue;
              totalPnl!.impliedVolatility! += position.pnl.impliedVolatility * weight;
              totalVolatilityWeight += weight;
            }
            
            // Set the underlying price (should be the same for all positions in the group)
            if (position.pnl.underlyingPrice) {
              totalPnl!.underlyingPrice = position.pnl.underlyingPrice;
            }
            
            // If any position has client-calculated P&L, mark the group as client-calculated
            if (position.pnl.clientCalculated) {
              totalPnl!.clientCalculated = true;
            }
          }
        });
        
        // Normalize implied volatility
        if (totalVolatilityWeight > 0) {
          totalPnl!.impliedVolatility = totalPnl!.impliedVolatility! / totalVolatilityWeight;
        }
        
        // Calculate total percent P&L
        if (totalInitialValue > 0) {
          // For P&L percent, we need to calculate it as a weighted average of individual positions
          // to avoid showing incorrect percentage for mixed long and short position groups
          let weightedPnlPercent = 0;
          
          positionsList.forEach(position => {
            if (position.pnl && position.pnl.initialValue > 0) {
              const weight = position.pnl.initialValue / totalInitialValue;
              weightedPnlPercent += (position.pnl.pnlPercent * weight);
            }
          });
          
          totalPnl.pnlPercent = weightedPnlPercent;
        }
      }
      
      // Calculate aggregated theoretical P&L if all positions have theoretical P&L
      if (allPositionsHaveTheoreticalPnL) {
        totalTheoreticalPnl = {
          pnlAmount: 0,
          pnlPercent: 0,
          initialValue: 0,
          currentValue: 0,
          clientCalculated: false // Initialize as false, will set to true if any position has client-calculated theoretical P&L
        };
        
        let totalInitialValue = 0;
        
        positionsList.forEach(position => {
          if (position.theoreticalPnl) {
            totalTheoreticalPnl!.pnlAmount += position.theoreticalPnl.pnlAmount;
            totalTheoreticalPnl!.initialValue += position.theoreticalPnl.initialValue;
            totalTheoreticalPnl!.currentValue += position.theoreticalPnl.currentValue;
            totalInitialValue += position.theoreticalPnl.initialValue;
            
            // If any position has client-calculated theoretical P&L, mark the group as client-calculated
            if (position.theoreticalPnl.clientCalculated) {
              totalTheoreticalPnl!.clientCalculated = true;
            }
          }
        });
        
        // Calculate total percent theoretical P&L
        if (totalInitialValue > 0) {
          // For theoretical P&L percent, use weighted average to handle mixed long/short positions
          let weightedPnlPercent = 0;
          
          positionsList.forEach(position => {
            if (position.theoreticalPnl && position.theoreticalPnl.initialValue > 0) {
              const weight = position.theoreticalPnl.initialValue / totalInitialValue;
              weightedPnlPercent += (position.theoreticalPnl.pnlPercent * weight);
            }
          });
          
          totalTheoreticalPnl.pnlPercent = weightedPnlPercent;
        }
      }
      
      // Get the most recent underlying price from any position that has it
      let underlyingPrice: number | undefined = undefined;
      for (const pos of positionsList) {
        if (pos.pnl?.underlyingPrice) {
          underlyingPrice = pos.pnl.underlyingPrice;
          break; // Use the first valid price we find
        }
      }
      
      return {
        underlying: ticker,
        underlyingPrice,
        positions: positionsList,
        totalGreeks,
        totalPnl,
        totalTheoreticalPnl
      };
    });
  }
}));