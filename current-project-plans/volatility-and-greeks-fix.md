# Backend Volatility and Greeks Calculation Fix Plan

## Problem Statement
While the option price (NPV) calculation and basic visualization are now working, the backend has two significant remaining issues:

1.  **Incorrect Volatility:** The scenario analysis frequently falls back to using a hardcoded default volatility (0.3 or 30%) instead of fetching and using real market implied volatility (IV) data. This makes the scenario results less accurate.
2.  **Inaccurate Greeks:** The calculation of certain Greeks (specifically Vega and Rho, and potentially others intermittently) within the QuantLib pricing engine frequently fails, causing them to default to 0 or a small placeholder value. This limits the usefulness of the scenario analysis for risk management.

## Root Causes Identified

1.  **Volatility Fallback Logic:** The `analyze_price_scenario` function in `scenarios.py` tries to fetch `current_vol` using `market_data_service.get_implied_volatility(ticker)`. However, the base `MarketDataService` and the `YFinanceProvider` implementations for `get_implied_volatility` are placeholders or have simple fallbacks that often return the default 0.3. There's no robust calculation based on actual option market prices.
2.  **Pricing Engine Limitations/Parameters:** The `FdBlackScholesVanillaEngine` currently used, while fixing the price calculation, still struggles to reliably calculate all Greeks (Vega, Rho) for American options under certain conditions (e.g., far from the money, close to expiration). This might be due to the chosen grid parameters (`timeSteps`, `gridPoints`) or inherent limitations of the engine for specific Greeks.

## Implementation Plan

### Phase 1: Implement Robust Implied Volatility Calculation

1.  **Backend IV Calculation Service:**
    *   Modify `src/backend/app/services/market_data.py` (or potentially create a new `VolatilityService`).
    *   Implement a proper `get_implied_volatility(ticker)` method. This method should:
        *   Fetch the current option chain for the ticker (e.g., using `get_option_chain`).
        *   Identify near-the-money (ATM) options for a suitable near-term expiration.
        *   Fetch the current market price for these ATM options.
        *   Use the `option_pricer.calculate_implied_volatility` method (which uses QuantLib's solver) to calculate the IV for these options based on their market price.
        *   Average the IV from a few suitable ATM call and put options to get a representative `current_vol`.
        *   Implement caching for the calculated IV.
        *   Provide a *last resort* fallback (like 0.3) only if the entire calculation process fails, but log this clearly.
    ```python
    # Potential logic sketch in market_data_service.py or volatility_service.py
    def get_implied_volatility(self, ticker: str) -> float:
        # Check cache first...
        try:
            spot_price = self.get_stock_price(ticker)
            expirations = self.get_option_expirations(ticker)
            # Find nearest expiration (e.g., > 7 days away)
            # Fetch option chain for that expiration
            # Find ATM call/put options (strike closest to spot_price)
            # Get market prices for those ATM options (bid/ask midpoint or last price)
            
            iv_sum = 0.0
            count = 0
            for option in relevant_atm_options:
                 market_price = # Get market price
                 try:
                      iv = self.option_pricer.calculate_implied_volatility(
                          # ... pass option details, spot_price, market_price ...
                      )
                      if iv > 0.01 and iv < 2.0: # Basic validation
                           iv_sum += iv
                           count += 1
                 except Exception as iv_calc_error:
                      print(f"WARN: IV calculation failed for one option: {iv_calc_error}")

            if count > 0:
                 avg_iv = iv_sum / count
                 # Save to cache...
                 return avg_iv
            else:
                 print("WARN: Could not calculate average IV from market data. Using fallback.")
                 return 0.3 # Fallback
        except Exception as e:
            print(f"ERROR: Failed to get implied volatility for {ticker}: {e}. Using fallback.")
            return 0.3 # Fallback
    ```
2.  **Update Scenario Endpoint:**
    *   Ensure `src/backend/app/routes/scenarios.py` correctly uses the improved `get_implied_volatility` and logs warnings only when the *true fallback* is hit, not just when `base_volatility` isn't provided in the request. Remove the overly aggressive minimum volatility check for PUTs added previously if the IV calculation is now robust.

### Phase 2: Improve Greek Calculation Reliability

1.  **Experiment with Engine Parameters:**
    *   In `src/backend/app/services/option_pricing.py`, systematically vary the `timeSteps` and `gridPoints` for the `FdBlackScholesVanillaEngine` (e.g., try 100x100, 200x200, 100x500).
    *   Test if different parameter combinations improve the reliability of Vega and Rho calculations for American PUTs in the scenarios that previously failed.
2.  **Consider Alternative Engines (If Needed):**
    *   If adjusting FD parameters doesn't help, research and potentially implement alternative QuantLib engines specifically known for better Greek stability for American options, such as `ql.FdShoutEngine` or potentially custom implementations if available. This would be a fallback if parameter tuning fails.
3.  **Refine Greek Error Handling:**
    *   Review the `try...except` blocks for each Greek. Ensure the default values used (currently 0.0 or small placeholders) are appropriate or if `None` would be better for signaling calculation failure to the frontend/API consumer. For now, keep 0.0 but ensure logging is clear.

### Phase 3: Frontend Handling of Missing Greeks (Optional)

1.  **UI Indication:** Modify the frontend components that display Greeks to visually indicate when a value is defaulted (e.g., display "N/A" or "0\*") if the backend signals a calculation failure (potentially by returning `None` instead of `0.0` in the future, or based on the warning logs for now).

## Implementation Sequence

1.  Implement Phase 1: Robust IV calculation in the backend.
2.  Test Phase 1 thoroughly to ensure scenarios use market IV where possible.
3.  Implement Phase 2: Experiment with FD engine parameters to improve Greek reliability.
4.  Test Phase 2: Check if Vega/Rho warnings decrease and values become more accurate.
5.  Implement Phase 3 (Optional): Enhance frontend to indicate missing/defaulted Greeks.

## Success Criteria

1.  Backend logs show market-derived implied volatility being used in scenarios far more often than the hardcoded default.
2.  Backend logs show significantly fewer warnings about Vega and Rho calculations failing.
3.  Scenario analysis results include more accurate and consistently calculated Greeks. 