"""
Volatility Service

This module provides a service for calculating implied volatility from market data.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from app.services.market_data_provider import MarketDataProvider
from app.services.option_pricing import OptionPricer

logger = logging.getLogger(__name__)

class VolatilityService:
    """
    Service for calculating implied volatility from market option prices.
    
    This service uses real market data to calculate implied volatility
    by finding ATM options and solving for the volatility that matches
    their market prices.
    """
    
    def __init__(self, market_data_provider: MarketDataProvider, option_pricer: OptionPricer):
        """
        Initialize the volatility service.
        
        Args:
            market_data_provider: Provider for market data
            option_pricer: Service for option pricing and IV calculation
        """
        self.market_data_provider = market_data_provider
        self.option_pricer = option_pricer
        self._iv_cache = {}  # Simple cache: {ticker: (timestamp, iv)}
        self.CACHE_EXPIRY_SECONDS = 300  # 5 minutes
        logger.info("VolatilityService initialized")
    
    def get_implied_volatility(self, ticker: str, use_cache: bool = True) -> float:
        """
        Calculate implied volatility for a ticker using market option prices.
        
        This method finds ATM options for a near-term expiration and calculates
        the implied volatility that matches their market prices.
        
        Args:
            ticker: The ticker symbol
            use_cache: Whether to use cached values (if available)
            
        Returns:
            Implied volatility as a float
        """
        # Check cache first if enabled
        import time
        current_time = time.time()
        
        if use_cache and ticker in self._iv_cache:
            timestamp, iv = self._iv_cache[ticker]
            # Use cached value if it's fresh (less than cache expiry time)
            if current_time - timestamp < self.CACHE_EXPIRY_SECONDS:
                logger.info(f"Using cached IV for {ticker}: {iv}")
                return iv
        
        try:
            # Get current stock price
            spot_price = self.market_data_provider.get_stock_price(ticker)
            if not spot_price or spot_price <= 0:
                logger.warning(f"Failed to get valid stock price for {ticker}. Using fallback volatility.")
                return 0.3  # Fallback volatility
            
            # Get available expirations
            expirations = self.market_data_provider.get_option_expirations(ticker)
            if not expirations:
                logger.warning(f"No option expirations found for {ticker}. Using fallback volatility.")
                return 0.3  # Fallback volatility
            
            # Find the nearest expiration that is at least 7 days away
            from datetime import datetime, timedelta
            today = datetime.now().date()
            nearest_expiration = None
            for exp in expirations:
                if isinstance(exp, str):
                    try:
                        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                elif isinstance(exp, datetime):
                    exp_date = exp.date()
                else:
                    continue
                
                days_to_exp = (exp_date - today).days
                if days_to_exp >= 7:
                    nearest_expiration = exp
                    logger.info(f"Selected expiration {exp} ({days_to_exp} days away) for IV calculation")
                    break
            
            if not nearest_expiration:
                logger.warning(f"No suitable expiration found for {ticker}. Using fallback volatility.")
                return 0.3  # Fallback volatility
            
            # Get option chain for nearest expiration
            option_chain = self.market_data_provider.get_option_chain(ticker, nearest_expiration)
            if not option_chain:
                logger.warning(f"Empty option chain for {ticker} at expiration {nearest_expiration}. Using fallback volatility.")
                return 0.3  # Fallback volatility
            
            # Find ATM options (nearest strikes to current price)
            atm_calls = []
            atm_puts = []
            
            # First, filter options that have market prices
            valid_options = []
            for option in option_chain:
                # Check for the required fields and valid prices
                if (
                    'strike' in option and 
                    'option_type' in option and 
                    'ask' in option and option['ask'] > 0 and
                    'bid' in option and option['bid'] > 0 and
                    'expiration' in option
                ):
                    # Use midpoint of bid-ask as the market price
                    option['market_price'] = (option['bid'] + option['ask']) / 2
                    valid_options.append(option)
            
            if not valid_options:
                logger.warning(f"No valid options with prices found for {ticker}. Using fallback volatility.")
                return 0.3  # Fallback volatility
            
            # Sort by distance from ATM
            valid_options.sort(key=lambda x: abs(x['strike'] - spot_price))
            
            # Take the closest few options of each type (call and put)
            for option in valid_options:
                if option['option_type'].lower() == 'call' and len(atm_calls) < 3:
                    atm_calls.append(option)
                elif option['option_type'].lower() == 'put' and len(atm_puts) < 3:
                    atm_puts.append(option)
                
                # Break once we have enough options
                if len(atm_calls) >= 3 and len(atm_puts) >= 3:
                    break
            
            # Calculate IV for each ATM option
            iv_sum = 0.0
            iv_count = 0
            
            # Process all collected ATM options
            all_atm_options = atm_calls + atm_puts
            for option in all_atm_options:
                try:
                    # Extract option details
                    option_type = option['option_type'].lower()
                    strike = option['strike']
                    expiration_date = option['expiration']
                    market_price = option['market_price']
                    
                    # Skip options with very low prices (to avoid numerical issues)
                    if market_price < 0.05:
                        logger.info(f"Skipping {option_type} with very low price ${market_price} for IV calculation")
                        continue
                    
                    # Calculate implied volatility
                    iv = self.option_pricer.calculate_implied_volatility(
                        option_type=option_type,
                        strike=strike,
                        expiration_date=expiration_date,
                        spot_price=spot_price,
                        option_price=market_price,
                        american=True  # Assume American options
                    )
                    
                    # Validate the IV (should be between 1% and 200%)
                    if 0.01 <= iv <= 2.0:
                        iv_sum += iv
                        iv_count += 1
                        logger.info(f"Calculated IV for {ticker} {option_type} (K={strike}): {iv:.4f}")
                    else:
                        logger.warning(f"Calculated IV outside valid range: {iv:.4f} for {ticker} {option_type} (K={strike})")
                
                except Exception as e:
                    logger.warning(f"Error calculating IV for one option: {e}")
            
            # Calculate average IV
            if iv_count > 0:
                avg_iv = iv_sum / iv_count
                logger.info(f"Average IV for {ticker} from {iv_count} options: {avg_iv:.4f}")
                
                # Update cache
                self._iv_cache[ticker] = (current_time, avg_iv)
                
                return avg_iv
            else:
                logger.warning(f"Could not calculate IV for any option. Using fallback volatility.")
                return 0.3  # Fallback volatility
        
        except Exception as e:
            logger.error(f"Error calculating implied volatility for {ticker}: {e}")
            return 0.3  # Fallback volatility