import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import uuid

from app.main import app
from app.services.market_data import MarketDataService
from app.services.option_pricing import OptionPricer
from app.services.option_chain_service import OptionChainService
from app.models.database import get_db
from tests.conftest import override_get_db


# Use the client fixture from conftest.py


@pytest.fixture
def test_client(client):
    """Create a test client for the FastAPI app."""
    return client


class TestAPIEndpoints:
    """Test suite for the FastAPI endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_ticker = "AAPL"
        self.sample_option_symbol = "O:AAPL230616C00150000"
        self.sample_expiration_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Sample option chain data
        self.sample_options = [
            {
                "ticker": "AAPL",
                "expiration": "2025-06-20T00:00:00",
                "strike": 200.0,
                "option_type": "call",
                "bid": 10.5,
                "ask": 11.2,
                "volume": 1000,
                "open_interest": 5000,
                "implied_volatility": 0.35,
                "delta": 0.65,
            },
            {
                "ticker": "AAPL",
                "expiration": "2025-06-20T00:00:00",
                "strike": 200.0,
                "option_type": "put",
                "bid": 8.4,
                "ask": 8.9,
                "volume": 800,
                "open_interest": 4200,
                "implied_volatility": 0.33,
                "delta": -0.35,
            }
        ]
        
        # Sample expiration dates
        self.sample_expirations = [
            {
                "date": "2025-03-21T00:00:00",
                "formatted_date": "2025-03-21"
            },
            {
                "date": "2025-06-20T00:00:00",
                "formatted_date": "2025-06-20"
            }
        ]

    def test_health_check(self, test_client):
        """Test the health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
        
    @patch.object(OptionChainService, 'get_option_chain')
    def test_get_options_chain(self, mock_get_chain, test_client):
        """Test the get options chain endpoint."""
        # Configure the mock
        mock_get_chain.return_value = self.sample_options
        
        # Make the request
        response = test_client.get(f"/options/chains/{self.sample_ticker}")
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["ticker"] == self.sample_ticker
        assert data[0]["strike"] == 200.0
        
        # Verify the mock was called correctly
        mock_get_chain.assert_called_once()
    
    @patch.object(OptionChainService, 'get_option_chain')
    def test_get_options_chain_with_filters(self, mock_get_chain, test_client):
        """Test the get options chain endpoint with filters."""
        # Configure the mock to return only calls
        filtered_options = [opt for opt in self.sample_options if opt["option_type"] == "call"]
        mock_get_chain.return_value = filtered_options
        
        # Make the request with filters
        response = test_client.get(
            f"/options/chains/{self.sample_ticker}",
            params={"option_type": "call", "min_strike": 200.0}
        )
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["option_type"] == "call"
        
    @patch.object(OptionChainService, 'get_expirations')
    def test_get_option_expirations(self, mock_get_expirations, test_client):
        """Test the get option expirations endpoint."""
        # Configure the mock
        exp_dates = [datetime.strptime(exp["formatted_date"], "%Y-%m-%d") for exp in self.sample_expirations]
        mock_get_expirations.return_value = exp_dates
        
        # Make the request
        response = test_client.get(f"/options/chains/{self.sample_ticker}/expirations")
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert "2025-03-21" in [exp["formatted_date"] for exp in data]
        assert "2025-06-20" in [exp["formatted_date"] for exp in data]
        
    @patch.object(OptionChainService, 'get_option_chain')
    def test_get_options_for_expiration(self, mock_get_chain, test_client):
        """Test the get options for expiration endpoint."""
        # Configure the mock
        mock_get_chain.return_value = self.sample_options
        
        # Make the request
        response = test_client.get(
            f"/options/chains/{self.sample_ticker}/2025-06-20"
        )
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(opt["expiration"].startswith("2025-06-20") for opt in data)
        
    @patch.object(MarketDataService, 'search_tickers')
    def test_search_tickers(self, mock_search_tickers, test_client):
        """Test the search tickers endpoint."""
        # Sample ticker search results
        search_results = [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "APLS", "name": "Apellis Pharmaceuticals, Inc."}
        ]
        
        # Configure the mock
        mock_search_tickers.return_value = search_results
        
        # Make the request
        response = test_client.get("/options/search/APL")
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "AAPL"
        assert data[1]["symbol"] == "APLS"
        
        # Verify the mock was called correctly
        mock_search_tickers.assert_called_once_with("APL")

    def test_api_version(self, test_client):
        """Test the API version endpoint."""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "status" in response.json()
        assert "message" in response.json()

    @patch('app.routes.market_data.MarketDataService')
    def test_get_ticker_details(self, mock_market_data_service, test_client):
        """Test the ticker details endpoint."""
        # Mock the service
        mock_service_instance = MagicMock()
        mock_market_data_service.return_value = mock_service_instance
        
        # Set up the mock return value
        mock_service_instance.get_ticker_details.return_value = {
            "status": "OK",
            "results": {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "NASDAQ"
            }
        }
        
        # Make the request
        response = test_client.get(f"/market-data/ticker/{self.sample_ticker}")
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"
        assert data["results"]["ticker"] == "AAPL"
        assert data["results"]["name"] == "Apple Inc."
        
        # Verify the service was called correctly
        mock_service_instance.get_ticker_details.assert_called_once_with(self.sample_ticker)

    @patch('app.routes.market_data.MarketDataService')
    def test_get_stock_price(self, mock_market_data_service, test_client):
        """Test the stock price endpoint."""
        # Mock the service
        mock_service_instance = MagicMock()
        mock_market_data_service.return_value = mock_service_instance
        
        # Set up the mock return value
        mock_service_instance.get_stock_price.return_value = 150.25
        
        # Make the request
        response = test_client.get(f"/market-data/price/{self.sample_ticker}")
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == self.sample_ticker
        assert data["price"] == 150.25
        
        # Verify the service was called correctly
        mock_service_instance.get_stock_price.assert_called_once_with(self.sample_ticker)

    @patch('app.routes.market_data.MarketDataService')
    def test_get_option_chain(self, mock_market_data_service, test_client):
        """Test the option chain endpoint."""
        # Mock the service
        mock_service_instance = MagicMock()
        mock_market_data_service.return_value = mock_service_instance
        
        # Set up the mock return value
        mock_service_instance.get_option_chain.return_value = [
            {
                "underlying_ticker": "AAPL",
                "ticker": "O:AAPL230616C00150000",
                "strike_price": 150.0,
                "expiration_date": "2023-06-16",
                "contract_type": "call",
                "exercise_style": "american"
            },
            {
                "underlying_ticker": "AAPL",
                "ticker": "O:AAPL230616P00150000",
                "strike_price": 150.0,
                "expiration_date": "2023-06-16",
                "contract_type": "put",
                "exercise_style": "american"
            }
        ]
        
        # Make the request
        response = test_client.get(
            f"/market-data/option-chain/{self.sample_ticker}",
            params={"expiration_date": self.sample_expiration_date}
        )
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert "ticker" in data
        assert "options" in data
        assert len(data["options"]) == 2
        assert data["options"][0]["underlying_ticker"] == "AAPL"
        assert data["options"][0]["strike_price"] == 150.0
        assert data["options"][0]["contract_type"] == "call"
        assert data["options"][1]["contract_type"] == "put"
        
        # Verify the service was called correctly
        mock_service_instance.get_option_chain.assert_called_once()

    def test_calculate_option_greeks(self, test_client):
        """Test the calculate option Greeks endpoint."""
        # Request data
        option_data = {
            "ticker": self.sample_ticker,
            "option_type": "call",
            "strike": 150.0,
            "expiration": self.sample_expiration_date,
            "spot_price": 155.0,
            "volatility": 0.2,
            "risk_free_rate": 0.05
        }
        
        # Make the request
        response = test_client.post("/greeks/calculate", json=option_data)
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        
        # We're using the real OptionPricer, so we just check that the values are reasonable
        assert "price" in data
        assert "delta" in data
        assert "gamma" in data
        assert "theta" in data
        assert "vega" in data
        assert "rho" in data
        
        # Check that the values are within reasonable ranges
        assert 0 < data["price"] < 50  # Option price should be positive but not too large
        assert 0 <= data["delta"] <= 1  # Delta should be between 0 and 1 for a call
        assert data["gamma"] >= 0  # Gamma should be positive
        assert data["theta"] <= 0  # Theta is typically negative (time decay)
        assert data["vega"] >= 0  # Vega should be positive

    def test_create_position(self, test_client):
        """Test creating a position."""
        # Create a mock database session
        mock_db = MagicMock()
        
        # Create a mock for the Position model with datetime fields
        from datetime import datetime, timezone
        from app.models.database import Position, OptionLeg
        
        # Create a mock position ID that will be used for both the position and its legs
        position_id = str(uuid.uuid4())
        
        # Store created legs to simulate the relationship
        created_legs = []
        
        # Mock the add method to set datetime fields and handle relationships
        def mock_add_side_effect(obj):
            if isinstance(obj, Position):
                # Set ID and datetime fields for Position
                obj.id = position_id
                obj.created_at = datetime.now(timezone.utc)
                obj.updated_at = datetime.now(timezone.utc)
                # Initialize empty legs list if not present
                if not hasattr(obj, 'legs'):
                    obj.legs = []
            elif isinstance(obj, OptionLeg):
                # Set ID, position_id, and datetime fields for OptionLeg
                obj.id = str(uuid.uuid4())
                obj.position_id = position_id
                obj.created_at = datetime.now(timezone.utc)
                obj.updated_at = datetime.now(timezone.utc)
                # Track the leg for the relationship
                created_legs.append(obj)
            return None
        
        mock_db.add.side_effect = mock_add_side_effect
        
        # Mock the flush method to simulate the database assigning IDs
        def mock_flush_side_effect():
            return None
        
        mock_db.flush.side_effect = mock_flush_side_effect
        
        # Mock the refresh method to ensure datetime fields are set and relationships are maintained
        def mock_refresh_side_effect(obj):
            if isinstance(obj, Position):
                # Ensure datetime fields are set for Position
                if not obj.created_at:
                    obj.created_at = datetime.now(timezone.utc)
                if not obj.updated_at:
                    obj.updated_at = datetime.now(timezone.utc)
                
                # Set the legs relationship
                obj.legs = created_legs
            return None
        
        mock_db.refresh.side_effect = mock_refresh_side_effect
        
        # Override the get_db dependency for this test
        def override_get_db():
            yield mock_db
        
        # Apply the override
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            # Position data
            position_data = {
                "name": "AAPL Call Option",
                "legs": [
                    {
                        "option_type": "call",
                        "strike": 150.0,
                        "expiration_date": self.sample_expiration_date,
                        "quantity": 1,
                        "underlying_ticker": "AAPL",
                        "underlying_price": 155.0,
                        "option_price": 5.75,
                        "volatility": 0.2
                    }
                ]
            }
            
            # Make the request
            response = test_client.post("/positions/with-legs", json=position_data)
            
            # Verify the response
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "AAPL Call Option"
            assert len(data["legs"]) == 1
            assert data["legs"][0]["option_type"] == "call"
            assert data["legs"][0]["strike"] == 150.0
            
            # Verify the database was called
            assert mock_db.add.called
            assert mock_db.commit.called
            assert mock_db.refresh.called
        
        finally:
            # Clean up the override
            app.dependency_overrides.pop(get_db, None)

    def test_price_vs_volatility_scenario(self, test_client):
        """Test the price vs volatility scenario endpoint."""
        # Import the dependency function
        from app.routes.scenarios import get_option_pricer
        
        # Mock the OptionPricer instance
        mock_service_instance = MagicMock()
        
        # Set up the mock return value for multiple volatility values
        def side_effect_func(*args, **kwargs):
            print(f"Mock price_option called with args: {args}, kwargs: {kwargs}")
            volatility = kwargs.get("volatility", 0.2)
            return {
                "price": 5.0 + (volatility - 0.2) * 10,  # Simple formula for test
                "delta": 0.6,
                "gamma": 0.05,
                "theta": -0.1,
                "vega": 0.2,
                "rho": 0.15,
                "time_to_expiry": 30.0
            }
        
        mock_service_instance.price_option.side_effect = side_effect_func
        
        # Override the dependency
        app.dependency_overrides[get_option_pricer] = lambda: mock_service_instance
        
        # Request data
        scenario_data = {
            "option_type": "call",
            "strike": 150.0,
            "expiration_date": self.sample_expiration_date,
            "spot_price": 155.0,
            "volatility_range": {
                "min": 0.1,
                "max": 0.5,
                "steps": 5
            },
            "risk_free_rate": 0.05,
            "dividend_yield": 0.0,
            "american": True
        }
        
        try:
            # Make the request
            response = test_client.post("/scenarios/price-vs-volatility", json=scenario_data)
            
            # Print error response if status code is not 200
            if response.status_code != 200:
                print(f"Error response: {response.json()}")
            
            # Verify the response
            assert response.status_code == 200
            data = response.json()
            assert "volatilities" in data
            assert "prices" in data
            assert "deltas" in data
            assert "vegas" in data
            assert len(data["volatilities"]) == 5
            assert len(data["prices"]) == 5
        finally:
            # Clean up the override
            app.dependency_overrides.pop(get_option_pricer, None)

    @patch('app.services.option_pricing.OptionPricer')
    def test_time_decay_scenario(self, mock_option_pricer, test_client):
        """Test the time decay scenario endpoint."""
        # Import necessary dependencies
        from app.routes.scenarios import get_option_pricer, get_db
        from app.models.database import DBPosition
        
        # Mock the OptionPricer instance
        mock_service_instance = MagicMock()
        mock_option_pricer.return_value = mock_service_instance
        
        # Set up the mock return value for multiple days to expiry
        def side_effect_func(*args, **kwargs):
            days_to_expiry = kwargs.get("days_to_expiry", 30)
            return {
                "price": 5.0 * (days_to_expiry / 30),  # Simple formula for test
                "delta": 0.6,
                "gamma": 0.05,
                "theta": -0.1 * (days_to_expiry / 30),
                "vega": 0.2,
                "rho": 0.15,
                "time_to_expiry": days_to_expiry
            }
        
        mock_service_instance.price_option.side_effect = side_effect_func
        
        # Create a mock position ID
        position_id = str(uuid.uuid4())
        
        # Create a mock database session
        mock_db = MagicMock()
        
        # Create a mock position
        mock_position = MagicMock(spec=DBPosition)
        mock_position.id = position_id
        mock_position.ticker = "AAPL"
        mock_position.expiration = self.sample_expiration_date
        mock_position.strike = 150.0
        mock_position.option_type = "call"
        mock_position.action = "buy"
        mock_position.quantity = 1
        
        # Set up the mock query to return our mock position
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = [mock_position]
        
        # Mock the market data service used in the endpoint
        with patch('app.routes.scenarios.market_data_service') as mock_market_data:
            mock_market_data.get_stock_price.return_value = 155.0
            mock_market_data.get_implied_volatility.return_value = 0.2
            
            # Mock the scenario engine used in the endpoint
            with patch('app.routes.scenarios.scenario_engine') as mock_scenario_engine:
                # Set up the mock return value for the price_vs_time_surface method
                mock_scenario_engine.price_vs_time_surface.return_value = {
                    "days": [1, 8, 15, 23, 30],
                    "prices": [0.17, 0.83, 1.67, 2.5, 5.0],
                    "thetas": [-0.003, -0.017, -0.033, -0.05, -0.1]
                }
                
                # Override the get_db dependency
                def override_get_db():
                    yield mock_db
                
                app.dependency_overrides[get_db] = override_get_db
                
                try:
                    # Request data matching ScenarioAnalysisRequest schema
                    scenario_data = {
                        "position_ids": [position_id],
                        "days_to_expiry_range": {
                            "min": 1,
                            "max": 30,
                            "steps": 5
                        }
                    }
                    
                    # Make the request
                    response = test_client.post("/scenarios/price-vs-time", json=scenario_data)
                    
                    # Print error response if status code is not 200
                    if response.status_code != 200:
                        print(f"Error response: {response.json()}")
                    
                    # Verify the response
                    assert response.status_code == 200
                    data = response.json()
                    assert "days" in data
                    assert "prices" in data
                    assert "thetas" in data
                    assert len(data["days"]) == 5
                    assert len(data["prices"]) == 5
                    assert len(data["thetas"]) == 5
                    
                    # Verify the scenario engine was called with the correct parameters
                    mock_scenario_engine.price_vs_time_surface.assert_called_once()
                    call_args = mock_scenario_engine.price_vs_time_surface.call_args[1]
                    assert "positions" in call_args
                    assert "current_price" in call_args
                    assert "current_vol" in call_args
                    assert "days_range" in call_args
                    assert call_args["current_price"] == 155.0
                    assert call_args["current_vol"] == 0.2
                
                finally:
                    # Clean up the override
                    app.dependency_overrides.pop(get_db, None)

    def test_cors_headers(self, test_client):
        """Test that CORS headers are properly set."""
        response = test_client.options(
            "/market-data/ticker/AAPL",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_error_handling(self, test_client):
        """Test error handling for invalid requests."""
        # Test with invalid option data
        invalid_option_data = {
            "option_type": "invalid_type",  # Should be 'call' or 'put'
            "strike": 150.0,
            "expiration_date": self.sample_expiration_date,
            "spot_price": 155.0,
            "volatility": 0.2,
            "risk_free_rate": 0.05,
            "dividend_yield": 0.0,
            "american": True
        }
        
        response = test_client.post("/greeks/calculate", json=invalid_option_data)
        
        # Verify the response
        assert response.status_code == 422  # Unprocessable Entity
        assert "detail" in response.json() 