# Backend Testing Suite

This directory contains comprehensive test scripts for the OptionsStrat backend components. The tests are organized by component and functionality to ensure thorough coverage of the codebase.

## Test Files

- `test_option_pricing.py`: Tests for the QuantLib option pricing service
- `test_market_data.py`: Tests for the Polygon.io market data integration
- `test_api_endpoints.py`: Tests for the FastAPI endpoints
- `test_database.py`: Tests for database operations and position management
- `test_scenario_engine.py`: Tests for scenario analysis calculations
- `test_health.py`: Basic health check tests for the API

## Running Tests

### Prerequisites

Make sure you have all the required dependencies installed:

```bash
uv sync  # Install dependencies (dev group included by default)
```

### Using Test Scripts

We provide several convenient scripts for running tests:

#### Comprehensive Test Runner (Recommended)

The `run_all_tests.sh` script provides a flexible way to run tests with various options:

```bash
# Run all tests with mock API key
./src/backend/run_all_tests.sh

# Run a specific test file
./src/backend/run_all_tests.sh src/backend/tests/test_api_endpoints.py

# Run a specific test class or method
./src/backend/run_all_tests.sh src/backend/tests/test_api_endpoints.py::TestAPIEndpoints::test_health_check

# Generate HTML coverage report
./src/backend/run_all_tests.sh --html

# Use real API keys instead of mocks
./src/backend/run_all_tests.sh --no-mock

# Combine options
./src/backend/run_all_tests.sh src/backend/tests/test_database.py --html
```

#### Other Test Scripts

- `src/backend/run_tests.sh`: Runs tests with coverage and generates an HTML report
- `src/backend/run_test_with_mock.sh`: Runs tests with a mocked Polygon API key

### Running Tests Manually

To run all tests with pytest:

```bash
uv run pytest src/backend/tests/
```

### Running Specific Test Files

To run tests from a specific file:

```bash
uv run pytest src/backend/tests/test_option_pricing.py
```

### Running Specific Test Classes or Methods

To run a specific test class:

```bash
uv run pytest src/backend/tests/test_market_data.py::TestMarketDataService
```

To run a specific test method:

```bash
uv run pytest src/backend/tests/test_market_data.py::TestMarketDataService::test_get_option_chain
```

## Test Coverage

To generate a test coverage report:

```bash
uv run pytest --cov=app src/backend/tests/
```

For a detailed HTML coverage report:

```bash
uv run pytest --cov=app --cov-report=html src/backend/tests/
```

The HTML report will be generated in the `htmlcov` directory.

## Mocking External Services

The tests use Python's `unittest.mock` library to mock external services like Polygon.io API and Redis. This ensures that tests can run without actual network connections or external dependencies.

By default, our test scripts use a mock Polygon API key (`test_api_key_for_mocking`). You can disable this behavior with the `--no-mock` flag if you want to test with real API keys.

Example of mocking in `test_market_data.py`:

```python
@patch('app.services.market_data.requests.get')
def test_get_ticker_details(self, mock_get):
    # Mock setup and assertions
```

## Test Database

Database tests use an in-memory SQLite database to avoid affecting any real database. The database is created fresh for each test and destroyed afterward.

## Integration Tests

Integration tests verify that different components work together correctly. They test the flow from API request to database operation to response.

## Performance Tests

Some tests include performance benchmarks to ensure that calculations remain efficient, especially for large datasets or complex scenarios.

## Adding New Tests

When adding new functionality to the backend, please follow these guidelines for creating tests:

1. Create test methods in the appropriate test class
2. Use descriptive method names that explain what is being tested
3. Include docstrings that describe the test purpose
4. Mock external dependencies
5. Test both success and failure cases
6. Verify all relevant aspects of the output

## Continuous Integration

These tests are run automatically in the CI/CD pipeline on every pull request and merge to the main branch. 
