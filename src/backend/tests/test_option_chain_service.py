"""
Test module for the Option Chain Service.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from app.services.option_chain_service import OptionChainService
from app.services.market_data import MarketDataService


@pytest.fixture
def mock_market_data_service():
    """Fixture for a mocked market data service."""
    mock_service = MagicMock(spec=MarketDataService)
    
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
        },
        {
            "ticker": "AAPL",
            "expiration": "2025-06-20T00:00:00",
            "strike": 205.0,
            "option_type": "call",
            "bid": 8.3,
            "ask": 8.7,
            "volume": 600,
            "open_interest": 3800,
            "implied_volatility": 0.32,
            "delta": 0.58,
        },
    ]
    
    # Define sample expiration dates
    sample_expirations = [
        datetime.strptime("2025-03-21", "%Y-%m-%d"),
        datetime.strptime("2025-04-18", "%Y-%m-%d"),
        datetime.strptime("2025-06-20", "%Y-%m-%d"),
        datetime.strptime("2025-09-19", "%Y-%m-%d"),
    ]
    
    # Define option data for a specific contract
    sample_option_data = {
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
        "gamma": 0.03,
        "theta": -0.15,
        "vega": 0.8,
        "rho": 0.2,
    }
    
    # Set up mock return values
    mock_service.get_option_chain.return_value = sample_options
    mock_service.get_option_expirations.return_value = sample_expirations
    mock_service.get_option_data.return_value = sample_option_data
    
    return mock_service


def test_get_option_chain(mock_market_data_service):
    """Test getting option chain data."""
    # Create the service with our mock
    service = OptionChainService(mock_market_data_service)
    
    # Call the method
    options = service.get_option_chain("AAPL")
    
    # Verify the result
    assert len(options) == 3
    assert options[0]["ticker"] == "AAPL"
    assert options[0]["strike"] == 200.0
    assert options[0]["option_type"] == "call"
    
    # Verify the mock was called correctly
    mock_market_data_service.get_option_chain.assert_called_once_with("AAPL", None)


def test_get_option_chain_with_filters(mock_market_data_service):
    """Test getting option chain data with filters."""
    # Create the service with our mock
    service = OptionChainService(mock_market_data_service)
    
    # Define expiration date
    expiration_date = datetime.strptime("2025-06-20", "%Y-%m-%d")
    
    # Call with option_type filter
    call_options = service.get_option_chain("AAPL", expiration_date, "call")
    
    # Verify the result
    assert len(call_options) == 2
    assert all(option["option_type"] == "call" for option in call_options)
    
    # Call with strike filter
    filtered_options = service.get_option_chain(
        "AAPL", 
        expiration_date, 
        min_strike=205.0
    )
    
    # Verify the result
    assert len(filtered_options) == 1
    assert filtered_options[0]["strike"] == 205.0


def test_get_expirations(mock_market_data_service):
    """Test getting option expiration dates."""
    # Create the service with our mock
    service = OptionChainService(mock_market_data_service)
    
    # Call the method
    expirations = service.get_expirations("AAPL")
    
    # Verify the result
    assert len(expirations) == 4
    assert expirations[0].strftime("%Y-%m-%d") == "2025-03-21"
    
    # Verify the mock was called correctly
    mock_market_data_service.get_option_expirations.assert_called_once_with("AAPL")


def test_get_option_data(mock_market_data_service):
    """Test getting specific option data."""
    # Create the service with our mock
    service = OptionChainService(mock_market_data_service)
    
    # Define parameters
    ticker = "AAPL"
    expiration_date = datetime.strptime("2025-06-20", "%Y-%m-%d")
    strike = 200.0
    option_type = "call"
    
    # Call the method
    option_data = service.get_option_data(ticker, expiration_date, strike, option_type)
    
    # Verify the result
    assert option_data["ticker"] == ticker
    assert option_data["strike"] == strike
    assert option_data["option_type"] == option_type
    assert option_data["implied_volatility"] == 0.35
    
    # Verify the mock was called correctly
    mock_market_data_service.get_option_data.assert_called_once_with(
        ticker, expiration_date, strike, option_type
    )


def test_caching(mock_market_data_service):
    """Test that caching works correctly."""
    # Create the service with our mock
    service = OptionChainService(mock_market_data_service)
    
    # Call the method twice
    service.get_option_chain("AAPL")
    service.get_option_chain("AAPL")
    
    # Verify that the mock was only called once (because of caching)
    assert mock_market_data_service.get_option_chain.call_count == 1
    
    # Call with different parameters
    service.get_option_chain("MSFT")
    
    # Verify that the mock was called again (different cache key)
    assert mock_market_data_service.get_option_chain.call_count == 2
