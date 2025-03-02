"""
Volatility Service

This module provides services for retrieving and calculating volatility data
for option pricing and analysis.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta

from app.services.market_data import MarketDataService

logger = logging.getLogger(__name__)

class VolatilityService:
    """
    Service for retrieving and calculating volatility metrics
    including implied volatility and historical volatility.
    """
    
    def __init__(self, market_data_service: MarketDataService):
        """
        Initialize the volatility service.
        
        Args:
            market_data_service: Service for retrieving market data
        """
        self.market_data_service = market_data_service
    
    def get_implied_volatility(self, ticker: str) -> float:
        """
        Get the implied volatility for a ticker.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Implied volatility as a float
        """
        # Delegate to market data service
        return self.market_data_service.get_implied_volatility(ticker)
    
    def get_historical_volatility(
        self,
        ticker: str,
        days: int = 30,
        annualize: bool = True
    ) -> float:
        """
        Calculate historical volatility for a ticker based on past price data.
        
        Args:
            ticker: Ticker symbol
            days: Number of days to look back
            annualize: Whether to annualize the volatility
            
        Returns:
            Historical volatility as a float
        """
        try:
            # Get historical price data for the specified number of days
            # Add buffer days to ensure we have enough data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 10)  # Add buffer
            
            price_data = self.market_data_service.get_historical_prices(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                interval="day"
            )
            
            # Extract closing prices and calculate daily returns
            if not price_data or len(price_data) < 2:
                logger.warning(f"Not enough historical data for {ticker} to calculate volatility")
                return 0.3  # Default volatility
            
            # Extract closing prices
            closing_prices = []
            for data_point in price_data:
                if 'close' in data_point:
                    closing_prices.append(data_point['close'])
            
            # Ensure we have enough data
            if len(closing_prices) < 2:
                logger.warning(f"Not enough valid closing prices for {ticker}")
                return 0.3  # Default volatility
            
            # Convert to numpy array and calculate log returns
            prices = np.array(closing_prices)
            log_returns = np.diff(np.log(prices))
            
            # Calculate standard deviation of log returns
            volatility = np.std(log_returns)
            
            # Annualize if requested (assuming 252 trading days per year)
            if annualize:
                volatility *= np.sqrt(252)
            
            logger.info(f"Calculated historical volatility for {ticker}: {volatility}")
            return float(volatility)
        except Exception as e:
            logger.error(f"Error calculating historical volatility for {ticker}: {str(e)}")
            return 0.3  # Default volatility
    
    def get_volatility_surface(
        self,
        ticker: str,
        expiration_dates: Optional[List[datetime]] = None
    ) -> Dict:
        """
        Get the volatility surface for a ticker across different strikes and expirations.
        
        Args:
            ticker: Ticker symbol
            expiration_dates: List of expiration dates to include
            
        Returns:
            Dictionary with volatility surface data
        """
        # Implementation would need to leverage option chain data and compute IV for each strike/expiry
        # This is a simplified placeholder implementation
        result = {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "surface": []
        }
        
        # Get available expiration dates if not provided
        if not expiration_dates:
            try:
                expiration_dates = self.market_data_service.get_option_expirations(ticker)
            except Exception as e:
                logger.error(f"Error getting expiration dates for {ticker}: {str(e)}")
                return result
        
        # Get volatility data for each expiration
        for expiry in expiration_dates:
            try:
                # Get option chain for this expiration
                option_chain = self.market_data_service.get_option_chain(
                    ticker=ticker,
                    expiration_date=expiry
                )
                
                # Process option chain to extract IVs
                strikes_data = []
                for option in option_chain:
                    if 'strike' in option and 'implied_volatility' in option:
                        strikes_data.append({
                            "strike": option['strike'],
                            "call_iv": option['implied_volatility'] if option.get('option_type') == 'call' else None,
                            "put_iv": option['implied_volatility'] if option.get('option_type') == 'put' else None
                        })
                
                result["surface"].append({
                    "expiration_date": expiry.isoformat(),
                    "strikes": strikes_data
                })
            except Exception as e:
                logger.error(f"Error processing volatility data for {ticker} expiry {expiry}: {str(e)}")
        
        return result
    
    def get_term_structure(self, ticker: str) -> Dict:
        """
        Get the volatility term structure for a ticker.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Dictionary with term structure data
        """
        result = {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "term_structure": []
        }
        
        try:
            # Get ATM volatility for different expirations
            expirations = self.market_data_service.get_option_expirations(ticker)
            current_price = self.market_data_service.get_stock_price(ticker)
            
            for expiry in expirations:
                # Find the ATM strike
                strikes = self.market_data_service.get_option_strikes(
                    ticker=ticker,
                    expiration_date=expiry
                )
                
                # Simplified approach to find ATM strike
                if not strikes:
                    continue
                
                atm_strike = min(strikes, key=lambda x: abs(x - current_price))
                
                # Get option data for ATM strike
                option_data = self.market_data_service.get_option_data(
                    ticker=ticker,
                    expiration_date=expiry,
                    strike=atm_strike,
                    option_type='call'
                )
                
                # Extract IV
                if option_data and 'implied_volatility' in option_data:
                    days_to_expiry = (expiry - datetime.now()).days
                    result["term_structure"].append({
                        "days_to_expiry": days_to_expiry,
                        "expiration_date": expiry.isoformat(),
                        "implied_volatility": option_data['implied_volatility']
                    })
        except Exception as e:
            logger.error(f"Error getting volatility term structure for {ticker}: {str(e)}")
        
        return result
