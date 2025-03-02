import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any, Union


class MarketDataProvider(ABC):
    """
    Abstract base class for market data providers.
    Defines the interface that all market data providers must implement.
    """
    
    @abstractmethod
    def get_ticker_details(self, ticker: str) -> Dict:
        """
        Get detailed information about a ticker symbol.
        
        Args:
            ticker: The ticker symbol to look up
            
        Returns:
            Ticker details dictionary
        """
        pass
    
    @abstractmethod
    def get_stock_price(self, ticker: str) -> float:
        """
        Get the latest price for a stock.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            Latest price as float
        """
        pass
    
    @abstractmethod
    def get_option_chain(self, ticker: str, expiration_date: Optional[str] = None) -> List[Dict]:
        """
        Get the option chain for a ticker.
        
        Args:
            ticker: The ticker symbol
            expiration_date: Option expiration date (YYYY-MM-DD)
            
        Returns:
            List of option details as dictionaries
        """
        pass
    
    @abstractmethod
    def get_option_price(self, option_symbol: str) -> Dict:
        """
        Get the latest price for an option.
        
        Args:
            option_symbol: Option symbol
            
        Returns:
            Option price data as dictionary
        """
        pass
    
    @abstractmethod
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
            List of historical price data as dictionaries
        """
        pass
    
    @abstractmethod
    def get_implied_volatility(self, ticker: str) -> float:
        """
        Get the implied volatility for a ticker.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            Implied volatility as float
        """
        pass
    
    @abstractmethod
    def get_option_expirations(self, ticker: str) -> Dict:
        """
        Get available expiration dates for options on a ticker.
        
        Args:
            ticker: The ticker symbol
            
        Returns:
            Dictionary with expiration dates
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def search_tickers(self, query: str) -> List[str]:
        """
        Search for ticker symbols matching a query.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching ticker symbols
        """
        pass
