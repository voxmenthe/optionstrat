'use client';

import React from 'react';

export default function Home() {
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">Options Analysis Tool</h1>
      <p className="mb-4">
        Welcome to the Options Scenario Analysis & Exploration App. This tool helps you analyze
        option positions and explore different scenarios for your investment strategies.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
        <div className="border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="text-xl font-semibold mb-2">Position Management</h2>
          <p className="text-gray-600 mb-4">Add, edit, and manage your option positions in a spreadsheet-like interface.</p>
          <a href="/positions" className="text-blue-600 hover:text-blue-800 font-medium">Go to Positions →</a>
        </div>
        <div className="border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="text-xl font-semibold mb-2">Analysis & Visualization</h2>
          <p className="text-gray-600 mb-4">Visualize option payoffs, Greeks, and explore different price and volatility scenarios.</p>
          <a href="/visualizations" className="text-blue-600 hover:text-blue-800 font-medium">Go to Analysis →</a>
        </div>
        <div className="border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="text-xl font-semibold mb-2">Market Data</h2>
          <p className="text-gray-600 mb-4">View current market data including prices, implied volatility, and option chains.</p>
          <a href="/market-data" className="text-blue-600 hover:text-blue-800 font-medium">Go to Market Data →</a>
        </div>
      </div>
    </div>
  );
} 