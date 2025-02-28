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
    
    def __init__(self, option_pricer=None):
        """Initialize the scenario engine with an option pricer."""
        self.option_pricer = option_pricer if option_pricer is not None else OptionPricer()
    
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
            "prices": prices,
            "vols": vols,
            "pnl": pnl_matrix
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
            "prices": prices,
            "days": days,
            "pnl": pnl_matrix
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
            "prices": prices,
            "delta": delta_array,
            "gamma": gamma_array,
            "theta": theta_array,
            "vega": vega_array,
            "rho": rho_array
        }
    
    def generate_price_vs_volatility_surface(
        self,
        option_type: str,
        strike: float,
        expiration_date: datetime,
        spot_price_range: np.ndarray,
        volatility_range: np.ndarray,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0,
        american: bool = False
    ) -> Dict:
        """
        Generate a surface of option prices and Greeks for different spot prices and volatilities.
        
        Args:
            option_type: "call" or "put"
            strike: Strike price
            expiration_date: Option expiration date
            spot_price_range: Array of spot prices
            volatility_range: Array of volatilities
            risk_free_rate: Risk-free interest rate
            dividend_yield: Dividend yield
            american: Whether the option is American (True) or European (False)
            
        Returns:
            Dictionary with spot prices, volatilities, and surfaces for price and Greeks
        """
        # Initialize matrices for price and Greeks
        # Matrices have shape (len(volatility_range), len(spot_price_range))
        # Access values using matrix[vol_idx, spot_idx]
        price_surface = np.zeros((len(volatility_range), len(spot_price_range)))
        delta_surface = np.zeros((len(volatility_range), len(spot_price_range)))
        gamma_surface = np.zeros((len(volatility_range), len(spot_price_range)))
        theta_surface = np.zeros((len(volatility_range), len(spot_price_range)))
        vega_surface = np.zeros((len(volatility_range), len(spot_price_range)))
        
        # Calculate price and Greeks for each combination of spot price and volatility
        for i, vol in enumerate(volatility_range):
            for j, spot in enumerate(spot_price_range):
                # i is the volatility index, j is the spot price index
                result = self.option_pricer.price_option(
                    option_type=option_type,
                    strike=strike,
                    expiration_date=expiration_date,
                    spot_price=spot,
                    volatility=vol,
                    risk_free_rate=risk_free_rate,
                    dividend_yield=dividend_yield,
                    american=american
                )
                
                price_surface[i, j] = result["price"]
                delta_surface[i, j] = result["delta"]
                gamma_surface[i, j] = result["gamma"]
                theta_surface[i, j] = result["theta"]
                vega_surface[i, j] = result["vega"]
        
        return {
            "spot_price_values": spot_price_range,
            "volatility_values": volatility_range,
            "price_surface": price_surface,  # Matrix indexed as [vol_idx, spot_idx]
            "delta_surface": delta_surface,
            "gamma_surface": gamma_surface,
            "theta_surface": theta_surface,
            "vega_surface": vega_surface
        }
    
    def generate_time_decay_analysis(
        self,
        option_type: str,
        strike: float,
        expiration_date: datetime,
        spot_price: float,
        volatility: float,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0,
        american: bool = False,
        days_range: np.ndarray = None
    ) -> Dict:
        """
        Generate an analysis of option price and Greeks over time.
        
        Args:
            option_type: "call" or "put"
            strike: Strike price
            expiration_date: Option expiration date
            spot_price: Current spot price
            volatility: Implied volatility
            risk_free_rate: Risk-free interest rate
            dividend_yield: Dividend yield
            american: Whether the option is American (True) or European (False)
            days_range: Array of days to expiry
            
        Returns:
            Dictionary with days and arrays for price and Greeks
        """
        # Calculate days to expiry
        days_to_expiry = (expiration_date - datetime.now()).days
        
        # Generate days range if not provided
        if days_range is None:
            days_range = np.linspace(0, days_to_expiry, 7)
        
        # Initialize arrays for price and Greeks
        price_values = np.zeros(len(days_range))
        delta_values = np.zeros(len(days_range))
        gamma_values = np.zeros(len(days_range))
        theta_values = np.zeros(len(days_range))
        vega_values = np.zeros(len(days_range))
        
        # Calculate price and Greeks for each day
        for i, days in enumerate(days_range):
            # Calculate new expiration date
            new_expiration = datetime.now() + timedelta(days=int(days))
            
            # If new_expiration is after the original expiration, use the original
            if new_expiration > expiration_date:
                new_expiration = expiration_date
            
            result = self.option_pricer.price_option(
                option_type=option_type,
                strike=strike,
                expiration_date=new_expiration,
                spot_price=spot_price,
                volatility=volatility,
                risk_free_rate=risk_free_rate,
                dividend_yield=dividend_yield,
                american=american
            )
            
            price_values[i] = result["price"]
            delta_values[i] = result["delta"]
            gamma_values[i] = result["gamma"]
            theta_values[i] = result["theta"]
            vega_values[i] = result["vega"]
        
        return {
            "days_values": days_range,
            "price_values": price_values,
            "delta_values": delta_values,
            "gamma_values": gamma_values,
            "theta_values": theta_values,
            "vega_values": vega_values
        }
    
    def calculate_implied_volatility(
        self,
        option_price: float,
        option_type: str,
        strike: float,
        expiration_date: datetime,
        spot_price: float,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0,
        american: bool = False
    ) -> float:
        """
        Calculate implied volatility for an option.
        
        Args:
            option_price: Market price of the option
            option_type: "call" or "put"
            strike: Strike price
            expiration_date: Option expiration date
            spot_price: Current spot price
            risk_free_rate: Risk-free interest rate
            dividend_yield: Dividend yield
            american: Whether the option is American (True) or European (False)
            
        Returns:
            Implied volatility
        """
        return self.option_pricer.calculate_implied_volatility(
            option_type=option_type,
            strike=strike,
            expiration_date=expiration_date,
            spot_price=spot_price,
            option_price=option_price,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            american=american
        )
    
    def generate_price_vs_time_and_volatility(
        self,
        option_type: str,
        strike: float,
        expiration_date: datetime,
        spot_price: float,
        volatility_range: np.ndarray,
        days_range: np.ndarray,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0,
        american: bool = False
    ) -> Dict:
        """
        Generate a surface of option prices for different volatilities and days to expiry.
        
        Args:
            option_type: "call" or "put"
            strike: Strike price
            expiration_date: Option expiration date
            spot_price: Current spot price
            volatility_range: Array of volatilities
            days_range: Array of days to expiry
            risk_free_rate: Risk-free interest rate
            dividend_yield: Dividend yield
            american: Whether the option is American (True) or European (False)
            
        Returns:
            Dictionary with volatilities, days, and surfaces for price and Greeks
        """
        # Initialize matrices for price and Greeks
        price_surface = np.zeros((len(volatility_range), len(days_range)))
        delta_surface = np.zeros((len(volatility_range), len(days_range)))
        gamma_surface = np.zeros((len(volatility_range), len(days_range)))
        theta_surface = np.zeros((len(volatility_range), len(days_range)))
        vega_surface = np.zeros((len(volatility_range), len(days_range)))
        
        # Calculate price and Greeks for each combination of volatility and days
        for i, vol in enumerate(volatility_range):
            for j, days in enumerate(days_range):
                # Calculate new expiration date
                new_expiration = datetime.now() + timedelta(days=int(days))
                
                # If new_expiration is after the original expiration, use the original
                if new_expiration > expiration_date:
                    new_expiration = expiration_date
                
                result = self.option_pricer.price_option(
                    option_type=option_type,
                    strike=strike,
                    expiration_date=new_expiration,
                    spot_price=spot_price,
                    volatility=vol,
                    risk_free_rate=risk_free_rate,
                    dividend_yield=dividend_yield,
                    american=american
                )
                
                price_surface[i, j] = result["price"]
                delta_surface[i, j] = result["delta"]
                gamma_surface[i, j] = result["gamma"]
                theta_surface[i, j] = result["theta"]
                vega_surface[i, j] = result["vega"]
        
        return {
            "volatility_values": volatility_range,
            "days_values": days_range,
            "price_surface": price_surface,
            "delta_surface": delta_surface,
            "gamma_surface": gamma_surface,
            "theta_surface": theta_surface,
            "vega_surface": vega_surface
        }
    
    def analyze_strategy(
        self,
        legs: List[Dict],
        spot_price_range: np.ndarray,
        volatility: float,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0
    ) -> Dict:
        """
        Analyze a multi-leg option strategy across a range of spot prices.
        
        Args:
            legs: List of option legs, each with option_type, strike, expiration_date, quantity, american
            spot_price_range: Array of spot prices
            volatility: Implied volatility
            risk_free_rate: Risk-free interest rate
            dividend_yield: Dividend yield
            
        Returns:
            Dictionary with spot prices and arrays for price and Greeks
        """
        # Initialize arrays for price and Greeks
        price_values = np.zeros(len(spot_price_range))
        delta_values = np.zeros(len(spot_price_range))
        gamma_values = np.zeros(len(spot_price_range))
        theta_values = np.zeros(len(spot_price_range))
        vega_values = np.zeros(len(spot_price_range))
        
        # Calculate price and Greeks for each spot price
        for i, spot in enumerate(spot_price_range):
            total_price = 0
            total_delta = 0
            total_gamma = 0
            total_theta = 0
            total_vega = 0
            
            for leg in legs:
                result = self.option_pricer.price_option(
                    option_type=leg["option_type"],
                    strike=leg["strike"],
                    expiration_date=leg["expiration_date"],
                    spot_price=spot,
                    volatility=volatility,
                    risk_free_rate=risk_free_rate,
                    dividend_yield=dividend_yield,
                    american=leg.get("american", False)
                )
                
                quantity = leg["quantity"]
                
                total_price += result["price"] * quantity
                total_delta += result["delta"] * quantity
                total_gamma += result["gamma"] * quantity
                total_theta += result["theta"] * quantity
                total_vega += result["vega"] * quantity
            
            price_values[i] = total_price
            delta_values[i] = total_delta
            gamma_values[i] = total_gamma
            theta_values[i] = total_theta
            vega_values[i] = total_vega
        
        return {
            "spot_price_values": spot_price_range,
            "price_values": price_values,
            "delta_values": delta_values,
            "gamma_values": gamma_values,
            "theta_values": theta_values,
            "vega_values": vega_values
        }
    
    def analyze_strategy_profit_loss(
        self,
        legs: List[Dict],
        entry_spot_price: float,
        spot_price_range: np.ndarray,
        entry_volatility: float,
        exit_volatility: float = None,
        days_to_exit: int = 0,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0
    ) -> Dict:
        """
        Analyze profit and loss for a multi-leg option strategy.
        
        Args:
            legs: List of option legs, each with option_type, strike, expiration_date, quantity, american
            entry_spot_price: Spot price at entry
            spot_price_range: Array of potential exit spot prices
            entry_volatility: Implied volatility at entry
            exit_volatility: Implied volatility at exit (defaults to entry_volatility)
            days_to_exit: Days until exit (0 means at expiration)
            risk_free_rate: Risk-free interest rate
            dividend_yield: Dividend yield
            
        Returns:
            Dictionary with spot prices and arrays for P&L
        """
        if exit_volatility is None:
            exit_volatility = entry_volatility
        
        # Calculate entry prices
        entry_prices = {}
        for i, leg in enumerate(legs):
            result = self.option_pricer.price_option(
                option_type=leg["option_type"],
                strike=leg["strike"],
                expiration_date=leg["expiration_date"],
                spot_price=entry_spot_price,
                volatility=entry_volatility,
                risk_free_rate=risk_free_rate,
                dividend_yield=dividend_yield,
                american=leg.get("american", False)
            )
            entry_prices[i] = result["price"] * leg["quantity"]
        
        # Calculate total entry cost
        total_entry_cost = sum(entry_prices.values())
        
        # Initialize P&L array
        pnl_values = np.zeros(len(spot_price_range))
        
        # Calculate P&L for each exit spot price
        for i, spot in enumerate(spot_price_range):
            total_exit_value = 0
            
            for j, leg in enumerate(legs):
                # Calculate new expiration date
                if days_to_exit > 0:
                    new_expiration = datetime.now() + timedelta(days=days_to_exit)
                    if new_expiration > leg["expiration_date"]:
                        new_expiration = leg["expiration_date"]
                else:
                    # At expiration
                    if leg["option_type"] == "call":
                        # Call option payoff at expiration
                        option_value = max(0, spot - leg["strike"])
                    else:
                        # Put option payoff at expiration
                        option_value = max(0, leg["strike"] - spot)
                    
                    total_exit_value += option_value * leg["quantity"]
                    continue
                
                # Calculate option value at exit
                result = self.option_pricer.price_option(
                    option_type=leg["option_type"],
                    strike=leg["strike"],
                    expiration_date=new_expiration,
                    spot_price=spot,
                    volatility=exit_volatility,
                    risk_free_rate=risk_free_rate,
                    dividend_yield=dividend_yield,
                    american=leg.get("american", False)
                )
                
                total_exit_value += result["price"] * leg["quantity"]
            
            # Calculate P&L
            pnl_values[i] = total_exit_value - total_entry_cost
        
        return {
            "spot_price_values": spot_price_range,
            "pnl_values": pnl_values,
            "entry_cost": total_entry_cost
        } 