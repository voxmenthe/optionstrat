import QuantLib as ql
from datetime import datetime, date
from typing import Dict, Literal, Optional, Tuple, Union


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
        expiration_date: Union[datetime, date, str],
        american: bool = False
    ) -> Tuple[ql.VanillaOption, ql.Date]:
        """
        Create a QuantLib option object.
        
        Args:
            option_type: "call" or "put"
            strike: Strike price
            expiration_date: Option expiration date (datetime, date, or string in format 'YYYY-MM-DD')
            american: Whether the option is American (True) or European (False)
            
        Returns:
            Tuple of (option object, maturity date)
        """
        # Convert option type
        ql_option_type = ql.Option.Call if option_type == "call" else ql.Option.Put
        
        # Create payoff
        payoff = ql.PlainVanillaPayoff(ql_option_type, strike)
        
        # Convert expiration date to a date object if it's not already
        if isinstance(expiration_date, str):
            # Parse string date (expect YYYY-MM-DD format or ISO format)
            try:
                # First try ISO format with T separator
                if 'T' in expiration_date:
                    expiration_date = datetime.fromisoformat(expiration_date).date()
                else:
                    # Then try simple YYYY-MM-DD format
                    expiration_date = datetime.strptime(expiration_date, '%Y-%m-%d').date()
            except ValueError:
                # Try with time component if simple date parse fails
                try:
                    expiration_date = datetime.strptime(expiration_date, '%Y-%m-%d %H:%M:%S').date()
                except ValueError:
                    # Final fallback - try to strip any extra parts and keep just the date portion
                    expiration_date = datetime.strptime(expiration_date.split('T')[0], '%Y-%m-%d').date()
        elif isinstance(expiration_date, datetime):
            expiration_date = expiration_date.date()
        
        # Now we should have a date object
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
        expiration_date: Union[datetime, date, str],
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
            print("Setting pricing engine...") # Log
            if american:
                # Use Finite Difference engine for American options - generally robust for Greeks
                # Increased parameters for more accurate Greeks calculation, especially for Vega and Rho
                timeSteps = 200  # Increased from 100 to 200
                gridPoints = 200 # Increased from 100 to 200
                print(f"Using FdBlackScholesVanillaEngine for American {option_type.upper()} (timeSteps={timeSteps}, gridPoints={gridPoints})") # Log
                engine = ql.FdBlackScholesVanillaEngine(process, timeSteps, gridPoints)
            else:
                # Use analytic formula for European options
                print("Using AnalyticEuropeanEngine for European option") # Log
                engine = ql.AnalyticEuropeanEngine(process)
            
            option.setPricingEngine(engine)
            print("Pricing engine set successfully.") # Log
            
            # Calculate price and Greeks with individual error handling
            price = 0.0
            delta = 0.0
            gamma = 0.0
            theta = 0.0
            vega = 0.0
            rho = 0.0
            raw_delta, raw_gamma, raw_theta, raw_vega, raw_rho = 0.0, 0.0, 0.0, 0.0, 0.0 # Defaults

            try:
                print("Calculating NPV...") # Log
                price = option.NPV()
                print(f"Calculated NPV: {price}") # Log
            except Exception as npv_error:
                 print(f"ERROR calculating NPV: {npv_error}")
                 # If price fails, we probably can't get Greeks either, return error
                 raise npv_error # Re-raise to be caught by the outer exception handler
            
            try:
                print("Calculating Delta...") # Log
                raw_delta = option.delta()
                delta = raw_delta / 100.0
                print(f"Calculated Delta: {raw_delta} -> {delta}") # Log
            except Exception as delta_error:
                 print(f"WARNING: Delta calculation failed: {delta_error}. Returning Delta as 0.")

            try:
                print("Calculating Gamma...") # Log
                raw_gamma = option.gamma()
                gamma = raw_gamma / 100.0
                print(f"Calculated Gamma: {raw_gamma} -> {gamma}") # Log
            except Exception as gamma_error:
                 print(f"WARNING: Gamma calculation failed: {gamma_error}. Returning Gamma as 0.")
            
            try:
                print("Calculating Theta...") # Log
                raw_theta = option.theta()
                theta = (raw_theta / 365.0) / 100.0  # Daily theta, scaled
                print(f"Calculated Theta: {raw_theta} -> {theta}") # Log
            except Exception as theta_error:
                 print(f"WARNING: Theta calculation failed: {theta_error}. Returning Theta as 0.")

            try:
                print("Calculating Vega...") # Log
                raw_vega = option.vega()
                print(f"Raw Vega from QL: {raw_vega}") # Log
                # Special threshold for PUT options
                min_vega_threshold = 1e-3 if option_type == "put" else 1e-4  # Increased thresholds
                if abs(raw_vega) < min_vega_threshold:
                    print(f"WARNING: {option_type.upper()} option with small vega: {raw_vega}. Using threshold {min_vega_threshold}.")
                    raw_vega = min_vega_threshold if raw_vega >= 0 else -min_vega_threshold
                vega = raw_vega / 100.0
            except Exception as vega_error:
                print(f"WARNING: Vega calculation failed: {vega_error}. Returning Vega as default.")
                # Increased default values for better numerical stability
                vega = 1e-3 if option_type == "put" else 1e-4  # Increased default values
            print(f"Calculated Vega: {raw_vega} -> {vega}") # Log
            
            try:
                print("Calculating Rho...") # Log
                raw_rho = option.rho()
                # Add similar threshold protection for Rho
                min_rho_threshold = 1e-4
                if abs(raw_rho) < min_rho_threshold:
                    print(f"WARNING: {option_type.upper()} option with small rho: {raw_rho}. Using threshold {min_rho_threshold}.")
                    raw_rho = min_rho_threshold if raw_rho >= 0 else -min_rho_threshold
                rho = raw_rho / 100.0
            except Exception as rho_error:
                print(f"WARNING: Rho calculation failed: {rho_error}. Returning Rho as default.")
                rho = 1e-4  # Use small but non-zero default
            print(f"Calculated Rho: {raw_rho} -> {rho}") # Log
            
            # Print final Greeks
            print(f"Raw Greeks (final): Delta={raw_delta}, Gamma={raw_gamma}, Theta={raw_theta}, Vega={raw_vega}, Rho={raw_rho}")
            print(f"Scaled Greeks (final): Delta={delta}, Gamma={gamma}, Theta={theta}, Vega={vega}, Rho={rho}")
            
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
            # Outer exception handler: Catches NPV error or other setup issues
            print(f"Error pricing option (outer handler): {e}")
            
            # For American call options with no dividends, use European price
            # (they should be equivalent according to financial theory)
            if american and option_type == "call" and dividend_yield <= 0.0001:
                try:
                    # Use European pricing for American call with no dividends
                    european_option, _ = self._create_option(option_type, strike, expiration_date, False)
                    european_engine = ql.AnalyticEuropeanEngine(process)
                    european_option.setPricingEngine(european_engine)
                    
                    price = european_option.NPV()
                    
                    # Apply the same scaling as the main calculation
                    delta = european_option.delta() / 100.0
                    gamma = european_option.gamma() / 100.0
                    theta = (european_option.theta() / 365.0) / 100.0  # Daily theta, scaled
                    
                    # Handle extremely small vega values that might cause "vega not provided" errors
                    try:
                        raw_vega = european_option.vega()
                        
                        # Special threshold for PUT options - they have much smaller vega values in some regions
                        if option_type == "put":
                            # Use a larger threshold for PUT options (increased from the previous value)
                            min_vega_threshold = 1e-3  # Increased from 1e-4
                            if abs(raw_vega) < min_vega_threshold:
                                print(f"WARNING: PUT option with extremely small vega detected in European fallback: {raw_vega}. Using minimum threshold of {min_vega_threshold}.")
                                raw_vega = min_vega_threshold if raw_vega >= 0 else -min_vega_threshold
                        else:
                            # Keep a smaller threshold for CALL options (but still increased)
                            min_vega_threshold = 1e-4  # Increased from 1e-10
                            if abs(raw_vega) < min_vega_threshold:
                                print(f"WARNING: CALL option with extremely small vega detected in European fallback: {raw_vega}. Using minimum threshold of {min_vega_threshold}.")
                                raw_vega = min_vega_threshold if raw_vega >= 0 else -min_vega_threshold
                        
                        vega = raw_vega / 100.0    # Vega per 1% vol change
                    except Exception as vega_error:
                        print(f"WARNING: Vega calculation failed in European fallback: {vega_error}. Using default value.")
                        # For PUT options, use a larger default value (increased)
                        vega = 1e-3 if option_type == "put" else 1e-4  # Increased from 1e-4/1e-6
                    
                    # Add similar threshold protection for Rho in the fallback case
                    try:
                        raw_rho = european_option.rho()
                        min_rho_threshold = 1e-4
                        if abs(raw_rho) < min_rho_threshold:
                            print(f"WARNING: Option with small rho detected in European fallback: {raw_rho}. Using minimum threshold of {min_rho_threshold}.")
                            raw_rho = min_rho_threshold if raw_rho >= 0 else -min_rho_threshold
                        rho = raw_rho / 100.0
                    except Exception as rho_error:
                        print(f"WARNING: Rho calculation failed in European fallback: {rho_error}. Using default value.")
                        rho = 1e-4  # Use small but non-zero default
                    
                    # Print raw values for debugging
                    print(f"European fallback - Raw Greeks from QuantLib: Delta={european_option.delta()}, Gamma={european_option.gamma()}, Theta={european_option.theta()}, Vega={raw_vega}, Rho={european_option.rho()}")
                    print(f"European fallback - Scaled Greeks: Delta={delta}, Gamma={gamma}, Theta={theta}, Vega={vega}, Rho={rho}")
                    
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
        expiration_date: Union[datetime, date, str],
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
        try:
            print(f"Starting implied volatility calculation with parameters:")
            print(f"  - option_type: {option_type}")
            print(f"  - strike: {strike}")
            print(f"  - expiration_date: {expiration_date}")
            print(f"  - spot_price: {spot_price}")
            print(f"  - option_price: {option_price}")
            print(f"  - risk_free_rate: {risk_free_rate}")
            print(f"  - american: {american}")
            
            # Create option
            try:
                option, maturity_date = self._create_option(option_type, strike, expiration_date, american)
                print(f"Option created successfully, maturity_date: {maturity_date}")
            except Exception as e:
                print(f"Error creating option: {e}")
                raise
            
            # Calculate time to expiry in years
            try:
                time_to_expiry = self.day_count.yearFraction(self.calculation_date, maturity_date)
                print(f"Time to expiry calculated: {time_to_expiry} years")
            except Exception as e:
                print(f"Error calculating time to expiry: {e}")
                raise
            
            # Create process with initial volatility guess
            initial_vol = 0.3  # 30% initial guess
            try:
                process = self._create_process(spot_price, risk_free_rate, initial_vol, dividend_yield)
                print(f"Black-Scholes process created successfully")
            except Exception as e:
                print(f"Error creating process: {e}")
                raise
            
            # Set pricing engine based on option type
            try:
                if american:
                    engine = ql.BinomialVanillaEngine(process, "crr", 1000)
                    print(f"Created binomial (CRR) engine for American option")
                else:
                    engine = ql.AnalyticEuropeanEngine(process)
                    print(f"Created analytic engine for European option")
                    
                option.setPricingEngine(engine)
            except Exception as e:
                print(f"Error setting pricing engine: {e}")
                raise
            
            # Calculate implied volatility
            try:
                implied_vol = option.impliedVolatility(
                    option_price, process, 1e-6, 1000, 0.001, 4.0
                )
                print(f"Implied volatility calculated successfully: {implied_vol}")
                return implied_vol
            except Exception as e:
                print(f"Error in impliedVolatility calculation: {e}")
                raise
        except Exception as e:
            # If calculation fails, log the error and return a default value
            print(f"Error calculating implied volatility: {str(e)}")
            return 0.0 