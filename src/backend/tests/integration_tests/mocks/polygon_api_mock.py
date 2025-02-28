"""
Mock for the Polygon.io API service for use in integration tests.

This module provides mock data and responses for the Polygon API
to avoid making real API calls during tests.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


class MockPolygonAPI:
    """Mock implementation of the Polygon API for testing."""
    
    def __init__(self):
        """Initialize with mock data."""
        self.tickers = {
            "AAPL": {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "market": "stocks",
                "price": 175.50,
                "previous_close": 173.75,
                "change": 1.75,
                "change_percent": 1.01,
            },
            "SPY": {
                "ticker": "SPY",
                "name": "SPDR S&P 500 ETF Trust",
                "market": "stocks",
                "price": 430.25,
                "previous_close": 428.50,
                "change": 1.75,
                "change_percent": 0.41,
            }
        }
        
        # Generate some mock option expirations
        today = datetime.today().date()
        days_to_friday = (4 - today.weekday()) % 7
        if days_to_friday == 0:
            days_to_friday = 7
            
        self.expirations = {
            "AAPL": [
                (today + timedelta(days=days_to_friday)).strftime("%Y-%m-%d"),
                (today + timedelta(days=days_to_friday + 7)).strftime("%Y-%m-%d"),
                (today + timedelta(days=days_to_friday + 14)).strftime("%Y-%m-%d"),
                (today + timedelta(days=days_to_friday + 28)).strftime("%Y-%m-%d"),
                (today + timedelta(days=days_to_friday + 90)).strftime("%Y-%m-%d"),
            ],
            "SPY": [
                (today + timedelta(days=days_to_friday)).strftime("%Y-%m-%d"),
                (today + timedelta(days=days_to_friday + 7)).strftime("%Y-%m-%d"),
                (today + timedelta(days=days_to_friday + 14)).strftime("%Y-%m-%d"),
                (today + timedelta(days=days_to_friday + 28)).strftime("%Y-%m-%d"),
                (today + timedelta(days=days_to_friday + 90)).strftime("%Y-%m-%d"),
            ]
        }
        
        # Generate mock options data
        self.generate_options_data()
    
    def generate_options_data(self):
        """Generate mock options data for each ticker and expiration."""
        self.options_data = {}
        
        for ticker, ticker_data in self.tickers.items():
            underlying_price = ticker_data["price"]
            self.options_data[ticker] = {}
            
            for expiration in self.expirations[ticker]:
                # Calculate days to expiration for pricing
                exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
                days_to_exp = (exp_date - datetime.today().date()).days
                
                # Generate strikes around current price
                strikes = [
                    round(underlying_price * (1 - 0.15 + i * 0.03), 1)
                    for i in range(11)
                ]
                
                options = []
                
                for strike in strikes:
                    # Calculate approximate option prices and greeks
                    atm_factor = abs(strike - underlying_price) / underlying_price
                    expiration_factor = days_to_exp / 30  # Normalize to 30 days
                    
                    # Call option
                    call_price = max(0.1, (underlying_price - strike) + 2 * expiration_factor * underlying_price * 0.05)
                    call_iv = 0.2 + 0.1 * atm_factor + 0.05 * expiration_factor
                    
                    options.append({
                        "type": "call",
                        "strike_price": strike,
                        "expiration_date": expiration,
                        "symbol": f"{ticker}{exp_date.strftime('%y%m%d')}C{int(strike * 1000)}",
                        "bid": round(call_price * 0.95, 2),
                        "ask": round(call_price * 1.05, 2),
                        "last_price": round(call_price, 2),
                        "volume": int(1000 * (1 - atm_factor)),
                        "open_interest": int(5000 * (1 - atm_factor)),
                        "implied_volatility": round(call_iv, 4),
                        "delta": round(0.5 - 0.5 * atm_factor if strike < underlying_price else 0.5 * (1 - atm_factor), 2),
                        "gamma": round(0.05 * (1 - atm_factor), 4),
                        "theta": round(-0.05 * expiration_factor, 4),
                        "vega": round(0.1 * expiration_factor, 4)
                    })
                    
                    # Put option
                    put_price = max(0.1, (strike - underlying_price) + 2 * expiration_factor * underlying_price * 0.05)
                    put_iv = 0.2 + 0.1 * atm_factor + 0.05 * expiration_factor
                    
                    options.append({
                        "type": "put",
                        "strike_price": strike,
                        "expiration_date": expiration,
                        "symbol": f"{ticker}{exp_date.strftime('%y%m%d')}P{int(strike * 1000)}",
                        "bid": round(put_price * 0.95, 2),
                        "ask": round(put_price * 1.05, 2),
                        "last_price": round(put_price, 2),
                        "volume": int(1000 * (1 - atm_factor)),
                        "open_interest": int(5000 * (1 - atm_factor)),
                        "implied_volatility": round(put_iv, 4),
                        "delta": round(-0.5 + 0.5 * atm_factor if strike > underlying_price else -0.5 * (1 - atm_factor), 2),
                        "gamma": round(0.05 * (1 - atm_factor), 4),
                        "theta": round(-0.05 * expiration_factor, 4),
                        "vega": round(0.1 * expiration_factor, 4)
                    })
                
                self.options_data[ticker][expiration] = options
    
    def get_ticker_details(self, ticker: str) -> Dict:
        """Get mock ticker details."""
        if ticker not in self.tickers:
            return {"status": "error", "message": f"Ticker {ticker} not found"}
        
        return {
            "status": "success",
            "results": self.tickers[ticker]
        }
    
    def get_ticker_price(self, ticker: str) -> Dict:
        """Get mock ticker price."""
        if ticker not in self.tickers:
            return {"status": "error", "message": f"Ticker {ticker} not found"}
        
        return {
            "status": "success",
            "results": {
                "ticker": ticker,
                "price": self.tickers[ticker]["price"]
            }
        }
    
    def get_option_expirations(self, ticker: str) -> Dict:
        """Get mock option expirations."""
        if ticker not in self.expirations:
            return {"status": "error", "message": f"No expirations found for {ticker}"}
        
        return {
            "status": "success",
            "results": {
                "ticker": ticker,
                "expirations": self.expirations[ticker]
            }
        }
    
    def get_option_chain(self, ticker: str, expiration_date: str) -> Dict:
        """Get mock option chain."""
        if ticker not in self.options_data:
            return {"status": "error", "message": f"No options data found for {ticker}"}
        
        if expiration_date not in self.options_data[ticker]:
            return {"status": "error", "message": f"No options found for {ticker} with expiration {expiration_date}"}
        
        return {
            "status": "success",
            "results": {
                "ticker": ticker,
                "expiration_date": expiration_date,
                "options": self.options_data[ticker][expiration_date]
            }
        } 