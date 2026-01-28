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

- Python 3.13.11+ (see `.python-version`)
- Node.js 18+
- uv (for Python dependency management)
- Redis (optional, for caching)

Install uv (if needed):
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quick Start (Local)

1. Create backend env file:
   ```
   cp src/backend/.env.example src/backend/.env
   ```
   Then edit `src/backend/.env` and set `POLYGON_API_KEY`.
2. Install frontend dependencies once:
   ```
   (cd src/frontend && npm install)
   ```
3. Run both servers:
   ```
   ./run_app.sh
   ```

By default this starts:
- Backend: http://localhost:8003
- Frontend: http://localhost:3003

## Manual Setup

### Backend

1. Install dependencies:
   ```
   cd src/backend
   uv sync
   ```
2. Create `.env` (required for API keys and ports):
   ```
   cp .env.example .env
   ```
3. Start the API server (uses `PORT` from `.env`, default 8003):
   ```
   uv run python -m app.main
   ```
   If you prefer uvicorn directly, pass the port explicitly:
   ```
   uv run uvicorn app.main:app --reload --port 8003
   ```

### Frontend

1. Install dependencies:
   ```
   cd src/frontend
   npm install
   ```
2. (Optional) Set backend URL (defaults to `http://localhost:8003`):
   ```
   export NEXT_PUBLIC_API_URL=http://localhost:8003
   ```
   Or create `src/frontend/.env.local`:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8003
   ```
3. Start the Next.js dev server (runs on port 3003):
   ```
   npm run dev
   ```

## Docker Compose (Backend + Redis)

Docker Compose is wired for the backend + Redis and exposes port 8000. If you want a containerized frontend, add a `src/frontend/Dockerfile` first (the current repo does not include one).

1. Create a root `.env` with your Polygon.io API key:
   ```
   POLYGON_API_KEY=your_polygon_api_key_here
   ```
2. Start services:
   ```
   docker compose up -d backend redis
   ```
3. Backend API is available at http://localhost:8000

## Development

### Backend

The backend is built with FastAPI and uses QuantLib for option pricing and Greeks calculation. It also integrates with Polygon.io for market data.

See the [backend README](src/backend/README.md) for more details.

### Frontend

The frontend is built with Next.js and uses Tailwind CSS for styling. It provides a user-friendly interface for managing positions, visualizing option strategies, and exploring market data.

## License

MIT

## Running the Application

Use `./run_app.sh` for local development. It starts the backend on port 8003 and the frontend on port 3003. It will also attempt to start Redis if available.
