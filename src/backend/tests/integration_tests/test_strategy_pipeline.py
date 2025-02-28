"""
Integration test for the complete options strategy pipeline.

This test verifies the end-to-end flow from strategy creation to scenario analysis
and visualization data generation.
"""
import pytest
from fastapi.testclient import TestClient
import json
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy.orm import Session

from app.main import app
from app.models.database import get_db, Position, OptionLeg, Base, engine, SessionLocal


@pytest.fixture(scope="module")
def test_db():
    """Create a test database session that persists across the module."""
    # Create tables in the test database
    Base.metadata.create_all(bind=engine)
    
    # Create a test session
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def integration_client():
    """Create a test client with a persistent database session."""
    # Override the get_db dependency to use our test database
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    # Apply the override
    app.dependency_overrides[get_db] = override_get_db
    
    # Create and return the test client
    client = TestClient(app)
    return client


class TestOptionsStrategyPipeline:
    """Integration tests for the full options strategy pipeline."""
    
    def setup_method(self):
        """Set up test data."""
        self.today = datetime.today().date()
        self.expiry_date = self.today + timedelta(days=30)
        self.expiry_str = self.expiry_date.strftime("%Y-%m-%d")
        
        # Test strategy: Bull Call Spread on AAPL
        self.strategy_data = {
            "name": "AAPL Bull Call Spread",
            "ticker": "AAPL",
            "strategy_type": "BULL_CALL_SPREAD",
            "legs": [
                {
                    "option_type": "call",
                    "strike": 150,
                    "expiration_date": self.expiry_str,
                    "quantity": 1,
                    "underlying_ticker": "AAPL",
                    "underlying_price": 155.0,
                    "option_price": 8.5,
                    "volatility": 0.25
                },
                {
                    "option_type": "call",
                    "strike": 160,
                    "expiration_date": self.expiry_str,
                    "quantity": -1,  # Negative for short position
                    "underlying_ticker": "AAPL",
                    "underlying_price": 155.0,
                    "option_price": 3.2,
                    "volatility": 0.28
                }
            ],
            "underlying_price": 155.0,
            "risk_free_rate": 0.02
        }
        
        # Scenario analysis parameters
        self.scenario_params = {
            "price_range": {
                "min": 140.0,
                "max": 170.0,
                "steps": 30
            },
            "time_range": {
                "days": [0, 7, 14, 21, 30]
            },
            "volatility_range": {
                "min": 0.2,
                "max": 0.3,
                "steps": 10
            }
        }
    
    def test_full_strategy_pipeline(self, integration_client, test_db):
        """Test the entire flow from strategy creation to visualization data."""
        # Step 1: Create the strategy
        response = integration_client.post(
            "/positions/with-legs",
            json=self.strategy_data
        )
        assert response.status_code == 201
        position_data = response.json()
        assert position_data["id"] is not None
        
        position_id = position_data["id"]
        
        # Step 2: Retrieve the created position
        response = integration_client.get(f"/positions/{position_id}")
        assert response.status_code == 200
        retrieved_position = response.json()
        assert retrieved_position["name"] == self.strategy_data["name"]
        assert len(retrieved_position["legs"]) == 2
        
        # Step 3: Calculate Greeks for the position
        response = integration_client.get(f"/greeks/position/{position_id}")
        assert response.status_code == 200
        greeks = response.json()
        assert "delta" in greeks
        assert "gamma" in greeks
        assert "theta" in greeks
        assert "vega" in greeks
        
        # Step 4: Generate price vs time scenario
        response = integration_client.post(
            f"/scenarios/position/{position_id}/price-time",
            json=self.scenario_params
        )
        assert response.status_code == 200
        price_time_data = response.json()
        assert "prices" in price_time_data
        assert "days" in price_time_data
        assert "values" in price_time_data
        
        # Step 5: Generate price vs volatility scenario
        response = integration_client.post(
            f"/scenarios/position/{position_id}/price-volatility",
            json=self.scenario_params
        )
        assert response.status_code == 200
        price_vol_data = response.json()
        assert "prices" in price_vol_data
        assert "volatilities" in price_vol_data
        assert "values" in price_vol_data
        
        # Step 6: Verify visualization data is consistent
        # Price range should be the same in both scenarios
        assert price_time_data["prices"] == price_vol_data["prices"]
        
        # The middle value in the price-time data should match when days=0
        middle_day_index = 0  # Days = 0
        middle_price_index = len(price_time_data["prices"]) // 2
        
        price_at_today = price_time_data["values"][middle_day_index][middle_price_index]
        
        # This should be close to the strategy's initial value (difference between option prices)
        leg1_price = self.strategy_data["legs"][0]["option_price"]
        leg2_price = self.strategy_data["legs"][1]["option_price"]
        expected_value = (leg1_price - leg2_price) * 100  # Convert to dollar value per contract
        
        # Allow for small differences due to calculation methods
        assert abs(price_at_today - expected_value) < 50
        
        # Step 7: Clean up - delete the position
        response = integration_client.delete(f"/positions/{position_id}")
        assert response.status_code == 200
        
        # Verify it's gone
        response = integration_client.get(f"/positions/{position_id}")
        assert response.status_code == 404 