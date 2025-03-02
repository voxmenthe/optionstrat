import os
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import json
import redis
from fastapi import HTTPException
import pandas as pd
import numpy as np
import logging
from sqlalchemy.orm import Session

from app.services.market_data_provider import MarketDataProvider
from app.models.database import CacheEntry, get_db

# Set up logging
logger = logging.getLogger(__name__)

class YFinanceProvider(MarketDataProvider):
    """
    Implementation of MarketDataProvider using Yahoo Finance (yfinance) API.
    Includes caching with Redis to minimize API calls.
    Falls back to database storage if Redis is unavailable.
    """
    
    def __init__(self, use_cache: bool = True):
        """
        Initialize the Yahoo Finance market data provider.
        
        Args:
            use_cache: Whether to use caching (Redis or DB)
        """
        self.use_cache = use_cache
        self.redis_available = False
        self.redis = None
        # Don't store a persistent database session - we'll get a fresh one when needed
        self.cache_expiry = 3600  # Cache for 1 hour - set this regardless of Redis availability
        
        # Initialize Redis connection if caching is enabled and Redis is available
        if self.use_cache and os.environ.get("REDIS_ENABLED", "true").lower() == "true":
            try:
                self.redis = redis.Redis(
                    host=os.environ.get("REDIS_HOST", "localhost"),
                    port=int(os.environ.get("REDIS_PORT", 6379)),
                    db=0,
                    decode_responses=True
                )
                # Test the connection
                self.redis.ping()
                self.redis_available = True
                logger.info("Redis caching enabled")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Falling back to database caching.")
                self.redis_available = False
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """
        Get data from cache (Redis or database).
        
        Args:
            cache_key: The cache key to retrieve
            
        Returns:
            Cached data or None if not found
        """
        if not self.use_cache:
            return None
            
        # Try Redis first if available
        if self.redis_available:
            try:
                cached_data = self.redis.get(cache_key)
                if cached_data:
                    logger.debug(f"Redis cache hit for {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis cache retrieval error: {e}. Falling back to database.")
                self.redis_available = False
        
        # Fallback to database if Redis failed or is not available
        db = None
        try:
            # Get a fresh session for each database operation
            db = next(get_db())
            db_cache = db.query(CacheEntry).filter(CacheEntry.key == cache_key).first()
            if db_cache and db_cache.expires_at > datetime.now():
                logger.debug(f"Database cache hit for {cache_key}")
                result = json.loads(db_cache.value)
                return result
            elif db_cache:
                # Remove expired entry
                db.delete(db_cache)
                db.commit()
        except Exception as e:
            logger.warning(f"Database cache retrieval error: {e}")
            if db and db.is_active:
                db.rollback()
        finally:
            # Always close the session
            if db:
                db.close()
        
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict) -> None:
        """
        Save data to cache (Redis or database).
        
        Args:
            cache_key: The cache key
            data: The data to save
        """
        if not self.use_cache:
            return
            
        serialized_data = json.dumps(data)
        expiry_time = datetime.now() + timedelta(seconds=self.cache_expiry)
        
        # Try Redis first if available
        if self.redis_available:
            try:
                self.redis.setex(
                    cache_key,
                    self.cache_expiry,
                    serialized_data
                )
                logger.debug(f"Saved data to Redis cache: {cache_key}")
                return
            except Exception as e:
                logger.warning(f"Redis cache save error: {e}. Falling back to database.")
                self.redis_available = False
        
        # Fallback to database if Redis failed or is not available
        db = None
        try:
            # Get a fresh session for each database operation
            db = next(get_db())
            # Check if entry exists
            existing_cache = db.query(CacheEntry).filter(CacheEntry.key == cache_key).first()
            if existing_cache:
                existing_cache.value = serialized_data
                existing_cache.expires_at = expiry_time
            else:
                new_cache = CacheEntry(
                    key=cache_key,
                    value=serialized_data,
                    expires_at=expiry_time
                )
                db.add(new_cache)
            db.commit()
            logger.debug(f"Saved data to database cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Database cache save error: {e}")
            if db and db.is_active:
                db.rollback()
        finally:
            # Always close the session
            if db:
                db.close()
    
    def _convert_dataframe_to_list(self, df: pd.DataFrame) -> List[Dict]:
        """Convert a pandas DataFrame to a list of dictionaries."""
        if df is None or df.empty:
            return []
        
        # Convert NaN values to None for JSON serialization
        return json.loads(df.replace({np.nan: None}).to_json(orient='records'))
    
    def get_ticker_details(self, ticker: str) -> Dict:
        """
        Get detailed information about a ticker symbol.
        
        Args:
            ticker: The ticker symbol to look up
            
        Returns:
            Ticker details
        """
        print(f"get_ticker_details called for ticker: {ticker}")
        
        # Check cache first
        cache_key = f"yfinance:ticker_details:{ticker}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return cached_data
        
        try:
            # Get ticker data from yfinance
            ticker_data = yf.Ticker(ticker)
            
            # Get info and fast_info
            info = ticker_data.info
            
            # Standardize the data to match the expected format
            standardized_data = {
                "ticker": ticker,
                "name": info.get("shortName", ""),
                "market": info.get("market", ""),
                "price": info.get("currentPrice", 0.0),
                "previous_close": info.get("previousClose", 0.0),
                "change": info.get("currentPrice", 0.0) - info.get("previousClose", 0.0),
                "change_percent": (info.get("currentPrice", 0.0) / info.get("previousClose", 1.0) - 1) * 100 if info.get("previousClose", 0) > 0 else 0.0,
            }
            
            # Format the response to match the expected structure
            result = {
                "status": "OK",
                "results": standardized_data
            }
            
            # Cache the result
            self._save_to_cache(cache_key, result)
            
            return result
                
        except Exception as e:
            import traceback
            print(f"Error in get_ticker_details: {str(e)}")
            print(traceback.format_exc())
            # Re-raise the exception to be handled by the route
            raise HTTPException(status_code=500, detail=f"Yahoo Finance API error: {str(e)}")
    
    def get_stock_price(self, ticker: str) -> float:
        """
        Get the latest price for a stock.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            Latest price as float
        """
        print(f"get_stock_price called for ticker: {ticker}")
        
        # Check cache first
        cache_key = f"yfinance:stock_price:{ticker}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return cached_data.get("price", 0.0)
        
        try:
            # Get ticker data from yfinance
            ticker_data = yf.Ticker(ticker)
            
            # Get the latest price
            latest_price = ticker_data.fast_info.get("lastPrice", 0.0)
            
            # Cache the result
            self._save_to_cache(cache_key, {"price": latest_price})
            
            return latest_price
        except Exception as e:
            print(f"Error in get_stock_price: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Yahoo Finance API error: {str(e)}")
    
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
        
        # Check cache first
        cache_key = f"yfinance:option_chain:{ticker}:{expiration_date or 'all'}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return cached_data
        
        try:
            # Get ticker data from yfinance
            ticker_data = yf.Ticker(ticker)
            
            # Get the available expiration dates
            expirations = ticker_data.options
            
            if not expirations:
                print(f"No options found for {ticker}")
                return []
            
            # Use the provided expiration date or the nearest one
            if expiration_date:
                if expiration_date not in expirations:
                    print(f"Expiration {expiration_date} not found for {ticker}")
                    return []
                selected_expiration = expiration_date
            else:
                selected_expiration = expirations[0]
            
            # Get the option chain for the selected expiration
            options = ticker_data.option_chain(selected_expiration)
            
            # Process calls
            calls_df = options.calls.copy()
            calls_df['optionType'] = 'call'
            calls_df['underlying'] = ticker
            calls_df['expiration_date'] = selected_expiration
            
            # Process puts
            puts_df = options.puts.copy()
            puts_df['optionType'] = 'put'
            puts_df['underlying'] = ticker
            puts_df['expiration_date'] = selected_expiration
            
            # Combine calls and puts
            all_options = pd.concat([calls_df, puts_df])
            
            # Convert to list of dictionaries
            options_list = self._convert_dataframe_to_list(all_options)
            
            # Standardize field names to match the expected format
            standardized_options = []
            for option in options_list:
                standardized_option = {
                    "contract_type": option.get("optionType", "").upper(),
                    "underlying_ticker": option.get("underlying", ticker),
                    "ticker": option.get("contractSymbol", ""),
                    "strike_price": option.get("strike", 0.0),
                    "expiration_date": option.get("expiration_date", ""),
                    "last_price": option.get("lastPrice", 0.0),
                    "bid": option.get("bid", 0.0),
                    "ask": option.get("ask", 0.0),
                    "volume": option.get("volume", 0),
                    "open_interest": option.get("openInterest", 0),
                    "implied_volatility": option.get("impliedVolatility", 0.0),
                    "in_the_money": option.get("inTheMoney", False),
                }
                standardized_options.append(standardized_option)
            
            # Cache the result
            self._save_to_cache(cache_key, standardized_options)
            
            return standardized_options
        except Exception as e:
            import traceback
            print(f"Error in get_option_chain: {str(e)}")
            print(traceback.format_exc())
            return []
    
    def get_option_price(self, option_symbol: str) -> Dict:
        """
        Get the latest price for an option.
        
        Args:
            option_symbol: Option symbol
            
        Returns:
            Option price data
        """
        print(f"get_option_price called for option: {option_symbol}")
        
        # Check cache first
        cache_key = f"yfinance:option_price:{option_symbol}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return cached_data
        
        try:
            # Parse the option symbol to extract the ticker and contract details
            # This is a simplified approach, the actual parsing might be more complex
            # Format example: O:AAPL230616C00150000
            parts = option_symbol.split(":")
            if len(parts) > 1:
                contract_symbol = parts[1]
            else:
                contract_symbol = option_symbol
            
            # Extract the ticker (first letters until the first digit)
            ticker = ""
            for char in contract_symbol:
                if not char.isdigit():
                    ticker += char
                else:
                    break
            
            # Get ticker data from yfinance
            ticker_data = yf.Ticker(contract_symbol)
            
            # Get the latest price data
            history = ticker_data.history(period="1d")
            
            if history.empty:
                raise HTTPException(status_code=404, detail=f"No price data found for option {option_symbol}")
            
            # Get the latest row
            latest_data = history.iloc[-1]
            
            # Format the result
            result = {
                "price": latest_data.get("Close", 0.0),
                "volume": latest_data.get("Volume", 0),
                "open_interest": 0,  # Not available directly
                "bid": 0.0,  # Not available directly
                "ask": 0.0,  # Not available directly
            }
            
            # Cache the result
            self._save_to_cache(cache_key, result)
            
            return result
        except Exception as e:
            print(f"Error in get_option_price: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Yahoo Finance API error: {str(e)}")
    
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
        
        # Mapping from API timespan to yfinance interval
        interval_mapping = {
            "minute": "1m",
            "hour": "1h",
            "day": "1d",
            "week": "1wk",
            "month": "1mo",
            "quarter": "3mo",
            "year": "1y"
        }
        
        # Get the corresponding interval
        interval = interval_mapping.get(timespan, "1d")
        
        # Check cache first
        cache_key = f"yfinance:historical_prices:{ticker}:{from_date.strftime('%Y-%m-%d')}:{to_date.strftime('%Y-%m-%d')}:{interval}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return cached_data
        
        try:
            # Get ticker data from yfinance
            ticker_data = yf.Ticker(ticker)
            
            # Get historical data
            history = ticker_data.history(
                start=from_date.strftime("%Y-%m-%d"),
                end=to_date.strftime("%Y-%m-%d"),
                interval=interval
            )
            
            if history.empty:
                return []
            
            # Format the data
            formatted_data = []
            for date, row in history.iterrows():
                formatted_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": row.get("Open", 0.0),
                    "high": row.get("High", 0.0),
                    "low": row.get("Low", 0.0),
                    "close": row.get("Close", 0.0),
                    "volume": row.get("Volume", 0),
                })
            
            # Cache the result
            self._save_to_cache(cache_key, formatted_data)
            
            return formatted_data
        except Exception as e:
            print(f"Error in get_historical_prices: {str(e)}")
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
        
        # Check cache first
        cache_key = f"yfinance:implied_volatility:{ticker}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return cached_data.get("implied_volatility", 0.3)
        
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
                    
                    # Cache the result
                    self._save_to_cache(cache_key, {"implied_volatility": avg_iv})
                    
                    return avg_iv
            
            # If no options found or no valid IV, return a default
            return 0.3  # 30% as a default
        except Exception as e:
            print(f"Error in get_implied_volatility: {str(e)}")
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
        
        # Check cache first
        cache_key = f"yfinance:option_expirations:{ticker}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return cached_data
        
        try:
            # Get ticker data from yfinance
            ticker_data = yf.Ticker(ticker)
            
            # Get available expirations
            expirations = ticker_data.options
            
            # Format the result
            result = {
                "ticker": ticker,
                "expirations": list(expirations) if expirations else []
            }
            
            # Cache the result
            self._save_to_cache(cache_key, result)
            
            return result
        except Exception as e:
            print(f"Error in get_option_expirations: {str(e)}")
            return {"ticker": ticker, "expirations": []}
    
    def get_option_strikes(
        self, 
        ticker: str, 
        expiration_date: Union[datetime, str], 
        option_type: Optional[str] = None
    ) -> Dict:
        """
        Get available strike prices for options on a ticker.
        
        Args:
            ticker: The ticker symbol
            expiration_date: Option expiration date (datetime object or string in YYYY-MM-DD format)
            option_type: Option type (call or put)
            
        Returns:
            Dictionary with strike prices
        """
        print(f"get_option_strikes called for ticker: {ticker}, expiration: {expiration_date}, type: {option_type}")
        
        # Format the expiration date for the API - handle both datetime and string
        if isinstance(expiration_date, datetime):
            exp_date_str = expiration_date.strftime("%Y-%m-%d")
        else:
            # Assume it's already a string in YYYY-MM-DD format
            exp_date_str = str(expiration_date)
        
        # Check cache first
        cache_key = f"yfinance:option_strikes:{ticker}:{exp_date_str}:{option_type or 'all'}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return cached_data
        
        try:
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
            
            # Format the result
            result = {
                "ticker": ticker,
                "expiration_date": exp_date_str,
                "option_type": option_type,
                "strikes": sorted_strikes
            }
            
            # Cache the result
            self._save_to_cache(cache_key, result)
            
            return result
        except Exception as e:
            print(f"Error in get_option_strikes: {str(e)}")
            return {
                "ticker": ticker,
                "expiration_date": exp_date_str,
                "option_type": option_type,
                "strikes": []
            }
    
    def search_tickers(self, query: str) -> List[str]:
        """
        Validate ticker symbol and return it if valid.
        Since users are expected to know their ticker symbols, this is a simplified
        implementation that just validates the input ticker.
        
        Args:
            query: Ticker symbol to validate
            
        Returns:
            List containing the ticker if valid, empty list otherwise
        """
        print(f"validate_ticker called with ticker: {query}")
        
        if not query:
            return []
            
        # Check cache first
        cache_key = f"yfinance:ticker_validation:{query}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return cached_data
            
        try:
            # Standardize the ticker format
            ticker = query.strip().upper()
            
            # Basic validation - is it a reasonable ticker format?
            if not ticker or len(ticker) > 6 or not any(c.isalpha() for c in ticker):
                return []
                
            # Try to fetch basic info from yfinance to validate
            ticker_data = yf.Ticker(ticker)
            
            # Check if the ticker is valid by attempting to get its info
            info = ticker_data.info
            
            # If we get a name, it's probably valid
            if "shortName" in info or "longName" in info:
                result = [ticker]
                
                # Cache the result
                self._save_to_cache(cache_key, result)
                
                return result
            
            # Otherwise return empty list (invalid ticker)
            return []
                
        except Exception as e:
            # Most exceptions here would indicate an invalid ticker
            import traceback
            print(f"Error validating ticker: {str(e)}")
            print(traceback.format_exc())
            return [] # Return empty list rather than raising an exception
