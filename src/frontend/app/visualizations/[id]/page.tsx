'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { usePositionStore, OptionPosition } from '../../../lib/stores/positionStore';
import { useScenariosStore } from '../../../lib/stores/scenariosStore';
import { ApiError } from '../../../lib/api';
import { PayoffDiagram } from '../../../components/visualizations/charts';
import { PayoffDiagramData } from '../../../types/visualization';
import { transformToPricePayoffData } from '../../../components/visualizations/common/utils';

// Helper function to generate sample payoff data when API is not available
function generateSamplePayoffData(position: OptionPosition): PayoffDiagramData {
  const basePrice = position.strike;
  const steps = 100; // More steps for smoother curve
  
  // Generate price points with appropriate range based on option type
  let underlyingPrices: number[] = [];
  
  if (position.type === 'put') {
    // For PUT options, focus heavily on prices below the strike
    // Range from 30% to 150% of strike with more points below strike
    const minPrice = basePrice * 0.3;
    const maxPrice = basePrice * 1.5;
    
    // Create two sets of points with different density
    // More dense below strike, less dense above strike
    for (let i = 0; i <= steps * 0.7; i++) {
      // Points below and around strike (higher density)
      const price = minPrice + ((basePrice - minPrice) * i / (steps * 0.7));
      underlyingPrices.push(price);
    }
    
    for (let i = 1; i <= steps * 0.3; i++) {
      // Points above strike (lower density)
      const price = basePrice + ((maxPrice - basePrice) * i / (steps * 0.3));
      underlyingPrices.push(price);
    }
    
    // Sort to ensure correct order
    underlyingPrices.sort((a, b) => a - b);
  } else {
    // For CALL options, focus on prices around and above the strike
    // Range from 50% to 170% of strike
    const minPrice = basePrice * 0.5;
    const maxPrice = basePrice * 1.7;
    
    // Create two sets of points with different density
    // Less dense below strike, more dense above strike
    for (let i = 0; i <= steps * 0.3; i++) {
      // Points below strike (lower density)
      const price = minPrice + ((basePrice - minPrice) * i / (steps * 0.3));
      underlyingPrices.push(price);
    }
    
    for (let i = 1; i <= steps * 0.7; i++) {
      // Points above strike (higher density)
      const price = basePrice + ((maxPrice - basePrice) * i / (steps * 0.7));
      underlyingPrices.push(price);
    }
    
    // Sort to ensure correct order
    underlyingPrices.sort((a, b) => a - b);
  }
  
  // Calculate premium if not provided (use realistic pricing)
  const premium = position.premium || calculateEstimatedPremium(position);
  
  // Calculate payoff based on option type and action
  const payoffValues: number[] = underlyingPrices.map(price => {
    let payoff = 0;
    
    if (position.type === 'call') {
      if (position.action === 'buy') {
        // Long call: max(0, price - strike) - premium
        payoff = Math.max(0, price - position.strike) - premium;
      } else {
        // Short call: premium - max(0, price - strike)
        payoff = premium - Math.max(0, price - position.strike);
      }
    } else { // PUT option
      if (position.action === 'buy') {
        // Long put: max(0, strike - price) - premium
        payoff = Math.max(0, position.strike - price) - premium;
      } else {
        // Short put: premium - max(0, strike - price)
        payoff = premium - Math.max(0, position.strike - price);
      }
    }
    
    // Scale the payoff by quantity and limit extreme values
    return Math.min(1000, Math.max(-1000, payoff * position.quantity));
  });
  
  // Calculate break-even points
  const breakEvenPoints: number[] = [];
  for (let i = 1; i < payoffValues.length; i++) {
    if ((payoffValues[i-1] <= 0 && payoffValues[i] >= 0) || 
        (payoffValues[i-1] >= 0 && payoffValues[i] <= 0)) {
      // Linear interpolation to find the exact break-even price
      const x1 = underlyingPrices[i-1];
      const x2 = underlyingPrices[i];
      const y1 = payoffValues[i-1];
      const y2 = payoffValues[i];
      
      if (y1 !== y2) {
        const x = x1 + (0 - y1) * (x2 - x1) / (y2 - y1);
        breakEvenPoints.push(parseFloat(x.toFixed(2)));
      }
    }
  }
  
  // Find max profit and max loss
  const maxProfit = Math.max(...payoffValues);
  const maxLoss = Math.min(...payoffValues);
  
  // Return the payoff data
  return {
    underlyingPrices,
    payoffValues,
    breakEvenPoints,
    maxProfit: maxProfit > 0 ? maxProfit : undefined,
    maxLoss: maxLoss < 0 ? maxLoss : undefined,
    currentPrice: basePrice,
    positions: [position]
  };
}

// Helper to calculate estimated premium based on simple option pricing model
function calculateEstimatedPremium(position: OptionPosition): number {
  const strike = position.strike;
  
  // Use 5% of strike as a simple default for OTM options
  // Adjust based on option type to create more realistic pricing
  if (position.type === 'put') {
    return strike * 0.05; // 5% of strike for PUT
  } else {
    return strike * 0.07; // 7% of strike for CALL (typically more expensive)
  }
}

export default function PositionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { positions, fetchPositions, loading: positionsLoading, error: positionsError } = usePositionStore();
  const { 
    analyzePriceScenario, 
    analyzeVolatilityScenario, 
    analyzeTimeDecayScenario, 
    analyzePriceVsVolatilitySurface,
    priceScenario,
    loading: scenarioLoading,
    error: scenarioError
  } = useScenariosStore();
  
  const [position, setPosition] = useState<OptionPosition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  // Visualization state and data
  const [visualizationType, setVisualizationType] = useState<'price-vol' | 'price-time' | 'payoff'>('payoff');
  const [priceRange, setPriceRange] = useState<[number, number]>([-20, 20]); // Percentage change
  const [volRange, setVolRange] = useState<[number, number]>([-50, 50]); // Percentage change
  const [days, setDays] = useState<number>(30);
  const [calculating, setCalculating] = useState(false);
  const [payoffData, setPayoffData] = useState<PayoffDiagramData | null>(null);
  const [usingFallbackData, setUsingFallbackData] = useState(false);
  
  useEffect(() => {
    const positionId = params.id as string;
    
    const loadPosition = async () => {
      setLoading(true);
      setError(null);
      
      try {
        if (positions.length === 0) {
          await fetchPositions();
        }
        
        const foundPosition = positions.find(p => p.id === positionId);
        
        if (foundPosition) {
          setPosition(foundPosition);
        } else {
          // Position not found, redirect to the visualization list
          router.push('/visualizations');
        }
      } catch (err) {
        console.error('Failed to load position:', err);
        let errorMessage = 'Failed to load position data';
        if (err instanceof ApiError) {
          errorMessage = `API Error (${err.status}): ${err.message}`;
        } else if (err instanceof Error) {
          errorMessage = err.message;
        }
        setError(new Error(errorMessage));
      } finally {
        setLoading(false);
      }
    };
    
    loadPosition();
  }, [params.id, positions, fetchPositions, router]);
  
  // Load payoff data when position loads
  useEffect(() => {
    if (position && visualizationType === 'payoff') {
      handleCalculateVisualization();
    }
  }, [position, visualizationType]);
  
  // Update payoff data when price scenario data changes
  useEffect(() => {
    if (position && priceScenario.length > 0) {
      // Calculate the current price of the underlying if available
      const currentPrice = position.pnl?.underlyingPrice || 
                          (position.strike * 1.05); // Fallback estimation if no price available
      
      // Transform the price scenario data into payoff diagram data
      const payoffData = transformToPricePayoffData(
        priceScenario, 
        [position], 
        currentPrice
      );
      
      setPayoffData(payoffData);
      setUsingFallbackData(false);
    }
  }, [position, priceScenario]);
  
  const handleCalculateVisualization = async () => {
    if (!position) return;
    
    setCalculating(true);
    try {
      // Create a scenario based on the current visualization settings
      if (visualizationType === 'price-vol') {
        await analyzePriceVsVolatilitySurface([position]);
      } else if (visualizationType === 'price-time') {
        await analyzeTimeDecayScenario([position]);
      } else if (visualizationType === 'payoff') {
        await analyzePriceScenario([position]);
      }
      
    } catch (err) {
      console.error('Failed to calculate visualization:', err);
      
      // If this is the payoff visualization type, use our fallback data generator
      if (visualizationType === 'payoff' && position) {
        console.log('Using client-side fallback for payoff calculation');
        const fallbackData = generateSamplePayoffData(position);
        setPayoffData(fallbackData);
        setUsingFallbackData(true);
      } else {
        let errorMessage = 'Failed to calculate visualization';
        if (err instanceof ApiError) {
          errorMessage = `API Error (${err.status}): ${err.message}`;
        } else if (err instanceof Error) {
          errorMessage = err.message;
        }
        alert(errorMessage);
      }
    } finally {
      setCalculating(false);
    }
  };
  
  if (loading || positionsLoading) {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <p className="ml-3 text-lg text-gray-600">Loading position data...</p>
      </div>
    );
  }
  
  if (error || positionsError) {
    const displayError = error || positionsError;
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
        <h3 className="font-bold text-lg mb-2">Error Loading Position</h3>
        <p>{displayError instanceof Error ? displayError.message : 'An unknown error occurred'}</p>
        <div className="mt-4 flex space-x-3">
          <button 
            onClick={() => router.push('/visualizations')}
            className="bg-white hover:bg-gray-100 text-gray-800 font-semibold py-2 px-4 border border-gray-300 rounded shadow-sm"
          >
            Back to Visualizations
          </button>
          <button 
            onClick={() => window.location.reload()}
            className="bg-red-100 hover:bg-red-200 text-red-800 font-semibold py-2 px-4 rounded"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }
  
  if (!position) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded-lg mb-6">
        <h3 className="font-bold text-lg mb-2">Position Not Found</h3>
        <p>The position you're looking for might have been deleted or doesn't exist.</p>
        <button 
          onClick={() => router.push('/visualizations')}
          className="mt-3 bg-white hover:bg-gray-100 text-gray-800 font-semibold py-2 px-4 border border-gray-300 rounded shadow-sm"
        >
          Back to Visualizations
        </button>
      </div>
    );
  }
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">
          Position Analysis: {position.ticker} {position.strike} {position.type.toUpperCase()}
        </h1>
        <button
          onClick={() => router.push('/visualizations')}
          className="bg-white hover:bg-gray-100 text-gray-800 font-semibold py-2 px-4 border border-gray-300 rounded shadow-sm"
        >
          Back to All Positions
        </button>
      </div>
      
      {/* Position Details Card */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
        <h2 className="text-lg font-semibold mb-4">Position Details</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <p className="text-gray-500 text-sm">Ticker</p>
            <p className="font-semibold">{position.ticker}</p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Expiration</p>
            <p className="font-semibold">{new Date(position.expiration).toLocaleDateString()}</p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Strike</p>
            <p className="font-semibold">
              {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(position.strike)}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Option Type</p>
            <p className="font-semibold">{position.type.toUpperCase()}</p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Action</p>
            <p className="font-semibold">{position.action.toUpperCase()}</p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Quantity</p>
            <p className="font-semibold">{position.quantity}</p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Premium</p>
            <p className="font-semibold">
              {position.premium 
                ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(position.premium) 
                : '-'}
            </p>
          </div>
        </div>
        
        {position.greeks && (
          <div className="mt-6 pt-4 border-t border-gray-100">
            <h3 className="text-md font-semibold mb-3">Greeks</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div>
                <p className="text-gray-500 text-sm">Delta</p>
                <p className="font-semibold">{position.greeks.delta.toFixed(4)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Gamma</p>
                <p className="font-semibold">{position.greeks.gamma.toFixed(4)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Theta</p>
                <p className="font-semibold">{position.greeks.theta.toFixed(4)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Vega</p>
                <p className="font-semibold">{position.greeks.vega.toFixed(4)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Rho</p>
                <p className="font-semibold">{position.greeks.rho.toFixed(4)}</p>
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Analysis Settings Card */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
        <h2 className="text-lg font-semibold mb-4">Analysis Settings</h2>
        
        <div className="mb-4">
          <label className="form-label">Visualization Type</label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-1">
            <button
              className={`py-2 px-4 border rounded-md ${visualizationType === 'payoff' ? 'bg-blue-100 border-blue-300' : 'bg-white border-gray-300'}`}
              onClick={() => setVisualizationType('payoff')}
              disabled={calculating}
            >
              Payoff Diagram
            </button>
            <button
              className={`py-2 px-4 border rounded-md ${visualizationType === 'price-vol' ? 'bg-blue-100 border-blue-300' : 'bg-white border-gray-300'}`}
              onClick={() => setVisualizationType('price-vol')}
              disabled={calculating}
            >
              Price vs Volatility
            </button>
            <button
              className={`py-2 px-4 border rounded-md ${visualizationType === 'price-time' ? 'bg-blue-100 border-blue-300' : 'bg-white border-gray-300'}`}
              onClick={() => setVisualizationType('price-time')}
              disabled={calculating}
            >
              Price vs Time
            </button>
          </div>
        </div>
        
        <div className="mt-4">
          <button
            className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-6 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleCalculateVisualization}
            disabled={calculating || !position}
          >
            {calculating ? 'Calculating...' : 'Calculate'}
          </button>
        </div>
      </div>
      
      {/* Visualization Card */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
        <h2 className="text-lg font-semibold mb-4">
          {visualizationType === 'payoff' && 'Payoff Diagram'}
          {visualizationType === 'price-vol' && 'Price vs Volatility Surface'}
          {visualizationType === 'price-time' && 'Price vs Time Decay'}
        </h2>
        
        {visualizationType === 'payoff' && payoffData ? (
          <div className="h-[500px]">
            {usingFallbackData && (
              <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 p-3 mb-3 rounded-md text-sm">
                Note: Using client-side estimation as the backend API is not available. Actual results may vary.
              </div>
            )}
            <PayoffDiagram
              data={payoffData}
              config={{
                title: `${position.ticker} ${position.strike} ${position.type.toUpperCase()} Payoff`,
                showLegend: true,
                colorScale: 'profits',
                showGridLines: true,
                showTooltips: true,
                responsiveResize: true,
              }}
              isLoading={calculating || (scenarioLoading && !usingFallbackData)}
              error={scenarioError && !usingFallbackData ? scenarioError : null}
            />
          </div>
        ) : visualizationType === 'payoff' ? (
          <div className="flex flex-col items-center justify-center h-[400px] bg-gray-50 rounded-lg">
            <p className="text-gray-500 mb-4">No payoff data available yet</p>
            <button
              className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-6 rounded-md"
              onClick={handleCalculateVisualization}
              disabled={calculating}
            >
              Calculate Payoff
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-[400px] bg-gray-50 rounded-lg">
            <p className="text-gray-500">Visualization type not yet implemented</p>
            <p className="text-sm text-gray-400 mt-2">Please select 'Payoff Diagram' from the visualization types</p>
          </div>
        )}
      </div>
    </div>
  );
}