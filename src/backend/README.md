# OptionsStrat Backend

This is the backend API for the Options Scenario Analysis & Exploration App. It provides endpoints for option pricing, Greeks calculation, scenario analysis, and market data.

## Features

- Option pricing and Greeks calculation using QuantLib
- Scenario analysis for option strategies
- Market data integration with Polygon.io
- Redis caching for API responses
- SQLite database for position storage

## Requirements

- Python 3.11+
- Poetry (for dependency management)
- QuantLib 1.32
- FastAPI 0.109+
- SQLAlchemy 2.0+
- Redis (optional, for caching)

## Installation

1. Clone the repository
2. Install Poetry if you don't have it already:
   ```
   curl -sSL https://install.python-poetry.org | python3 -
   ```
3. Install dependencies using Poetry:
   ```
   cd src/backend
   poetry install
   ```
4. Copy `.env.example` to `.env` and update with your API keys:
   ```
   cp .env.example .env
   ```

## Running the API

Start the FastAPI server using Poetry:

```
poetry run uvicorn app.main:app --reload
```

Or activate the Poetry shell first and then run:

```
poetry shell
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000.

API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

### Code Formatting and Linting

This project uses Black, isort, and flake8 for code formatting and linting:

```
# Format code
poetry run black .
poetry run isort .

# Lint code
poetry run flake8 .
poetry run mypy .
```

### Testing

Run tests using pytest:

```
poetry run pytest
```

## API Endpoints

### Positions

- `GET /positions`: Get all positions
- `GET /positions/{position_id}`: Get a specific position
- `POST /positions`: Create a new position
- `PUT /positions/{position_id}`: Update a position
- `DELETE /positions/{position_id}`: Delete a position

### Greeks

- `POST /greeks/calculate`: Calculate Greeks for an option
- `POST /greeks/implied-volatility`: Calculate implied volatility
- `GET /greeks/position/{position_id}`: Get Greeks for a position
- `GET /greeks/portfolio`: Get aggregate Greeks for a portfolio

### Scenarios

- `POST /scenarios/price-vs-vol`: Generate price vs. volatility surface
- `POST /scenarios/price-vs-time`: Generate price vs. time surface
- `POST /scenarios/greeks-profile`: Generate Greeks profiles
- `GET /scenarios/strategy/{strategy_name}`: Get pre-defined strategy analysis

### Market Data

- `GET /market-data/ticker/{ticker}`: Get ticker details
- `GET /market-data/price/{ticker}`: Get stock price
- `GET /market-data/option-chain/{ticker}`: Get option chain
- `GET /market-data/option-price/{option_symbol}`: Get option price
- `GET /market-data/historical-prices/{ticker}`: Get historical prices
- `GET /market-data/implied-volatility/{ticker}`: Get implied volatility
- `GET /market-data/expirations/{ticker}`: Get option expirations
- `GET /market-data/strikes/{ticker}`: Get option strikes

## License

MIT 