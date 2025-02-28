"""
Mocks for integration testing.

This package provides mock implementations of external dependencies
to avoid relying on real external services during testing.
"""

from .polygon_api_mock import MockPolygonAPI
from .redis_mock import MockRedis

__all__ = ['MockPolygonAPI', 'MockRedis'] 