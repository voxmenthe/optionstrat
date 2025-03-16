# P&L Calculation Implementation Plan

## Overview

This document outlines the implementation plan for adding P&L calculation features to the editable position table. The key requirements are:

1. Calculate four P&L columns in the editable position table
2. Base pricing on the mark (mid of bid and ask)
3. Handle missing bid/ask data gracefully
4. Allow manual overrides of the mark price
5. Determine the best approach for loading option prices for existing positions during recalculations

## Current State Analysis

### Frontend Components
- The `EditablePositionTable` component displays positions with editable fields
- P&L columns exist but rely on backend endpoints that are not yet implemented
- The component handles missing endpoints gracefully with error flags

### Data Flow
- Option prices are fetched through the `optionsApi.getOptionsForExpiration` endpoint
- P&L calculations are attempted through the `positionsApi` endpoints
- The position store manages position data and calculation states

### Backend Status
- P&L calculation endpoints are not yet implemented
- The ScenarioEngine service could potentially be leveraged for calculations

## Implementation Plan

### 1. Add Mark Price Column to Position Table

#### Frontend Changes
1. Update the `OptionPosition` interface in `positionStore.ts`:
```typescript
export interface OptionPosition {
  // Existing fields...
  markPrice?: number;  // New field for the mid price
  markPriceOverride?: boolean;  // Flag to indicate if mark price is manually overridden
}
```

2. Add the mark price column to the `EditablePositionTable` component:
   - Add a new column header in the table header section
   - Implement an editable cell for the mark price
   - Add the field to the `EDITABLE_POSITION_FIELDS` constant

3. Update the position store to handle mark price updates:
   - Add logic to calculate the mark price (mid of bid/ask) when option data is loaded
   - Preserve user overrides when recalculating

### 2. Implement Mark Price Calculation Logic

1. Create a utility function to calculate mark price:
```typescript
// In a new file: src/frontend/lib/utils/optionPriceUtils.ts
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
```

2. Integrate mark price calculation when loading option data:
   - Update the position store to calculate and store mark prices
   - Ensure mark prices are preserved during position updates

### 3. Enhance P&L Calculation with Mark Prices

1. Update the P&L calculation logic to use mark prices:
   - Modify the `calculatePnL` and `calculateTheoreticalPnL` functions to use mark prices
   - Add fallback logic for when mark prices are unavailable

2. Implement client-side P&L calculations as a fallback:
```typescript
// In positionStore.ts
const calculateClientSidePnL = (position: OptionPosition): PnLResult => {
  // Use mark price if available, otherwise use premium as a fallback
  const currentPrice = position.markPrice ?? position.premium ?? 0;
  const initialPrice = position.premium ?? 0;
  
  // Calculate P&L based on price difference
  const contractMultiplier = 100; // Standard for options
  const quantity = position.quantity || 0;
  const initialValue = initialPrice * contractMultiplier * quantity;
  const currentValue = currentPrice * contractMultiplier * quantity;
  const pnlAmount = currentValue - initialValue;
  const pnlPercent = initialValue !== 0 ? (pnlAmount / initialValue) * 100 : 0;
  
  return {
    positionId: position.id,
    pnlAmount,
    pnlPercent,
    initialValue,
    currentValue,
    calculationTimestamp: new Date().toISOString(),
  };
};
```

### 4. Implement Option Price Loading for Existing Positions

1. Create a function to fetch option prices for existing positions:
```typescript
// In optionChainStore.ts
const fetchOptionPricesForPositions = async (positions: OptionPosition[]): Promise<Record<string, OptionContract>> => {
  const results: Record<string, OptionContract> = {};
  
  // Group positions by ticker and expiration to minimize API calls
  const positionsByTickerAndExpiry: Record<string, OptionPosition[]> = {};
  
  positions.forEach(position => {
    const key = `${position.ticker}|${position.expiration}`;
    if (!positionsByTickerAndExpiry[key]) {
      positionsByTickerAndExpiry[key] = [];
    }
    positionsByTickerAndExpiry[key].push(position);
  });
  
  // Fetch option chains for each ticker/expiry combination
  for (const [key, positionGroup] of Object.entries(positionsByTickerAndExpiry)) {
    const [ticker, expiration] = key.split('|');
    
    try {
      const options = await optionsApi.getOptionsForExpiration(ticker, expiration);
      
      // Match options to positions
      positionGroup.forEach(position => {
        const matchingOption = options.find(option => 
          option.strike === position.strike && 
          option.optionType.toLowerCase() === position.type.toLowerCase()
        );
        
        if (matchingOption) {
          results[position.id] = matchingOption;
        }
      });
    } catch (error) {
      console.error(`Failed to fetch options for ${ticker} expiring ${expiration}:`, error);
    }
  }
  
  return results;
};
```

2. Integrate with the "Force Recalculate" functionality:
   - Update the recalculation handler to fetch fresh option prices
   - Apply the fetched prices to positions before calculating P&L

### 5. Update Position Store with Mark Price Handling

1. Enhance the position store to update mark prices during recalculation:
```typescript
// In positionStore.ts - recalculateAllGreeks function
recalculateAllGreeks: async (forceRecalculate = false) => {
  // Existing code...
  
  // If force recalculating, fetch fresh option prices
  if (forceRecalculate) {
    try {
      const optionPrices = await fetchOptionPricesForPositions(positions);
      
      // Update positions with fresh option prices
      set(state => {
        const updatedPositions = state.positions.map(position => {
          const optionData = optionPrices[position.id];
          
          if (optionData) {
            // Calculate mark price
            const markPrice = calculateMarkPrice(optionData.bid, optionData.ask);
            
            // Only update mark price if not manually overridden
            if (!position.markPriceOverride) {
              return {
                ...position,
                markPrice,
                impliedVolatility: optionData.impliedVolatility
              };
            }
          }
          
          return position;
        });
        
        return { positions: updatedPositions };
      });
    } catch (error) {
      console.error('Failed to fetch option prices during recalculation:', error);
    }
  }
  
  // Continue with existing recalculation logic...
}
```

### 6. Handle Manual Mark Price Overrides

1. Implement the mark price override functionality:
```typescript
// In EditablePositionTable.tsx
const handleMarkPriceEdit = async (position: OptionPosition, newValue: number) => {
  try {
    // Update the position with the new mark price and set the override flag
    await updatePosition(position.id, {
      markPrice: newValue,
      markPriceOverride: true
    });
    
    // Recalculate P&L with the new mark price
    requestAnimationFrame(() => {
      try {
        recalculateAllPnL().catch(() => {
          // Silent catch - errors are already handled in the store
        });
      } catch {
        // Silent catch
      }
    });
    
    // Show success message
    setToastMessage({
      title: 'Mark price updated',
      status: 'success'
    });
    
    // Auto clear toast after 2 seconds
    setTimeout(() => setToastMessage(null), 2000);
  } catch (error) {
    console.error('Error updating mark price:', error);
    setToastMessage({
      title: 'Error updating mark price',
      status: 'error',
      message: error instanceof Error ? error.message : String(error)
    });
    
    // Auto clear toast after 5 seconds
    setTimeout(() => setToastMessage(null), 5000);
  }
};
```

2. Add a button to reset the mark price override:
```typescript
// In EditablePositionTable.tsx - renderPositionRow function
<td className="py-2 px-3">
  <div className="flex items-center">
    <EditableCell
      value={position.markPrice}
      isEditable={true}
      onEdit={(newValue) => handleMarkPriceEdit(position, newValue)}
      type="number"
      validator={(value) => value >= 0}
      formatter={(value) => value?.toFixed(2) || 'N/A'}
      isCalculating={isRecalculating}
      align="right"
    />
    {position.markPriceOverride && (
      <button
        onClick={() => handleResetMarkPrice(position)}
        className="ml-2 text-xs text-gray-500 hover:text-red-500"
        title="Reset to calculated mark price"
      >
        ↺
      </button>
    )}
  </div>
</td>
```

### 7. Update P&L Calculation to Use Mark Prices

1. Modify the P&L calculation logic to prioritize mark prices:
```typescript
// In positionStore.ts - calculateClientSidePnL function
const calculateClientSidePnL = (position: OptionPosition): PnLResult => {
  // Use mark price if available, otherwise fall back to premium
  const currentPrice = position.markPrice ?? position.premium ?? 0;
  const initialPrice = position.premium ?? 0;
  
  // Calculate P&L
  // ...existing calculation logic...
};
```

2. Update the theoretical P&L calculation to use mark prices as a starting point

## Testing Plan

1. Unit Tests:
   - Test mark price calculation with various bid/ask combinations
   - Test P&L calculations with different mark price scenarios
   - Test the override and reset functionality

2. Integration Tests:
   - Test the end-to-end flow of loading option prices and calculating P&L
   - Test the recalculation process with and without force recalculation

3. Manual Testing:
   - Verify mark price display and editing in the UI
   - Confirm P&L calculations match expected values
   - Test with real market data to ensure accuracy

## Implementation Sequence

1. Add the mark price field to the position interface and table
2. Implement mark price calculation logic
3. Add client-side P&L calculation as a fallback
4. Implement option price loading for existing positions
5. Add mark price override functionality
6. Update P&L calculations to use mark prices
7. Test and refine the implementation

## Future Enhancements

1. Implement backend P&L calculation endpoints
2. Add caching for option prices to improve performance
3. Enhance visualization of P&L data with charts or graphs
4. Add historical P&L tracking over time

## Implementation Progress (March 16, 2025)

### Completed Tasks ✅

1. **Mark Price Infrastructure**:
   - Created utility functions in `optionPriceUtils.ts` for calculating mark prices from bid/ask data
   - Added `markPrice` and `markPriceOverride` fields to the `OptionPosition` interface
   - Added mark price column to the editable position table
   - Implemented manual override and reset functionality

2. **Option Data Integration**:
   - Added `getOptionDataForPosition` function to the options API to fetch option data for a specific position
   - Implemented `updatePositionMarkPrice` and `fetchAndUpdateMarkPrice` functions in the position store
   - Integrated mark price calculation with the Greeks calculation flow
   - Added fallback handling for missing bid/ask data

### In Progress 🔄

1. **API Integration**:
   - Need to fix export issues in the options API
   - Need to implement batch fetching of option data for multiple positions

### Remaining Tasks 📋

1. **P&L Calculation Updates**:
   - Update P&L calculation logic to use mark prices
   - Implement client-side fallback calculations
   - Handle edge cases for missing data

2. **UI Enhancements**:
   - Add P&L columns to the table
   - Implement formatting and visual indicators
   - Add tooltips and user guidance

3. **Testing and Validation**:
   - Create unit tests
   - Test with various scenarios
   - Validate calculations

### Next Steps

1. Fix the export issues with the options API
2. Implement batch fetching of option data for multiple positions
3. Update P&L calculation logic to use mark prices
4. Add P&L columns to the editable position table
5. Implement client-side fallback calculations

### Updated Timeline

- Mark Price Column and Calculation Logic (2 days) ✅
- P&L Calculation Updates (2 days) 🔄
- UI Enhancements (1 day) 📋
- Client-Side Fallback (1 day) 📋
- Testing and Bug Fixes (1 day) 📋

Current progress: ~35% complete
