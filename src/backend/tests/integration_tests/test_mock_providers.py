"""
Test that our mock providers for Redis and Polygon API are working correctly.
"""
import pytest
import time
from .mocks import MockRedis, MockPolygonAPI


class TestMockProviders:
    """Tests for the mock providers used in integration tests."""
    
    def test_mock_redis(self):
        """Verify the mock Redis implementation."""
        redis = MockRedis()
        
        # Test basic operations
        redis.set("test_key", "test_value")
        assert redis.get("test_key") == "test_value"
        
        # Test expiration
        redis.setex("expiring_key", 1, "will expire")
        assert redis.get("expiring_key") == "will expire"
        
        # Test deletion
        redis.delete("test_key")
        assert redis.get("test_key") is None
        
        # Test key pattern matching
        redis.set("prefix:key1", "value1")
        redis.set("prefix:key2", "value2")
        redis.set("other:key", "value3")
        
        assert len(redis.keys("prefix:*")) == 2
        
        # The expiring_key is still present until it expires, so we have 4 keys total
        # Either wait for expiration or adjust the assertion
        assert len(redis.keys("*")) == 4  # Changed from 3 to 4 to account for expiring_key
        
        # Wait for expiration and test again
        time.sleep(1.1)  # Wait slightly more than the 1 second expiry time
        assert redis.get("expiring_key") is None  # Should be expired now
        assert len(redis.keys("*")) == 3  # Now we should have only 3 keys
        
        # Test ping
        assert redis.ping() is True
    
    def test_mock_polygon_api(self):
        """Verify the mock Polygon API implementation."""
        api = MockPolygonAPI()
        
        # Test ticker details
        ticker_details = api.get_ticker_details("AAPL")
        assert ticker_details["status"] == "success"
        assert ticker_details["results"]["ticker"] == "AAPL"
        assert "price" in ticker_details["results"]
        
        # Test non-existent ticker
        non_existent_ticker = api.get_ticker_details("NONEXISTENT")
        assert non_existent_ticker["status"] == "error"
        
        # Test ticker price
        price_data = api.get_ticker_price("AAPL")
        assert price_data["status"] == "success"
        assert price_data["results"]["ticker"] == "AAPL"
        assert "price" in price_data["results"]
        
        # Test option expirations
        expirations = api.get_option_expirations("AAPL")
        assert expirations["status"] == "success"
        assert "expirations" in expirations["results"]
        assert len(expirations["results"]["expirations"]) > 0
        
        # Test option chain
        expiration = expirations["results"]["expirations"][0]
        chain = api.get_option_chain("AAPL", expiration)
        assert chain["status"] == "success"
        assert "options" in chain["results"]
        
        options = chain["results"]["options"]
        assert len(options) > 0
        
        # Verify option attributes
        option = options[0]
        assert "type" in option
        assert "strike_price" in option
        assert "implied_volatility" in option
        assert "bid" in option
        assert "ask" in option 