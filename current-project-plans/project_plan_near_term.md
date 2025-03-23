# Options Scenario Analysis & Exploration App - Updated Plan

## Current Status Summary

As of March 23, 2025, we have completed the frontend implementation of the Options Analysis Tool, successfully upgraded all packages to their latest versions, and made significant progress on the backend development. We have implemented the core QuantLib integration for options pricing and Greeks calculations, set up the FastAPI project structure, and created a solid foundation for the backend services.

Frontend-backend integration is now complete, with real API calls replacing mock data. We've also implemented an editable position management system that allows for direct manipulation of position data. The visualization framework is in place, but the actual visualization components using Plotly.js still need to be implemented.

## What's Been Completed

### Frontend Implementation

- ✅ Set up Next.js application structure 
- ✅ Implemented Tailwind CSS for styling
- ✅ Created responsive layout with header, navigation, and footer
- ✅ Implemented home page with overview of application features
- ✅ Position management
  - ✅ Created position form for adding new options
  - ✅ Implemented position table for displaying positions
  - ✅ Added functionality for calculating Greeks with real API
  - ✅ Enhanced position management with editable position table
- ✅ Visualization pages
  - ✅ Implemented visualization list view
  - ✅ Created individual position visualization page with analysis settings
  - ✅ Added UI framework for visualizations
  - ⏳ Implementation of actual chart and visualization components
- ✅ Market data page
  - ✅ Created search interface for ticker symbols
  - ✅ Implemented real data display for market information
  - ✅ Added option chain table with calls and puts
  - ✅ Improved option chain selection with filters
- ✅ State management with Zustand
- ✅ API client service with Axios
- ✅ Error handling and loading states

### Package Upgrades

- ✅ Upgraded Next.js to version 15.1.7
  - ✅ Reviewed breaking changes and migration guide
  - ✅ Updated Next.js and related dependencies
  - ✅ Tested application after upgrade to ensure functionality
  
- ✅ Upgraded Tailwind CSS to 4.0.8
  - ✅ Reviewed breaking changes and migration guide
  - ✅ Updated configuration files as needed
  - ✅ Fixed styling issues

- ✅ Updated other dependencies to their latest versions
  - ✅ React 19.0.0 and React DOM
  - ✅ Zustand 5.0.3
  - ✅ Plotly.js 3.0.1 and React-Plotly.js 2.6.0
  - ✅ Development dependencies (TypeScript, ESLint, etc.)

### Backend Development

- ✅ Set up FastAPI project structure
  - ✅ Created basic API endpoints for health checks and testing
  - ✅ Set up project structure following best practices
  - ✅ Configured CORS for frontend-backend communication

- ✅ Integrated QuantLib for option pricing and Greeks calculation
  - ✅ Installed QuantLib and necessary dependencies
  - ✅ Created a QuantLib wrapper service for option pricing
  - ✅ Implemented both American and European pricing for vanilla options
  - ✅ Developed endpoints for calculating Delta, Gamma, Theta, Vega, and Rho
  - ✅ Implemented implied volatility calculations

- ✅ Created scenario analysis functionality
  - ✅ Developed price vs. volatility surface calculations
  - ✅ Implemented time decay analysis
  - ✅ Added support for multi-leg option strategies

- ✅ Implemented market data integration
  - ✅ Set up Polygon.io client for real-time data
  - ✅ Implemented yfinance as an alternative data source
  - ✅ Created endpoints for fetching market prices and option chains
  - ✅ Implemented Redis caching for API responses

- ✅ Set up package management with Poetry
  - ✅ Created pyproject.toml for dependency management
  - ✅ Configured development dependencies for testing and linting

- ✅ Implemented database models
  - ✅ Created SQLAlchemy models for positions
  - ✅ Set up SQLite database for development

- ✅ Set up Docker configuration
  - ✅ Created Dockerfile for backend
  - ✅ Set up docker-compose.yml for the entire project

- ✅ Implemented unit testing
  - ✅ Created test suite for option pricing
  - ✅ Fixed issues with American option pricing

### Current Technical Stack

- Frontend: Next.js 15.1.7, React 19.0.0
- UI: Tailwind CSS 4.0.8
- State Management: Zustand 5.0.3
- Visualization (planned): Plotly.js 3.0.1, React-Plotly.js 2.6.0
- API Client: Axios 1.8.3
- Backend: FastAPI 0.109.0, Python 3.13.2
- Options Pricing: QuantLib 1.37
- Database: SQLAlchemy 2.0.38, SQLite
- Package Management: Poetry
- Containerization: Docker, Docker Compose

## Immediate Next Steps

### 1. Implement Visualization Components (Highest Priority)

- [ ] Create a dedicated visualization components directory
  - [ ] Set up base visualization component structure
  - [ ] Create reusable chart configuration utilities
  - [ ] Implement common visualization helpers

- [ ] Implement price vs. volatility surface visualization
  - [ ] Create 3D surface component using Plotly.js
  - [ ] Implement color mapping for profit/loss
  - [ ] Add interactive controls (rotation, zoom, pan)
  - [ ] Support hover tooltips with detailed information
  - [ ] Add axis labels and legends

- [ ] Implement price vs. time visualization
  - [ ] Create 2D line chart for time decay
  - [ ] Add multiple lines for different price points
  - [ ] Implement range selection for time frames
  - [ ] Support interactive data exploration

- [ ] Create profit and loss diagrams
  - [ ] Implement payoff diagram component
  - [ ] Support multiple legs in a single chart
  - [ ] Add break-even point indicators
  - [ ] Support comparison between strategies

- [ ] Add Greeks profile visualizations
  - [ ] Create Delta vs. price chart
  - [ ] Implement Gamma surface visualization
  - [ ] Add Theta decay chart
  - [ ] Create Vega sensitivity visualization

- [ ] Implement visualization export functionality
  - [ ] Add image export (PNG, JPG, SVG)
  - [ ] Support data export (CSV, JSON)
  - [ ] Create sharable links for visualizations

### 2. Implement Preset Strategy Selection and What-If Analysis

- [ ] Create strategy template definitions
  - [ ] Define data model for strategy templates
  - [ ] Implement common strategy types (spreads, condors, butterflies, etc.)
  - [ ] Create mapping of strategy parameters to option selection criteria
  - [ ] Develop strategy configuration schema

- [ ] Build strategy selection UI
  - [ ] Create strategy selector component with dropdown and description
  - [ ] Implement parameter input fields based on selected strategy
  - [ ] Add ticker search integration with existing market data functionality
  - [ ] Develop expiry date selection based on available options
  - [ ] Add validation for strategy parameters

- [ ] Implement automatic option selection algorithm
  - [ ] Develop logic to find ATM options
  - [ ] Create algorithms for finding options at specific price offsets
  - [ ] Implement expiration date proximity search
  - [ ] Add filtering by delta/gamma or other Greeks
  - [ ] Create logic for multi-leg strategy construction

- [ ] Build scenario builder for preset strategies
  - [ ] Create integration with option chain store
  - [ ] Implement strategy construction workflow
  - [ ] Add ability to customize generated strategies
  - [ ] Create preview of selected options and strategy characteristics

- [ ] Develop what-if scenario analysis modal
  - [ ] Create UI for scenario parameters (price movement, volatility changes, time decay)
  - [ ] Implement calculation of scenario outcomes
  - [ ] Integrate with visualization components
  - [ ] Add ability to save and compare scenarios
  - [ ] Develop tabular view of scenario outcomes

- [ ] Enhance position management with preset strategies
  - [ ] Add option to create position from preset strategy
  - [ ] Implement bulk position creation for multi-leg strategies
  - [ ] Create unified workflow from strategy selection to position creation

### 3. Enhance User Experience

- [ ] Add dark mode support 
  - [ ] Implement theme switching
  - [ ] Create dark mode color schemes for charts
  - [ ] Ensure proper contrast for accessibility

- [ ] Improve responsive design for visualizations
  - [ ] Ensure charts resize correctly on all devices
  - [ ] Create mobile-optimized view for small screens
  - [ ] Implement touch controls for mobile interaction

- [ ] Add user preferences for visualizations
  - [ ] Save default chart settings
  - [ ] Allow users to customize color schemes
  - [ ] Remember last used visualization type

- [ ] Implement visualization comparison
  - [ ] Create side-by-side view for comparing strategies
  - [ ] Support overlaying multiple scenarios on one chart
  - [ ] Add difference calculation between scenarios

### 4. Complete Documentation

- [ ] Document API endpoints
  - [ ] Create OpenAPI documentation with FastAPI
  - [ ] Add detailed descriptions for all endpoints
  - [ ] Create Postman collection for testing

- [ ] Create visualization usage guide
  - [ ] Document each chart type and its purpose
  - [ ] Explain how to interpret different visualizations
  - [ ] Create examples for common scenarios

- [ ] Add developer documentation for extending visualizations
  - [ ] Document component architecture
  - [ ] Explain how to create new visualization types
  - [ ] Provide examples for customization

- [ ] Document preset strategies and what-if analysis
  - [ ] Create guide for each strategy type
  - [ ] Explain parameters and selection criteria
  - [ ] Provide examples of common use cases
  - [ ] Document how to create custom strategies

## Updated Timeline

### Week 1 (March 24-30, 2025)
- Implement core visualization components
  - Create visualization component directory structure
  - Implement price vs. volatility surface
  - Add price vs. time visualization
  - Create profit and loss diagrams

### Week 2 (March 31-April 6, 2025)
- Complete visualization implementation
  - Add Greeks profile visualizations
  - Implement export functionality
  - Add responsive design for all visualizations
- Begin preset strategy template implementation
  - Define strategy template data model
  - Create initial set of common strategy templates

### Week 3 (April 7-13, 2025)
- Implement strategy selection UI and option selection algorithm
  - Create strategy selector component
  - Implement parameter inputs
  - Develop option selection algorithms
  - Build scenario builder integration
- Enhance user experience
  - Implement dark mode support
  - Add user preferences

### Week 4 (April 14-20, 2025)
- Complete preset strategy and what-if analysis
  - Finalize what-if scenario modal
  - Integrate visualization components
  - Add scenario comparison functionality
- Complete documentation
  - Document API endpoints
  - Create visualization usage guide
  - Document preset strategies
- Conduct user testing and gather feedback

## Technical Design for Visualization Components

### Visualization Component Directory Structure

```
src/frontend/components/visualizations/
├── common/
│   ├── ChartContainer.tsx
│   ├── ChartControls.tsx
│   ├── ColorScales.ts
│   └── utils.ts
├── surfaces/
│   ├── PriceVolatilitySurface.tsx
│   └── GreeksSurface.tsx
├── charts/
│   ├── PriceTimeChart.tsx
│   ├── PayoffDiagram.tsx
│   └── GreeksChart.tsx
└── index.ts
```

### Key Visualization Components

1. **PriceVolatilitySurface**: 3D surface visualization showing option value across different price and volatility points.

2. **PriceTimeChart**: 2D line chart showing option value changes over time for different price points.

3. **PayoffDiagram**: 2D chart showing profit/loss at expiration across a range of underlying prices.

4. **GreeksChart**: Collection of charts showing how Greeks change with price, volatility, and time.

### Integration with Scenarios Store

Visualization components will connect to the existing scenariosStore to fetch data:

1. User selects a position and visualization type
2. UI triggers the appropriate scenario analysis in the store
3. Store makes API call to backend for calculations
4. Visualization component renders the results using Plotly.js

### Responsive Design Strategy

1. Use container queries to adapt charts to available space
2. Create tailored layouts for mobile, tablet, and desktop
3. Simplify interactions on small screens
4. Implement touch-friendly controls for mobile

## Technical Design for Preset Strategy Selection

### Strategy Template Data Model

```typescript
interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  type: 'spread' | 'condor' | 'butterfly' | 'straddle' | 'strangle' | 'custom';
  legs: StrategyLegTemplate[];
  parameters: StrategyParameter[];
}

interface StrategyLegTemplate {
  action: 'buy' | 'sell';
  optionType: 'call' | 'put';
  // Selection criteria relative to parameters
  strikeSelectionMethod: 'atm' | 'otm' | 'itm' | 'offset' | 'delta';
  strikeOffset?: StrategyParameterRef; // Reference to a parameter
  expirySelectionMethod: 'days' | 'weeks' | 'months' | 'specific';
  expiryOffset?: StrategyParameterRef; // Reference to a parameter
  quantity?: StrategyParameterRef; // Reference to a parameter
}

interface StrategyParameter {
  id: string;
  name: string;
  description: string;
  type: 'number' | 'percentage' | 'date' | 'select';
  defaultValue: any;
  min?: number;
  max?: number;
  step?: number;
  options?: { value: any; label: string }[];
}

interface StrategyParameterRef {
  parameterId: string;
  transform?: (value: any) => any; // Optional transformation function
}
```

### Common Strategy Templates

1. **Long Call Spread**
   - Buy 1 ATM call
   - Sell 1 OTM call (strike offset parameter)
   - Parameters: expiry days, strike percentage offset

2. **Long Put Spread**
   - Buy 1 ATM put
   - Sell 1 OTM put (strike offset parameter)
   - Parameters: expiry days, strike percentage offset

3. **Iron Condor**
   - Sell 1 OTM put (strike offset parameter)
   - Buy 1 further OTM put (strike offset parameter)
   - Sell 1 OTM call (strike offset parameter)
   - Buy 1 further OTM call (strike offset parameter)
   - Parameters: expiry days, put spread width, call spread width, center offset

4. **Butterfly**
   - Buy 1 ITM call/put (strike offset parameter)
   - Sell 2 ATM calls/puts
   - Buy 1 OTM call/put (equal distance as first leg)
   - Parameters: expiry days, wing width, option type (call/put)

### Option Selection Algorithm

1. **Find ATM options**
   - Fetch current underlying price
   - Find option strikes closest to current price
   - Calculate distance and select closest strike

2. **Find options by offset**
   - Calculate target strike (underlying price * (1 + offset))
   - Find option with strike closest to target

3. **Find options by expiry**
   - Calculate target expiry date (current date + days)
   - Find available expiry dates
   - Select closest expiry date

4. **Find options by delta**
   - Sort options by delta
   - Find option with delta closest to target

### What-If Scenario Analysis Modal

1. **Input Parameters Section**
   - Ticker input with autocomplete
   - Strategy type selection
   - Strategy-specific parameters (adjustable)
   - Scenario parameters (price range, volatility range, time range)

2. **Results Section**
   - Selected options details
   - Strategy summary (max profit, max loss, breakeven)
   - Visualization integration
   - Tabular scenario results

3. **Actions Section**
   - Save to positions
   - Export visualization
   - Compare with other strategies
   - Adjust parameters

## Next Immediate Steps (Next Week)

1. **Set up visualization component structure**
   - Create the directory structure for visualization components
   - Implement base visualization utilities and helpers
   - Create chart container and control components

2. **Implement first visualization component**
   - Start with the price vs. volatility surface (3D)
   - Connect it to the scenarios store
   - Implement basic interactivity
   - Add color mapping for profit/loss regions

3. **Define strategy template data model**
   - Create interfaces for strategy templates
   - Implement initial set of common strategies
   - Develop parameter schema

## Technical Debt & Improvements

- Optimize visualization performance for large data sets
- Implement client-side caching for visualization data
- Add offline support for previously calculated visualizations
- Improve accessibility of visualization components
- Add more sophisticated option selection algorithms based on liquidity and other factors
- Implement strategy backtesting using historical data
- Add more complex multi-leg strategies with advanced parameters

---

This plan will be updated regularly as progress is made and requirements evolve. 