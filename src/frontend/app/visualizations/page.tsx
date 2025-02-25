'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { usePositionStore } from '../../lib/stores/positionStore';

export default function VisualizationsPage() {
  const { positions, fetchPositions, loading, error } = usePositionStore();
  
  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);
  
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Position Analysis</h1>
      
      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4">
          <p>{error}</p>
        </div>
      )}
      
      {loading ? (
        <div className="flex justify-center p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          <p className="ml-2">Loading positions...</p>
        </div>
      ) : positions.length === 0 ? (
        <div className="bg-gray-50 p-6 rounded-lg text-center mb-6">
          <p className="text-gray-500">No positions found for analysis. Add positions first to visualize them.</p>
          <Link href="/positions" className="text-blue-500 hover:text-blue-700 font-medium mt-2 inline-block">
            Go to Positions Page
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {positions.map(position => (
            <div key={position.id} className="option-card hover:shadow-lg hover:border-blue-300 transition-all">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-lg font-semibold">
                    {position.ticker} {position.strike} {position.type.toUpperCase()}
                  </h2>
                  <p className="text-gray-600">
                    Expires: {new Date(position.expiration).toLocaleDateString()}
                  </p>
                  <p className={position.action === 'buy' ? 'text-green-600' : 'text-red-600'}>
                    {position.action.toUpperCase()} {position.quantity} contract{position.quantity !== 1 ? 's' : ''}
                  </p>
                </div>
                
                <div className="text-right">
                  <div className="bg-gray-100 rounded-lg p-2 inline-block">
                    <p className="text-xs text-gray-500">Premium</p>
                    <p className="font-medium">
                      {position.premium 
                        ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(position.premium) 
                        : '-'}
                    </p>
                  </div>
                </div>
              </div>
              
              {position.greeks && (
                <div className="mt-4 bg-gray-50 p-3 rounded">
                  <p className="text-xs font-medium text-gray-500 mb-2">Greeks</p>
                  <div className="grid grid-cols-4 gap-2 text-sm">
                    <div>
                      <p className="text-gray-500">Delta</p>
                      <p className="font-medium">{position.greeks.delta.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Gamma</p>
                      <p className="font-medium">{position.greeks.gamma.toFixed(4)}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Theta</p>
                      <p className="font-medium">{position.greeks.theta.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Vega</p>
                      <p className="font-medium">{position.greeks.vega.toFixed(2)}</p>
                    </div>
                  </div>
                </div>
              )}
              
              <div className="mt-4 pt-3 border-t border-gray-100 flex justify-between">
                <Link
                  href={`/visualizations/${position.id}`}
                  className="btn-primary text-sm py-1 px-3"
                >
                  Analyze
                </Link>
                
                {!position.greeks && (
                  <button
                    onClick={() => usePositionStore.getState().calculateGreeks(position)}
                    className="btn-secondary text-sm py-1 px-3"
                  >
                    Calculate Greeks
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      
      <div className="bg-blue-50 p-6 rounded-lg border border-blue-100">
        <h2 className="text-lg font-semibold mb-2">Analysis Tools</h2>
        <p className="text-gray-600 mb-4">
          Select a position from above to access the following analysis tools:
        </p>
        <ul className="list-disc pl-6 text-gray-600">
          <li>Price vs Volatility Surface (3D visualization)</li>
          <li>Price vs Time Surface (3D visualization)</li>
          <li>Profit & Loss Diagrams</li>
          <li>Sensitivity Analysis</li>
          <li>Risk Metrics</li>
        </ul>
      </div>
    </div>
  );
} 