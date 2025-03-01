import os
import sys
import logging
from datetime import datetime, timedelta
from pprint import pprint

# Add the parent directory to sys.path to import app modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from services.market_data import MarketDataService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def compare_providers(ticker="AAPL"):
    """Compare data between YFinance and Polygon providers."""
    # Configure providers
    os.environ["MARKET_DATA_PROVIDER"] = "yfinance"
    yf_service = MarketDataService()
    
    os.environ["MARKET_DATA_PROVIDER"] = "polygon"
    polygon_service = MarketDataService()
    
    # Get current date and a future expiration date
    today = datetime.now()
    expiration = today + timedelta(days=30)  # ~1 month out
    
    # Compare stock prices
    print(f"\n===== COMPARING STOCK PRICES FOR {ticker} =====")
    yf_price = yf_service.get_stock_price(ticker)
    polygon_price = polygon_service.get_stock_price(ticker)
    
    print(f"YFinance price: ${yf_price:.2f}")
    print(f"Polygon price: ${polygon_price:.2f}")
    print(f"Difference: ${abs(yf_price - polygon_price):.2f}")
    
    # Compare options data
    print(f"\n===== COMPARING OPTION CHAIN FOR {ticker} (Expiry: {expiration.date()}) =====")
    yf_options = yf_service.get_option_chain(ticker, expiration)
    polygon_options = polygon_service.get_option_chain(ticker, expiration)
    
    print(f"YFinance options count: {len(yf_options)}")
    print(f"Polygon options count: {len(polygon_options)}")
    
    # Show a sample call option from each provider
    yf_calls = [opt for opt in yf_options if opt.get("option_type", "").lower() == "call"]
    polygon_calls = [opt for opt in polygon_options if opt.get("option_type", "").lower() == "call"]
    
    if yf_calls:
        print("\nYFinance sample call option:")
        pprint(yf_calls[0])
    
    if polygon_calls:
        print("\nPolygon sample call option:")
        pprint(polygon_calls[0])
    
    # Compare historical data
    print(f"\n===== COMPARING HISTORICAL PRICES FOR {ticker} (Last 7 days) =====")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    yf_history = yf_service.get_historical_prices(ticker, start_date, end_date)
    polygon_history = polygon_service.get_historical_prices(ticker, start_date, end_date)
    
    print(f"YFinance data points: {len(yf_history)}")
    print(f"Polygon data points: {len(polygon_history)}")
    
    # Show the latest data point from each
    if yf_history:
        print("\nYFinance latest historical data:")
        pprint(yf_history[-1])
    
    if polygon_history:
        print("\nPolygon latest historical data:")
        pprint(polygon_history[-1])

if __name__ == "__main__":
    # Set the ticker to compare
    ticker = "AAPL"  # Can be changed to any other ticker
    
    print(f"Comparing market data providers for {ticker}")
    compare_providers(ticker)
