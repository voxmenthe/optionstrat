'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePositionStore } from '../../lib/stores/positionStore';

/**
 * Visualizations Page
 * Displays chart visualizations for option strategies
 */
export default function VisualizationsPage() {
  const { positions, fetchPositions, loading, error } = usePositionStore();
  const [isLoading, setIsLoading] = useState(true);
  const [fetchError, setFetchError] = useState<Error | null>(null);

  useEffect(() => {
    const loadPositions = async () => {
      setIsLoading(true);
      try {
        await fetchPositions();
      } catch (err) {
        console.error('Failed to fetch positions:', err);
        setFetchError(err instanceof Error ? err : new Error('Failed to fetch positions'));
      } finally {
        setIsLoading(false);
      }
    };

    loadPositions();
  }, [fetchPositions]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Visualizations</h1>
        <Link 
          href="/visualizations/demo" 
          className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded transition duration-150"
        >
          Demo Chart
        </Link>
      </div>

      {isLoading || loading ? (
        <div className="flex justify-center items-center min-h-[400px]">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          <p className="ml-3 text-lg text-gray-600">Loading positions...</p>
        </div>
      ) : fetchError || error ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          <h3 className="font-bold text-lg mb-2">Error Loading Positions</h3>
          <p>{fetchError?.message || (typeof error === 'string' ? error : 'An unknown error occurred')}</p>
          <button 
            onClick={() => window.location.reload()}
            className="mt-4 bg-white hover:bg-gray-100 text-gray-800 font-semibold py-2 px-4 border border-gray-300 rounded shadow-sm"
          >
            Try Again
          </button>
        </div>
      ) : positions.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm p-6 text-center border border-gray-200">
          <h3 className="font-semibold text-lg mb-3">No Positions Found</h3>
          <p className="text-gray-600 mb-6">You don't have any positions to visualize.</p>
          <div className="flex flex-col space-y-4">
            <Link
              href="/positions"
              className="inline-block bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-6 rounded transition duration-150"
            >
              Create a Position
            </Link>
            <Link
              href="/visualizations/demo"
              className="inline-block bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-6 rounded transition duration-150"
            >
              View Demo Visualization
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {positions.map((position) => (
            <Link 
              key={position.id} 
              href={`/visualizations/${position.id}`}
              className="block"
            >
              <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200 hover:shadow-md transition duration-150 h-full">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="font-semibold text-lg">{position.ticker}</h3>
                    <p className="text-gray-600 text-sm">{formatDate(position.expiration)}</p>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                    position.type === 'call' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {position.type.toUpperCase()}
                  </span>
                </div>
                
                <div className="grid grid-cols-2 gap-2 mb-4">
                  <div>
                    <p className="text-gray-500 text-xs">Strike</p>
                    <p className="font-medium">
                      ${position.strike.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Quantity</p>
                    <p className="font-medium">{position.quantity}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Action</p>
                    <p className="font-medium">{position.action}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Premium</p>
                    <p className="font-medium">
                      {position.premium ? `$${position.premium.toFixed(2)}` : '-'}
                    </p>
                  </div>
                </div>
                
                <div className="mt-auto pt-3 border-t border-gray-100 flex justify-end">
                  <span className="text-blue-600 text-sm font-medium">
                    View Analysis →
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
} 