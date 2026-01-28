"""
Market Data Service

This module provides a service for retrieving market data from different data sources.
It supports multiple providers (Polygon.io and YFinance) and can be configured via
environment variables.
"""

import os
import logging
from typing import Dict, List, Optional, Union
from datetime import datetime

from app.services.market_data_provider import MarketDataProvider
from app.services.polygon_provider import PolygonProvider
from app.services.yfinance_provider import YFinanceProvider
from app.services.volatility_service import VolatilityService
from app.services.option_pricing import OptionPricer

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Service for retrieving market data from different sources.
    
    This service acts as a factory for concrete market data providers
    and delegates method calls to the currently selected provider.
    """
    
    def __init__(
        self,
        provider: Optional[MarketDataProvider] = None,
        provider_name: Optional[str] = None,
        use_cache: Optional[bool] = None,
    ):
        """
        Initialize the market data service.
        
        The provider is selected based on the MARKET_DATA_PROVIDER
        environment variable. If not specified, defaults to YFinance.

        Args:
            provider: Optional provider instance to use directly.
            provider_name: Optional provider name override (yfinance or polygon).
            use_cache: Optional cache toggle for providers that support it.
        """
        self.provider = provider or self._get_provider(
            provider_name=provider_name,
            use_cache=use_cache,
        )
        self.option_pricer = OptionPricer()
        self.volatility_service = VolatilityService(self.provider, self.option_pricer)
        logger.info(f"Using market data provider: {self.provider.__class__.__name__}")
    
    def _get_provider(
        self,
        provider_name: Optional[str] = None,
        use_cache: Optional[bool] = None,
    ) -> MarketDataProvider:
        """
        Factory method to get the appropriate market data provider.
        
        Returns:
            A concrete implementation of MarketDataProvider
        """
        resolved_provider = (
            provider_name or os.getenv("MARKET_DATA_PROVIDER", "yfinance")
        ).lower()

        if resolved_provider == "polygon":
            if use_cache is None:
                return PolygonProvider()
            return PolygonProvider(use_cache=use_cache)
        if resolved_provider == "yfinance":
            if use_cache is None:
                return YFinanceProvider()
            return YFinanceProvider(use_cache=use_cache)

        logger.warning(
            f"Unknown provider '{resolved_provider}', defaulting to YFinance"
        )
        if use_cache is None:
            return YFinanceProvider()
        return YFinanceProvider(use_cache=use_cache)
    
    def get_ticker_details(self, ticker: str) -> Dict:
        """
        Get detailed information about a ticker symbol.
        
        Args:
            ticker: The ticker symbol to look up
            
        Returns:
            Dictionary with ticker details including name, exchange, etc.
        """
        return self.provider.get_ticker_details(ticker)
    
    def get_stock_price(self, ticker: str) -> float:
        """
        Get the current stock price for a ticker.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            Current stock price
        """
        return self.provider.get_stock_price(ticker)
    
    def get_option_chain(
        self, 
        ticker: str, 
        expiration_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get option chain data for a ticker.
        
        Args:
            ticker: The ticker symbol
            expiration_date: Optional expiration date filter
            
        Returns:
            List of option contracts with details
        """
        return self.provider.get_option_chain(ticker, expiration_date)
    
    def get_option_expirations(self, ticker: str) -> List[datetime]:
        """
        Get available expiration dates for options on a ticker.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            List of available expiration dates
        """
        # Get expirations from provider (could be Dict with string expirations or other format)
        provider_expirations = self.provider.get_option_expirations(ticker)
        
        # Handle the case where the provider returns a Dict with "expirations" key
        if isinstance(provider_expirations, dict) and "expirations" in provider_expirations:
            expiration_strings = provider_expirations["expirations"]
        else:
            # If it's already a list of datetimes, return it directly
            if provider_expirations and isinstance(provider_expirations[0], datetime):
                return provider_expirations
            # Otherwise assume it's a list of string dates
            expiration_strings = provider_expirations
        
        # Convert string dates to datetime objects
        expiration_dates = []
        for exp_str in expiration_strings:
            try:
                # Parse the date string (assuming format is YYYY-MM-DD)
                expiration_date = datetime.strptime(exp_str, "%Y-%m-%d")
                expiration_dates.append(expiration_date)
            except (ValueError, TypeError) as e:
                logging.warning(f"Error parsing expiration date {exp_str}: {e}")
        
        return expiration_dates
    
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
        return self.provider.get_option_strikes(ticker, expiration_date, option_type)
    
    def get_historical_prices(
        self, 
        ticker: str, 
        start_date: datetime, 
        end_date: datetime, 
        interval: str = "day"
    ) -> List[Dict]:
        """
        Get historical price data for a ticker.
        
        Args:
            ticker: The ticker symbol
            start_date: Start date for data (inclusive)
            end_date: End date for data (inclusive)
            interval: Time interval between data points (day, hour, minute)
            
        Returns:
            List of data points with OHLCV data
        """
        return self.provider.get_historical_prices(ticker, start_date, end_date, interval)
    
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
        return self.provider.get_option_data(ticker, expiration_date, strike, option_type)
    
    def search_tickers(self, query: str) -> List[Dict]:
        """
        Search for ticker symbols matching a query.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching ticker symbols with metadata
        """
        logger.info(f"MarketDataService.search_tickers called with query: {query}")
        try:
            logger.info(f"Delegating to provider: {self.provider.__class__.__name__}")
            results = self.provider.search_tickers(query)
            logger.info(f"Provider returned results: {results}")
            return results
        except Exception as e:
            logger.error(f"Error in MarketDataService.search_tickers: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Return empty list instead of raising to avoid breaking the frontend
            return []
    
    def get_market_status(self) -> Dict:
        """
        Get current market status information.
        
        Returns:
            Dictionary with market status (open/closed, etc.)
        """
        return self.provider.get_market_status()
    
    def get_earnings_calendar(
        self, 
        ticker: Optional[str] = None, 
        from_date: Optional[datetime] = None, 
        to_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get earnings announcement calendar data.
        
        Args:
            ticker: Optional ticker filter
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            List of earnings announcements
        """
        return self.provider.get_earnings_calendar(ticker, from_date, to_date)
    
    def get_economic_calendar(
        self, 
        from_date: Optional[datetime] = None, 
        to_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get economic event calendar data.
        
        Args:
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            List of economic events
        """
        if hasattr(self.provider, 'get_economic_calendar'):
            return self.provider.get_economic_calendar(from_date, to_date)
        else:
            return []
    
    def get_implied_volatility(self, ticker: str) -> float:
        """
        Get the implied volatility for a ticker.
        
        This method calculates implied volatility using market option prices
        by finding ATM options and averaging their IVs.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Implied volatility as a float
        """
        try:
            return self.volatility_service.get_implied_volatility(ticker)
        except Exception as e:
            logger.error(f"Error getting implied volatility for {ticker}: {e}")
            logger.warning(f"Using fallback volatility (0.3) for {ticker}")
            return 0.3  # Fallback to 30% if calculation fails
