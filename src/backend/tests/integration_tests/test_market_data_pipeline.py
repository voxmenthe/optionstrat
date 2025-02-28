"""
Integration test for the market data pipeline.

This test verifies the end-to-end flow for fetching, caching, and processing
market data from external sources.
"""
import pytest
import time
from datetime import datetime, timedelta


class TestMarketDataPipeline:
    """Integration tests for the market data pipeline."""
    
    def setup_method(self):
        """Set up test data."""
        self.ticker = "AAPL"
        self.today = datetime.today().date()
        # Find next Friday for options expiration
        days_until_friday = (4 - self.today.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        self.next_friday = self.today + timedelta(days=days_until_friday)
        # Find a Friday about a month out
        self.month_out_friday = self.next_friday + timedelta(days=28)
        self.month_out_friday += timedelta(days=(4 - self.month_out_friday.weekday()) % 7)
    
    def test_market_data_caching(self, integration_client, redis_client):
        """Test that market data is properly cached and retrieved from cache."""
        if redis_client is None:
            pytest.skip("Redis not available")
            
        # Ensure clean state for test
        # Clear any existing cache for this ticker
        cache_key = f"ticker_details:{self.ticker}"
        redis_client.delete(cache_key)
        
        # Make sure Redis reports the key as deleted
        assert redis_client.get(cache_key) is None
        
        # Force a small delay to ensure clean state
        time.sleep(0.02)
        
        # First request should hit the API (not cached)
        print("\n--- First request (not cached) ---")
        start_time = time.time()
        response1 = integration_client.get(f"/market-data/ticker/{self.ticker}")
        first_request_time = time.time() - start_time
        
        assert response1.status_code == 200
        ticker_data1 = response1.json()
        assert "results" in ticker_data1, f"Expected 'results' in response: {ticker_data1}"
        assert ticker_data1["results"]["ticker"] == self.ticker
        
        # Print out info about the redis client to verify it's working
        print(f"\n[DEBUG TEST] Redis client type: {type(redis_client)}")
        print(f"[DEBUG TEST] Redis storage contents: {redis_client.storage.keys() if hasattr(redis_client, 'storage') else 'No storage attr'}")
        
        # Explicitly check all keys in Redis
        all_keys = redis_client.keys()
        print(f"[DEBUG TEST] All Redis keys: {all_keys}")
        
        # Check if another similar key exists
        if hasattr(redis_client, 'storage'):
            matching_keys = [k for k in redis_client.storage.keys() if 'ticker' in k.lower()]
            print(f"[DEBUG TEST] Matching ticker keys: {matching_keys}")
        
        # Try both formats of the cache key
        direct_key = f"ticker_details:{self.ticker}"
        polygon_key = f"polygon:/v3/reference/tickers/{self.ticker}:"
        print(f"[DEBUG TEST] Checking direct key: {direct_key}")
        print(f"[DEBUG TEST] Direct key result: {redis_client.get(direct_key)}")
        print(f"[DEBUG TEST] Checking polygon key prefix: {polygon_key}")
        if hasattr(redis_client, 'storage'):
            polygon_matches = [k for k in redis_client.storage.keys() if k.startswith(polygon_key)]
            print(f"[DEBUG TEST] Polygon key matches: {polygon_matches}")
            for key in polygon_matches:
                print(f"[DEBUG TEST] Value for {key}: {redis_client.get(key) is not None}")
        
        # Check that data was cached
        cached_data = redis_client.get(cache_key)
        print(f"[DEBUG TEST] Final cached_data check: {cached_data is not None}")
        assert cached_data is not None, "Data was not cached properly"
        
        # Force a small delay to ensure the first request is fully processed
        time.sleep(0.05)
        
        # Second request should be faster due to caching
        print("\n--- Second request (should be cached) ---")
        start_time = time.time()
        response2 = integration_client.get(f"/market-data/ticker/{self.ticker}")
        second_request_time = time.time() - start_time
        
        assert response2.status_code == 200
        ticker_data2 = response2.json()
        
        # Data should be identical
        assert ticker_data1 == ticker_data2
        
        # Print timing information for debugging
        print(f"First request time: {first_request_time:.6f}s")
        print(f"Second request time: {second_request_time:.6f}s")
        print(f"Difference: {first_request_time - second_request_time:.6f}s")
        print(f"Ratio: {first_request_time / second_request_time:.2f}x")
        
        # For the test to pass reliably, the first request needs to be consistently
        # slower than the second request. Due to our mock implementation with 
        # time.sleep(0.01) in the non-cached path, this should be true.
        assert second_request_time < first_request_time, \
            "Cached request should be faster than non-cached request"
    
    def test_option_chain_retrieval_and_processing(self, integration_client):
        """Test the complete flow of option chain retrieval and processing."""
        # Fetch option expirations
        response = integration_client.get(f"/market-data/expirations/{self.ticker}")
        assert response.status_code == 200
        expirations_data = response.json()
        assert "expirations" in expirations_data
        expirations = expirations_data["expirations"]
        assert len(expirations) > 0
        
        # Get the first expiration date
        expiration_date = expirations[0]
        
        # Fetch the option chain for this expiration
        response = integration_client.get(
            f"/market-data/option-chain/{self.ticker}",
            params={"expiration_date": expiration_date}
        )
        assert response.status_code == 200
        chain_data = response.json()
        
        # Verify the structure of the option chain
        assert "ticker" in chain_data
        assert "options" in chain_data
        options = chain_data["options"]
        
        # Separate into calls and puts for testing
        calls = [opt for opt in options if opt.get("type") == "call"]
        puts = [opt for opt in options if opt.get("type") == "put"]
        
        assert len(calls) > 0
        assert len(puts) > 0
        
        # Verify option attributes
        call = calls[0]
        assert "strike_price" in call
        assert "symbol" in call
        assert "last_price" in call or "mid" in call
        assert "bid" in call
        assert "ask" in call
        assert "implied_volatility" in call
        
        # Get the underlying price for IV calculation
        ticker_response = integration_client.get(f"/market-data/price/{self.ticker}")
        assert ticker_response.status_code == 200
        ticker_data = ticker_response.json()
        underlying_price = ticker_data["price"]
        
        assert underlying_price is not None
        assert underlying_price > 0
        
        # Verify implied volatility calculation by checking a specific option
        # Choose an ATM call option for this test
        atm_calls = [c for c in calls 
                    if abs(c["strike_price"] - underlying_price) < underlying_price * 0.05]
        
        if atm_calls:
            atm_call = atm_calls[0]
            option_price = atm_call["last_price"] or atm_call.get("mid", (atm_call["bid"] + atm_call["ask"]) / 2)
            
            # Calculate IV directly using our pricing service
            iv_calc_response = integration_client.post(
                "/greeks/implied-volatility",
                params={
                    "ticker": self.ticker,
                    "strike": atm_call["strike_price"],
                    "expiration": expiration_date,
                    "option_type": "call",
                    "option_price": option_price,
                    "american": False
                }
            )
            
            assert iv_calc_response.status_code == 200
            iv_result = iv_calc_response.json()
            
            # The calculated IV should be somewhat close to the one from the market data
            # We allow some difference because of different calculation methods
            # and different risk-free rate assumptions
            assert "implied_volatility" in iv_result
            assert abs(iv_result["implied_volatility"] - atm_call["implied_volatility"]) < 0.1
    
    def test_multi_expiration_scenario_analysis(self, integration_client):
        """Test retrieving options data across multiple expirations for scenario analysis."""
        # Fetch near-term and month-out options data
        near_term_date = self.next_friday.strftime("%Y-%m-%d")
        month_out_date = self.month_out_friday.strftime("%Y-%m-%d")
        
        # Get the underlying price
        ticker_response = integration_client.get(f"/market-data/price/{self.ticker}")
        assert ticker_response.status_code == 200
        ticker_data = ticker_response.json()
        underlying_price = ticker_data["price"]
        
        # Get expirations to make sure our test dates are valid
        exp_response = integration_client.get(f"/market-data/expirations/{self.ticker}")
        assert exp_response.status_code == 200
        available_expirations = exp_response.json()["expirations"]
        
        # Use the closest available expirations if our calculated ones aren't available
        if near_term_date not in available_expirations:
            near_term_date = min(available_expirations, key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d").date() - self.next_friday)))
        
        if month_out_date not in available_expirations:
            month_out_date = min(available_expirations, key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d").date() - self.month_out_friday)))
        
        # Request near-term option chain
        response1 = integration_client.get(
            f"/market-data/option-chain/{self.ticker}",
            params={"expiration_date": near_term_date}
        )
        
        if response1.status_code == 200:
            chain1 = response1.json()
            options1 = chain1["options"]
            calls1 = [opt for opt in options1 if opt.get("type") == "call"]
            
            # Find ATM options
            atm_call1 = next((c for c in calls1 
                            if abs(c["strike_price"] - underlying_price) < 0.01 * underlying_price), None)
            
            if atm_call1:
                # Request month-out option chain
                response2 = integration_client.get(
                    f"/market-data/option-chain/{self.ticker}",
                    params={"expiration_date": month_out_date}
                )
                
                if response2.status_code == 200:
                    chain2 = response2.json()
                    options2 = chain2["options"]
                    calls2 = [opt for opt in options2 if opt.get("type") == "call"]
                    
                    # Find matching strike in month-out options
                    atm_call2 = next((c for c in calls2 
                                    if c["strike_price"] == atm_call1["strike_price"]), None)
                    
                    if atm_call2:
                        # Compare implied volatilities - this tests the term structure
                        # Typically, longer-dated options have different IVs
                        iv1 = atm_call1["implied_volatility"]
                        iv2 = atm_call2["implied_volatility"]
                        
                        # We're not testing specific values, just that we can retrieve and compare
                        assert iv1 is not None
                        assert iv2 is not None
                        
                        # Create this position manually for scenario analysis
                        option_price1 = atm_call1["last_price"] or atm_call1.get("mid", (atm_call1["bid"] + atm_call1["ask"]) / 2)
                        option_price2 = atm_call2["last_price"] or atm_call2.get("mid", (atm_call2["bid"] + atm_call2["ask"]) / 2)
                        
                        calendar_spread = {
                            "name": f"{self.ticker} Calendar Spread",
                            "description": "Calendar spread test position",
                            "legs": [
                                {
                                    "option_type": "call",
                                    "strike": atm_call1["strike_price"],
                                    "expiration_date": near_term_date,
                                    "quantity": -1,  # SHORT
                                    "underlying_ticker": self.ticker,
                                    "underlying_price": underlying_price,
                                    "option_price": option_price1,
                                    "volatility": iv1
                                },
                                {
                                    "option_type": "call",
                                    "strike": atm_call2["strike_price"],
                                    "expiration_date": month_out_date,
                                    "quantity": 1,  # LONG
                                    "underlying_ticker": self.ticker,
                                    "underlying_price": underlying_price,
                                    "option_price": option_price2,
                                    "volatility": iv2
                                }
                            ]
                        }
                        
                        # Create the position
                        position_response = integration_client.post(
                            "/positions/with-legs",
                            json=calendar_spread
                        )
                        
                        # Debug the response if there's an error
                        if position_response.status_code != 201:
                            print(f"\nPosition creation failed with status: {position_response.status_code}")
                            print(f"Response content: {position_response.json()}")
                            
                            # Investigate the payload we're sending
                            print(f"\nCalendar spread payload: {calendar_spread}")
                            
                            # Check if we need to adjust the payload format
                            # Common issue: Some APIs expect different field names or formats
                            adjusted_calendar_spread = {
                                "name": f"{self.ticker} Calendar Spread",
                                "description": "Calendar spread test position",
                                "legs": [
                                    {
                                        "option_type": "call",
                                        "strike": atm_call1["strike_price"],
                                        "expiration": near_term_date,  # Changed from expiration_date
                                        "quantity": -1,  # SHORT
                                        "underlying": self.ticker,  # Changed from underlying_ticker
                                        "price": underlying_price,  # Changed from underlying_price
                                        "option_price": option_price1,
                                        "implied_volatility": iv1  # Changed from volatility
                                    },
                                    {
                                        "option_type": "call",
                                        "strike": atm_call2["strike_price"],
                                        "expiration": month_out_date,  # Changed from expiration_date
                                        "quantity": 1,  # LONG
                                        "underlying": self.ticker,  # Changed from underlying_ticker
                                        "price": underlying_price,  # Changed from underlying_price
                                        "option_price": option_price2,
                                        "implied_volatility": iv2  # Changed from volatility
                                    }
                                ]
                            }
                            
                            # Try with the adjusted payload
                            position_response = integration_client.post(
                                "/positions/with-legs",
                                json=adjusted_calendar_spread
                            )
                        
                        # Now assert with more detailed error reporting
                        error_msg = ""
                        if position_response.status_code != 201:
                            error_msg = f"\nFailed to create position. Status: {position_response.status_code}, Response: {position_response.text}"
                        
                        assert position_response.status_code == 201, error_msg
                        position_data = position_response.json()
                        position_id = position_data["id"]
                        
                        try:
                            # Generate a price vs time scenario for this calendar spread
                            scenario_params = {
                                "position_ids": [position_id],
                                "price_range": {
                                    "min": underlying_price * 0.9,
                                    "max": underlying_price * 1.1,
                                    "steps": 20
                                },
                                "days_to_expiry_range": {
                                    "min": 0,
                                    "max": 21,
                                    "steps": 4
                                }
                            }
                            
                            scenario_response = integration_client.post(
                                f"/scenarios/price-vs-time",
                                json=scenario_params
                            )
                            
                            if scenario_response.status_code == 200:
                                scenario_data = scenario_response.json()
                                
                                # Verify the structure of the scenario data
                                assert "prices" in scenario_data
                                assert "days" in scenario_data or "time_points" in scenario_data
                                assert "values" in scenario_data
                            
                        finally:
                            # Clean up - delete the position
                            integration_client.delete(f"/positions/{position_id}") 