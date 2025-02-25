'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { usePositionStore, OptionPosition } from '../../../lib/stores/positionStore';

export default function PositionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { positions, fetchPositions } = usePositionStore();
  const [position, setPosition] = useState<OptionPosition | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Visualization state
  const [visualizationType, setVisualizationType] = useState<'price-vol' | 'price-time' | 'pnl'>('price-vol');
  const [priceRange, setPriceRange] = useState<[number, number]>([-20, 20]); // Percentage change
  const [volRange, setVolRange] = useState<[number, number]>([-50, 50]); // Percentage change
  const [days, setDays] = useState<number>(30);
  
  useEffect(() => {
    const positionId = params.id as string;
    
    const loadPosition = async () => {
      setLoading(true);
      
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
      
      setLoading(false);
    };
    
    loadPosition();
  }, [params.id, positions, fetchPositions, router]);
  
  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <p className="ml-3">Loading position data...</p>
      </div>
    );
  }
  
  if (!position) {
    return (
      <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded">
        <p>Position not found. The position might have been deleted.</p>
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
          className="btn-secondary"
        >
          Back to All Positions
        </button>
      </div>
      
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
      
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
        <h2 className="text-lg font-semibold mb-4">Analysis Settings</h2>
        
        <div className="mb-4">
          <label className="form-label">Visualization Type</label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-1">
            <button
              className={`py-2 px-4 border rounded-md ${visualizationType === 'price-vol' ? 'bg-blue-100 border-blue-300' : 'bg-white border-gray-300'}`}
              onClick={() => setVisualizationType('price-vol')}
            >
              Price vs Volatility
            </button>
            <button
              className={`py-2 px-4 border rounded-md ${visualizationType === 'price-time' ? 'bg-blue-100 border-blue-300' : 'bg-white border-gray-300'}`}
              onClick={() => setVisualizationType('price-time')}
            >
              Price vs Time
            </button>
            <button
              className={`py-2 px-4 border rounded-md ${visualizationType === 'pnl' ? 'bg-blue-100 border-blue-300' : 'bg-white border-gray-300'}`}
              onClick={() => setVisualizationType('pnl')}
            >
              Profit & Loss
            </button>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {visualizationType === 'price-vol' && (
            <>
              <div>
                <label className="form-label">Price Range (%)</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="number"
                    value={priceRange[0]}
                    onChange={(e) => setPriceRange([Number(e.target.value), priceRange[1]])}
                    className="form-input w-24"
                  />
                  <span>to</span>
                  <input
                    type="number"
                    value={priceRange[1]}
                    onChange={(e) => setPriceRange([priceRange[0], Number(e.target.value)])}
                    className="form-input w-24"
                  />
                  <span>%</span>
                </div>
              </div>
              
              <div>
                <label className="form-label">Volatility Range (%)</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="number"
                    value={volRange[0]}
                    onChange={(e) => setVolRange([Number(e.target.value), volRange[1]])}
                    className="form-input w-24"
                  />
                  <span>to</span>
                  <input
                    type="number"
                    value={volRange[1]}
                    onChange={(e) => setVolRange([volRange[0], Number(e.target.value)])}
                    className="form-input w-24"
                  />
                  <span>%</span>
                </div>
              </div>
            </>
          )}
          
          {visualizationType === 'price-time' && (
            <>
              <div>
                <label className="form-label">Price Range (%)</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="number"
                    value={priceRange[0]}
                    onChange={(e) => setPriceRange([Number(e.target.value), priceRange[1]])}
                    className="form-input w-24"
                  />
                  <span>to</span>
                  <input
                    type="number"
                    value={priceRange[1]}
                    onChange={(e) => setPriceRange([priceRange[0], Number(e.target.value)])}
                    className="form-input w-24"
                  />
                  <span>%</span>
                </div>
              </div>
              
              <div>
                <label className="form-label">Days to Expiry</label>
                <input
                  type="number"
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                  className="form-input"
                  min="1"
                  max="365"
                />
              </div>
            </>
          )}
          
          {visualizationType === 'pnl' && (
            <div>
              <label className="form-label">Price Range (%)</label>
              <div className="flex items-center space-x-2">
                <input
                  type="number"
                  value={priceRange[0]}
                  onChange={(e) => setPriceRange([Number(e.target.value), priceRange[1]])}
                  className="form-input w-24"
                />
                <span>to</span>
                <input
                  type="number"
                  value={priceRange[1]}
                  onChange={(e) => setPriceRange([priceRange[0], Number(e.target.value)])}
                  className="form-input w-24"
                />
                <span>%</span>
              </div>
            </div>
          )}
        </div>
        
        <button className="btn-primary">
          Calculate & Visualize
        </button>
      </div>
      
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200 min-h-[400px] flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-500 mb-4">Visualization will appear here when calculated.</p>
          <p className="text-sm text-gray-400">
            Note: In a full implementation, this would display interactive 3D surfaces, 
            charts, and other visualizations using Plotly.js.
          </p>
        </div>
      </div>
    </div>
  );
} 