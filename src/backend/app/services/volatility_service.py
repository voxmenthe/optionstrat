import numpy as np
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from functools import lru_cache
import math

from app.services.market_data_provider import MarketDataProvider

# Setup logging
logger = logging.getLogger(__name__)

class VolatilityService:
    """Service for calculating historical and implied volatility."""
    
    def __init__(self, market_data_provider: MarketDataProvider):
        """Initialize with a market data provider."""
        self.market_data_provider = market_data_provider
        self.price_cache = {}  # Cache for historical prices
        self.vol_cache = {}    # Cache for calculated volatilities
    
    @lru_cache(maxsize=100)
    def calculate_historical_volatility(self, ticker: str, days: int = 30) -> float:
        """
        Calculate historical volatility for a ticker over the specified number of days.
        
        Args:
            ticker: The ticker symbol
            days: Number of days to use for calculation
            
        Returns:
            Annualized historical volatility as a decimal (e.g., 0.25 for 25%)
        """
        try:
            # Get historical prices - in practice, this would call an external API
            # We'd need to extend the market data provider to support historical data
            # For now, we'll simulate with a simplified implementation
            
            # Check if we have cached prices
            cache_key = f"{ticker}:{days}"
            if cache_key in self.vol_cache:
                logger.info(f"Cache hit for volatility {cache_key}")
                return self.vol_cache[cache_key]
                
            # In real implementation, we would fetch from the market data provider:
            # historical_prices = self.market_data_provider.get_historical_prices(
            #     ticker, 
            #     (datetime.now() - timedelta(days=days*2)), 
            #     datetime.now()
            # )
            
            # For now, we'll use a default
            default_volatility = 0.3  # 30%
            logger.warning(f"Historical data not available for {ticker}, using default volatility of {default_volatility}")
            
            # Cache the result for future use
            self.vol_cache[cache_key] = default_volatility
            return default_volatility
            
        except Exception as e:
            logger.error(f"Error calculating historical volatility: {str(e)}")
            return 0.3  # Default 30% volatility
    
    @staticmethod
    def calculate_volatility_from_prices(prices: List[float]) -> float:
        """
        Calculate historical volatility from a list of prices.
        
        Args:
            prices: List of historical prices
            
        Returns:
            Annualized volatility
        """
        if len(prices) < 2:
            return 0.3  # Default if not enough data
            
        # Calculate returns
        returns = np.diff(np.log(prices))
        
        # Calculate standard deviation of returns
        std_dev = np.std(returns, ddof=1)
        
        # Annualize (approximate trading days in a year)
        trading_days = 252
        annualized_vol = std_dev * math.sqrt(trading_days)
        
        return annualized_vol
    
    def get_combined_volatility(self, ticker: str, days: int = 30) -> Dict[str, float]:
        """
        Get both historical and implied volatility.
        
        Args:
            ticker: The ticker symbol
            days: Number of days for historical calculation
            
        Returns:
            Dictionary with both volatility values
        """
        historical_vol = self.calculate_historical_volatility(ticker, days)
        implied_vol = self.market_data_provider.get_implied_volatility(ticker)
        
        return {
            "historical_volatility": historical_vol,
            "implied_volatility": implied_vol
        }
