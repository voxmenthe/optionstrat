import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd
import redis
import yfinance as yf
from fastapi import HTTPException

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
        # Set up instance logger
        self.logger = logger
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
            Latest price as float, or 0.0 if price cannot be retrieved
        """
        if not ticker:
            self.logger.warning("Empty ticker provided to get_stock_price")
            return 0.0
            
        # Check cache first
        cache_key = f"yfinance:stock_price:{ticker}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            self.logger.debug(f"Cache hit for {cache_key}")
            return cached_data.get("price", 0.0)
        
        self.logger.info(f"Fetching stock price for ticker: {ticker}")
        
        try:
            # Get ticker data from yfinance
            ticker_data = yf.Ticker(ticker)
            
            # Get the latest price
            try:
                latest_price = ticker_data.fast_info.get("lastPrice", None)
                
                # If fast_info doesn't have the price, try the regular info
                if latest_price is None:
                    info = ticker_data.info
                    if info:
                        latest_price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
                    else:
                        self.logger.warning(f"No info available for ticker {ticker}")
                        return 0.0
            except AttributeError:
                self.logger.warning(f"Could not access price info for {ticker}, trying alternative method")
                # Fallback to regular info if fast_info is not available
                info = ticker_data.info
                if info:
                    latest_price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
                else:
                    self.logger.warning(f"No info available for ticker {ticker}")
                    return 0.0
            
            # Ensure we have a valid price
            if latest_price is None or not isinstance(latest_price, (int, float)):
                self.logger.warning(f"Invalid price value for {ticker}: {latest_price}")
                return 0.0
                
            # Cache the result with a short TTL (5 minutes)
            self._save_to_cache(cache_key, {"price": latest_price}, ttl=300)
            
            return latest_price
        except Exception as e:
            self.logger.error(f"Error in get_stock_price for {ticker}: {str(e)}")
            # Return 0.0 instead of raising an exception to prevent API failures
            return 0.0
    
    def get_option_chain(self, ticker: str, expiration_date: Optional[Union[str, datetime]] = None) -> List[Dict]:
        """
        Get the option chain for a ticker.
        
        Args:
            ticker: The ticker symbol
            expiration_date: Option expiration date (YYYY-MM-DD string or datetime object)
            
        Returns:
            List of option details
        """
        print(f"get_option_chain called for ticker: {ticker}, expiration: {expiration_date}")
        
        # Create cache key
        cache_key = f"yfinance:option_chain:{ticker}:{expiration_date or 'all'}"
        
        # Clear existing cache for this request to ensure we get fresh data with the correct format
        # This is a temporary measure until we fix the caching issue
        if self.redis_available and self.redis:
            try:
                self.redis.delete(cache_key)
                self.logger.info(f"Cleared cache for {cache_key}")
            except Exception as e:
                self.logger.warning(f"Error clearing cache: {e}")
        
        # Now check if there's still cached data (from DB perhaps)
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            self.logger.info(f"Cache hit for {cache_key}")
            
            # Check if cached data needs to be reformatted
            if cached_data and len(cached_data) > 0 and isinstance(cached_data[0], dict):
                first_item = cached_data[0]
                # Check if the first item has the expected fields
                if ("expiration" not in first_item or 
                    "strike" not in first_item or 
                    "option_type" not in first_item):
                    
                    self.logger.info(f"Cached data has old format, will fetch fresh data")
                    # Don't use this cached data
                    cached_data = None
            
            if cached_data:
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
                # Normalize expiration date to YYYY-MM-DD format
                if isinstance(expiration_date, datetime):
                    # Format datetime to string
                    normalized_expiration = expiration_date.strftime("%Y-%m-%d")
                elif isinstance(expiration_date, str):
                    # Handle string input - remove any time component
                    normalized_expiration = expiration_date.split()[0] if ' ' in expiration_date else expiration_date
                else:
                    # Unexpected type
                    raise ValueError(f"Unexpected type for expiration_date: {type(expiration_date)}")
                
                if normalized_expiration not in expirations:
                    print(f"Expiration {normalized_expiration} not found for {ticker}")
                    # Raise an HTTP exception instead of returning an empty list
                    raise HTTPException(
                        status_code=404,
                        detail=f"Expiration date {normalized_expiration} not found for {ticker}. Available dates: {', '.join(expirations[:5])}."
                    )
                selected_expiration = normalized_expiration
            else:
                selected_expiration = expirations[0]
            
            # Get the option chain for the selected expiration
            try:
                options = ticker_data.option_chain(selected_expiration)
                if not hasattr(options, 'calls') or not hasattr(options, 'puts'):
                    self.logger.warning(f"Invalid option chain data for {ticker} at {selected_expiration}")
                    return []
            except Exception as e:
                self.logger.error(f"Error getting option chain for {ticker} at {selected_expiration}: {str(e)}")
                return []
            
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
            
            # Debug: Print the first option to see its structure
            if options_list and len(options_list) > 0:
                self.logger.info(f"Sample option data structure: {options_list[0]}")
            
            # Standardize field names to match the expected OptionContract schema
            standardized_options = []
            
            # Get the current stock price once for all options
            underlying_price = self.get_stock_price(ticker)
            self.logger.info(f"Retrieved underlying price for {ticker}: {underlying_price}")
            
            # Process each option
            for option in options_list:
                # Only log the first option's keys for debugging
                if option == options_list[0]:
                    self.logger.debug(f"Sample option keys: {option.keys()}")
                
                # Format the expiration date properly
                expiration_date_obj = None
                if "expiration_date" in option:
                    # If it's already a datetime object, use it directly
                    if isinstance(option["expiration_date"], datetime):
                        expiration_date_obj = option["expiration_date"]
                    else:
                        # Try to convert string to datetime
                        try:
                            expiration_date_obj = datetime.fromisoformat(str(option["expiration_date"]).replace('Z', '+00:00'))
                        except ValueError:
                            try:
                                expiration_date_obj = datetime.strptime(str(option["expiration_date"]), "%Y-%m-%d")
                            except ValueError:
                                self.logger.error(f"Could not parse expiration date: {option['expiration_date']}")
                                # Use current date as fallback (not ideal but prevents validation errors)
                                expiration_date_obj = datetime.now()
                elif "expiration" in option:
                    # Same process for the 'expiration' field
                    if isinstance(option["expiration"], datetime):
                        expiration_date_obj = option["expiration"]
                    else:
                        try:
                            expiration_date_obj = datetime.fromisoformat(str(option["expiration"]).replace('Z', '+00:00'))
                        except ValueError:
                            try:
                                expiration_date_obj = datetime.strptime(str(option["expiration"]), "%Y-%m-%d")
                            except ValueError:
                                self.logger.error(f"Could not parse expiration date: {option['expiration']}")
                                expiration_date_obj = datetime.now()
                else:
                    # If no expiration date is found, use current date as fallback
                    self.logger.warning("No expiration date found in option data, using current date as fallback")
                    expiration_date_obj = datetime.now()
                
                # Extract the data from the option object based on the actual keys in the response
                # Ensure expiration is serialized as an ISO format string for the frontend
                expiration_str = expiration_date_obj.isoformat() if expiration_date_obj else datetime.now().isoformat()
                
                standardized_option = {
                    # Required fields based on OptionContract schema
                    "ticker": str(ticker),
                    "expiration": expiration_str,  # Use ISO format string instead of datetime object
                    "strike": float(option.get("strike", 0.0)),
                    "option_type": str(option.get("optionType", "")).lower(),
                    "bid": float(option.get("bid", 0.0)),
                    "ask": float(option.get("ask", 0.0)),
                    
                    # Optional fields - ensure proper type conversion
                    "last": float(option.get("lastPrice", 0.0)) if option.get("lastPrice") is not None else None,
                    "volume": int(float(option.get("volume", 0))) if option.get("volume") is not None else None,
                    "open_interest": int(float(option.get("openInterest", 0))) if option.get("openInterest") is not None else None,
                    "implied_volatility": float(option.get("impliedVolatility", 0.0)) if option.get("impliedVolatility") is not None else None,
                    
                    # Greeks (if available) - ensure proper type conversion
                    "delta": float(option.get("delta", 0.0)) if option.get("delta") is not None else None,
                    "gamma": float(option.get("gamma", 0.0)) if option.get("gamma") is not None else None,
                    "theta": float(option.get("theta", 0.0)) if option.get("theta") is not None else None,
                    "vega": float(option.get("vega", 0.0)) if option.get("vega") is not None else None,
                    "rho": float(option.get("rho", 0.0)) if option.get("rho") is not None else None,
                    
                    # Additional fields - ensure proper type conversion
                    "in_the_money": bool(option.get("inTheMoney", False)) if option.get("inTheMoney") is not None else None,
                    "underlying_price": float(underlying_price) if underlying_price is not None else None
                }
                
                # Only log the first standardized option for debugging
                if len(standardized_options) == 0:
                    self.logger.debug(f"Sample standardized option: {standardized_option}")
                standardized_options.append(standardized_option)
            
            # Cache the result
            self._save_to_cache(cache_key, standardized_options)
            
            return standardized_options
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
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
            try:
                expirations = ticker_data.options
                if not expirations or len(expirations) == 0:
                    self.logger.warning(f"No option expirations found for {ticker}")
                    return []
            except Exception as e:
                self.logger.error(f"Error getting options expirations for {ticker}: {str(e)}")
                return []
            
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
        self.logger.info(f"search_tickers called with query: {query}")
        
        # Early validation to prevent unnecessary processing
        if not query:
            self.logger.info("Empty query, returning empty list")
            return []
            
        # Standardize the ticker format
        ticker = query.strip().upper()
        self.logger.info(f"Standardized ticker: {ticker}")
        
        # Basic validation - is it a reasonable ticker format?
        if not ticker or len(ticker) > 6 or not any(c.isalpha() for c in ticker):
            self.logger.info(f"Invalid ticker format: {ticker}")
            return []
            
        # Check cache first
        cache_key = f"yfinance:ticker_validation:{ticker}"
        self.logger.info(f"Checking cache for key: {cache_key}")
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            self.logger.info(f"Cache hit for {cache_key}: {cached_data}")
            return cached_data
            
        try:
            # Try to fetch basic info from yfinance to validate
            self.logger.info(f"Fetching yfinance data for ticker: {ticker}")
            ticker_data = yf.Ticker(ticker)
            
            # Check if the ticker is valid by attempting to get its info
            try:
                self.logger.info(f"Getting info for ticker: {ticker}")
                info = ticker_data.info
                self.logger.info(f"Got info for ticker {ticker}: {info is not None}")
                
                # If info is None or empty, the ticker is invalid
                if not info:
                    self.logger.info(f"Empty info for ticker: {ticker}")
                    # Cache negative results too to prevent repeated lookups
                    self._save_to_cache(cache_key, [])
                    return []
                    
                # If we get a name, it's probably valid
                if "shortName" in info or "longName" in info:
                    self.logger.info(f"Valid ticker found: {ticker}")
                    result = [ticker]
                    # Cache the result
                    self._save_to_cache(cache_key, result)
                    return result
                
                # Otherwise cache and return empty list (invalid ticker)
                self.logger.info(f"No name found for ticker: {ticker}")
                self._save_to_cache(cache_key, [])
                return []
                
            except AttributeError as ae:
                self.logger.info(f"AttributeError for ticker {ticker}: {str(ae)}")
                # Cache negative results too
                self._save_to_cache(cache_key, [])
                return []
                
        except Exception as e:
            # Most exceptions here would indicate an invalid ticker
            self.logger.warning(f"Error validating ticker {ticker}: {str(e)}")
            # Don't cache errors - might be temporary
            return []
