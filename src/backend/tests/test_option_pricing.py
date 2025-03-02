import pytest
from datetime import datetime, timedelta

from app.services.option_pricing import OptionPricer


class TestOptionPricer:
    """Test suite for the OptionPricer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pricer = OptionPricer()
        self.spot_price = 100.0
        self.strike = 100.0
        self.volatility = 0.2
        self.risk_free_rate = 0.05
        self.dividend_yield = 0.0
        self.expiration_date = datetime.now() + timedelta(days=30)

    def test_price_european_call(self):
        """Test pricing a European call option."""
        result = self.pricer.price_option(
            option_type="call",
            strike=self.strike,
            expiration_date=self.expiration_date,
            spot_price=self.spot_price,
            volatility=self.volatility,
            risk_free_rate=self.risk_free_rate,
            dividend_yield=self.dividend_yield,
            american=False,
        )

        # Basic sanity checks
        assert "price" in result
        assert "delta" in result
        assert "gamma" in result
        assert "theta" in result
        assert "vega" in result
        assert "rho" in result
        assert "time_to_expiry" in result

        # Call option delta should be positive
        assert result["delta"] > 0

        # At-the-money call should have delta around 0.005 (after scaling)
        assert 0.004 < result["delta"] < 0.006

        # Gamma should be positive
        assert result["gamma"] > 0

        # Vega should be positive
        assert result["vega"] > 0

    def test_price_european_put(self):
        """Test pricing a European put option."""
        result = self.pricer.price_option(
            option_type="put",
            strike=self.strike,
            expiration_date=self.expiration_date,
            spot_price=self.spot_price,
            volatility=self.volatility,
            risk_free_rate=self.risk_free_rate,
            dividend_yield=self.dividend_yield,
            american=False,
        )

        # Basic sanity checks
        assert "price" in result
        assert "delta" in result
        assert "gamma" in result
        assert "theta" in result
        assert "vega" in result
        assert "rho" in result
        assert "time_to_expiry" in result

        # Put option delta should be negative
        assert result["delta"] < 0

        # At-the-money put should have delta around -0.005 (after scaling)
        assert -0.006 < result["delta"] < -0.004

        # Gamma should be positive
        assert result["gamma"] > 0

        # Vega should be positive
        assert result["vega"] > 0

    def test_price_american_option(self):
        """Test pricing an American option."""
        result = self.pricer.price_option(
            option_type="call",
            strike=self.strike,
            expiration_date=self.expiration_date,
            spot_price=self.spot_price,
            volatility=self.volatility,
            risk_free_rate=self.risk_free_rate,
            dividend_yield=self.dividend_yield,
            american=True,
        )

        # Basic sanity checks
        assert "price" in result
        assert "delta" in result
        assert "gamma" in result
        assert "theta" in result
        assert "vega" in result
        assert "rho" in result
        assert "time_to_expiry" in result

        # American call should be worth at least as much as European call
        european_result = self.pricer.price_option(
            option_type="call",
            strike=self.strike,
            expiration_date=self.expiration_date,
            spot_price=self.spot_price,
            volatility=self.volatility,
            risk_free_rate=self.risk_free_rate,
            dividend_yield=self.dividend_yield,
            american=False,
        )

        assert result["price"] >= european_result["price"] 