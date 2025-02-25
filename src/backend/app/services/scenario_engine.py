import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import pandas as pd

from app.services.option_pricing import OptionPricer


class ScenarioEngine:
    """
    Engine for running scenario analyses on option positions.
    Calculates P&L and Greeks across different price, volatility, and time scenarios.
    """
    
    def __init__(self):
        """Initialize the scenario engine with an option pricer."""
        self.option_pricer = OptionPricer()
    
    def _generate_price_range(
        self, 
        current_price: float, 
        min_pct: float = -0.2, 
        max_pct: float = 0.2, 
        steps: int = 41
    ) -> np.ndarray:
        """
        Generate a range of prices for scenario analysis.
        
        Args:
            current_price: Current price of the underlying
            min_pct: Minimum percentage change from current price
            max_pct: Maximum percentage change from current price
            steps: Number of steps in the range
            
        Returns:
            Array of prices
        """
        min_price = current_price * (1 + min_pct)
        max_price = current_price * (1 + max_pct)
        return np.linspace(min_price, max_price, steps)
    
    def _generate_vol_range(
        self, 
        current_vol: float, 
        min_pct: float = -0.5, 
        max_pct: float = 0.5, 
        steps: int = 21
    ) -> np.ndarray:
        """
        Generate a range of volatilities for scenario analysis.
        
        Args:
            current_vol: Current implied volatility
            min_pct: Minimum percentage change from current volatility
            max_pct: Maximum percentage change from current volatility
            steps: Number of steps in the range
            
        Returns:
            Array of volatilities
        """
        min_vol = max(0.01, current_vol * (1 + min_pct))
        max_vol = current_vol * (1 + max_pct)
        return np.linspace(min_vol, max_vol, steps)
    
    def _generate_time_range(
        self, 
        days_to_expiry: int, 
        min_days: int = 0, 
        steps: int = 11
    ) -> np.ndarray:
        """
        Generate a range of days to expiry for scenario analysis.
        
        Args:
            days_to_expiry: Current days to expiry
            min_days: Minimum days to expiry
            steps: Number of steps in the range
            
        Returns:
            Array of days to expiry
        """
        return np.linspace(min_days, days_to_expiry, steps).astype(int)
    
    def price_vs_vol_surface(
        self, 
        positions: List[Dict], 
        current_price: float,
        current_vol: float,
        price_range: Optional[Dict] = None,
        vol_range: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate a price vs. volatility surface for a set of positions.
        
        Args:
            positions: List of position dictionaries
            current_price: Current price of the underlying
            current_vol: Current implied volatility
            price_range: Dictionary with min_pct, max_pct, steps for price range
            vol_range: Dictionary with min_pct, max_pct, steps for volatility range
            
        Returns:
            Dictionary with price and volatility arrays and P&L matrix
        """
        # Set default ranges if not provided
        price_range = price_range or {"min_pct": -0.2, "max_pct": 0.2, "steps": 41}
        vol_range = vol_range or {"min_pct": -0.5, "max_pct": 0.5, "steps": 21}
        
        # Generate price and volatility arrays
        prices = self._generate_price_range(
            current_price, 
            price_range["min_pct"], 
            price_range["max_pct"], 
            price_range["steps"]
        )
        vols = self._generate_vol_range(
            current_vol, 
            vol_range["min_pct"], 
            vol_range["max_pct"], 
            vol_range["steps"]
        )
        
        # Initialize P&L matrix
        pnl_matrix = np.zeros((len(vols), len(prices)))
        
        # Calculate initial position values
        initial_values = {}
        for pos in positions:
            option_result = self.option_pricer.price_option(
                option_type=pos["option_type"],
                strike=pos["strike"],
                expiration_date=pos["expiration"],
                spot_price=current_price,
                volatility=current_vol
            )
            initial_values[pos["id"]] = option_result["price"] * pos["quantity"]
            
            # Adjust sign based on buy/sell
            if pos["action"] == "sell":
                initial_values[pos["id"]] *= -1
        
        # Calculate P&L for each price and volatility combination
        for i, vol in enumerate(vols):
            for j, price in enumerate(prices):
                total_pnl = 0
                
                for pos in positions:
                    # Calculate new option value
                    option_result = self.option_pricer.price_option(
                        option_type=pos["option_type"],
                        strike=pos["strike"],
                        expiration_date=pos["expiration"],
                        spot_price=price,
                        volatility=vol
                    )
                    
                    new_value = option_result["price"] * pos["quantity"]
                    
                    # Adjust sign based on buy/sell
                    if pos["action"] == "sell":
                        new_value *= -1
                    
                    # Calculate P&L
                    pnl = new_value - initial_values[pos["id"]]
                    total_pnl += pnl
                
                pnl_matrix[i, j] = total_pnl
        
        return {
            "prices": prices.tolist(),
            "vols": vols.tolist(),
            "pnl": pnl_matrix.tolist()
        }
    
    def price_vs_time_surface(
        self, 
        positions: List[Dict], 
        current_price: float,
        current_vol: float,
        price_range: Optional[Dict] = None,
        days_range: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate a price vs. time surface for a set of positions.
        
        Args:
            positions: List of position dictionaries
            current_price: Current price of the underlying
            current_vol: Current implied volatility
            price_range: Dictionary with min_pct, max_pct, steps for price range
            days_range: Dictionary with min_days, steps for days range
            
        Returns:
            Dictionary with price and days arrays and P&L matrix
        """
        # Set default ranges if not provided
        price_range = price_range or {"min_pct": -0.2, "max_pct": 0.2, "steps": 41}
        
        # Find maximum days to expiry
        max_days_to_expiry = 0
        for pos in positions:
            days = (pos["expiration"] - datetime.now()).days
            max_days_to_expiry = max(max_days_to_expiry, days)
        
        days_range = days_range or {"min_days": 0, "steps": 11}
        
        # Generate price and days arrays
        prices = self._generate_price_range(
            current_price, 
            price_range["min_pct"], 
            price_range["max_pct"], 
            price_range["steps"]
        )
        days = self._generate_time_range(
            max_days_to_expiry, 
            days_range["min_days"], 
            days_range["steps"]
        )
        
        # Initialize P&L matrix
        pnl_matrix = np.zeros((len(days), len(prices)))
        
        # Calculate initial position values
        initial_values = {}
        for pos in positions:
            option_result = self.option_pricer.price_option(
                option_type=pos["option_type"],
                strike=pos["strike"],
                expiration_date=pos["expiration"],
                spot_price=current_price,
                volatility=current_vol
            )
            initial_values[pos["id"]] = option_result["price"] * pos["quantity"]
            
            # Adjust sign based on buy/sell
            if pos["action"] == "sell":
                initial_values[pos["id"]] *= -1
        
        # Calculate P&L for each price and days combination
        for i, day in enumerate(days):
            for j, price in enumerate(prices):
                total_pnl = 0
                
                for pos in positions:
                    # Calculate new expiration date
                    days_to_expiry = (pos["expiration"] - datetime.now()).days
                    new_days_to_expiry = min(days_to_expiry, day)
                    new_expiration = datetime.now() + timedelta(days=new_days_to_expiry)
                    
                    # Calculate new option value
                    option_result = self.option_pricer.price_option(
                        option_type=pos["option_type"],
                        strike=pos["strike"],
                        expiration_date=new_expiration,
                        spot_price=price,
                        volatility=current_vol
                    )
                    
                    new_value = option_result["price"] * pos["quantity"]
                    
                    # Adjust sign based on buy/sell
                    if pos["action"] == "sell":
                        new_value *= -1
                    
                    # Calculate P&L
                    pnl = new_value - initial_values[pos["id"]]
                    total_pnl += pnl
                
                pnl_matrix[i, j] = total_pnl
        
        return {
            "prices": prices.tolist(),
            "days": days.tolist(),
            "pnl": pnl_matrix.tolist()
        }
    
    def calculate_greeks_profile(
        self, 
        positions: List[Dict], 
        current_price: float,
        current_vol: float,
        price_range: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate Greeks profiles for a set of positions.
        
        Args:
            positions: List of position dictionaries
            current_price: Current price of the underlying
            current_vol: Current implied volatility
            price_range: Dictionary with min_pct, max_pct, steps for price range
            
        Returns:
            Dictionary with price array and Greeks arrays
        """
        # Set default ranges if not provided
        price_range = price_range or {"min_pct": -0.2, "max_pct": 0.2, "steps": 41}
        
        # Generate price array
        prices = self._generate_price_range(
            current_price, 
            price_range["min_pct"], 
            price_range["max_pct"], 
            price_range["steps"]
        )
        
        # Initialize Greeks arrays
        delta_array = np.zeros(len(prices))
        gamma_array = np.zeros(len(prices))
        theta_array = np.zeros(len(prices))
        vega_array = np.zeros(len(prices))
        rho_array = np.zeros(len(prices))
        
        # Calculate Greeks for each price
        for i, price in enumerate(prices):
            total_delta = 0
            total_gamma = 0
            total_theta = 0
            total_vega = 0
            total_rho = 0
            
            for pos in positions:
                # Calculate option Greeks
                option_result = self.option_pricer.price_option(
                    option_type=pos["option_type"],
                    strike=pos["strike"],
                    expiration_date=pos["expiration"],
                    spot_price=price,
                    volatility=current_vol
                )
                
                # Adjust sign based on buy/sell and multiply by quantity
                sign = -1 if pos["action"] == "sell" else 1
                quantity = pos["quantity"]
                
                total_delta += option_result["delta"] * sign * quantity
                total_gamma += option_result["gamma"] * sign * quantity
                total_theta += option_result["theta"] * sign * quantity
                total_vega += option_result["vega"] * sign * quantity
                total_rho += option_result["rho"] * sign * quantity
            
            delta_array[i] = total_delta
            gamma_array[i] = total_gamma
            theta_array[i] = total_theta
            vega_array[i] = total_vega
            rho_array[i] = total_rho
        
        return {
            "prices": prices.tolist(),
            "delta": delta_array.tolist(),
            "gamma": gamma_array.tolist(),
            "theta": theta_array.tolist(),
            "vega": vega_array.tolist(),
            "rho": rho_array.tolist()
        } 