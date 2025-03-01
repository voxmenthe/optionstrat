'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { usePositionStore } from '../../lib/stores/positionStore';
import { ApiError } from '../../lib/api';

export default function VisualizationsPage() {
  const { positions, loading, error, fetchPositions } = usePositionStore();

  useEffect(() => {
    fetchPositions().catch(err => {
      console.error('Failed to fetch positions:', err);
    });
  }, [fetchPositions]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  if (error) {
    let errorMessage = 'An unknown error occurred';
    const err = error as Error | ApiError | unknown;
    
    if (err instanceof ApiError) {
      errorMessage = `API Error (${err.status}): ${err.message}`;
    } else if (err instanceof Error) {
      errorMessage = err.message;
    }

    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
        <h3 className="font-bold text-lg mb-2">Error Loading Positions</h3>
        <p>{errorMessage}</p>
        <button 
          onClick={() => fetchPositions()} 
          className="mt-3 bg-red-100 hover:bg-red-200 text-red-800 font-semibold py-2 px-4 rounded"
        >
          Try Again
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center p-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <p className="ml-3 text-lg text-gray-600">Loading positions...</p>
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="bg-gray-50 border border-gray-200 p-8 rounded-lg text-center">
        <h3 className="text-xl font-semibold text-gray-700 mb-4">No Positions Found</h3>
        <p className="text-gray-500 mb-6">You need to add positions before you can visualize them.</p>
        <Link 
          href="/positions" 
          className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-6 rounded-lg transition duration-150"
        >
          Go to Positions Page
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">Your Positions</h2>
      <p className="text-gray-600">Select a position to visualize its potential outcomes.</p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {positions.map(position => (
          <Link 
            key={position.id} 
            href={`/visualizations/${position.id}`}
            className="block bg-white hover:bg-gray-50 border border-gray-200 rounded-lg p-5 transition duration-150 hover:shadow-md"
          >
            <div className="flex justify-between items-start mb-3">
              <h3 className="text-lg font-semibold text-gray-800">{position.ticker}</h3>
              <span className={`px-2 py-1 rounded text-xs font-medium ${
                position.type === 'call' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}>
                {position.type.toUpperCase()}
              </span>
            </div>
            
            <div className="space-y-2 text-sm text-gray-600">
              <div className="flex justify-between">
                <span>Strike:</span>
                <span className="font-medium">${position.strike.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span>Expiration:</span>
                <span className="font-medium">{formatDate(position.expiration)}</span>
              </div>
              <div className="flex justify-between">
                <span>Action:</span>
                <span className={`font-medium ${
                  position.action === 'buy' ? 'text-green-600' : 'text-red-600'
                }`}>
                  {position.action.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Quantity:</span>
                <span className="font-medium">{position.quantity}</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
} 