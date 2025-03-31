# PUT Option Visualization Fix: PUT-Specific Vega Calculation Issues

## Problem Statement
The PUT option visualization is not displaying correctly and produces a flat line instead of the characteristic "hockey stick" shape expected. The key insight is that this issue only occurs with PUT options, not with CALL options.

## Root Causes Identified

Based on thorough investigation, we've discovered:

1. **PUT-Specific Vega Calculation Issues**: The "vega not provided" error only occurs for PUT options, suggesting there's something specific about how QuantLib calculates vega for PUTs that's causing issues.

2. **Extremely Small Vega Values**: The logs show vega values from QuantLib for PUT options are sometimes extremely small (e.g., 6.36e-25), essentially zero, which may trigger validation errors.

3. **Price Range Impact**: PUT options cover different price ranges than CALL options, and the vega calculation is more sensitive in certain regions of the price curve.

## Implementation Plan

### Phase 1: Special Handling for PUT Options in Backend
1. **Enhanced PUT Option Detection and Handling**:
   - Add PUT-specific vega handling in the option_pricing.py file
   - Use more appropriate minimum vega thresholds for PUT options specifically
   ```python
   # In OptionPricer.price_option method
   if option_type == "put":
       # Special threshold for PUT options - they might have extremely small vega values
       min_vega_threshold = 1e-4  # Use a larger threshold for PUT options
   else:
       min_vega_threshold = 1e-10  # Keep the smaller threshold for CALL options
       
   if abs(raw_vega) < min_vega_threshold:
       print(f"Small vega detected for {option_type.upper()}: {raw_vega}. Using minimum threshold.")
       raw_vega = min_vega_threshold if raw_vega >= 0 else -min_vega_threshold
   ```

2. **Add PUT-Specific Volatility Range**:
   - Add special volatility validation for PUT options, which have different sensitivity
   - Ensure volatility is always within a reliable range for PUT option calculations
   ```python
   # In scenarios.py
   # For PUT options, ensure volatility is high enough to allow valid vega calculation
   if positions[0].option_type == "put" and volatility < 0.1:
       volatility = 0.1  # Minimum volatility for PUT options
       print(f"WARNING: Increased volatility to minimum threshold of 0.1 for PUT option")
   ```

### Phase 2: Enhanced Frontend PUT Option Handling
1. **Separate PUT Logic in scenariosStore**:
   ```typescript
   // Enhanced logic for PUT option analysis
   if (isPut) {
     // For PUT options, we need to ensure reliable volatility
     console.log("Processing PUT option - using enhanced volatility handling");
     
     // Stronger validation for PUT options
     const PUT_MIN_VOLATILITY = 0.1; // Higher minimum for PUTs
     
     if (volatilityToSend < PUT_MIN_VOLATILITY) {
       console.log(`Increasing volatility for PUT option from ${volatilityToSend} to ${PUT_MIN_VOLATILITY}`);
       volatilityToSend = PUT_MIN_VOLATILITY;
     }
     
     // Add PUT-specific request parameters
     requestParams = {
       ...requestParams,
       option_type: "put", // Explicitly tell backend this is a PUT
       put_specific_handling: true // Flag for backend to use PUT-specific logic
     };
   }
   ```

2. **Improved PUT Fallback Data Generation**:
   - Refine the client-side fallback data generation for PUT options
   - Create more points around the strike price where PUT option behavior changes significantly

### Phase 3: Fix Visualization Components for PUT Options
1. **Update PayoffDiagram Component**:
   - Add special rendering logic for PUT options
   - Use linear interpolation for PUT option data points instead of smooth curves
   - Focus the visualization range appropriately for PUT options

```javascript
// In PayoffDiagram.tsx
if (isPut) {
  // Special handling for PUT option display
  chartConfig.displayModeBar = false; // Disable zoom/pan for PUT view
  chartConfig.staticPlot = true; // Make static for better PUT rendering
  
  // Force proper y-axis range for PUT payoff
  const maxLoss = Math.abs(Math.min(...values));
  layout.yaxis.range = [-maxLoss * 1.1, maxValue * 1.1];
  
  // Use different line style for PUT
  traces[0].line.shape = 'linear';
  traces[0].line.color = '#ff4d4f'; // Red for PUT
}
```

### Phase 4: Add PUT-Specific Debugging
1. **Add PUT Option Diagnostics**:
   - Add special logging when dealing with PUT options
   - Log the complete price and payoff curves to help diagnose rendering issues

```typescript
// PUT-specific debugging info
if (isPut) {
  console.log("PUT option details:", {
    strike,
    premium,
    volatility: volatilityToSend,
    payoffCurve: {
      belowStrike: prices.filter(p => p < strike).length,
      pointsAtStrike: prices.filter(p => Math.abs(p - strike) < 0.001).length,
      aboveStrike: prices.filter(p => p > strike).length
    }
  });
}
```

## Implementation Sequence
1. Phase 1: Implement backend fixes for PUT-specific vega handling
2. Phase 2: Update frontend to handle PUT options specially
3. Phase 3: Fix visualization components for PUT options
4. Phase 4: Add PUT-specific debugging and diagnostic tools

## Testing Approach
1. **PUT-Focused Testing:**
   - Test with a variety of PUT options at different strikes and premiums
   - Verify that both long and short PUT positions render correctly
   - Compare against known correct PUT payoff shapes
   
2. **Comparative Testing:**
   - Test both PUT and CALL options to ensure both work correctly
   - Verify that the special handling for PUTs doesn't negatively impact CALLs

3. **Edge Case Testing:**
   - Test with very low and very high strike prices
   - Test with extreme volatility values
   - Test with expiration dates at different ranges

## Timeline
1. **Day 1**: Implement the enhanced Phase 1 fixes for backend communication
   - Implement robust volatility validation that matches the position API's reliable approach
   - Add detailed logging before/after each validation step
   - Test with PUT options to verify the "vega not provided" error is resolved
   - Monitor backend logs to ensure volatility values are in the correct format

2. **Day 2-3**: Proceed with Phases 3 & 4 for visualization components
   - Implement the visualization fixes for proper PUT option rendering
   - Test with different strike prices and expiry dates

3. **Day 4**: Complete Phase 2 for data generation improvements
   - Enhance the fallback data mechanism for cases where API fails
   - Test with offline scenarios to verify fallback works correctly

4. **Day 5**: Add Phase 5 debug support and finalize testing
   - Add comprehensive logging for debugging future issues
   - Perform final validation with various PUT option scenarios

## Success Criteria
1. PUT options display with proper "hockey stick" shape 
2. No visual artifacts appear on chart edges
3. ⚠️ The backend no longer returns "vega error" messages - PARTIALLY FIXED, NEEDS FURTHER INVESTIGATION
4. Both API-based and fallback data generation produce correct visualizations

## Additional Backend Investigation Plan
1. **Compare API Differences**:
   - Compare successful position API calls vs. failing scenario API calls
   - Check parameter differences in backend controller code
   
2. **Trace Vega Calculation**:
   - Identify where vega calculation happens in the backend
   - Determine what parameters feed into the vega calculation
   
3. **Investigate QuantLib Dependencies**:
   - The logs show QuantLib is used for option calculations
   - Review QuantLib requirements for complete option pricing

4. **Test Incremental Parameters**:
   - Start with current implementation and add parameters incrementally
   - Test specific combinations to isolate the missing parameter

## Testing Approach
1. Create test cases with different strike prices and premium values
2. Test both long and short PUT positions
3. Verify visualization with both API data and fallback data
4. Test with extreme values (very high/low strikes, premiums)

## Backend API Investigation Results

### True Root Cause Identified

After examining the backend code thoroughly, I've identified the most likely root cause of the "vega not provided" error:

1. **Implied Volatility Retrieval Failure**:
   ```python
   # In market_data.py - base implementation
   def get_implied_volatility(self, ticker: str) -> float:
       """Get the implied volatility for a ticker."""
       # This is a placeholder - in a real implementation, you would calculate IV
       # from ATM options or use a volatility index
       return 0.3  # 30% as a default
   ```

   ```python
   # In yfinance_provider.py - tries to calculate real IV but has fallbacks
   def get_implied_volatility(self, ticker: str) -> float:
       try:
           # Get the nearest expiration option chain
           options = self.get_option_chain(ticker)
           
           # Calculate the average implied volatility from the options
           if options:
               total_iv = 0.0
               count = 0
               
               for option in options:
                   iv = option.get("implied_volatility", None)
                   if iv is not None and iv > 0:
                       total_iv += iv
                       count += 1
               
               if count > 0:
                   avg_iv = total_iv / count
                   return avg_iv
           
           # If no options found or no valid IV, return a default
           return 0.3  # 30% as a default
       except Exception as e:
           return 0.3  # 30% as a default
   ```

2. **The Key Difference**: 
   - In **position loading**, the system directly uses a hardcoded volatility value: `volatility=0.3` 
   - In **scenario calculation**, it tries to get the implied volatility from market data first:
     ```python
     # In scenarios.py
     current_vol = market_data_service.get_implied_volatility(ticker)
     volatility = request.base_volatility if request.base_volatility is not None else current_vol
     ```

3. **The Error Chain**:
   - When `base_volatility` is not provided in the request
   - The code falls back to `current_vol` from `market_data_service.get_implied_volatility(ticker)`
   - For some tickers or in some market conditions, this returns a value that causes QuantLib's vega calculation to fail
   - This could be due to an invalid volatility format, a zero/negative value, or another edge case

### Complete Solution Approach

The fix needs to ensure proper volatility values under all circumstances:

1. **Ensure Volatility Validation**:
   - Always validate that volatility is a valid positive number between reasonable bounds (e.g., 0.01 to 2.0)
   - Add a robust fallback chain that never allows invalid volatility values to reach QuantLib

2. **Fix Volatility Format**:
   - Ensure volatility is always in decimal form (e.g., 0.3 for 30%) in the correct range for QuantLib
   - Add conversion for percentage formats (>1) to decimal format

3. **Extended Logging**:
   - Add detailed logging around the volatility value that's actually being used
   - This will help diagnose if the issue is related to specific volatility values or formats

4. **Ensure Same Behavior as Position API**:
   - Make the scenario API use the same volatility handling approach that works reliably for the position API
