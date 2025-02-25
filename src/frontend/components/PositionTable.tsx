'use client';

import React from 'react';
import Link from 'next/link';
import { usePositionStore, OptionPosition } from '../lib/stores/positionStore';

export default function PositionTable() {
  const { positions, removePosition, calculateGreeks } = usePositionStore();
  
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
    try {
      await calculateGreeks(position);
    } catch (error) {
      console.error('Failed to calculate Greeks:', error);
    }
  };
  
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
            <tr key={position.id}>
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
                {!position.greeks && (
                  <button
                    onClick={() => handleCalculateGreeks(position)}
                    className="text-blue-500 hover:text-blue-700 font-medium text-sm"
                  >
                    Calculate Greeks
                  </button>
                )}
                <Link 
                  href={`/visualizations/${position.id}`} 
                  className="text-green-500 hover:text-green-700 font-medium text-sm"
                >
                  Visualize
                </Link>
                <button
                  onClick={() => removePosition(position.id)}
                  className="text-red-500 hover:text-red-700 font-medium text-sm"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
} 