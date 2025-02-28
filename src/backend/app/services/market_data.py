import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import json
import redis
from fastapi import HTTPException


class MarketDataService:
    """
    Service for fetching market data from Polygon.io API.
    Includes caching with Redis to minimize API calls.
    """
    
    def __init__(self, api_key: Optional[str] = None, use_cache: bool = True):
        """
        Initialize the market data service.
        
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
        url = f"{self.base_url}{endpoint}"
        
        # Add API key to params
        params = params or {}
        params["apiKey"] = self.api_key
        
        # Create cache key if caching is enabled
        cache_key = None
        if self.use_cache:
            cache_key = f"polygon:{endpoint}:{json.dumps(params, sort_keys=True)}"
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                return cached_data
        
        # Make API request
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Cache the response
            if self.use_cache and cache_key:
                self._save_to_cache(cache_key, data)
            
            return data
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Polygon.io API error: {str(e)}")
        except Exception as e:
            # Handle any other exceptions that might occur
            raise HTTPException(status_code=500, detail=f"Polygon.io API error: {str(e)}")
    
    def get_ticker_details(self, ticker: str) -> Dict:
        """
        Get details for a ticker symbol.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Ticker details
        """
        endpoint = f"/v3/reference/tickers/{ticker}"
        return self._make_request(endpoint)
    
    def get_stock_price(self, ticker: str) -> float:
        """
        Get the latest price for a stock.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Latest price
        """
        endpoint = f"/v2/last/trade/{ticker}"
        response = self._make_request(endpoint)
        
        if "results" in response and response["results"]:
            return response["results"]["p"]
        else:
            raise HTTPException(status_code=404, detail=f"No price data found for {ticker}")
    
    def get_option_chain(self, underlying_ticker: str, expiration_date: Optional[datetime] = None) -> List[Dict]:
        """
        Get the option chain for a ticker.
        
        Args:
            underlying_ticker: Underlying ticker symbol
            expiration_date: Option expiration date (optional)
            
        Returns:
            List of option contracts
        """
        endpoint = "/v3/reference/options/contracts"
        
        params = {
            "underlying_ticker": underlying_ticker,
            "limit": 1000
        }
        
        if expiration_date:
            params["expiration_date"] = expiration_date.strftime("%Y-%m-%d")
        
        response = self._make_request(endpoint, params)
        
        if "results" in response:
            return response["results"]
        else:
            return []
    
    def get_option_price(self, option_symbol: str) -> Dict:
        """
        Get the latest price and Greeks for an option.
        
        Args:
            option_symbol: Option symbol (e.g., O:AAPL230616C00150000)
            
        Returns:
            Option price and Greeks
        """
        endpoint = f"/v2/last/trade/{option_symbol}"
        response = self._make_request(endpoint)
        
        if "results" in response and response["results"]:
            return {
                "price": response["results"]["p"],
                "timestamp": response["results"]["t"]
            }
        else:
            raise HTTPException(status_code=404, detail=f"No price data found for {option_symbol}")
    
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
            ticker: Ticker symbol
            from_date: Start date
            to_date: End date
            timespan: Time interval (minute, hour, day, week, month, quarter, year)
            
        Returns:
            List of price data points
        """
        endpoint = f"/v2/aggs/ticker/{ticker}/range/1/{timespan}/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}"
        response = self._make_request(endpoint)
        
        if "results" in response:
            return response["results"]
        else:
            return []
    
    def get_implied_volatility(self, ticker: str) -> float:
        """
        Get the implied volatility for a ticker.
        This is a placeholder - Polygon.io doesn't directly provide IV.
        In a real implementation, you would calculate this from option prices.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Implied volatility
        """
        # This is a placeholder - in a real implementation, you would calculate IV
        # from ATM options or use a volatility index
        return 0.3  # 30% as a default 