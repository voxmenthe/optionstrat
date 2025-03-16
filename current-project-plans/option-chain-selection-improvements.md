# Option Chain Selection Improvements Plan

## Overview

This plan outlines the implementation of several enhancements to the option chain selection functionality:

1. **Center strikes around underlying price**: When an expiry date is selected, the page should initially display strikes centered around the underlying's current price.
2. **Highlight nearest strikes**: Rows for strikes nearest to the underlying price should be highlighted with a different color.
3. **Reduce selection clicks**: Enable users to enter a ticker and hit enter to load an options chain.
4. **Default expiry selection**: Implement a default number of days to expiry for faster option selection.

## Current Implementation Analysis

The current implementation has the following components:

- **OptionChainSelector**: Main component for selecting options, with ticker search and expiration date selection.
- **OptionChainTable**: Displays option chain data in a tabular format with calls on the left, puts on the right, and strikes in the middle.
- **optionChainStore**: Zustand store that manages the state for option chains, expirations, and selection.

The current implementation already has:
- Basic highlighting for strikes close to the underlying price (line 268-272 in OptionChainTable.tsx)
- Pagination for navigating through strikes
- Ticker search functionality

However, it lacks:
- Auto-centering the display on strikes near the underlying price
- Enter key support for ticker search
- Default expiry date selection
- Consistent and visually prominent highlighting of strikes near the underlying

## Implementation Plan

### 1. Retrieve and Use Underlying Price (2 days)

#### Backend Changes
1. **Update Option Chain API Endpoint**:
   - Modify `/options/chains/{ticker}/{expiration_date}` endpoint to include the underlying price in the response.
   - Add a new field `underlyingPrice` to the response schema.

#### Frontend Changes
1. **Update OptionContract Interface**:
   - Add `underlyingPrice` to the store state in `optionChainStore.ts`.
   ```typescript
   interface OptionChainState {
     // Existing fields...
     underlyingPrice: number | null;
     // Other fields...
   }
   ```

2. **Update API Response Handling**:
   - Modify the `getOptionsForExpiration` function in `optionsApi.ts` to extract and return the underlying price.
   - Update the store to save this value when option chain data is loaded.

### 2. Center Strikes Around Underlying Price (2 days)

1. **Modify Pagination Logic in OptionChainTable**:
   ```typescript
   // Calculate the initial page to show based on underlying price
   const calculateInitialPage = (strikes: number[], underlyingPrice: number | null, pageSize: number): number => {
     if (!underlyingPrice || strikes.length === 0) return 1;
     
     // Find the index of the strike closest to the underlying price
     const closestStrikeIndex = strikes.reduce((closest, strike, index) => {
       const currentDiff = Math.abs(strike - underlyingPrice);
       const closestDiff = Math.abs(strikes[closest] - underlyingPrice);
       return currentDiff < closestDiff ? index : closest;
     }, 0);
     
     // Calculate which page this strike should be on
     return Math.floor(closestStrikeIndex / pageSize) + 1;
   };
   ```

2. **Update OptionChainTable Component**:
   - Initialize the current page based on the underlying price when the component mounts or when the underlying price changes.
   ```typescript
   useEffect(() => {
     if (underlyingPrice && strikes.length > 0) {
       const initialPage = calculateInitialPage(strikes, underlyingPrice, pageSize);
       setCurrentPage(initialPage);
     }
   }, [underlyingPrice, strikes, pageSize]);
   ```

### 3. Enhance Strike Highlighting (1 day)

1. **Improve Strike Highlighting in OptionChainTable**:
   - Create a more sophisticated highlighting system that uses color gradients based on proximity to the underlying price.
   ```typescript
   const getStrikeHighlightClass = (strike: number, underlyingPrice: number | null): string => {
     if (!underlyingPrice) return '';
     
     const diff = Math.abs(strike - underlyingPrice);
     const percentDiff = (diff / underlyingPrice) * 100;
     
     if (percentDiff < 0.5) return 'bg-yellow-200'; // Very close
     if (percentDiff < 1.0) return 'bg-yellow-100'; // Close
     if (percentDiff < 2.0) return 'bg-yellow-50';  // Somewhat close
     
     return '';
   };
   ```

2. **Apply Enhanced Highlighting**:
   - Update the strike cell rendering to use the new highlighting function.
   ```tsx
   <td className={`px-2 py-2 text-center font-medium ${
     getStrikeHighlightClass(strike, underlyingPrice)
   }`}>
     {strike.toFixed(2)}
   </td>
   ```

### 4. Implement Enter Key Support for Ticker Search (1 day)

1. **Update Search Input in OptionChainSelector**:
   - Add form handling to support Enter key submission.
   ```tsx
   const handleSearchSubmit = (e: React.FormEvent) => {
     e.preventDefault();
     if (searchQuery.trim()) {
       handleTickerSelect(searchQuery.trim());
     }
   };
   
   // In the render function:
   <form onSubmit={handleSearchSubmit}>
     <input
       type="text"
       value={searchQuery}
       onChange={handleSearchChange}
       placeholder="Search ticker symbol..."
       className="search-input"
       onClick={() => searchQuery.trim() && setShowResults(true)}
     />
   </form>
   ```

### 5. Implement Default Days to Expiry Selection (2 days)

1. **Add Configuration Options to OptionChainStore**:
   ```typescript
   interface OptionChainConfig {
     defaultDaysToExpiry: number;
     showGreeks: boolean;
     strikesPerPage: number;
   }
   
   // Add to state
   config: OptionChainConfig;
   
   // Add action
   setConfig: (config: Partial<OptionChainConfig>) => void;
   ```

2. **Update Expiration Selection Logic**:
   ```typescript
   // When loading expirations
   if (expirations.length > 0) {
     const defaultExpiry = expirations.find(exp => 
       exp.daysToExpiration >= get().config.defaultDaysToExpiry
     ) || expirations[0];
     
     logger.info('Auto-selecting expiration based on default days setting', { 
       defaultDays: get().config.defaultDaysToExpiry,
       selectedExpiry: defaultExpiry.date 
     });
     
     get().setSelectedExpiration(defaultExpiry.date);
   }
   ```

3. **Add UI Controls for Default Days Setting**:
   - Create a settings dropdown in the OptionChainSelector component to allow users to change the default days to expiry. 
   ```tsx
   <div className="settings-dropdown">
     <label htmlFor="defaultDays">Default Days to Expiry:</label>
     <select 
       id="defaultDays"
       value={config.defaultDaysToExpiry}
       onChange={(e) => setConfig({ defaultDaysToExpiry: parseInt(e.target.value) })}
     >
       <option value="7">1 Week</option>
       <option value="14">2 Weeks</option>
       <option value="30">1 Month</option>
       <option value="60">2 Months</option>
       <option value="90">3 Months</option>
     </select>
   </div>
   ```

### 6. UI/UX Improvements (2 days)

1. **Add Visual Indicators for Loading States**:
   - Implement loading skeletons or spinners for better user feedback during data fetching.

2. **Improve Error Handling and User Feedback**:
   - Add more descriptive error messages and recovery options.

3. **Optimize Mobile Experience**:
   - Ensure the option chain is usable on smaller screens with responsive design improvements.

4. **Add Keyboard Navigation**:
   - Implement keyboard shortcuts for navigating through the option chain.

## Testing Plan - much later stage - ask for confirmation before implementing

1. **Unit Tests**:
   - Test the pagination calculation logic
   - Test the strike highlighting function
   - Test the default expiry selection logic

2. **Integration Tests**:
   - Test the complete flow from ticker search to option selection
   - Test with various market data scenarios (market open/closed)

3. **UI/UX Testing**:
   - Test the responsiveness of the UI
   - Test keyboard navigation
   - Test with different screen sizes

## Implementation Timeline

| Task | Duration | Dependencies |
|------|----------|--------------|
| Retrieve and Use Underlying Price | 2 days | None |
| Center Strikes Around Underlying Price | 2 days | Task 1 |
| Enhance Strike Highlighting | 1 day | Task 1 |
| Implement Enter Key Support | 1 day | None |
| Implement Default Days to Expiry | 2 days | None |
| UI/UX Improvements | 2 days | All previous tasks |
| Testing and Bug Fixes | 2 days | All previous tasks |

Total estimated time: **12 days**

## Success Criteria

1. When a user selects an expiry date, the option chain automatically displays strikes centered around the underlying price.
2. Strikes near the underlying price are clearly highlighted with a color gradient based on proximity.
3. Users can enter a ticker symbol and press Enter to load the option chain.
4. The system automatically selects an expiration date based on the configured default days to expiry.
5. The entire selection process requires fewer clicks than the current implementation.
6. The UI provides clear feedback during loading states and errors.
