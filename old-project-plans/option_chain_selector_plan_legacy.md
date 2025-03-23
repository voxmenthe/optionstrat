# Option Chain Selector Implementation Plan

## Current Implementation Status

### ✅ Completed Elements

#### Backend
1. **Core Infrastructure**
   - Created `OptionChainService` class in `/src/backend/app/services/option_chain_service.py`
   - Implemented API endpoints in `/src/backend/app/routes/options.py`
   - Integrated market data providers (Polygon, YFinance)
   - Implemented basic caching layer
   - Added provider abstraction with MarketDataService

2. **API Endpoints**
   - `GET /options/chains/{ticker}` - Get options chain for a ticker
   - `GET /options/chains/{ticker}/expirations` - Get available expiration dates
   - `GET /options/chains/{ticker}/{expiration_date}` - Get options for specific expiration
   - `GET /options/search/{query}` - Search for ticker symbols
   
3. **Data Models**
   - Updated schemas in `schemas.py` for option contracts and expirations
   
4. **Testing**
   - Created unit tests for OptionChainService in `test_option_chain_service.py`
   - Created API endpoint tests in `test_option_api_endpoints.py`

#### Frontend
1. **API Client**
   - Created options API client in `/src/frontend/lib/api/optionsApi.ts`
   - Implemented data conversion functions for backend to frontend models

### ⏳ Partially Implemented

#### 1. **Frontend Integration**

##### Current Market Data API Functionality
- `marketDataApi.ts` currently implements basic option chain fetching via:
  - `getOptionChain(ticker, expiration)` method that retrieves option data
  - Data model `OptionChainItem` for storing option contract information
  - Basic error handling and data formatting
- The implementation relies on `/market-data/option-chain/` endpoints rather than the new `/options/chains/` endpoints
- Response transformation is minimal with no specialized handling for greeks or implied volatility

##### Required Refactoring for New Options API
- Update API method signatures to match the new options API response structure
- Replace direct `/market-data/` endpoint calls with corresponding `/options/chains/` endpoints:
  - `/market-data/option-chain/{ticker}` → `/options/chains/{ticker}`
  - Add support for new filtering parameters (min_strike, max_strike, option_type)
- Ensure proper error handling for rate limits and market data provider fallbacks
- Implement data caching strategy at frontend level to reduce redundant API calls
- Add comprehensive typing for all API response structures

##### Current Option Chain Display
- Basic tabular display exists in `market-data/page.tsx` showing:
  - Strike prices
  - Basic option details (bid/ask/last)
  - No column sorting or advanced filtering
- The display lacks:
  - Proper pagination for large option chains
  - Visual indicators for in-the-money vs out-of-the-money options
  - Highlighting of selected options
  - Greek value displays (delta, gamma, theta, vega)
  - IV visualization

##### Integration Requirements
- The current display needs to be converted into a reusable component
- Selection functionality needs to be added to pass data to position creation
- State synchronization between option selection and position form
- Event handling for selection changes

### ❌ Not Started / Missing

#### 1. **Frontend Components**

##### Dedicated `OptionChainSelector` Component
- **Core functionality**:
  - Unified component integrating ticker search, expiration selection, and chain display
  - Selection state management with highlighting of selected options
  - Filter controls for strike range and option types
  - Pagination controls for large option chains
  
- **Implementation requirements**:
  - Create new file `components/OptionChainSelector.tsx`
  - Component props interface:
    ```typescript
    interface OptionChainSelectorProps {
      onSelect: (option: OptionContract) => void;
      initialTicker?: string;
      showGreeks?: boolean;
      compact?: boolean;
    }
    ```
  - Internal state management for local UI state:
    ```typescript
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedOption, setSelectedOption] = useState<OptionContract | null>(null);
    const [viewMode, setViewMode] = useState<'table' | 'grid'>('table');
    ```
  - Connection to global option chain store via hooks
  - Selection handling and propagation to parent components
  - Accessibility features including keyboard navigation

##### `OptionExpirationSelector` Component
- **Core functionality**:
  - Display available expiration dates for a selected ticker
  - Group by monthly/weekly expiration cycles
  - Highlight current and nearest expirations
  - Show days-to-expiration (DTE) information
  
- **Implementation requirements**:
  - Create new file `components/OptionExpirationSelector.tsx`
  - Component props interface:
    ```typescript
    interface OptionExpirationSelectorProps {
      ticker: string;
      selectedExpiration: string | null;
      onSelect: (expirationDate: string) => void;
      showDTE?: boolean;
      maxVisible?: number;
    }
    ```
  - Fetch and display expirations when ticker changes
  - Group expirations by month with collapsible UI
  - Calculate and display DTE information
  - Handle loading and error states

##### `OptionStrikeFilter` Component
- **Core functionality**:
  - Control for setting min/max strike range
  - Quick selections for common ranges (e.g., ±10% from underlying)
  - Display current underlying price as reference
  - Support both absolute and percentage-based ranges
  
- **Implementation requirements**:
  - Create new file `components/OptionStrikeFilter.tsx`
  - Component props interface:
    ```typescript
    interface OptionStrikeFilterProps {
      underlyingPrice: number;
      minStrike: number | null;
      maxStrike: number | null;
      onChange: (minStrike: number | null, maxStrike: number | null) => void;
      allowPercentMode?: boolean;
    }
    ```
  - Implement dual-thumb slider for strike range selection
  - Add quick selection buttons for common ranges
  - Toggle between absolute and percentage modes
  - Validate input to ensure min ≤ max

##### Option Type Toggle Component
- **Core functionality**:
  - Toggle between calls, puts, or both
  - Visual indicators for current selection
  - Optionally show call/put statistics (volume, OI)
  
- **Implementation requirements**:
  - Create new file `components/OptionTypeToggle.tsx`
  - Component props interface:
    ```typescript
    interface OptionTypeToggleProps {
      value: 'calls' | 'puts' | 'both';
      onChange: (value: 'calls' | 'puts' | 'both') => void;
      showStatistics?: boolean;
      statistics?: {
        callVolume?: number;
        putVolume?: number;
        callOI?: number;
        putOI?: number;
      };
    }
    ```
  - Implement styled radio button or tab-like interface
  - Add optional call/put ratio display
  - Connect to parent filter state

#### 2. **Frontend State Management**

##### Dedicated Option Chain Store Requirements
- **Core state elements**:
  - Current ticker symbol
  - Available expiration dates
  - Selected expiration date
  - Option chain data (calls and puts)
  - Current filters (strike range, option type, etc.)
  - Loading/error states
  - Selected option contract

- **Action implementations needed**:
  - `setTicker(ticker: string)`: Change current ticker and fetch expirations
  - `setExpiration(date: string)`: Set expiration date and fetch option chain
  - `setFilters(filters: OptionFilters)`: Update filtering parameters
  - `selectOption(option: OptionContract | null)`: Set selected option
  - `refreshData()`: Force refresh of current data
  - `clear()`: Reset store to initial state

- **Store persistence requirements**:
  - Implement session storage persistence for faster return visits
  - Cache expiration strategy based on market hours
  - Invalidation logic for stale data

- **Performance considerations**:
  - Memoization of filtered option chains
  - Pagination state for large option chains
  - Background refresh for real-time updates

#### 3. **Position Creation Integration**

##### Option Selection to Position Form Integration
- **Requirements**:
  - Add toggle in `PositionForm.tsx` to switch between manual and chain selection
  - Map selected option properties to form fields
  - Handle special cases (e.g., mid-price calculation)
  - Live update of form values as selection changes

- **Implementation details**:
  - Create wrapper component `PositionFormWithOptionChain.tsx`
  - Add UI toggle with tabbed interface or radio buttons
  - Implement selection handler:
    ```typescript
    const handleOptionSelect = (option: OptionContract) => {
      setPosition({
        ...position,
        ticker: option.ticker,
        expiration: new Date(option.expiration).toISOString().split('T')[0],
        strike: option.strike,
        type: option.optionType,
        premium: calculateMidPrice(option), // Helper function to calculate mid price
        impliedVolatility: option.impliedVolatility || null,
      });
      
      // Potentially fetch additional data like greeks
      if (option.impliedVolatility) {
        updateGreeks(option);
      }
    };
    ```
  - Add bidirectional synchronization between form and selector
  - Reset logic when switching between modes

##### UI Toggle for Selection Mode
- **Requirements**:
  - Clear visual distinction between manual entry and option chain modes
  - Smooth transition between modes
  - Retention of previously entered data when switching modes
  - Warning dialog for unsaved changes

- **Implementation details**:
  - Add toggle component at top of form
  - Implement conditional rendering:
    ```tsx
    {useOptionChain ? (
      <OptionChainSelector 
        onSelect={handleOptionSelect}
        initialTicker={position.ticker || undefined}
      />
    ) : (
      <ManualEntryFields 
        position={position}
        onChange={handlePositionChange}
        errors={errors}
      />
    )}
    ```
  - Add animation for smooth transition
  - Implement state preservation when switching modes

#### 4. **Advanced Features**

##### IV Range and Liquidity Filtering
- **Requirements**:
  - Add filters for implied volatility ranges
  - Add minimum volume and open interest thresholds
  - Visualize IV skew across strikes
  - Add historical IV percentile indicators

- **Implementation details**:
  - Create `IVRangeFilter` component with min/max inputs
  - Implement visual IV skew graph component
  - Add liquidity indicator with configurable thresholds
  - Create percentile calculation helper functions

##### Real-time Chain Updates
- **Requirements**:
  - Implement polling or WebSocket connection for live updates
  - Add user toggle for enabling/disabling live updates
  - Visual indicators for price changes
  - Configurable update frequency

- **Implementation details**:
  - Create update service with configurable intervals
  - Add visual price change indicators (up/down arrows with colors)
  - Implement throttling to prevent UI freezing
  - Add user preferences for update behavior

## Gap Analysis

1. **Backend Implementation**
   - ✅ The `OptionChainService` is fully implemented with caching and provider integration
   - ✅ API endpoints for option chains are implemented
   - ⚠️ Missing batch refresh logic for multiple chains

2. **Frontend Architecture**
   - ⚠️ Duplicate functionality between marketDataApi and optionsApi
   - ❌ Missing dedicated option chain selector component
   - ❌ No integration with position creation workflow

3. **UX/UI**
   - ❌ No dedicated interface for option selection in position creation
   - ⚠️ Basic chain display exists in market-data page but not reusable

## Revised Implementation Roadmap

### 1. Frontend State Management (1 day)
- [ ] Create dedicated `optionChainStore.ts` using Zustand
- [ ] Refactor to use the options API instead of marketDataApi
- [ ] Add state management for expiration/strike filtering

### 2. UI Components (2 days)
- [ ] Create `OptionChainSelector.tsx` component
- [ ] Create `OptionExpirationSelector.tsx` component
- [ ] Create `OptionChainTable.tsx` for displaying option chain data
- [ ] Implement strike price and option type filtering

### 3. Position Creation Integration (1 day)
- [ ] Update `PositionForm.tsx` to include option chain selector
- [ ] Add toggle to switch between manual entry and option chain selection
- [ ] Connect selected option data to position form fields

### 4. Advanced Features (2 days)
- [ ] Implement advanced filtering (IV range, volume, etc.)
- [ ] Add visualization for option data (price/IV charts)
- [ ] Implement real-time updates for option chains

### 5. Testing and Refinement (1 day)
- [ ] Create frontend component tests
- [ ] Performance optimizations for large option chains
- [ ] Edge case handling

## Component Specifications

### Backend Components

#### Option Chain Service
```python
# Already implemented in option_chain_service.py
```

#### API Endpoints
```python
# Already implemented in options.py
```

### Frontend Components

#### Option Chain Store
```typescript
// lib/stores/optionChainStore.ts (TO BE CREATED)
import create from 'zustand';
import { optionsApi, OptionContract, OptionExpiration } from '../api/optionsApi';

interface OptionChainState {
  ticker: string;
  expirations: OptionExpiration[];
  selectedExpiration: string | null;
  chain: OptionContract[];
  isLoading: boolean;
  error: string | null;
  filters: {
    optionType: 'all' | 'call' | 'put';
    minStrike: number | null;
    maxStrike: number | null;
    minIV: number | null;
    maxIV: number | null;
  };
  
  // Actions
  setTicker: (ticker: string) => Promise<void>;
  setSelectedExpiration: (date: string) => Promise<void>;
  setFilter: (filter: Partial<OptionChainState['filters']>) => void;
  refreshChain: () => Promise<void>;
  clear: () => void;
}

export const useOptionChainStore = create<OptionChainState>((set, get) => ({
  // State and actions implementation
}));
```

#### Option Chain Selector Component
```tsx
// components/OptionChainSelector.tsx (TO BE CREATED)
import React, { useState, useEffect } from 'react';
import { useOptionChainStore } from '../lib/stores/optionChainStore';
import { OptionContract } from '../lib/api/optionsApi';

interface OptionChainSelectorProps {
  onSelect: (option: OptionContract) => void;
}

export default function OptionChainSelector({ onSelect }: OptionChainSelectorProps) {
  const [ticker, setTicker] = useState('');
  const { 
    setTicker: storeSetTicker,
    expirations,
    selectedExpiration,
    setSelectedExpiration,
    chain,
    filters,
    setFilter,
    isLoading
  } = useOptionChainStore();
  
  // Component implementation
}
```

#### Position Form Integration
```tsx
// components/PositionForm.tsx (TO BE UPDATED)
// Add toggle for option chain selector
const [useOptionChain, setUseOptionChain] = useState(false);

// Add option selection handler
const handleOptionSelect = (option: OptionContract) => {
  setPosition({
    ...position,
    ticker: option.ticker,
    expiration: new Date(option.expiration).toISOString().split('T')[0],
    strike: option.strike,
    type: option.optionType,
    premium: (option.bid + option.ask) / 2,
  });
};

// Update form to include option chain toggle
<div className="form-control">
  <label className="cursor-pointer label">
    <span className="label-text">Use Option Chain</span>
    <input
      type="checkbox"
      checked={useOptionChain}
      onChange={(e) => setUseOptionChain(e.target.checked)}
      className="toggle toggle-primary"
    />
  </label>
</div>

{useOptionChain ? (
  <OptionChainSelector onSelect={handleOptionSelect} />
) : (
  /* Existing form fields */
)}
```

## Design Considerations

1. **User Flow**
   - User enters a ticker symbol
   - Frontend fetches available expiration dates
   - User selects an expiration date
   - Option chain is displayed with filtering options
   - User selects an option, which populates the position form
   - Position is created with accurate market data

2. **Performance Optimizations**
   - Backend caching for option chains (implemented)
   - Pagination for large option chains
   - Filtering on the client side to reduce API calls
   - Debouncing ticker input to reduce API calls

3. **Error Handling**
   - Graceful fallback when market data is unavailable
   - Clear user feedback for loading states
   - Rate limit handling for market data providers

## Future Enhancements

1. **Historical Option Data**
   - Allow viewing options based on historical data
   
2. **Option Screener**
   - Advanced filtering based on Greeks, IV percentile, etc.
   
3. **Strategy Builder**
   - Pre-built templates for common option strategies
   - Drag and drop interface for building custom strategies


## Success Metrics

1. **Data Accuracy** - Reduction in positions with default IV values
2. **User Experience** - Time spent creating positions
3. **Performance** - Response time for option chain retrieval

