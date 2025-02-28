# Integration Tests for OptionsStrat Backend

This directory contains integration tests for the OptionsStrat backend. Unlike unit tests that test individual components in isolation, these integration tests verify that multiple components work together correctly in real-world scenarios.

## Test Files

- `test_strategy_pipeline.py`: Tests the full options strategy pipeline from creation to scenario analysis
- `test_market_data_pipeline.py`: Tests the market data retrieval, caching, and processing pipeline
- `test_database_persistence.py`: Tests database operations and relationships

## API Endpoint Structure

The backend API is organized with the following route prefixes:

- `/positions` - Endpoints for managing option positions and strategies
- `/greeks` - Endpoints for calculating option Greeks and implied volatility
- `/scenarios` - Endpoints for generating scenario analyses
- `/market-data` - Endpoints for retrieving market data

Important URLs to note:

```
# Positions
GET    /positions/                - List all positions
POST   /positions/with-legs       - Create a new position with option legs
GET    /positions/{id}            - Get position details
DELETE /positions/{id}            - Delete a position

# Greeks
GET    /greeks/position/{id}      - Calculate Greeks for a position
POST   /greeks/implied-volatility - Calculate implied volatility

# Scenarios
POST   /scenarios/price-vs-time   - Generate price vs time scenario
POST   /scenarios/price-vs-vol    - Generate price vs volatility scenario

# Market Data
GET    /market-data/ticker/{ticker}         - Get ticker details
GET    /market-data/price/{ticker}          - Get current price
GET    /market-data/option-chain/{ticker}   - Get option chain
GET    /market-data/expirations/{ticker}    - Get option expiration dates
```

## Request Payload Formats

### Creating a Position with Legs

```json
{
  "name": "AAPL Bull Call Spread",
  "description": "A bullish options strategy",
  "legs": [
    {
      "option_type": "call",
      "strike": 150,
      "expiration_date": "2023-12-15",
      "quantity": 1,
      "underlying_ticker": "AAPL",
      "underlying_price": 155.0,
      "option_price": 8.5,
      "volatility": 0.25
    },
    {
      "option_type": "call",
      "strike": 160,
      "expiration_date": "2023-12-15",
      "quantity": -1,
      "underlying_ticker": "AAPL",
      "underlying_price": 155.0,
      "option_price": 3.2,
      "volatility": 0.28
    }
  ]
}
```

Note that:
- `option_type` should be lowercase ("call" or "put")
- Use positive `quantity` for long positions and negative `quantity` for short positions
- Each leg needs its own `underlying_ticker`, `underlying_price`, and `volatility`

## Running Integration Tests

### Prerequisites

Before running integration tests, ensure you have:

1. Set up your development environment
2. Installed all dependencies
3. Set up a Redis instance for caching tests (optional but recommended)

### Running All Integration Tests

```bash
cd src/backend
pytest tests/integration_tests/ -v
```

Alternatively, use the provided script with the integration flag:

```bash
./run_all_tests.sh --with-integration
```

### Running Specific Integration Tests

```bash
# Run a specific test file
pytest tests/integration_tests/test_strategy_pipeline.py -v

# Run a specific test class
pytest tests/integration_tests/test_strategy_pipeline.py::TestOptionsStrategyPipeline -v

# Run a specific test method
pytest tests/integration_tests/test_strategy_pipeline.py::TestOptionsStrategyPipeline::test_full_strategy_pipeline -v
```

### Using Real vs. Mock Data

By default, integration tests use mock data for external APIs. To run tests with real API keys:

```bash
# Set your API keys first
export POLYGON_API_KEY="your_polygon_api_key"

# Run tests with real API
cd src/backend
pytest tests/integration_tests/ -v --use-real-api
```

### Test Configuration

You can customize the tests using the following environment variables:

- `TEST_DB_URL`: Database URL for integration tests (default: SQLite in-memory)
- `REDIS_HOST`: Redis host for caching tests (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `POLYGON_API_KEY`: Polygon.io API key for market data tests

## Common Issues and Troubleshooting

### 422 Unprocessable Entity Errors

This error occurs when the request payload doesn't match the expected schema.

Common causes:
1. **Incorrect field names**: Ensure field names match exactly (e.g., `option_price` not `price`)
2. **Wrong data types**: Check that all fields have the correct data types
3. **Missing required fields**: All required fields must be included
4. **Wrong case in enum values**: Option types should be lowercase (`"call"` instead of `"CALL"`)
5. **Wrong endpoint**: Make sure you're using `/positions/with-legs` for creating positions with multiple legs

### 500 Internal Server Error

This error indicates a server-side issue that prevented the request from completing.

Common causes:
1. **Database issues**: The database may not be properly set up or migrations not applied
2. **Missing dependencies**: Ensure all packages are installed
3. **Redis connection failure**: If Redis is required but not available
4. **External API failures**: When using real APIs instead of mocks
5. **Code exceptions**: Check the server logs for specific error messages

### Redis Connection Issues

Integration tests will skip Redis-dependent tests if Redis is not available. To run these tests:

1. Ensure Redis is running: `redis-server`
2. Check if Redis is running: `redis-cli ping` (should return `PONG`)
3. Set the correct Redis connection parameters:
   ```bash
   export REDIS_HOST=localhost
   export REDIS_PORT=6379
   ```

### API Endpoint 404 Errors

If you encounter 404 Not Found errors:

1. Check that you're using the correct route prefix for each resource
2. Ensure endpoint paths match exactly (e.g., `/positions/with-legs` not `/positions/`)
3. Verify that the ID exists for endpoints that require an ID parameter

## Adding New Integration Tests

When adding new integration tests:

1. Create a new test file in this directory
2. Use the `integration_client` fixture for API testing
3. Test complete end-to-end flows rather than individual components
4. Clean up any resources created during tests
5. Follow existing naming conventions and organization patterns

## Test Organization

Integration tests are organized by functionality:

- **Setup methods**: Prepare test data and environment
- **Test methods**: Execute the tests
- **Fixtures**: Define reusable components and test clients
- **Cleanup**: Ensure resources are properly released

## Continuous Integration

These integration tests are part of the CI/CD pipeline but may be skipped in some environments if external dependencies (like Redis) aren't available. 