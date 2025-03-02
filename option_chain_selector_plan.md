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

1. **Frontend Integration**
   - Market data API functionality exists but needs to be refactored to use the new options API
   - Basic option chain display exists in market-data page but not integrated with position creation

### ❌ Not Started / Missing

1. **Frontend Components**
   - Dedicated `OptionChainSelector` component
   - `OptionExpirationSelector` component
   - `OptionStrikeFilter` component
   - Option type toggle (calls/puts)
   
2. **Frontend State Management**
   - Dedicated option chain store (currently using marketDataStore)
   
3. **Position Creation Integration**
   - No integration between option chain selection and position creation
   - No UI toggle to switch between manual entry and option chain selection
   
4. **Advanced Features**
   - Advanced filtering by IV ranges, liquidity thresholds
   - Visualization of option chain data (IV skew, etc.)
   - Real-time updates

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
