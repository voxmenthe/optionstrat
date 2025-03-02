"""
Test module for the Option Chain API endpoints.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import json
from fastapi.testclient import TestClient

from app.main import app
from app.services.option_chain_service import OptionChainService
from app.services.market_data import MarketDataService
from app.routes.options import get_option_chain_service
from app.models.database import get_db


@pytest.fixture
def mock_option_chain_service():
    """Fixture for a mocked option chain service."""
    mock_service = MagicMock(spec=OptionChainService)
    
    # Define sample option chain data
    sample_options = [
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
    
    # Define sample expiration dates
    sample_expirations = [
        datetime.strptime("2025-03-21", "%Y-%m-%d"),
        datetime.strptime("2025-06-20", "%Y-%m-%d")
    ]
    
    # Set up mock return values
    mock_service.get_option_chain.return_value = sample_options
    mock_service.get_expirations.return_value = sample_expirations
    
    return mock_service


@pytest.fixture
def mock_market_data_service():
    """Fixture for a mocked market data service."""
    mock_service = MagicMock(spec=MarketDataService)
    
    # Sample ticker search results
    search_results = [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "APLS", "name": "Apellis Pharmaceuticals, Inc."}
    ]
    
    # Set up mock return values
    mock_service.search_tickers.return_value = search_results
    
    return mock_service

# Create an override_get_db fixture to use an in-memory database
@pytest.fixture
def override_get_db():
    """Override the get_db dependency for testing."""
    # This is a simplified version for our test - in a real scenario you'd use a test DB
    db = MagicMock()
    try:
        yield db
    finally:
        pass  # We don't need to close our mock


# Create a client fixture with mocked dependencies
@pytest.fixture
def client(mock_option_chain_service, mock_market_data_service):
    """Create a test client with the mocked service."""
    # Set up dependency overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_option_chain_service] = lambda: mock_option_chain_service
    
    # Override the market data service dependency for search_tickers endpoint
    app.dependency_overrides[lambda: MarketDataService()] = lambda: mock_market_data_service
    
    # Create client
    with TestClient(app) as client:
        yield client
    
    # Clean up
    app.dependency_overrides = {}


class TestOptionApiEndpoints:
    """Test suite for the Option Chain API endpoints."""
    
    def test_get_options_chain(self, client, mock_option_chain_service):
        """Test the get options chain endpoint."""
        # Make API request
        ticker = "AAPL"
        response = client.get(f"/options/chains/{ticker}")
        
        # Verify the response
        assert response.status_code == 200
        result = response.json()
        assert len(result) == 2
        assert result[0]["ticker"] == ticker
        assert result[0]["strike"] == 200.0
        
        # Verify the mock was called correctly
        mock_option_chain_service.get_option_chain.assert_called_once()
    
    def test_get_options_chain_with_filters(self, client, mock_option_chain_service):
        """Test the get options chain endpoint with filters."""
        # Configure the mock to return filtered options
        filtered_options = [opt for opt in mock_option_chain_service.get_option_chain.return_value 
                          if opt["option_type"] == "call"]
        mock_option_chain_service.get_option_chain.return_value = filtered_options
        
        # Make API request with filters
        ticker = "AAPL"
        option_type = "call"
        min_strike = 200.0
        
        response = client.get(f"/options/chains/{ticker}?option_type={option_type}&min_strike={min_strike}")
        
        # Verify the response
        assert response.status_code == 200
        result = response.json()
        assert len(result) == 1
        assert result[0]["option_type"] == "call"
        
    def test_get_option_expirations(self, client, mock_option_chain_service):
        """Test the get option expirations endpoint."""
        # Make API request
        ticker = "AAPL"
        response = client.get(f"/options/chains/{ticker}/expirations")
        
        # Verify the response
        assert response.status_code == 200
        result = response.json()
        assert len(result) == 2
        assert "2025-03-21" in [exp["formatted_date"] for exp in result]
        assert "2025-06-20" in [exp["formatted_date"] for exp in result]
        
    def test_get_options_for_expiration(self, client, mock_option_chain_service):
        """Test the get options for expiration endpoint."""
        # Make API request
        ticker = "AAPL"
        expiration_date = "2025-06-20"
        
        response = client.get(f"/options/chains/{ticker}/{expiration_date}")
        
        # Verify the response
        assert response.status_code == 200
        result = response.json()
        assert len(result) == 2
        assert all(opt["expiration"].startswith("2025-06-20") for opt in result)
        
    def test_search_tickers(self, client, mock_market_data_service):
        """Test the search tickers endpoint."""
        # Make API request
        query = "APL"
        response = client.get(f"/options/search/{query}")
        
        # Verify the response
        assert response.status_code == 200
        result = response.json()
        assert len(result) == 2
        assert result[0]["symbol"] == "AAPL"
        assert result[1]["symbol"] == "APLS"
        
        # Verify the mock was called correctly
        mock_market_data_service.search_tickers.assert_called_once_with(query)
