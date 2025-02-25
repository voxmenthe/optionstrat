# OptionsStrat - Options Scenario Analysis & Exploration App

A comprehensive tool for options traders to analyze and visualize option strategies, calculate Greeks, and explore different market scenarios.

## Features

- Option pricing and Greeks calculation using QuantLib
- Scenario analysis for option strategies
- Market data integration with Polygon.io
- Interactive visualizations for option strategies
- Position management and portfolio analysis

## Project Structure

- `src/frontend`: Next.js frontend application
- `src/backend`: FastAPI backend application

## Requirements

- Python 3.11+
- Node.js 18+
- Poetry (for Python dependency management)
- Docker and Docker Compose (optional, for containerized setup)
- Redis (for caching)

## Getting Started

### Using Docker Compose (Recommended)

1. Clone the repository
2. Create a `.env` file in the root directory with your Polygon.io API key:
   ```
   POLYGON_API_KEY=your_polygon_api_key_here
   ```
3. Start the application using Docker Compose:
   ```
   docker-compose up -d
   ```
4. Access the frontend at http://localhost:3000 and the backend API at http://localhost:8000

### Manual Setup

#### Backend

1. Navigate to the backend directory:
   ```
   cd src/backend
   ```
2. Install dependencies using Poetry:
   ```
   poetry install
   ```
3. Copy `.env.example` to `.env` and update with your API keys:
   ```
   cp .env.example .env
   ```
4. Start the FastAPI server:
   ```
   poetry run uvicorn app.main:app --reload
   ```

#### Frontend

1. Navigate to the frontend directory:
   ```
   cd src/frontend
   ```
2. Install dependencies:
   ```
   npm install
   ```
3. Start the Next.js development server:
   ```
   npm run dev
   ```

## Development

### Backend

The backend is built with FastAPI and uses QuantLib for option pricing and Greeks calculation. It also integrates with Polygon.io for market data.

See the [backend README](src/backend/README.md) for more details.

### Frontend

The frontend is built with Next.js and uses Tailwind CSS for styling. It provides a user-friendly interface for managing positions, visualizing option strategies, and exploring market data.

## License

MIT
