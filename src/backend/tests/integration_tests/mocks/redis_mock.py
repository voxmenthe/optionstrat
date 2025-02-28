"""
Mock Redis client for integration tests.

This module provides a simple in-memory mock for Redis to use during testing.
"""
from typing import Dict, Any, Optional, Union
import json
import time


class MockRedis:
    """Mock Redis client that stores data in memory."""
    
    def __init__(self):
        """Initialize an empty storage dict."""
        self.storage = {}
        self.expirations = {}
    
    def get(self, key: str) -> Optional[str]:
        """Get a value from the mock Redis."""
        # Check if key exists and hasn't expired
        if key in self.storage:
            if key in self.expirations and self.expirations[key] < time.time():
                # Key has expired
                self.delete(key)
                return None
            return self.storage[key]
        return None
    
    def set(self, key: str, value: str) -> bool:
        """Set a value in the mock Redis."""
        self.storage[key] = value
        return True
    
    def setex(self, key: str, seconds: int, value: str) -> bool:
        """Set a value with an expiration time."""
        self.storage[key] = value
        self.expirations[key] = time.time() + seconds
        return True
    
    def delete(self, key: str) -> int:
        """Delete a key from the mock Redis."""
        if key in self.storage:
            del self.storage[key]
            if key in self.expirations:
                del self.expirations[key]
            return 1
        return 0
    
    def _check_expirations(self):
        """Check for expired keys and delete them."""
        now = time.time()
        expired_keys = [k for k, exp_time in self.expirations.items() 
                      if exp_time < now and k in self.storage]
        for key in expired_keys:
            self.delete(key)
    
    def keys(self, pattern: str = "*") -> list:
        """Get keys matching a pattern."""
        # First check for any expired keys
        self._check_expirations()
        
        # Simple implementation that only supports prefix matching with *
        if pattern == "*":
            return list(self.storage.keys())
        
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self.storage.keys() if k.startswith(prefix)]
        
        return [k for k in self.storage.keys() if k == pattern]
    
    def ping(self) -> bool:
        """Mock ping always succeeds."""
        return True
    
    def ttl(self, key: str) -> int:
        """Get the time to live for a key."""
        # First check if key has expired
        if key in self.expirations and self.expirations[key] < time.time():
            self.delete(key)
            return -2
            
        if key not in self.storage:
            return -2
        if key not in self.expirations:
            return -1
        
        remaining = self.expirations[key] - time.time()
        return max(0, int(remaining))
    
    def exists(self, key: str) -> int:
        """Check if a key exists."""
        # First check if key has expired
        if key in self.expirations and self.expirations[key] < time.time():
            self.delete(key)
            return 0
            
        return 1 if key in self.storage else 0
    
    def flushdb(self) -> bool:
        """Clear all keys in the current database."""
        self.storage.clear()
        self.expirations.clear()
        return True 