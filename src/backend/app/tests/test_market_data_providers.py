import os
import sys
import logging
from datetime import datetime, timedelta

# Add the parent directory to sys.path to import app modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from services.market_data import MarketDataService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_provider_selection():
    """Test that the provider can be selected via environment variable."""
    # Test with YFinance provider (default)
    os.environ["MARKET_DATA_PROVIDER"] = "yfinance"
    yf_service = MarketDataService()
    logger.info(f"YFinance provider type: {yf_service.provider.__class__.__name__}")
    
    # Test with Polygon provider
    os.environ["MARKET_DATA_PROVIDER"] = "polygon"
    polygon_service = MarketDataService()
    logger.info(f"Polygon provider type: {polygon_service.provider.__class__.__name__}")
    
    return yf_service, polygon_service

def test_get_ticker_details(service, ticker="AAPL"):
    """Test getting ticker details."""
    try:
        details = service.get_ticker_details(ticker)
        logger.info(f"Ticker details for {ticker}: {details}")
        return True
    except Exception as e:
        logger.error(f"Error getting ticker details: {e}")
        return False

def test_get_stock_price(service, ticker="AAPL"):
    """Test getting stock price."""
    try:
        price = service.get_stock_price(ticker)
        logger.info(f"Stock price for {ticker}: {price}")
        return True
    except Exception as e:
        logger.error(f"Error getting stock price: {e}")
        return False

def test_get_option_chain(service, ticker="AAPL"):
    """Test getting option chain."""
    today = datetime.now()
    expiration = today + timedelta(days=30)  # Look ~1 month out
    try:
        chain = service.get_option_chain(ticker, expiration)
        logger.info(f"Option chain for {ticker} expiring on {expiration.date()}: {len(chain)} options")
        return True
    except Exception as e:
        logger.error(f"Error getting option chain: {e}")
        return False

def test_get_historical_prices(service, ticker="AAPL"):
    """Test getting historical prices."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    try:
        prices = service.get_historical_prices(ticker, start_date, end_date)
        logger.info(f"Historical prices for {ticker}: {len(prices)} data points")
        return True
    except Exception as e:
        logger.error(f"Error getting historical prices: {e}")
        return False

def run_all_tests():
    """Run all tests for both providers."""
    # Get services
    yf_service, polygon_service = test_provider_selection()
    
    # Test YFinance provider
    logger.info("\n=== Testing YFinance Provider ===")
    yf_results = {
        "ticker_details": test_get_ticker_details(yf_service),
        "stock_price": test_get_stock_price(yf_service),
        "option_chain": test_get_option_chain(yf_service),
        "historical_prices": test_get_historical_prices(yf_service)
    }
    
    # Test Polygon provider
    logger.info("\n=== Testing Polygon Provider ===")
    polygon_results = {
        "ticker_details": test_get_ticker_details(polygon_service),
        "stock_price": test_get_stock_price(polygon_service),
        "option_chain": test_get_option_chain(polygon_service),
        "historical_prices": test_get_historical_prices(polygon_service)
    }
    
    # Summary
    logger.info("\n=== Test Results Summary ===")
    logger.info(f"YFinance Provider: {sum(yf_results.values())}/{len(yf_results)} tests passed")
    logger.info(f"Polygon Provider: {sum(polygon_results.values())}/{len(polygon_results)} tests passed")
    
if __name__ == "__main__":
    run_all_tests()
