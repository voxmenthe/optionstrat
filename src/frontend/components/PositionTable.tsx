'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePositionStore, OptionPosition } from '../lib/stores/positionStore';
import { ApiError } from '../lib/api';

export default function PositionTable() {
  const { positions, removePosition, calculateGreeks, loading } = usePositionStore();
  const [calculatingGreeks, setCalculatingGreeks] = useState<Record<string, boolean>>({});
  const [greeksErrors, setGreeksErrors] = useState<Record<string, string>>({});
  const [deletingPositions, setDeletingPositions] = useState<Record<string, boolean>>({});
  
  const formatCurrency = (value?: number) => {
    if (value === undefined) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };
  
  const formatNumber = (value?: number, decimals = 2) => {
    if (value === undefined) return '-';
    return value.toFixed(decimals);
  };
  
  const handleCalculateGreeks = async (position: OptionPosition) => {
    setCalculatingGreeks(prev => ({ ...prev, [position.id]: true }));
    setGreeksErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[position.id];
      return newErrors;
    });
    
    try {
      await calculateGreeks(position);
    } catch (error) {
      let errorMessage = 'Failed to calculate Greeks';
      if (error instanceof ApiError) {
        errorMessage = `API Error (${error.status}): ${error.message}`;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      setGreeksErrors(prev => ({ ...prev, [position.id]: errorMessage }));
    } finally {
      setCalculatingGreeks(prev => ({ ...prev, [position.id]: false }));
    }
  };
  
  const handleDeletePosition = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this position?')) {
      setDeletingPositions(prev => ({ ...prev, [id]: true }));
      try {
        await removePosition(id);
      } catch (error) {
        console.error('Failed to delete position:', error);
        alert(`Failed to delete position: ${error instanceof Error ? error.message : String(error)}`);
      } finally {
        setDeletingPositions(prev => ({ ...prev, [id]: false }));
      }
    }
  };
  
  if (loading) {
    return (
      <div className="flex justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        <p className="ml-2">Loading positions...</p>
      </div>
    );
  }
  
  if (positions.length === 0) {
    return (
      <div className="bg-gray-50 p-6 rounded-lg text-center">
        <p className="text-gray-500">No positions added yet. Use the form above to add your first position.</p>
      </div>
    );
  }
  
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="positions-table">
        <thead className="bg-gray-50">
          <tr>
            <th>Ticker</th>
            <th>Expiration</th>
            <th>Strike</th>
            <th>Type</th>
            <th>Action</th>
            <th>Qty</th>
            <th>Premium</th>
            <th>Delta</th>
            <th>Gamma</th>
            <th>Theta</th>
            <th>Vega</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {positions.map(position => (
            <tr key={position.id} className={deletingPositions[position.id] ? 'opacity-50' : ''}>
              <td className="font-medium">{position.ticker}</td>
              <td>{new Date(position.expiration).toLocaleDateString()}</td>
              <td>{formatCurrency(position.strike)}</td>
              <td className={position.type === 'call' ? 'text-green-600' : 'text-red-600'}>
                {position.type.toUpperCase()}
              </td>
              <td className={position.action === 'buy' ? 'text-green-600' : 'text-red-600'}>
                {position.action.toUpperCase()}
              </td>
              <td>{position.quantity}</td>
              <td>{formatCurrency(position.premium)}</td>
              <td>{position.greeks ? formatNumber(position.greeks.delta) : '-'}</td>
              <td>{position.greeks ? formatNumber(position.greeks.gamma, 4) : '-'}</td>
              <td>{position.greeks ? formatNumber(position.greeks.theta) : '-'}</td>
              <td>{position.greeks ? formatNumber(position.greeks.vega) : '-'}</td>
              <td className="space-x-2">
                {greeksErrors[position.id] && (
                  <div className="text-red-500 text-xs mb-1">{greeksErrors[position.id]}</div>
                )}
                
                {!position.greeks && !calculatingGreeks[position.id] && (
                  <button
                    onClick={() => handleCalculateGreeks(position)}
                    className="text-blue-500 hover:text-blue-700 font-medium text-sm"
                    disabled={deletingPositions[position.id]}
                  >
                    Calculate Greeks
                  </button>
                )}
                
                {calculatingGreeks[position.id] && (
                  <span className="text-blue-500 text-sm flex items-center">
                    <svg className="animate-spin -ml-1 mr-1 h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Calculating...
                  </span>
                )}
                
                <Link 
                  href={`/visualizations/${position.id}`} 
                  className={`text-green-500 hover:text-green-700 font-medium text-sm ${deletingPositions[position.id] ? 'pointer-events-none opacity-50' : ''}`}
                >
                  Visualize
                </Link>
                
                <button
                  onClick={() => handleDeletePosition(position.id)}
                  className="text-red-500 hover:text-red-700 font-medium text-sm"
                  disabled={deletingPositions[position.id]}
                >
                  {deletingPositions[position.id] ? (
                    <span className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-1 h-3 w-3 text-red-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Deleting...
                    </span>
                  ) : 'Delete'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
} 