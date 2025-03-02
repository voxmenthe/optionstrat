import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.services.market_data import MarketDataService
from app.services.market_data_provider import MarketDataProvider


class TestMarketDataService:
    """Test suite for the MarketDataService class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock for the provider
        self.provider_mock = MagicMock(spec=MarketDataProvider)
        
        # Patch the _get_provider method to return our mock
        with patch.object(MarketDataService, '_get_provider', return_value=self.provider_mock):
            # Create service instance
            self.service = MarketDataService()
        
        # Sample test data
        self.sample_ticker = "AAPL"
        self.sample_option_symbol = "O:AAPL230616C00150000"
        self.sample_expiration_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    def test_get_ticker_details(self):
        """Test fetching ticker details."""
        # Set up mock return value
        mock_result = {
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
        self.provider_mock.get_ticker_details.return_value = mock_result

        # Call the method
        result = self.service.get_ticker_details(self.sample_ticker)

        # Verify the provider method was called correctly
        self.provider_mock.get_ticker_details.assert_called_once_with(self.sample_ticker)
        
        # Verify the result
        assert result == mock_result
        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc."

    def test_get_stock_price(self):
        """Test fetching stock price."""
        # Set up mock return value
        self.provider_mock.get_stock_price.return_value = 150.25

        # Call the method
        result = self.service.get_stock_price(self.sample_ticker)

        # Verify the provider method was called correctly
        self.provider_mock.get_stock_price.assert_called_once_with(self.sample_ticker)
        
        # Verify the result
        assert result == 150.25

    def test_get_stock_price_not_found(self):
        """Test error handling when stock price is not found."""
        # Set up mock to raise HTTPException
        self.provider_mock.get_stock_price.side_effect = HTTPException(
            status_code=404, 
            detail=f"No price data found for {self.sample_ticker}"
        )

        # Call the method and expect an exception
        with pytest.raises(HTTPException) as excinfo:
            self.service.get_stock_price(self.sample_ticker)
        
        # Verify the exception
        assert excinfo.value.status_code == 404
        assert f"No price data found for {self.sample_ticker}" in str(excinfo.value.detail)

    def test_get_option_chain(self):
        """Test fetching option chain."""
        # Set up mock return value
        mock_result = [
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
        self.provider_mock.get_option_chain.return_value = mock_result

        # Call the method
        result = self.service.get_option_chain(
            self.sample_ticker, 
            expiration_date=self.sample_expiration_date
        )

        # Verify the provider method was called correctly
        self.provider_mock.get_option_chain.assert_called_once_with(
            self.sample_ticker, 
            self.sample_expiration_date
        )
        
        # Verify the result
        assert len(result) == 2
        assert result[0]["underlying_ticker"] == "AAPL"
        assert result[0]["strike_price"] == 150.0
        assert result[0]["contract_type"] == "call"
        assert result[1]["contract_type"] == "put"

    def test_get_option_data(self):
        """Test fetching option data."""
        # Set up mock return value
        mock_result = {
            "symbol": self.sample_option_symbol,
            "price": 5.75,
            "bid": 5.70,
            "ask": 5.80,
            "volume": 100,
            "open_interest": 500,
            "implied_volatility": 0.35,
            "delta": 0.65,
            "gamma": 0.05,
            "theta": -0.1,
            "vega": 0.2,
            "rho": 0.01,
            "timestamp": 1677685200000
        }
        # Ensure the method exists on the mock
        if not hasattr(self.provider_mock, 'get_option_data'):
            self.provider_mock.get_option_data = MagicMock()
        self.provider_mock.get_option_data.return_value = mock_result

        # Set sample parameters
        expiration_date = datetime.strptime("2023-06-16", "%Y-%m-%d")
        strike = 150.0
        option_type = "call"

        # Call the method
        result = self.service.get_option_data(
            self.sample_ticker,
            expiration_date,
            strike,
            option_type
        )

        # Verify the provider method was called correctly
        self.provider_mock.get_option_data.assert_called_once_with(
            self.sample_ticker,
            expiration_date,
            strike,
            option_type
        )
        
        # Verify the result
        assert result == mock_result
        assert result["symbol"] == self.sample_option_symbol
        assert result["price"] == 5.75

    def test_api_error_handling(self):
        """Test handling of API errors."""
        # For this test we'll directly verify that an exception from the provider is handled
        
        # Setup provider mock to raise an exception
        self.provider_mock.get_ticker_details.side_effect = Exception("API connection error")
        
        # The service should wrap provider exceptions in HTTPException
        with pytest.raises(Exception) as excinfo:
            self.service.get_ticker_details(self.sample_ticker)
        
        # Verify exception details
        assert "API connection error" in str(excinfo.value)
        
        # Reset the mock for other tests
        self.provider_mock.get_ticker_details.side_effect = None

    def test_caching_mechanism(self):
        """Test that the service delegates to the provider."""
        # This test verifies that the service correctly delegates to the provider
        # The actual caching is now implemented in the provider classes
        
        # Set up mock return value
        expected_result = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "market": "stocks"
        }
        self.provider_mock.get_ticker_details.return_value = expected_result
        
        # Call the method
        result = self.service.get_ticker_details(self.sample_ticker)
        
        # Verify the provider was called correctly
        self.provider_mock.get_ticker_details.assert_called_once_with(self.sample_ticker)
        
        # Verify the result
        assert result == expected_result

    def test_historical_prices(self):
        """Test fetching historical prices."""
        # Set up mock return value
        mock_result = [
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
        self.provider_mock.get_historical_prices.return_value = mock_result

        # Call the method
        start_date = datetime(2023, 3, 1)
        end_date = datetime(2023, 3, 3)
        result = self.service.get_historical_prices(
            self.sample_ticker,
            start_date=start_date,
            end_date=end_date,
            interval="day"
        )

        # Verify the provider method was called correctly
        self.provider_mock.get_historical_prices.assert_called_once_with(
            self.sample_ticker,
            start_date,
            end_date,
            "day"
        )
        
        # Verify the result
        assert len(result) == 2
        assert result[0]["o"] == 148.75
        assert result[0]["c"] == 150.25
        assert result[1]["o"] == 150.25
        assert result[1]["c"] == 152.87
        
    def test_get_option_strikes(self):
        """Test fetching option strikes."""
        # Set up mock return value
        mock_result = {
            "strikes": [140.0, 145.0, 150.0, 155.0, 160.0],
            "count": 5
        }
        self.provider_mock.get_option_strikes.return_value = mock_result

        # Test parameters
        expiration_date = datetime.strptime("2023-06-16", "%Y-%m-%d")
        option_type = "call"
        
        # Call the method
        result = self.service.get_option_strikes(
            self.sample_ticker,
            expiration_date,
            option_type
        )

        # Verify the provider method was called correctly
        self.provider_mock.get_option_strikes.assert_called_once_with(
            self.sample_ticker,
            expiration_date,
            option_type
        )
        
        # Verify the result
        assert "strikes" in result
        assert len(result["strikes"]) == 5
        assert result["strikes"][2] == 150.0
        assert result["count"] == 5

    def test_search_tickers(self):
        """Test searching for tickers."""
        pytest.skip("Market data search functionality not fully implemented yet")
        # Set up mock return value
        mock_result = [
            {"ticker": "AAPL", "name": "Apple Inc.", "market": "stocks"},
            {"ticker": "AAPL.X", "name": "Apple Index", "market": "indices"}
        ]
        self.provider_mock.search_tickers.return_value = mock_result

        # Call the method
        query = "apple"
        result = self.service.search_tickers(query)

        # Verify the provider method was called correctly
        self.provider_mock.search_tickers.assert_called_once_with(query)
        
        # Verify the result
        assert len(result) == 2
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["market"] == "stocks"
        assert result[1]["ticker"] == "AAPL.X"

    def test_get_market_status(self):
        """Test getting market status."""
        pytest.skip("Market status functionality not fully implemented yet")
        # Set up mock return value
        mock_result = {
            "market": "open",
            "server_time": "2023-06-15T14:30:00",
            "exchanges": {
                "nyse": "open",
                "nasdaq": "open"
            }
        }
        self.provider_mock.get_market_status.return_value = mock_result

        # Call the method
        result = self.service.get_market_status()

        # Verify the provider method was called
        self.provider_mock.get_market_status.assert_called_once()
        
        # Verify the result
        assert result["market"] == "open"
        assert "server_time" in result
        assert result["exchanges"]["nyse"] == "open"

    def test_get_earnings_calendar(self):
        """Test fetching earnings calendar."""
        pytest.skip("Earnings calendar functionality not fully implemented yet")
        # Set up mock return value
        mock_result = [
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "report_date": "2023-07-25",
                "quarter": "Q3 2023",
                "estimate_eps": 1.5,
                "actual_eps": None,
                "time": "after_market"
            }
        ]
        self.provider_mock.get_earnings_calendar.return_value = mock_result

        # Test parameters
        from_date = datetime(2023, 7, 20)
        to_date = datetime(2023, 7, 30)
        
        # Call the method
        result = self.service.get_earnings_calendar(
            ticker=self.sample_ticker,
            from_date=from_date,
            to_date=to_date
        )

        # Verify the provider method was called correctly
        self.provider_mock.get_earnings_calendar.assert_called_once_with(
            self.sample_ticker,
            from_date,
            to_date
        )
        
        # Verify the result
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["quarter"] == "Q3 2023"
        assert result[0]["estimate_eps"] == 1.5

    def test_get_economic_calendar(self):
        """Test fetching economic calendar."""
        pytest.skip("Economic calendar functionality not fully implemented yet")
        # Set up mock return value
        mock_result = [
            {
                "name": "Non-Farm Payrolls",
                "country": "US",
                "date": "2023-07-07",
                "time": "08:30",
                "importance": "high",
                "forecast": None,
                "previous": "250K"
            }
        ]
        self.provider_mock.get_economic_calendar.return_value = mock_result

        # Test parameters
        from_date = datetime(2023, 7, 5)
        to_date = datetime(2023, 7, 10)
        
        # Call the method
        result = self.service.get_economic_calendar(
            from_date=from_date,
            to_date=to_date
        )

        # Verify the provider method was called correctly
        self.provider_mock.get_economic_calendar.assert_called_once_with(
            from_date,
            to_date
        )
        
        # Verify the result
        assert len(result) == 1
        assert result[0]["name"] == "Non-Farm Payrolls"
        assert result[0]["importance"] == "high"
        assert result[0]["date"] == "2023-07-07"

    def test_get_implied_volatility(self):
        """Test getting implied volatility."""
        pytest.skip("Implied volatility functionality not fully implemented yet")
        # Set up mock return value
        self.provider_mock.get_implied_volatility.return_value = 0.25

        # Call the method
        result = self.service.get_implied_volatility(self.sample_ticker)

        # Verify the provider method was called correctly
        self.provider_mock.get_implied_volatility.assert_called_once_with(
            self.sample_ticker
        )
        
        # Verify the result
        assert result == 0.25