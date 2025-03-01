# Market Data Provider System

This document provides an overview of the Market Data Provider system, which allows the application to fetch market data from different sources.

## Provider Architecture

The Market Data Provider system is designed using the Strategy pattern, allowing easy switching between different market data sources. The system consists of:

1. **Abstract Base Class**: `MarketDataProvider` defines the interface that all providers must implement.
2. **Concrete Providers**: Implementation of specific market data sources.
3. **Factory/Service**: `MarketDataService` selects and initializes the appropriate provider.

## Available Providers

### 1. Polygon.io Provider

The original provider that uses the Polygon.io API to fetch market data.

**Features:**
- Professional-grade market data
- Access to real-time and historical data
- Comprehensive options data
- Requires API key

### 2. YFinance Provider

A new provider that uses the Yahoo Finance API (via the yfinance library) to fetch market data.

**Features:**
- Free to use (no API key required)
- Good for development and testing
- May have limitations for high-volume production use
- Coverage for most major stocks and options

## Configuration

The provider selection is controlled by an environment variable:

```
MARKET_DATA_PROVIDER=yfinance  # or "polygon"
```

### Default Configuration

If no provider is specified, the system defaults to using YFinance.

## Adding a New Provider

To add a new market data provider:

1. Create a new class that extends `MarketDataProvider`
2. Implement all required methods
3. Add the provider to the factory in `market_data.py`

Example:

```python
# New provider implementation
class NewProvider(MarketDataProvider):
    def __init__(self):
        super().__init__()
        # Provider-specific initialization
    
    # Implement all required methods
    
# Add to factory in market_data.py
def get_provider():
    provider_name = os.getenv("MARKET_DATA_PROVIDER", "yfinance").lower()
    
    if provider_name == "polygon":
        return PolygonProvider()
    elif provider_name == "yfinance":
        return YFinanceProvider()
    elif provider_name == "newprovider":
        return NewProvider()
    else:
        # Default to YFinance
        return YFinanceProvider()
```

## Data Standardization

Each provider is responsible for transforming its specific API responses into a standardized format that the rest of the application expects. This ensures that changing providers doesn't affect code that uses the market data.

## Error Handling

Providers should implement appropriate error handling for their specific APIs. The base service will handle general exceptions, but provider-specific errors should be caught and transformed in the provider implementation.

## Caching

The caching mechanism is implemented at the service level and is available to all providers. However, each provider can also implement its own internal caching if needed.

## Testing

A test script is available at `tests/test_market_data_providers.py` that validates the functionality of each provider.

## Usage Example

```python
from services.market_data import MarketDataService
from datetime import datetime, timedelta

# Initialize the service (provider selected via environment variable)
service = MarketDataService()

# Get stock price
price = service.get_stock_price("AAPL")

# Get option chain
expiration = datetime.now() + timedelta(days=30)
options = service.get_option_chain("AAPL", expiration)

# Get historical data
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
history = service.get_historical_prices("AAPL", start_date, end_date)
```

## Performance Considerations

The performance characteristics of each provider may differ. YFinance is generally suitable for development and testing but may not be appropriate for high-frequency production use due to rate limiting and reliability concerns.

For production use with high performance requirements, Polygon.io is recommended.
