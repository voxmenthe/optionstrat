'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { PayoffDiagram } from '../../../components/visualizations/charts';
import { PayoffDiagramData } from '../../../types/visualization';

/**
 * Demo Visualization Page
 * Showcases the PayoffDiagram component with sample strategy data
 */
export default function VisualizationDemoPage() {
  const [loading, setLoading] = useState(true);
  const [sampleData, setSampleData] = useState<PayoffDiagramData | null>(null);

  useEffect(() => {
    // Generate sample data for a Bull Call Spread
    const generateBullCallSpreadData = () => {
      setLoading(true);
      
      // Create an array of underlying price points for the x-axis
      const stockPrice = 100;
      const lowerStrike = 95;
      const upperStrike = 105;
      const step = 2;
      const range = 30;
      
      const prices: number[] = [];
      for (let i = stockPrice - range; i <= stockPrice + range; i += step) {
        prices.push(i);
      }
      
      // Calculate payoff for each price point for our Bull Call Spread
      // Bull Call Spread = Long Call at lower strike + Short Call at higher strike
      const payoff: number[] = prices.map(price => {
        // Long Call payoff at lower strike
        const longCallPayoff = Math.max(0, price - lowerStrike) - 2; // premium $2
        
        // Short Call payoff at higher strike
        const shortCallPayoff = -Math.max(0, price - upperStrike) + 1; // premium $1
        
        // Combined payoff
        return longCallPayoff + shortCallPayoff;
      });
      
      // Determine break-even points
      const breakEvenPoints: number[] = [];
      
      // Find where the payoff crosses zero (typical break-even calculation)
      for (let i = 1; i < payoff.length; i++) {
        if ((payoff[i-1] <= 0 && payoff[i] >= 0) || (payoff[i-1] >= 0 && payoff[i] <= 0)) {
          // Linear interpolation to find the exact break-even point
          const x1 = prices[i-1];
          const x2 = prices[i];
          const y1 = payoff[i-1];
          const y2 = payoff[i];
          
          if (y1 !== y2) {
            const x = x1 + (0 - y1) * (x2 - x1) / (y2 - y1);
            breakEvenPoints.push(x);
          }
        }
      }
      
      // Create the sample data for the PayoffDiagram component
      const data: PayoffDiagramData = {
        underlyingPrices: prices,
        payoffValues: payoff,
        breakEvenPoints,
        maxProfit: 9,
        maxLoss: -1,
        currentPrice: stockPrice
      };
      
      setSampleData(data);
      setLoading(false);
    };
    
    generateBullCallSpreadData();
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Visualization Demo</h1>
        <Link 
          href="/visualizations" 
          className="bg-white hover:bg-gray-100 text-gray-800 font-semibold py-2 px-4 border border-gray-300 rounded shadow-sm"
        >
          Back to Visualizations
        </Link>
      </div>
      
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
        <h2 className="text-lg font-semibold mb-4">Bull Call Spread Strategy</h2>
        <div className="h-[500px]">
          {sampleData ? (
            <PayoffDiagram
              data={sampleData}
              config={{
                title: 'Bull Call Spread Payoff Diagram',
                showLegend: true,
                colorScale: 'profits',
                showGridLines: true,
                showTooltips: true,
                responsiveResize: true,
              }}
              isLoading={loading}
              error={null}
            />
          ) : (
            <div className="flex justify-center items-center h-full">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
              <p className="ml-3 text-lg text-gray-600">Generating sample data...</p>
            </div>
          )}
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <h3 className="text-md font-semibold mb-3">Strategy Details</h3>
          <p className="text-gray-700 mb-3">
            A Bull Call Spread is created by buying a call option at a lower strike price and selling a call 
            option at a higher strike price, both with the same expiration date. 
          </p>
          <p className="text-gray-700 mb-3">
            This example uses a 95/105 Bull Call Spread on a stock trading at $100, with:
          </p>
          <ul className="list-disc pl-5 mb-3 text-gray-700">
            <li>Long 95 Strike Call (cost: $7)</li>
            <li>Short 105 Strike Call (premium received: $2)</li>
            <li>Net cost: $5 ($7 - $2)</li>
          </ul>
          <p className="text-gray-700">
            The maximum profit is $5 (width of the spread - net cost) achieved when the stock price is above $105 
            at expiration. The maximum loss is the net cost of $5 if the stock price is below $95 at expiration.
          </p>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <h3 className="text-md font-semibold mb-3">When to Use</h3>
          <p className="text-gray-700 mb-3">
            Consider a Bull Call Spread when you have a moderately bullish outlook on the underlying asset.
            This strategy:
          </p>
          <ul className="list-disc pl-5 mb-3 text-gray-700">
            <li>Reduces the cost of buying a call option alone</li>
            <li>Limits both potential profit and risk</li>
            <li>Provides better returns than a solo call option if the underlying moves only modestly higher</li>
            <li>Has a defined maximum profit and maximum loss</li>
          </ul>
          <h3 className="text-md font-semibold mb-3 mt-4">Risk Analysis</h3>
          <p className="text-gray-700">
            The breakeven point is at $100 (lower strike + net cost). The strategy reaches maximum profit when 
            the stock is at or above the higher strike price ($105) and reaches maximum loss when the stock is 
            below the lower strike price ($95).
          </p>
        </div>
      </div>
    </div>
  );
} 