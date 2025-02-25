import QuantLib as ql
from datetime import datetime, date
from typing import Dict, Literal, Optional, Tuple


class OptionPricer:
    """
    A wrapper class for QuantLib to price options and calculate Greeks.
    """
    
    def __init__(self):
        self.day_count = ql.Actual365Fixed()
        self.calendar = ql.UnitedStates(ql.UnitedStates.NYSE)
        self.calculation_date = ql.Date.todaysDate()
        ql.Settings.instance().evaluationDate = self.calculation_date
    
    def _create_option(
        self, 
        option_type: Literal["call", "put"], 
        strike: float, 
        expiration_date: datetime,
        american: bool = False
    ) -> Tuple[ql.VanillaOption, ql.Date]:
        """
        Create a QuantLib option object.
        
        Args:
            option_type: "call" or "put"
            strike: Strike price
            expiration_date: Option expiration date
            american: Whether the option is American (True) or European (False)
            
        Returns:
            Tuple of (option object, maturity date)
        """
        # Convert option type
        ql_option_type = ql.Option.Call if option_type == "call" else ql.Option.Put
        
        # Create payoff
        payoff = ql.PlainVanillaPayoff(ql_option_type, strike)
        
        # Convert expiration date to QuantLib date
        if isinstance(expiration_date, datetime):
            expiration_date = expiration_date.date()
        
        year = expiration_date.year
        month = expiration_date.month
        day = expiration_date.day
        maturity_date = ql.Date(day, month, year)
        
        # Create exercise
        if american:
            exercise = ql.AmericanExercise(self.calculation_date, maturity_date)
        else:
            exercise = ql.EuropeanExercise(maturity_date)
        
        # Create option
        option = ql.VanillaOption(payoff, exercise)
        
        return option, maturity_date
    
    def _create_process(
        self, 
        spot_price: float, 
        risk_free_rate: float, 
        volatility: float, 
        dividend_yield: float = 0.0
    ) -> ql.BlackScholesMertonProcess:
        """
        Create a Black-Scholes-Merton process.
        
        Args:
            spot_price: Current price of the underlying
            risk_free_rate: Risk-free interest rate
            volatility: Implied volatility
            dividend_yield: Dividend yield
            
        Returns:
            QuantLib Black-Scholes-Merton process
        """
        # Create handles
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot_price))
        risk_free_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(self.calculation_date, risk_free_rate, self.day_count)
        )
        dividend_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(self.calculation_date, dividend_yield, self.day_count)
        )
        volatility_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(self.calculation_date, self.calendar, volatility, self.day_count)
        )
        
        # Create process
        process = ql.BlackScholesMertonProcess(
            spot_handle, dividend_ts, risk_free_ts, volatility_ts
        )
        
        return process
    
    def price_option(
        self,
        option_type: Literal["call", "put"],
        strike: float,
        expiration_date: datetime,
        spot_price: float,
        volatility: float,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0,
        american: bool = False
    ) -> Dict[str, float]:
        """
        Price an option and calculate Greeks.
        
        Args:
            option_type: "call" or "put"
            strike: Strike price
            expiration_date: Option expiration date
            spot_price: Current price of the underlying
            volatility: Implied volatility
            risk_free_rate: Risk-free interest rate
            dividend_yield: Dividend yield
            american: Whether the option is American (True) or European (False)
            
        Returns:
            Dictionary with option price and Greeks
        """
        # Create option and process
        option, maturity_date = self._create_option(option_type, strike, expiration_date, american)
        process = self._create_process(spot_price, risk_free_rate, volatility, dividend_yield)
        
        # Calculate time to expiry in years
        time_to_expiry = self.day_count.yearFraction(self.calculation_date, maturity_date)
        
        try:
            # Set pricing engine based on option type
            if american:
                # Use binomial tree for American options
                # Increase steps for better accuracy
                engine = ql.BinomialVanillaEngine(process, "crr", 1000)
            else:
                # Use analytic formula for European options
                engine = ql.AnalyticEuropeanEngine(process)
            
            option.setPricingEngine(engine)
            
            # Calculate price and Greeks
            price = option.NPV()
            delta = option.delta()
            gamma = option.gamma()
            theta = option.theta() / 365.0  # Daily theta
            vega = option.vega() / 100.0    # Vega per 1% vol change
            rho = option.rho() / 100.0      # Rho per 1% rate change
            
            return {
                "price": price,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "rho": rho,
                "time_to_expiry": time_to_expiry
            }
        except Exception as e:
            print(f"Error pricing option: {e}")
            
            # For American call options with no dividends, use European price
            # (they should be equivalent according to financial theory)
            if american and option_type == "call" and dividend_yield <= 0.0001:
                try:
                    # Use European pricing for American call with no dividends
                    european_option, _ = self._create_option(option_type, strike, expiration_date, False)
                    european_engine = ql.AnalyticEuropeanEngine(process)
                    european_option.setPricingEngine(european_engine)
                    
                    price = european_option.NPV()
                    delta = european_option.delta()
                    gamma = european_option.gamma()
                    theta = european_option.theta() / 365.0
                    vega = european_option.vega() / 100.0
                    rho = european_option.rho() / 100.0
                    
                    return {
                        "price": price,
                        "delta": delta,
                        "gamma": gamma,
                        "theta": theta,
                        "vega": vega,
                        "rho": rho,
                        "time_to_expiry": time_to_expiry
                    }
                except Exception as inner_e:
                    print(f"Error in fallback European pricing: {inner_e}")
            
            # Return zeros if all pricing attempts fail
            return {
                "error": str(e),
                "price": 0.0,
                "delta": 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0,
                "time_to_expiry": time_to_expiry
            }
    
    def calculate_implied_volatility(
        self,
        option_type: Literal["call", "put"],
        strike: float,
        expiration_date: datetime,
        spot_price: float,
        option_price: float,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0,
        american: bool = False
    ) -> float:
        """
        Calculate implied volatility from option price.
        
        Args:
            option_type: "call" or "put"
            strike: Strike price
            expiration_date: Option expiration date
            spot_price: Current price of the underlying
            option_price: Market price of the option
            risk_free_rate: Risk-free interest rate
            dividend_yield: Dividend yield
            american: Whether the option is American (True) or European (False)
            
        Returns:
            Implied volatility
        """
        # Create option
        option, maturity_date = self._create_option(option_type, strike, expiration_date, american)
        
        # Calculate time to expiry in years
        time_to_expiry = self.day_count.yearFraction(self.calculation_date, maturity_date)
        
        # Create process with initial volatility guess
        initial_vol = 0.3  # 30% initial guess
        process = self._create_process(spot_price, risk_free_rate, initial_vol, dividend_yield)
        
        try:
            # Set pricing engine based on option type
            if american:
                engine = ql.BinomialVanillaEngine(process, "crr", 1000)
            else:
                engine = ql.AnalyticEuropeanEngine(process)
            
            option.setPricingEngine(engine)
            
            # Calculate implied volatility
            implied_vol = option.impliedVolatility(
                option_price, process, 1e-6, 1000, 0.001, 4.0
            )
            return implied_vol
        except Exception as e:
            # If calculation fails, return the error message and a default value
            print(f"Error calculating implied volatility: {e}")
            return 0.0 