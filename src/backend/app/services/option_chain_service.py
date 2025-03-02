"""
Option Chain Service

This module provides a service for retrieving option chain data for a given ticker.
It caches the data to minimize API calls and provides filtering capabilities.
"""

import logging
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from functools import lru_cache

from app.services.market_data import MarketDataService

logger = logging.getLogger(__name__)

class OptionChainService:
    """
    Service for retrieving and managing option chain data.
    
    This service utilizes the MarketDataService to fetch option chains
    and provides additional filtering and caching capabilities.
    """
    
    def __init__(self, market_data_service: MarketDataService = None):
        """
        Initialize the option chain service.
        
        Args:
            market_data_service: An instance of MarketDataService or None (will create one if None)
        """
        self.market_data_service = market_data_service or MarketDataService()
        self._cache = {}  # In-memory cache
        self._cache_ttl = 300  # Cache TTL in seconds (5 minutes)
    
    def get_option_chain(
        self, 
        ticker: str, 
        expiration_date: Optional[datetime] = None,
        option_type: Optional[str] = None,
        min_strike: Optional[float] = None,
        max_strike: Optional[float] = None
    ) -> List[Dict]:
        """
        Get option chain data for a ticker with optional filtering.
        
        Args:
            ticker: The ticker symbol
            expiration_date: Optional expiration date filter
            option_type: Optional option type filter ('call' or 'put')
            min_strike: Optional minimum strike price filter
            max_strike: Optional maximum strike price filter
            
        Returns:
            List of option contracts with details
        """
        # Use normalized ticker for cache key
        normalized_ticker = ticker.upper().strip()
        
        # Create cache key
        cache_key = f"option_chain:{normalized_ticker}"
        if expiration_date:
            cache_key += f":{expiration_date.strftime('%Y-%m-%d')}"
            
        # Check cache
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for {cache_key}")
            option_chain = cached_data
        else:
            # Fetch from market data service
            try:
                option_chain = self.market_data_service.get_option_chain(
                    normalized_ticker, expiration_date
                )
                # Cache the result
                self._add_to_cache(cache_key, option_chain)
            except Exception as e:
                logger.error(f"Error fetching option chain for {normalized_ticker}: {e}")
                raise
        
        # Apply filters
        filtered_chain = option_chain
        
        if option_type:
            filtered_chain = [
                option for option in filtered_chain 
                if option.get("option_type", "").lower() == option_type.lower()
            ]
            
        if min_strike is not None:
            filtered_chain = [
                option for option in filtered_chain 
                if option.get("strike", 0) >= min_strike
            ]
            
        if max_strike is not None:
            filtered_chain = [
                option for option in filtered_chain 
                if option.get("strike", 0) <= max_strike
            ]
            
        return filtered_chain
    
    def get_expirations(self, ticker: str) -> List[datetime]:
        """
        Get available expiration dates for options on a ticker.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            List of available expiration dates
        """
        normalized_ticker = ticker.upper().strip()
        cache_key = f"option_expirations:{normalized_ticker}"
        
        # Check cache
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for {cache_key}")
            return cached_data
        
        # Fetch from market data service
        try:
            expirations = self.market_data_service.get_option_expirations(normalized_ticker)
            # Cache the result
            self._add_to_cache(cache_key, expirations)
            return expirations
        except Exception as e:
            logger.error(f"Error fetching expirations for {normalized_ticker}: {e}")
            raise
    
    def get_option_data(
        self, 
        ticker: str, 
        expiration_date: datetime, 
        strike: float, 
        option_type: str
    ) -> Dict:
        """
        Get detailed data for a specific option contract.
        
        Args:
            ticker: The underlying ticker symbol
            expiration_date: Option expiration date
            strike: Strike price
            option_type: Option type (call or put)
            
        Returns:
            Dictionary with option contract data
        """
        normalized_ticker = ticker.upper().strip()
        normalized_option_type = option_type.lower()
        
        # Validate option_type
        if normalized_option_type not in ['call', 'put']:
            raise ValueError(f"Invalid option type: {option_type}. Must be 'call' or 'put'.")
        
        # Create cache key
        cache_key = (
            f"option_data:{normalized_ticker}:{expiration_date.strftime('%Y-%m-%d')}:"
            f"{strike}:{normalized_option_type}"
        )
        
        # Check cache
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for {cache_key}")
            return cached_data
        
        # Fetch from market data service
        try:
            option_data = self.market_data_service.get_option_data(
                normalized_ticker, expiration_date, strike, normalized_option_type
            )
            # Cache the result
            self._add_to_cache(cache_key, option_data)
            return option_data
        except Exception as e:
            logger.error(
                f"Error fetching option data for {normalized_ticker} "
                f"{expiration_date.strftime('%Y-%m-%d')} {strike} {normalized_option_type}: {e}"
            )
            raise
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """
        Get data from the cache if it exists and is not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found or expired
        """
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() < entry["expires_at"]:
                return entry["data"]
            else:
                # Remove expired entry
                del self._cache[key]
        return None
    
    def _add_to_cache(self, key: str, data: Any) -> None:
        """
        Add data to the cache with an expiration time.
        
        Args:
            key: Cache key
            data: Data to cache
        """
        expires_at = datetime.now() + timedelta(seconds=self._cache_ttl)
        self._cache[key] = {
            "data": data,
            "expires_at": expires_at
        }

    def clear_cache(self) -> None:
        """
        Clear the entire cache.
        """
        self._cache = {}
    
    def remove_from_cache(self, key_prefix: str) -> int:
        """
        Remove all cache entries with keys starting with the given prefix.
        
        Args:
            key_prefix: Cache key prefix to match
            
        Returns:
            Number of entries removed
        """
        keys_to_remove = [key for key in self._cache if key.startswith(key_prefix)]
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)
