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
import json
from datetime import datetime
import time

from app.main import app
from app.models.database import Base, engine, SessionLocal, get_db
from app.services.market_data import MarketDataService
from app.services.option_pricing import OptionPricer  # Add import for OptionPricer

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
def integration_client(mock_redis, mock_polygon_api, mock_market_data_service):
    """Create a test client with a persistent database session and mocked dependencies."""
    # Override the get_db dependency to use our test database
    original_dependency = app.dependency_overrides.get(get_db)
    
    # Apply the override
    app.dependency_overrides[get_db] = lambda: override_get_db().__enter__()
    
    # Override market data service to use our mocked redis
    from app.routes.market_data import get_market_data_service
    app.dependency_overrides[get_market_data_service] = mock_market_data_service
    
    # Apply patches for external services
    with patch('redis.Redis', return_value=mock_redis):
        with patch.object(MarketDataService, '_make_request', new=mock_polygon_api_request(mock_polygon_api)):
            # Create and return the test client
            with TestClient(app) as test_client:
                yield test_client
    
    # Clean up by removing the override or restoring the original
    if original_dependency:
        app.dependency_overrides[get_db] = original_dependency
    else:
        app.dependency_overrides.pop(get_db, None)
    
    # Remove the market data service override
    app.dependency_overrides.pop(get_market_data_service, None)


def mock_polygon_api_request(mock_api):
    """Create a function for mocking Polygon API requests."""
    from datetime import datetime  # Add local import to ensure datetime is available
    
    def _mock_request(self, endpoint, params=None):
        """
        Mock implementation of the _make_request method.
        
        Args:
            self: The MarketDataService instance
            endpoint: The API endpoint
            params: Optional query parameters
        """
        params = params or {}
        
        # Add API key to params to match real behavior
        params["apiKey"] = self.api_key
        
        print(f"Mock API request to {endpoint} with params {params}")
        
        # Create cache key if caching is enabled
        cache_key = None
        if hasattr(self, 'use_cache') and self.use_cache and hasattr(self, 'redis'):
            # Use specific cache key format for ticker details
            if "/v3/reference/tickers/" in endpoint:
                ticker = endpoint.split("/")[-1]
                cache_key = f"ticker_details:{ticker}"
                print(f"[DEBUG MOCK] Created cache key: {cache_key}")
            else:
                import json
                cache_key = f"polygon:{endpoint}:{json.dumps(params, sort_keys=True)}"
                
            if hasattr(self, '_get_from_cache'):
                cached_data = self._get_from_cache(cache_key)
                if cached_data:
                    print(f"[DEBUG MOCK] Cache hit for {cache_key}")
                    return cached_data
            
            print(f"[DEBUG MOCK] Cache miss for {cache_key}")
        
        # Simulate a small delay like a real API call would have
        time.sleep(0.01)
        
        # Handle different endpoint types
        if '/v3/reference/tickers/' in endpoint:
            # Format: /v3/reference/tickers/AAPL
            symbol = endpoint.split('/')[-1]
            
            # Return mock ticker data
            if symbol in mock_api.tickers:
                ticker_data = mock_api.tickers[symbol]
                response = {
                    "status": "OK",
                    "results": ticker_data
                }
            else:
                # Create basic data for unknown tickers
                response = {
                    "status": "OK",
                    "results": {
                        "ticker": symbol,
                        "name": f"{symbol} Inc.",
                        "market": "stocks",
                        "price": 100.0
                    }
                }
            print(f"Mock API: returning ticker data for {symbol}")
            
            # IMPORTANT: Save to cache if caching is enabled
            if hasattr(self, 'use_cache') and self.use_cache and hasattr(self, '_save_to_cache') and cache_key:
                print(f"[DEBUG MOCK] Saving to cache with key {cache_key}")
                try:
                    self._save_to_cache(cache_key, response)
                    # Verify cache was saved correctly
                    if hasattr(self, 'redis') and hasattr(self.redis, 'get'):
                        cached = self.redis.get(cache_key)
                        print(f"[DEBUG MOCK] Cache saved successfully: {cached is not None}")
                except Exception as e:
                    print(f"[DEBUG MOCK] Error saving to cache: {e}")
            
            return response
        elif '/v3/reference/options/contracts/' in endpoint and not endpoint.endswith('/contracts'):
            # Format: /v3/reference/options/contracts/AAPL
            # This is the endpoint for getting option expirations
            symbol = endpoint.split('/')[-1]
            
            # Generate mock expirations (next several Fridays)
            from datetime import timedelta
            
            expirations = []
            current_date = datetime.now().date()
            
            # Find next 4 Fridays for option expirations
            for _ in range(4):
                # Find next Friday
                days_until_friday = (4 - current_date.weekday()) % 7
                if days_until_friday == 0:
                    days_until_friday = 7
                
                next_friday = current_date + timedelta(days=days_until_friday)
                expirations.append(next_friday.strftime("%Y-%m-%d"))
                
                # Move to next week
                current_date = next_friday + timedelta(days=3)
            
            response = {
                "status": "OK",
                "results": {
                    "expirations": expirations
                }
            }
            print(f"Mock API: returning option expirations for {symbol}: {expirations}")
        elif '/v3/reference/options/contracts' in endpoint and 'underlying_ticker' in params and 'expiration_date' in params:
            # Format: /v3/reference/options/contracts?underlying_ticker=AAPL&expiration_date=2023-06-16
            # This endpoint returns the option chain for a specific expiration
            ticker = params['underlying_ticker']
            expiration = params['expiration_date']
            
            # Generate mock options chain with some calls and puts
            strike_base = 100.0
            if ticker in mock_api.tickers:
                strike_base = mock_api.tickers[ticker]["price"]
            
            # Create mock options
            options = []
            
            # Generate 5 calls and 5 puts around the current price
            for i in range(-2, 3):
                strike = round(strike_base * (1 + i * 0.05), 2)
                
                # Calculate time to expiration in years for more realistic pricing
                exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
                today = datetime.now().date()
                days_to_exp = (exp_date - today).days
                years_to_exp = days_to_exp / 365.0
                
                # Use a simple approximation of Black-Scholes for more realistic prices
                iv = 0.3  # 30% implied volatility
                atm_factor = abs(strike - strike_base) / strike_base
                
                # For call options, higher price when stock price > strike
                # For put options, higher price when stock price < strike
                # Include time value based on days to expiration
                
                # Call option
                intrinsic_value_call = max(0, strike_base - strike)
                time_value_call = strike_base * iv * (years_to_exp ** 0.5) * 0.4 * (1 - 0.5 * atm_factor)
                call_price = round(intrinsic_value_call + time_value_call, 2)
                call_price = max(0.1, call_price)  # Ensure minimum price
                
                call = {
                    "type": "call",
                    "strike_price": strike,
                    "expiration_date": expiration,
                    "symbol": f"O:{ticker}{expiration.replace('-','')}C{str(int(strike*1000)).zfill(8)}",
                    "underlying_ticker": ticker,
                    "bid": round(call_price * 0.95, 2),
                    "ask": round(call_price * 1.05, 2),
                    "last_price": call_price,
                    "volume": 100,
                    "open_interest": 500,
                    "implied_volatility": iv
                }
                
                # Put option
                intrinsic_value_put = max(0, strike - strike_base)
                time_value_put = strike_base * iv * (years_to_exp ** 0.5) * 0.4 * (1 - 0.5 * atm_factor)
                put_price = round(intrinsic_value_put + time_value_put, 2)
                put_price = max(0.1, put_price)  # Ensure minimum price
                
                put = {
                    "type": "put",
                    "strike_price": strike,
                    "expiration_date": expiration,
                    "symbol": f"O:{ticker}{expiration.replace('-','')}P{str(int(strike*1000)).zfill(8)}",
                    "underlying_ticker": ticker,
                    "bid": round(put_price * 0.95, 2),
                    "ask": round(put_price * 1.05, 2),
                    "last_price": put_price,
                    "volume": 100,
                    "open_interest": 500,
                    "implied_volatility": iv
                }
                
                options.append(call)
                options.append(put)
            
            # Return just the options array, not wrapped in a dictionary
            response = options
            print(f"Mock API: returning {len(options)} options for {ticker} expiring on {expiration}")
        elif '/v2/last/trade/' in endpoint:
            # Format: /v2/last/trade/AAPL
            symbol = endpoint.split('/')[-1]
            
            # Return mock price data
            if symbol in mock_api.tickers:
                price = mock_api.tickers[symbol]["price"]
            else:
                price = 100.0  # Default price if ticker not found
            
            response = {
                "status": "success",
                "results": {
                    "T": symbol,
                    "p": price,
                    "s": 100,
                    "t": int(datetime.now().timestamp() * 1000),
                    "c": ["@", "T"],
                    "z": "A"
                }
            }
            print(f"Mock API: returning price data for {symbol}: {response}")
        else:
            # Default response for unhandled endpoints
            response = {
                "status": "success",
                "results": {"message": f"Mocked response for {endpoint}"}
            }
            print(f"Mock API: returning default response for {endpoint}: {response}")
        
        return response
    
    return _mock_request


@pytest.fixture(scope="session")
def redis_client(mock_redis):
    """Provide the mock Redis client for tests that require it."""
    return mock_redis


# Add a dependency override function for MarketDataService
@pytest.fixture(scope="function")
def mock_market_data_service(mock_redis):
    """Provide a properly configured mock MarketDataService that uses our mock_redis."""
    def get_market_data_service():
        service = MarketDataService(api_key="test_key", use_cache=True)
        service.redis = mock_redis  # Override the redis client with our mock
        
        # Add a wrapper around the _save_to_cache method to debug it
        original_save_to_cache = service._save_to_cache
        
        def debug_save_to_cache(cache_key, data):
            print(f"\n[DEBUG] Saving to cache: key={cache_key}, data_type={type(data)}")
            try:
                result = original_save_to_cache(cache_key, data)
                # Verify the data was actually saved
                saved_data = mock_redis.get(cache_key)
                print(f"[DEBUG] Cache save result: {result}, saved_data: {saved_data is not None}")
                return result
            except Exception as e:
                print(f"[DEBUG] Error saving to cache: {e}")
                import traceback
                print(traceback.format_exc())
                raise
        
        # Replace the method with our debug version
        service._save_to_cache = debug_save_to_cache
        
        # Also enhance the get_from_cache method
        original_get_from_cache = service._get_from_cache
        
        def debug_get_from_cache(cache_key):
            print(f"\n[DEBUG] Getting from cache: key={cache_key}")
            result = original_get_from_cache(cache_key)
            print(f"[DEBUG] Cache get result: {result is not None}")
            return result
        
        service._get_from_cache = debug_get_from_cache
        
        return service
    
    return get_market_data_service 