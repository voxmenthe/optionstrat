"""
Mock implementations for testing.

This module provides mock implementations of services for testing purposes.
"""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union


class MockRedis:
    """
    Mock implementation of Redis for testing.
    
    This class implements a subset of the Redis client interface
    that is used in our application for testing purposes.
    """
    
    def __init__(self):
        """Initialize with an empty storage dict."""
        self.storage = {}
        self.expiry = {}
    
    def set(self, key: str, value: str) -> bool:
        """Set a key-value pair."""
        self.storage[key] = value
        return True
    
    def get(self, key: str) -> Optional[str]:
        """Get a value by key."""
        self._check_expiry(key)
        return self.storage.get(key)
    
    def setex(self, key: str, expires: int, value: str) -> bool:
        """Set a key with an expiration time."""
        self.storage[key] = value
        self.expiry[key] = time.time() + expires
        return True
    
    def delete(self, key: str) -> bool:
        """Delete a key."""
        if key in self.storage:
            del self.storage[key]
            if key in self.expiry:
                del self.expiry[key]
            return True
        return False
    
    def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching a pattern."""
        import fnmatch
        self._check_all_expiry()
        if pattern == "*":
            return list(self.storage.keys())
        return [k for k in self.storage.keys() if fnmatch.fnmatch(k, pattern)]
    
    def ping(self) -> bool:
        """Test connection."""
        return True
    
    def _check_expiry(self, key: str) -> None:
        """Check if a key has expired and remove it if so."""
        if key in self.expiry and time.time() > self.expiry[key]:
            del self.storage[key]
            del self.expiry[key]
    
    def _check_all_expiry(self) -> None:
        """Check all keys for expiry."""
        now = time.time()
        expired_keys = [k for k, exp in self.expiry.items() if now > exp]
        for key in expired_keys:
            if key in self.storage:
                del self.storage[key]
            del self.expiry[key]


class MockPolygonAPI:
    """
    Mock implementation of the Polygon.io API for testing.
    
    This class provides predefined responses for API endpoints
    that would normally be called on the Polygon.io API.
    """
    
    def __init__(self):
        """Initialize with some predefined test data."""
        # Sample ticker data
        self.tickers = {
            "AAPL": {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "market": "stocks",
                "locale": "us",
                "currency": "USD",
                "primary_exchange": "NASDAQ",
                "type": "CS",
                "active": True,
                "last_updated_utc": datetime.now().isoformat(),
                "price": 150.0
            },
            "MSFT": {
                "ticker": "MSFT",
                "name": "Microsoft Corporation",
                "market": "stocks",
                "locale": "us",
                "currency": "USD",
                "primary_exchange": "NASDAQ",
                "type": "CS",
                "active": True,
                "last_updated_utc": datetime.now().isoformat(),
                "price": 300.0
            },
            "TSLA": {
                "ticker": "TSLA",
                "name": "Tesla, Inc.",
                "market": "stocks",
                "locale": "us",
                "currency": "USD",
                "primary_exchange": "NASDAQ",
                "type": "CS",
                "active": True,
                "last_updated_utc": datetime.now().isoformat(),
                "price": 250.0
            }
        }
