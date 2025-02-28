"""
Common test fixtures for integration tests.

This module provides shared fixtures that can be used across integration tests.
"""
import pytest
from fastapi.testclient import TestClient
import redis
import os
from contextlib import contextmanager
import sys
from unittest.mock import patch

from app.main import app
from app.models.database import Base, engine, SessionLocal, get_db
from app.services.market_data import MarketDataService

# Import our mocks
from .mocks import MockRedis, MockPolygonAPI


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create test database tables before tests run and clean up after."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Optionally drop tables after tests finish
    # Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def test_db():
    """Create a test database that persists for the entire test session."""
    # Create a test session
    db = SessionLocal()
    try:
        yield db
    finally:
        # Clean up - close the session but don't drop tables
        # to allow inspection after tests if needed
        db.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test function."""
    # Create a test session
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()  # Rollback any uncommitted changes
        db.close()


@contextmanager
def override_get_db():
    """Context manager for overriding the get_db dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def mock_redis():
    """Provide a mock Redis implementation for testing."""
    return MockRedis()


@pytest.fixture(scope="session")
def mock_polygon_api():
    """Provide a mock Polygon API implementation for testing."""
    return MockPolygonAPI()


@pytest.fixture(scope="session")
def client():
    """Create a test client for the FastAPI app."""
    # Use a TestClient to make requests to the API
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def integration_client(mock_redis, mock_polygon_api):
    """Create a test client with a persistent database session and mocked dependencies."""
    # Override the get_db dependency to use our test database
    original_dependency = app.dependency_overrides.get(get_db)
    
    # Apply the override
    app.dependency_overrides[get_db] = lambda: override_get_db().__enter__()
    
    # Apply patches for external services
    with patch('redis.Redis', return_value=mock_redis):
        with patch.object(MarketDataService, '_make_request', side_effect=mock_polygon_api_request(mock_polygon_api)):
            # Create and return the test client
            with TestClient(app) as test_client:
                yield test_client
    
    # Clean up by removing the override or restoring the original
    if original_dependency:
        app.dependency_overrides[get_db] = original_dependency
    else:
        app.dependency_overrides.pop(get_db, None)


def mock_polygon_api_request(mock_api):
    """Create a side_effect function for mocking Polygon API requests."""
    def _mock_request(self, endpoint, params=None):
        params = params or {}
        
        # Extract ticker from endpoint if present
        ticker = None
        if '/v3/reference/tickers/' in endpoint:
            # Format: /v3/reference/tickers/AAPL
            parts = endpoint.split('/')
            ticker = parts[-1]
        elif '/v2/aggs/ticker/' in endpoint:
            # Format: /v2/aggs/ticker/AAPL/prev
            parts = endpoint.split('/')
            ticker = parts[-2]
        elif '/v3/reference/options/contracts/' in endpoint and not endpoint.endswith('/contracts'):
            # Format: /v3/reference/options/contracts/AAPL
            parts = endpoint.split('/')
            ticker = parts[-1]
        elif 'underlying_ticker' in params:
            ticker = params['underlying_ticker']
        elif 'ticker' in params:
            ticker = params['ticker']
        elif 'symbol' in params:
            ticker = params['symbol']
        
        # Simple mapping of endpoints to mock methods
        if ticker and endpoint.endswith('/prev'):
            return mock_api.get_ticker_price(ticker)
        elif ticker and '/v3/reference/tickers/' in endpoint:
            return mock_api.get_ticker_details(ticker)
        elif '/v3/reference/options/contracts' in endpoint and 'expiration_date' in params:
            # Option chain endpoint
            ticker = params.get('underlying_ticker', '')
            expiration = params.get('expiration_date', '')
            return mock_api.get_option_chain(ticker, expiration)
        elif '/v3/reference/options/contracts/' in endpoint and ticker:
            # Option expirations endpoint
            return mock_api.get_option_expirations(ticker)
        
        # Default response for unhandled endpoints
        return {
            "status": "success",
            "results": {"message": "Mocked response for " + endpoint}
        }
    
    return _mock_request


@pytest.fixture(scope="session")
def redis_client(mock_redis):
    """Provide the mock Redis client for tests that require it."""
    return mock_redis 