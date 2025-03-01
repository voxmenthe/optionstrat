import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import json
import redis
from fastapi import HTTPException

from app.services.market_data_provider import MarketDataProvider


class PolygonProvider(MarketDataProvider):
    """
    Implementation of MarketDataProvider using Polygon.io API.
    Includes caching with Redis to minimize API calls.
    """
    
    def __init__(self, api_key: Optional[str] = None, use_cache: bool = True):
        """
        Initialize the Polygon market data provider.
        
        Args:
            api_key: Polygon.io API key (defaults to environment variable)
            use_cache: Whether to use Redis caching
        """
        self.api_key = api_key or os.environ.get("POLYGON_API_KEY", "")
        if not self.api_key:
            print("Warning: No Polygon.io API key provided. API calls will fail.")
        
        self.base_url = "https://api.polygon.io"
        self.use_cache = use_cache
        
        # Initialize Redis connection if caching is enabled
        if self.use_cache:
            try:
                self.redis = redis.Redis(
                    host=os.environ.get("REDIS_HOST", "localhost"),
                    port=int(os.environ.get("REDIS_PORT", 6379)),
                    db=0,
                    decode_responses=True
                )
                self.cache_expiry = 3600  # Cache for 1 hour
            except Exception as e:
                print(f"Warning: Redis connection failed: {e}. Caching disabled.")
                self.use_cache = False
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Get data from Redis cache."""
        if not self.use_cache:
            return None
        
        try:
            cached_data = self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            print(f"Cache retrieval error: {e}")
        
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict) -> None:
        """Save data to Redis cache."""
        if not self.use_cache:
            return
        
        try:
            self.redis.setex(
                cache_key,
                self.cache_expiry,
                json.dumps(data)
            )
        except Exception as e:
            print(f"Cache save error: {e}")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Make a request to the Polygon.io API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            API response as dictionary
        """
        print(f"Making request to {endpoint} with params {params}")
        url = f"{self.base_url}{endpoint}"
        
        # Add API key to params
        params = params or {}
        params["apiKey"] = self.api_key
        
        # Create cache key if caching is enabled
        cache_key = None
        if self.use_cache:
            # Use specific cache key format for ticker details
            if "/v3/reference/tickers/" in endpoint:
                ticker = endpoint.split("/")[-1]
                cache_key = f"polygon:ticker_details:{ticker}"
                print(f"Using cache key: {cache_key}")
            else:
                cache_key = f"polygon:{endpoint}:{json.dumps(params, sort_keys=True)}"
                
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                print(f"Cache hit for {cache_key}")
                return cached_data
            else:
                print(f"Cache miss for {cache_key}")
        
        # Make API request
        try:
            print(f"Making actual API request to {url}")
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Debug print what was received
            print(f"API response received: {json.dumps(data)[:200]}...")
            
            # Cache the response if caching is enabled
            if self.use_cache and cache_key:
                print(f"Saving to cache with key {cache_key}")
                self._save_to_cache(cache_key, data)
            
            return data
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            # For 403 errors, provide more helpful message about API key
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 403:
                raise HTTPException(
                    status_code=500, 
                    detail="Polygon.io API key is invalid or has expired. Please check your API key."
                )
            raise HTTPException(status_code=500, detail=f"Polygon.io API error: {str(e)}")
        except Exception as e:
            print(f"Unexpected API error: {e}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Polygon.io API error: {str(e)}")
    
    def get_ticker_details(self, ticker: str) -> Dict:
        """
        Get detailed information about a ticker symbol.
        
        Args:
            ticker: The ticker symbol to look up
            
        Returns:
            Ticker details
        """
        print(f"get_ticker_details called for ticker: {ticker}")
        endpoint = f"/v3/reference/tickers/{ticker}"
        
        try:
            response = self._make_request(endpoint)
            print(f"Response from _make_request: {response}")
            
            # Handle different response formats, but preserve the nested structure for tests
            
            # Check if response already has the exact format we need
            if isinstance(response, dict) and "status" in response and "results" in response:
                if isinstance(response["results"], dict) and "ticker" in response["results"]:
                    # Response already has the structure tests expect
                    return response
            
            # Otherwise, construct a response in the format tests expect
            # Standardize the data regardless of source
            ticker_data = {}
            
            # Extract ticker data from different possible response formats
            if isinstance(response, dict):
                if "results" in response and isinstance(response["results"], dict):
                    ticker_data = response["results"]
                else:
                    # Try to extract from top level
                    ticker_data = response
            
            # Ensure we have at least the basic fields
            standardized_data = {
                "ticker": ticker_data.get("ticker", ticker),
                "name": ticker_data.get("name", ""),
                "market": ticker_data.get("market", ""),
                "price": ticker_data.get("price", 0.0),
                "previous_close": ticker_data.get("previous_close", 0.0),
                "change": ticker_data.get("change", 0.0),
                "change_percent": ticker_data.get("change_percent", 0.0),
            }
            
            # Return in the nested format tests expect
            return {
                "status": "OK",
                "results": standardized_data
            }
                
        except Exception as e:
            import traceback
            print(f"Error in get_ticker_details: {str(e)}")
            print(traceback.format_exc())
            # Re-raise the exception to be handled by the route
            raise
    
    def get_stock_price(self, ticker: str) -> float:
        """
        Get the latest price for a stock.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            Latest price as float
        """
        print(f"get_stock_price called for ticker: {ticker}")
        endpoint = f"/v2/aggs/ticker/{ticker}/prev"
        
        response = self._make_request(endpoint)
        
        # Extract the closing price from the response
        if "results" in response and response["results"]:
            # We use the most recent result if there are multiple
            latest_result = response["results"][0]
            return latest_result.get("c", 0.0)
        else:
            raise HTTPException(status_code=404, detail=f"No price data found for {ticker}")
    
    def get_option_chain(self, ticker: str, expiration_date: Optional[str] = None) -> List[Dict]:
        """
        Get the option chain for a ticker.
        
        Args:
            ticker: The ticker symbol
            expiration_date: Option expiration date (YYYY-MM-DD)
            
        Returns:
            List of option details
        """
        print(f"get_option_chain called for ticker: {ticker}, expiration: {expiration_date}")
        
        # Construct the API endpoint
        if expiration_date:
            endpoint = f"/v3/reference/options/contracts?underlying_ticker={ticker}&expiration_date={expiration_date}"
        else:
            # Get the nearest expiration if not specified
            endpoint = f"/v3/reference/options/contracts?underlying_ticker={ticker}"
        
        response = self._make_request(endpoint)
        
        # Extract the options data from the response
        if "results" in response and isinstance(response["results"], list):
            options_data = response["results"]
            print(f"Found {len(options_data)} options")
            return options_data
        else:
            print(f"No options found for {ticker} with expiration {expiration_date}")
            return []
    
    def get_option_price(self, option_symbol: str) -> Dict:
        """
        Get the latest price for an option.
        
        Args:
            option_symbol: Option symbol (e.g., O:AAPL230616C00150000)
            
        Returns:
            Option price data
        """
        print(f"get_option_price called for option: {option_symbol}")
        endpoint = f"/v2/aggs/ticker/{option_symbol}/prev"
        
        response = self._make_request(endpoint)
        
        # Extract the option price data from the response
        if "results" in response and response["results"]:
            # We use the most recent result if there are multiple
            latest_result = response["results"][0]
            return {
                "price": latest_result.get("c", 0.0),
                "volume": latest_result.get("v", 0),
                "open_interest": latest_result.get("o", 0),
                "bid": latest_result.get("l", 0.0),  # Using low as a proxy for bid
                "ask": latest_result.get("h", 0.0),  # Using high as a proxy for ask
            }
        else:
            raise HTTPException(status_code=404, detail=f"No price data found for option {option_symbol}")
    
    def get_historical_prices(
        self, 
        ticker: str, 
        from_date: datetime, 
        to_date: datetime, 
        timespan: str = "day"
    ) -> List[Dict]:
        """
        Get historical price data for a ticker.
        
        Args:
            ticker: The ticker symbol
            from_date: Start date
            to_date: End date
            timespan: Time interval (minute, hour, day, week, month, quarter, year)
            
        Returns:
            List of historical price data
        """
        print(f"get_historical_prices called for ticker: {ticker}")
        
        # Format dates for API
        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")
        
        # Construct the API endpoint
        endpoint = f"/v2/aggs/ticker/{ticker}/range/1/{timespan}/{from_str}/{to_str}"
        
        response = self._make_request(endpoint)
        
        # Extract the historical price data from the response
        if "results" in response and isinstance(response["results"], list):
            price_data = response["results"]
            
            # Format the data for the API response
            formatted_data = []
            for data_point in price_data:
                formatted_data.append({
                    "date": datetime.fromtimestamp(data_point.get("t", 0) / 1000).strftime("%Y-%m-%d"),
                    "open": data_point.get("o", 0.0),
                    "high": data_point.get("h", 0.0),
                    "low": data_point.get("l", 0.0),
                    "close": data_point.get("c", 0.0),
                    "volume": data_point.get("v", 0),
                })
            
            return formatted_data
        else:
            return []
    
    def get_implied_volatility(self, ticker: str) -> float:
        """
        Get the implied volatility for a ticker.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            Implied volatility as float
        """
        print(f"get_implied_volatility called for ticker: {ticker}")
        
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
                return total_iv / count
        
        # If no options found or no valid IV, return a default
        return 0.3  # 30% as a default
    
    def get_option_expirations(self, ticker: str) -> Dict:
        """
        Get available expiration dates for options on a ticker.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            Dictionary with expiration dates
        """
        print(f"get_option_expirations called for ticker: {ticker}")
        
        # Using a different endpoint that gives us the contract specifications
        endpoint = f"/v3/reference/options/contracts?underlying_ticker={ticker}"
        
        response = self._make_request(endpoint)
        
        # Extract unique expiration dates
        expirations = set()
        if "results" in response and isinstance(response["results"], list):
            for contract in response["results"]:
                exp_date = contract.get("expiration_date")
                if exp_date:
                    expirations.add(exp_date)
        
        # Sort the expiration dates
        sorted_expirations = sorted(list(expirations))
        
        return {
            "ticker": ticker,
            "expirations": sorted_expirations
        }
    
    def get_option_strikes(
        self, 
        ticker: str, 
        expiration_date: datetime, 
        option_type: Optional[str] = None
    ) -> Dict:
        """
        Get available strike prices for options on a ticker.
        
        Args:
            ticker: The ticker symbol
            expiration_date: Option expiration date
            option_type: Option type (call or put)
            
        Returns:
            Dictionary with strike prices
        """
        print(f"get_option_strikes called for ticker: {ticker}, expiration: {expiration_date}, type: {option_type}")
        
        # Format the expiration date for the API
        exp_date_str = expiration_date.strftime("%Y-%m-%d")
        
        # Get the option chain for the specified expiration
        options = self.get_option_chain(ticker, exp_date_str)
        
        # Filter by option type if specified
        if option_type:
            if option_type.lower() == "call":
                options = [opt for opt in options if opt.get("contract_type", "").lower() == "call"]
            elif option_type.lower() == "put":
                options = [opt for opt in options if opt.get("contract_type", "").lower() == "put"]
        
        # Extract unique strike prices
        strikes = set()
        for option in options:
            strike = option.get("strike_price")
            if strike is not None:
                strikes.add(float(strike))
        
        # Sort the strike prices
        sorted_strikes = sorted(list(strikes))
        
        return {
            "ticker": ticker,
            "expiration_date": exp_date_str,
            "option_type": option_type,
            "strikes": sorted_strikes
        }
