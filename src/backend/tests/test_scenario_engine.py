import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.services.scenario_engine import ScenarioEngine
from app.services.option_pricing import OptionPricer


class TestScenarioEngine:
    """Test suite for the ScenarioEngine class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.option_pricer = OptionPricer()
        self.scenario_engine = ScenarioEngine(option_pricer=self.option_pricer)
        
        # Sample option data
        self.sample_expiration_date = datetime.now() + timedelta(days=30)
        self.option_data = {
            "option_type": "call",
            "strike": 100.0,
            "expiration_date": self.sample_expiration_date,
            "spot_price": 100.0,
            "volatility": 0.2,
            "risk_free_rate": 0.05,
            "dividend_yield": 0.0,
            "american": False
        }

    def test_price_vs_volatility_surface(self):
        """Test generating a price vs volatility surface."""
        # Define volatility and spot price ranges
        volatility_range = np.linspace(0.1, 0.3, 5)
        spot_price_range = np.linspace(90, 110, 5)
        
        # Generate the surface
        result = self.scenario_engine.generate_price_vs_volatility_surface(
            option_type=self.option_data["option_type"],
            strike=self.option_data["strike"],
            expiration_date=self.option_data["expiration_date"],
            spot_price_range=spot_price_range,
            volatility_range=volatility_range,
            risk_free_rate=self.option_data["risk_free_rate"],
            dividend_yield=self.option_data["dividend_yield"],
            american=self.option_data["american"]
        )
        
        # Verify the result structure
        assert "spot_price_values" in result
        assert "volatility_values" in result
        assert "price_surface" in result
        assert "delta_surface" in result
        assert "gamma_surface" in result
        assert "theta_surface" in result
        assert "vega_surface" in result
        
        # Verify dimensions
        assert len(result["spot_price_values"]) == 5
        assert len(result["volatility_values"]) == 5
        assert result["price_surface"].shape == (5, 5)
        assert result["delta_surface"].shape == (5, 5)
        
        # Verify some basic properties
        # Delta should increase with spot price
        for vol_idx in range(5):
            for spot_idx in range(4):
                assert result["delta_surface"][vol_idx][spot_idx] <= result["delta_surface"][vol_idx][spot_idx + 1]
        
        # Vega should increase with volatility (for ATM options)
        atm_idx = 2  # Middle of the spot price range
        for vol_idx in range(4):
            assert result["vega_surface"][vol_idx][atm_idx] <= result["vega_surface"][vol_idx + 1][atm_idx]

    def test_time_decay_analysis(self):
        """Test time decay analysis."""
        # Define days to expiry range
        days_range = np.linspace(0, 30, 7)
        
        # Generate the analysis
        result = self.scenario_engine.generate_time_decay_analysis(
            option_type=self.option_data["option_type"],
            strike=self.option_data["strike"],
            expiration_date=self.sample_expiration_date,
            spot_price=self.option_data["spot_price"],
            volatility=self.option_data["volatility"],
            risk_free_rate=self.option_data["risk_free_rate"],
            dividend_yield=self.option_data["dividend_yield"],
            american=self.option_data["american"],
            days_range=days_range
        )
        
        # Verify the result structure
        assert "days_values" in result
        assert "price_values" in result
        assert "theta_values" in result
        assert "delta_values" in result
        assert "gamma_values" in result
        assert "vega_values" in result
        
        # Verify dimensions
        assert len(result["days_values"]) == 7
        assert len(result["price_values"]) == 7
        assert len(result["theta_values"]) == 7
        
        # Verify some basic properties
        # Price should decrease as we approach expiration (for ATM options)
        for day_idx in range(6):
            assert result["price_values"][day_idx] >= result["price_values"][day_idx + 1]
        
        # Theta should become more negative as we approach expiration
        for day_idx in range(6):
            assert result["theta_values"][day_idx] >= result["theta_values"][day_idx + 1]

    @patch('app.services.option_pricing.OptionPricer')
    def test_multi_leg_strategy_analysis(self, mock_option_pricer):
        """Test analysis of multi-leg option strategies."""
        # Mock the option pricer
        mock_pricer_instance = MagicMock()
        mock_option_pricer.return_value = mock_pricer_instance
        
        # Set up the mock return values for different option types
        def side_effect_func(*args, **kwargs):
            option_type = kwargs.get("option_type")
            spot_price = kwargs.get("spot_price", 100.0)
            strike = kwargs.get("strike", 100.0)
            
            # Simple formulas for testing
            if option_type == "call":
                price = max(0, spot_price - strike) + 5.0
                delta = 0.6 if spot_price >= strike else 0.4
            else:  # put
                price = max(0, strike - spot_price) + 4.5
                delta = -0.4 if spot_price <= strike else -0.6
                
            return {
                "price": price,
                "delta": delta,
                "gamma": 0.05,
                "theta": -0.1,
                "vega": 0.2,
                "rho": 0.15,
                "time_to_expiry": 30.0
            }
        
        mock_pricer_instance.price_option.side_effect = side_effect_func
        
        # Create a scenario engine with the mocked pricer
        scenario_engine = ScenarioEngine(option_pricer=mock_pricer_instance)
        
        # Define a straddle strategy (long call + long put)
        legs = [
            {
                "option_type": "call",
                "strike": 100.0,
                "expiration_date": self.sample_expiration_date,
                "quantity": 1,
                "american": False
            },
            {
                "option_type": "put",
                "strike": 100.0,
                "expiration_date": self.sample_expiration_date,
                "quantity": 1,
                "american": False
            }
        ]
        
        # Define spot price range
        spot_price_range = np.linspace(80, 120, 9)
        
        # Generate the analysis
        result = scenario_engine.analyze_strategy(
            legs=legs,
            spot_price_range=spot_price_range,
            volatility=0.2,
            risk_free_rate=0.05,
            dividend_yield=0.0
        )
        
        # Verify the result structure
        assert "spot_price_values" in result
        assert "price_values" in result
        assert "delta_values" in result
        assert "gamma_values" in result
        assert "theta_values" in result
        assert "vega_values" in result
        
        # Verify dimensions
        assert len(result["spot_price_values"]) == 9
        assert len(result["price_values"]) == 9
        assert len(result["delta_values"]) == 9
        
        # Verify straddle properties
        # Straddle should have minimum value at the strike price
        min_price_idx = np.argmin(result["price_values"])
        assert abs(result["spot_price_values"][min_price_idx] - 100.0) < 5.0
        
        # Delta should be negative below strike and positive above strike
        middle_idx = 4  # Index for spot price 100
        assert result["delta_values"][0] < 0  # Delta at spot price 80
        assert result["delta_values"][8] > 0  # Delta at spot price 120
        
        # Gamma should be positive for all spot prices
        for gamma in result["gamma_values"]:
            assert gamma > 0

    def test_implied_volatility_calculation(self):
        """Test calculation of implied volatility."""
        # Define a known option price
        option_price = 5.0
        
        # Calculate implied volatility
        implied_vol = self.scenario_engine.calculate_implied_volatility(
            option_price=option_price,
            option_type=self.option_data["option_type"],
            strike=self.option_data["strike"],
            expiration_date=self.option_data["expiration_date"],
            spot_price=self.option_data["spot_price"],
            risk_free_rate=self.option_data["risk_free_rate"],
            dividend_yield=self.option_data["dividend_yield"],
            american=self.option_data["american"]
        )
        
        # Verify the result is a reasonable volatility value
        assert 0.05 <= implied_vol <= 0.5
        
        # Verify that using this implied volatility gives us back the original price
        priced_result = self.option_pricer.price_option(
            option_type=self.option_data["option_type"],
            strike=self.option_data["strike"],
            expiration_date=self.option_data["expiration_date"],
            spot_price=self.option_data["spot_price"],
            volatility=implied_vol,
            risk_free_rate=self.option_data["risk_free_rate"],
            dividend_yield=self.option_data["dividend_yield"],
            american=self.option_data["american"]
        )
        
        # The price should be close to the original price
        assert abs(priced_result["price"] - option_price) < 0.01

    def test_price_vs_time_and_volatility(self):
        """Test generating a price vs time and volatility surface."""
        # Define volatility and days to expiry ranges
        volatility_range = np.linspace(0.1, 0.3, 5)
        days_range = np.linspace(0, 30, 5)
        
        # Generate the surface
        result = self.scenario_engine.generate_price_vs_time_and_volatility(
            option_type=self.option_data["option_type"],
            strike=self.option_data["strike"],
            expiration_date=self.sample_expiration_date,
            spot_price=self.option_data["spot_price"],
            volatility_range=volatility_range,
            days_range=days_range,
            risk_free_rate=self.option_data["risk_free_rate"],
            dividend_yield=self.option_data["dividend_yield"],
            american=self.option_data["american"]
        )
        
        # Verify the result structure
        assert "days_values" in result
        assert "volatility_values" in result
        assert "price_surface" in result
        assert "theta_surface" in result
        assert "vega_surface" in result
        
        # Verify dimensions
        assert len(result["days_values"]) == 5
        assert len(result["volatility_values"]) == 5
        assert result["price_surface"].shape == (5, 5)
        assert result["theta_surface"].shape == (5, 5)
        assert result["vega_surface"].shape == (5, 5)
        
        # Verify some basic properties
        # Price should increase with volatility
        for day_idx in range(5):
            for vol_idx in range(4):
                assert result["price_surface"][vol_idx][day_idx] <= result["price_surface"][vol_idx + 1][day_idx]
        
        # Price should decrease as we approach expiration
        for vol_idx in range(5):
            for day_idx in range(4):
                assert result["price_surface"][vol_idx][day_idx] >= result["price_surface"][vol_idx][day_idx + 1]

    def test_strategy_profit_loss_analysis(self):
        """Test profit and loss analysis for option strategies."""
        # Define a covered call strategy (long stock + short call)
        legs = [
            {
                "option_type": "stock",
                "quantity": 100,  # 100 shares
                "entry_price": 100.0
            },
            {
                "option_type": "call",
                "strike": 105.0,
                "expiration_date": self.sample_expiration_date,
                "quantity": -1,  # Short 1 call
                "entry_price": 3.0,
                "american": False
            }
        ]
        
        # Define spot price range
        spot_price_range = np.linspace(90, 120, 7)
        
        # Generate the analysis
        result = self.scenario_engine.analyze_strategy_profit_loss(
            legs=legs,
            spot_price_range=spot_price_range,
            volatility=0.2,
            risk_free_rate=0.05,
            dividend_yield=0.0,
            days_to_expiration=0  # Analyze at expiration
        )
        
        # Verify the result structure
        assert "spot_price_values" in result
        assert "profit_loss_values" in result
        
        # Verify dimensions
        assert len(result["spot_price_values"]) == 7
        assert len(result["profit_loss_values"]) == 7
        
        # Verify covered call properties
        # At spot price 90, P&L should be (90 - 100) * 100 + 3.0 * 100 = -700 + 300 = -400
        assert abs(result["profit_loss_values"][0] - (-400)) < 50
        
        # At spot price 105, P&L should be (105 - 100) * 100 + 3.0 * 100 = 500 + 300 = 800
        middle_idx = 3  # Index for spot price around 105
        assert abs(result["profit_loss_values"][middle_idx] - 800) < 50
        
        # At spot price 120, P&L should be (105 - 100) * 100 + 3.0 * 100 = 500 + 300 = 800
        # (profit is capped at strike price for covered call)
        assert abs(result["profit_loss_values"][6] - 800) < 50 