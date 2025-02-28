import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.services.market_data import MarketDataService


class TestMarketDataService:
    """Test suite for the MarketDataService class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use a test API key
        self.api_key = "test_api_key"
        # Disable caching for most tests
        self.service = MarketDataService(api_key=self.api_key, use_cache=False)
        
        # Sample test data
        self.sample_ticker = "AAPL"
        self.sample_option_symbol = "O:AAPL230616C00150000"
        self.sample_expiration_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    @patch('app.services.market_data.requests.get')
    def test_get_ticker_details(self, mock_get):
        """Test fetching ticker details."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "NASDAQ",
                "type": "CS",
                "active": True,
                "currency_name": "usd",
                "cik": "0000320193",
                "composite_figi": "BBG000B9XRY4",
                "share_class_figi": "BBG001S5N8V8",
                "last_updated_utc": "2023-02-10T00:00:00Z"
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the method
        result = self.service.get_ticker_details(self.sample_ticker)

        # Verify the API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert f"{self.service.base_url}/v3/reference/tickers/{self.sample_ticker}" == call_args
        
        # Verify the result
        assert result["status"] == "OK"
        assert result["results"]["ticker"] == "AAPL"
        assert result["results"]["name"] == "Apple Inc."

    @patch('app.services.market_data.requests.get')
    def test_get_stock_price(self, mock_get):
        """Test fetching stock price."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": {
                "T": "AAPL",
                "p": 150.25,
                "s": 100,
                "t": 1677685200000,
                "c": ["@", "T"],
                "z": "A"
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the method
        result = self.service.get_stock_price(self.sample_ticker)

        # Verify the API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert f"{self.service.base_url}/v2/last/trade/{self.sample_ticker}" == call_args
        
        # Verify the result
        assert result == 150.25

    @patch('app.services.market_data.requests.get')
    def test_get_stock_price_not_found(self, mock_get):
        """Test error handling when stock price is not found."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": None
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the method and expect an exception
        with pytest.raises(HTTPException) as excinfo:
            self.service.get_stock_price(self.sample_ticker)
        
        # Verify the exception
        assert excinfo.value.status_code == 404
        assert f"No price data found for {self.sample_ticker}" in str(excinfo.value.detail)

    @patch('app.services.market_data.requests.get')
    def test_get_option_chain(self, mock_get):
        """Test fetching option chain."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [
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
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the method
        result = self.service.get_option_chain(
            self.sample_ticker, 
            expiration_date=self.sample_expiration_date
        )

        # Verify the API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert f"{self.service.base_url}/v3/reference/options/contracts" == call_args
        
        # Verify the parameters
        call_kwargs = mock_get.call_args[1]['params']
        assert call_kwargs["underlying_ticker"] == self.sample_ticker
        assert call_kwargs["limit"] == 1000
        assert call_kwargs["expiration_date"] == self.sample_expiration_date
        
        # Verify the result
        assert len(result) == 2
        assert result[0]["underlying_ticker"] == "AAPL"
        assert result[0]["strike_price"] == 150.0
        assert result[0]["contract_type"] == "call"
        assert result[1]["contract_type"] == "put"

    @patch('app.services.market_data.requests.get')
    def test_get_option_price(self, mock_get):
        """Test fetching option price."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": {
                "T": self.sample_option_symbol,
                "p": 5.75,
                "s": 10,
                "t": 1677685200000,
                "c": ["@", "T"],
                "z": "A"
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the method
        result = self.service.get_option_price(self.sample_option_symbol)

        # Verify the API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert f"{self.service.base_url}/v2/last/trade/{self.sample_option_symbol}" == call_args
        
        # Verify the result
        assert result["price"] == 5.75
        assert result["timestamp"] == 1677685200000

    @patch('app.services.market_data.requests.get')
    def test_api_error_handling(self, mock_get):
        """Test handling of API errors."""
        # Mock a failed response
        mock_get.side_effect = Exception("API connection error")

        # Call the method and expect an exception
        with pytest.raises(HTTPException) as excinfo:
            self.service.get_ticker_details(self.sample_ticker)
        
        # Verify the exception
        assert excinfo.value.status_code == 500
        assert "Polygon.io API error" in str(excinfo.value.detail)

    @patch('app.services.market_data.redis.Redis')
    @patch('app.services.market_data.requests.get')
    def test_caching_mechanism(self, mock_get, mock_redis):
        """Test that responses are cached and retrieved from cache."""
        # Set up the Redis mock before creating the service
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        
        # Create a service with caching enabled
        service_with_cache = MarketDataService(api_key=self.api_key, use_cache=True)
        
        # Ensure the Redis instance is properly set
        service_with_cache.redis = mock_redis_instance
        
        # First call - not in cache
        mock_redis_instance.get.return_value = None
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": {
                "ticker": "AAPL",
                "name": "Apple Inc."
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # First call should make an API request
        result1 = service_with_cache.get_ticker_details(self.sample_ticker)
        assert mock_get.call_count == 1
        
        # Verify the result
        assert result1["status"] == "OK"
        assert result1["results"]["ticker"] == "AAPL"
        
        # Verify that the result was cached
        mock_redis_instance.setex.assert_called_once()
        
        # Second call - should be in cache
        cached_response = json.dumps(mock_response.json.return_value)
        mock_redis_instance.get.return_value = cached_response
        
        # Reset the mock for the second call
        mock_get.reset_mock()
        
        # Second call should use the cache
        result2 = service_with_cache.get_ticker_details(self.sample_ticker)
        
        # Verify no API call was made
        mock_get.assert_not_called()
        
        # Verify the result is the same
        assert result2["status"] == "OK"
        assert result2["results"]["ticker"] == "AAPL"

    @patch('app.services.market_data.requests.get')
    def test_historical_prices(self, mock_get):
        """Test fetching historical prices."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [
                {
                    "v": 55627300,  # volume
                    "o": 148.75,    # open
                    "c": 150.25,    # close
                    "h": 151.42,    # high
                    "l": 148.12,    # low
                    "t": 1677685200000  # timestamp
                },
                {
                    "v": 48123400,
                    "o": 150.25,
                    "c": 152.87,
                    "h": 153.12,
                    "l": 149.95,
                    "t": 1677771600000
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the method
        from_date = datetime(2023, 3, 1)
        to_date = datetime(2023, 3, 3)
        result = self.service.get_historical_prices(
            self.sample_ticker,
            from_date=from_date,
            to_date=to_date
        )

        # Verify the API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        expected_url = f"{self.service.base_url}/v2/aggs/ticker/{self.sample_ticker}/range/1/day/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}"
        assert expected_url == call_args
        
        # Verify the result
        assert len(result) == 2
        assert result[0]["o"] == 148.75
        assert result[0]["c"] == 150.25
        assert result[1]["o"] == 150.25
        assert result[1]["c"] == 152.87 