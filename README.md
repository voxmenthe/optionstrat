# Options Scenario Analysis & Exploration App

A comprehensive tool for analyzing options positions, visualizing risk and return scenarios, and exploring market data.

## Features

- **Position Management**: Add, edit, and manage option positions in a spreadsheet-like interface
- **Advanced Visualization**: Explore 3D surfaces showing price vs. volatility, price vs. time, and more
- **Greeks Calculation**: Automatically calculate and display option Greeks (Delta, Gamma, Theta, Vega, Rho)
- **Market Data**: Search and view current market data including option chains
- **Scenario Analysis**: Test different market scenarios and see how they affect your positions

## Project Structure

```
OPTIONSTRAT/
├── src
   ├── frontend/              # Next.js application
   │   ├── app/              # Next.js App Router
   │   │   ├── page.tsx      # Home page
   │   │   ├── positions/    # Position management pages
   │   │   └── visualizations/ # Charts and analysis pages
   │   ├── components/       # Reusable UI components
   │   ├── lib/              # Frontend utilities
   ├── backend/               # FastAPI application (planned)
```

## Tech Stack

- **Frontend**: Next.js 14.2.24, React 18.2.0
- **State Management**: Zustand 4.4.7
- **UI**: Tailwind CSS 3.4.17
- **Visualization**: Plotly.js 2.28.0
- **Backend** (planned): FastAPI, QuantLib
- **Data Source** (planned): Polygon.io

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation and Setup

1. Clone the repository
   ```
   git clone https://github.com/yourusername/optionstrat.git
   cd optionstrat
   ```

2. Install frontend dependencies
   ```
   cd src/frontend
   npm install
   ```

3. Start the development server
   ```
   npm run dev
   ```

4. Open your browser and navigate to http://localhost:3000

## Current Status

This project is under active development. The frontend implementation is complete with mock data, and we're currently working on:

1. Upgrading packages to the latest versions (Next.js 15.1.7, Tailwind CSS 4.0.8)
2. Implementing the backend with FastAPI and QuantLib
3. Connecting real market data through Polygon.io

## Project Planning

- See [project_plan_updated.md](project_plan_updated.md) for current status and next steps
- See [package_upgrade_plan.md](package_upgrade_plan.md) for details on upcoming package upgrades

## Disclaimer

This tool is for educational purposes only. Options trading involves significant risk and is not suitable for all investors. The information provided by this application should not be considered financial advice.
