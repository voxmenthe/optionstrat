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
def mock_market_data_service(mock_redis, mock_polygon_api):
    """Provide a properly configured mock MarketDataService with a mock provider."""
    def get_market_data_service():
        # Create a service instance
        service = MarketDataService()
        
        # Create a mock provider
        from unittest.mock import MagicMock
        from app.services.market_data_provider import MarketDataProvider
        
        mock_provider = MagicMock(spec=MarketDataProvider)
        
        # Set up the mock provider methods to use our mock polygon API
        def get_ticker_details(ticker):
            endpoint = f"/v3/reference/tickers/{ticker}"
            result = mock_polygon_api_request(mock_polygon_api)(None, endpoint)
            return result["results"]
        
        def get_stock_price(ticker):
            # Return a mock stock price
            if ticker in mock_polygon_api.tickers:
                return mock_polygon_api.tickers[ticker]["price"]
            return 100.0
        
        def get_option_chain(ticker, expiration_date=None):
            endpoint = f"/v3/reference/options/contracts"
            params = {"underlying_ticker": ticker}
            if expiration_date:
                if isinstance(expiration_date, datetime):
                    params["expiration_date"] = expiration_date.strftime("%Y-%m-%d")
                else:
                    params["expiration_date"] = expiration_date
            
            result = mock_polygon_api_request(mock_polygon_api)(None, endpoint, params)
            return result["results"]
        
        def get_option_expirations(ticker):
            endpoint = f"/v3/reference/options/contracts/{ticker}"
            result = mock_polygon_api_request(mock_polygon_api)(None, endpoint)
            return result["results"]["expirations"]
        
        def get_historical_prices(ticker, from_date, to_date, timespan="day"):
            # Return some mock historical data
            return [
                {
                    "o": 150.25,    # open
                    "c": 152.87,    # close
                    "h": 153.12,    # high
                    "l": 149.95,    # low
                    "v": 55627300,  # volume
                    "t": int(datetime.timestamp(from_date) * 1000)  # timestamp
                },
                {
                    "o": 152.87,
                    "c": 155.10,
                    "h": 156.42,
                    "l": 152.10,
                    "v": 48123400,
                    "t": int(datetime.timestamp(to_date) * 1000)
                }
            ]
        
        def get_option_data(ticker, expiration_date, strike, option_type):
            # Create a mock option data response
            if isinstance(expiration_date, datetime):
                exp_str = expiration_date.strftime("%Y-%m-%d")
            else:
                exp_str = expiration_date
                
            # Generate a standardized option symbol
            option_type_code = "C" if option_type.lower() == "call" else "P"
            strike_formatted = str(int(float(strike) * 1000)).zfill(8)
            symbol = f"O:{ticker}{exp_str.replace('-','')}C{strike_formatted}"
            
            # Calculate a theoretical option price
            stock_price = get_stock_price(ticker)
            days_to_expiry = (datetime.strptime(exp_str, "%Y-%m-%d").date() - datetime.now().date()).days
            years_to_expiry = max(0.01, days_to_expiry / 365.0)
            
            # Simple price approximation
            iv = 0.3  # 30% implied volatility
            atm_factor = abs(float(strike) - stock_price) / stock_price
            time_value = stock_price * iv * (years_to_expiry ** 0.5) * 0.4 * (1 - 0.5 * atm_factor)
            
            if option_type.lower() == "call":
                intrinsic_value = max(0, stock_price - float(strike))
            else:
                intrinsic_value = max(0, float(strike) - stock_price)
                
            option_price = round(intrinsic_value + time_value, 2)
            option_price = max(0.1, option_price)  # Ensure minimum price
            
            return {
                "symbol": symbol,
                "price": option_price,
                "bid": round(option_price * 0.95, 2),
                "ask": round(option_price * 1.05, 2),
                "volume": 100,
                "open_interest": 500,
                "implied_volatility": iv,
                "delta": 0.65 if option_type.lower() == "call" else -0.65,
                "gamma": 0.05,
                "theta": -0.1,
                "vega": 0.2,
                "rho": 0.01,
                "timestamp": int(time.time() * 1000)
            }
            
        def get_option_strikes(ticker, expiration_date, option_type=None):
            # Return a list of strike prices around the current stock price
            stock_price = get_stock_price(ticker)
            strikes = []
            
            # Generate strikes at 5% intervals around the stock price
            for i in range(-4, 5):
                strikes.append(round(stock_price * (1 + i * 0.05), 2))
                
            return {
                "strikes": strikes,
                "count": len(strikes)
            }
            
        def get_market_status():
            # Return a mock market status
            return {
                "market": "open",
                "server_time": datetime.now().isoformat(),
                "exchanges": {
                    "nyse": "open",
                    "nasdaq": "open"
                }
            }
            
        def search_tickers(query):
            # Return mock search results
            return [
                {"ticker": query.upper(), "name": f"{query.upper()} Inc.", "market": "stocks"},
                {"ticker": f"{query.upper()}.X", "name": f"{query.upper()} Index", "market": "indices"}
            ]
            
        def get_earnings_calendar(ticker=None, from_date=None, to_date=None):
            # Create mock earnings calendar data
            if from_date and to_date:
                days_range = (to_date - from_date).days
            else:
                days_range = 10  # Default range
                
            # Sample earnings announcements
            earnings = []
            base_date = datetime.now()
            
            # Sample companies with upcoming earnings
            companies = [
                {"ticker": "AAPL", "name": "Apple Inc."},
                {"ticker": "MSFT", "name": "Microsoft Corporation"},
                {"ticker": "AMZN", "name": "Amazon.com Inc."},
                {"ticker": "GOOGL", "name": "Alphabet Inc."},
                {"ticker": "META", "name": "Meta Platforms Inc."}
            ]
            
            # If ticker is provided, filter the list
            if ticker:
                companies = [c for c in companies if c["ticker"] == ticker]
            
            # Generate earnings events
            for i, company in enumerate(companies):
                # Calculate a future date for the earnings
                event_date = base_date + timedelta(days=(i % days_range) + 1)
                
                earnings.append({
                    "ticker": company["ticker"],
                    "company_name": company["name"],
                    "report_date": event_date.strftime("%Y-%m-%d"),
                    "quarter": f"Q{((event_date.month-1)//3)+1} {event_date.year}",
                    "estimate_eps": round(1.5 + 0.1 * i, 2),
                    "actual_eps": None,  # Not reported yet
                    "time": "after_market" if i % 2 == 0 else "before_market"
                })
            
            return earnings
            
        def get_economic_calendar(from_date=None, to_date=None):
            # Create mock economic calendar data
            if from_date and to_date:
                days_range = (to_date - from_date).days
            else:
                days_range = 10  # Default range
                
            # Sample economic events
            events = []
            base_date = datetime.now()
            
            # Sample economic indicators
            economic_indicators = [
                {"name": "Non-Farm Payrolls", "country": "US", "importance": "high"},
                {"name": "CPI", "country": "US", "importance": "high"},
                {"name": "GDP", "country": "US", "importance": "high"},
                {"name": "FOMC Statement", "country": "US", "importance": "high"},
                {"name": "Retail Sales", "country": "US", "importance": "medium"},
                {"name": "PMI", "country": "US", "importance": "medium"},
                {"name": "Unemployment Rate", "country": "US", "importance": "high"}
            ]
            
            # Generate economic events
            for i, indicator in enumerate(economic_indicators):
                # Calculate a future date for the event
                event_date = base_date + timedelta(days=(i % days_range) + 1)
                
                events.append({
                    "name": indicator["name"],
                    "country": indicator["country"],
                    "date": event_date.strftime("%Y-%m-%d"),
                    "time": "08:30" if i % 2 == 0 else "14:00",
                    "importance": indicator["importance"],
                    "forecast": None,
                    "previous": "2.5%" if "%" in indicator["name"] else "250K"
                })
            
            return events
            
        def get_implied_volatility(ticker):
            # Return a mock implied volatility value
            # Use a consistent but somewhat random value based on the ticker symbol
            seed = sum(ord(c) for c in ticker)
            volatility = 0.15 + (seed % 10) / 100  # Generate values between 0.15 and 0.25
            return round(volatility, 2)
        
        # Assign the mock methods to the mock provider
        mock_provider.get_ticker_details.side_effect = get_ticker_details
        mock_provider.get_stock_price.side_effect = get_stock_price
        mock_provider.get_option_chain.side_effect = get_option_chain
        mock_provider.get_option_expirations.side_effect = get_option_expirations
        mock_provider.get_historical_prices.side_effect = get_historical_prices
        # TODO: Implement get_option_data when option chain functionality is fully implemented
        # mock_provider.get_option_data.side_effect = get_option_data
        mock_provider.get_option_strikes.side_effect = get_option_strikes
        # TODO: Implement get_market_status when market data functionality is fully implemented
        # mock_provider.get_market_status.side_effect = get_market_status
        # TODO: Implement search_tickers when functionality is fully implemented
        # mock_provider.search_tickers.side_effect = search_tickers
        # TODO: Implement get_earnings_calendar when functionality is fully implemented
        # mock_provider.get_earnings_calendar.side_effect = get_earnings_calendar
        # TODO: Implement get_economic_calendar when functionality is fully implemented
        # mock_provider.get_economic_calendar.side_effect = get_economic_calendar
        # TODO: Implement get_implied_volatility when functionality is fully implemented
        # mock_provider.get_implied_volatility.side_effect = get_implied_volatility
        
        # Replace the service's provider with our mock
        service.provider = mock_provider
        
        return service
    
    return get_market_data_service