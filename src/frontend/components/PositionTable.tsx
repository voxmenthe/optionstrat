'use client';

import React, { FC, useState, useEffect } from 'react';
import { OptionPosition, usePositionStore, GroupedPosition, TheoreticalPnLSettings } from '../lib/stores/positionStore';
import PositionForm from './PositionForm';

const PositionTable: FC = () => {
  const {
    positions,
    fetchPositions,
    removePosition,
    recalculateAllGreeks,
    calculatingAllGreeks,
    getGroupedPositions,
    theoreticalPnLSettings,
    updateTheoreticalPnLSettings,
    recalculateAllTheoreticalPnL,
    calculatingTheoreticalPnL,
    recalculateAllPnL,
    calculatingPnL
  } = usePositionStore();
  
  const [isLoading, setIsLoading] = useState(true);
  const [editingPosition, setEditingPosition] = useState<OptionPosition | null>(null);
  const [toastMessage, setToastMessage] = useState<{title: string, status: 'success' | 'error', message?: string} | null>(null);

  useEffect(() => {
    const loadPositions = async () => {
      setIsLoading(true);
      try {
        await fetchPositions();
        // Immediately recalculate Greeks after loading positions
        if (positions.length > 0) {
          console.log('Auto-recalculating Greeks for loaded positions');
          await recalculateAllGreeks();
        }
      } catch (error) {
        console.error('Error loading positions:', error);
        setToastMessage({
          title: 'Error loading positions',
          status: 'error',
          message: error instanceof Error ? error.message : String(error)
        });
      } finally {
        setIsLoading(false);
      }
    };

    loadPositions();
    
    // No automatic refresh interval - manual recalculation only
    return () => {};
  }, [fetchPositions, recalculateAllGreeks]);

  const handleEdit = (position: OptionPosition) => {
    setEditingPosition(position);
  };

  const handleDelete = async (id: string) => {
    try {
      await removePosition(id);
      setToastMessage({
        title: 'Position removed',
        status: 'success'
      });
      
      // Auto clear toast after 3 seconds
      setTimeout(() => setToastMessage(null), 3000);
    } catch (error) {
      setToastMessage({
        title: 'Error removing position',
        status: 'error',
        message: error instanceof Error ? error.message : String(error)
      });
      
      // Auto clear toast after 5 seconds
      setTimeout(() => setToastMessage(null), 5000);
    }
  };

  const handleRecalculateGreeks = async (forceRecalculate: boolean = false) => {
    try {
      // Always recalculate Greeks (they're not cached anyway)
      await recalculateAllGreeks();
      
      // Only force recalculation of P&L if explicitly requested
      await recalculateAllPnL(forceRecalculate);
      await recalculateAllTheoreticalPnL(forceRecalculate);
      
      setToastMessage({
        title: forceRecalculate 
          ? 'Forced complete recalculation of Greeks and P&L - all cache ignored'
          : 'Greeks and P&L recalculated (using cache where available)',
        status: 'success'
      });
      
      // Auto clear toast after 3 seconds
      setTimeout(() => setToastMessage(null), 3000);
    } catch (error) {
      setToastMessage({
        title: 'Error recalculating',
        status: 'error',
        message: error instanceof Error ? error.message : String(error)
      });
      
      // Auto clear toast after 5 seconds
      setTimeout(() => setToastMessage(null), 5000);
    }
  };

  const handleTheoreticalSettingsChange = (settings: Partial<TheoreticalPnLSettings>) => {
    updateTheoreticalPnLSettings(settings);
    recalculateAllTheoreticalPnL();
  };

  const formatGreeks = (value?: number) => {
    if (value === undefined) return 'N/A';
    
    // Values should already be properly normalized from the backend
    // We don't need to rescale them, just ensure consistent display format
    return value.toFixed(4);
  };

  const formatMoney = (value?: number) => {
    if (value === undefined || value === null) return '-';
    return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const formatPercent = (value?: number) => {
    if (value === undefined || value === null) return '-';
    return `${value.toFixed(2)}%`;
  };

  // Custom toast component
  const Toast = () => {
    if (!toastMessage) return null;
    
    return (
      <div className={`fixed bottom-4 right-4 p-4 rounded shadow-lg ${toastMessage.status === 'success' ? 'bg-green-500' : 'bg-red-500'} text-white`}>
        <div className="font-bold">{toastMessage.title}</div>
        {toastMessage.message && <div className="text-sm">{toastMessage.message}</div>}
      </div>
    );
  };

  if (editingPosition) {
    return (
      <div>
        <div className="mb-4">
          <button 
            onClick={() => setEditingPosition(null)} 
            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-100"
          >
            Back to Positions
          </button>
        </div>
        <PositionForm 
          existingPosition={editingPosition} 
          onSuccess={() => setEditingPosition(null)}
        />
        <Toast />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        <span className="ml-2">Loading positions...</span>
      </div>
    );
  }

  const formatIV = (value?: number) => {
    if (value === undefined || value === null) return '-';
    return `${(value * 100).toFixed(1)}%`;
  };
  
  const calculateCostBasis = (position: OptionPosition): number => {
    // Calculate cost basis as quantity * premium * 100 (standard contract size)
    // If premium or quantity is missing, return 0
    if (position.premium === undefined || position.premium === null ||
        position.quantity === undefined || position.quantity === 0) {
      return 0;
    }
    
    // For buying options, cost basis is positive (money spent)
    // For selling options, cost basis is negative (money received)
    const sign = position.action === 'buy' ? 1 : -1;
    const contractSize = 100; // Standard contract size is 100 shares
    
    // Return the absolute cost basis (always positive for display purposes)
    // The sign determines whether money was spent or received
    return Math.abs(position.quantity) * position.premium * contractSize;
  };

  const renderPositionRow = (position: OptionPosition) => (
    <tr key={position.id} className="border-b hover:bg-gray-50">
      <td className="py-2 px-3">{position.ticker}</td>
      <td className="py-2 px-3">{position.expiration}</td>
      <td className="py-2 px-3 text-right">{position.strike}</td>
      <td className="py-2 px-3">{position.type}</td>
      <td className="py-2 px-3">{position.action}</td>
      <td className="py-2 px-3 text-right">{position.quantity}</td>
      <td className="py-2 px-3 text-right">{position.premium}</td>
      <td className="py-2 px-3 text-right">
        {position.action && position.premium ? 
          (position.action === 'buy' ? '-' : '+') + formatMoney(calculateCostBasis(position)).substring(1) : 
          formatMoney(calculateCostBasis(position))
        }
      </td>
      <td className="py-2 px-3 text-right">{formatIV(position.pnl?.impliedVolatility)}</td>
      <td className="py-2 px-3 text-right">{formatMoney(position.pnl?.currentValue)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.delta)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.gamma)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.theta)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.vega)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.rho)}</td>
      <td className="py-2 px-3 text-right">{formatMoney(position.pnl?.pnlAmount)}</td>
      <td className="py-2 px-3 text-right">{formatPercent(position.pnl?.pnlPercent)}</td>
      <td className="py-2 px-3 text-right">{formatMoney(position.theoreticalPnl?.pnlAmount)}</td>
      <td className="py-2 px-3 text-right">{formatPercent(position.theoreticalPnl?.pnlPercent)}</td>
      <td className="py-2 px-3">
        <div className="flex space-x-2">
          <button 
            className="px-2 py-1 bg-blue-500 text-white text-xs rounded hover:bg-blue-600" 
            onClick={() => handleEdit(position)}
          >
            Edit
          </button>
          <button 
            className="px-2 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600" 
            onClick={() => handleDelete(position.id)}
          >
            Delete
          </button>
        </div>
      </td>
    </tr>
  );

  const renderGroupedPositions = () => {
    const groupedPositions = getGroupedPositions();
    
    return groupedPositions.map((group: GroupedPosition) => (
      <React.Fragment key={group.underlying}>
        <tr className="bg-gray-100 font-semibold">
          <td colSpan={8} className="py-3 px-3">
            <span className="text-lg">
              {group.underlying} {group.underlyingPrice ? `@ $${group.underlyingPrice.toFixed(2)}` : ''} ({group.positions.length} positions)
            </span>
          </td>
          <td className="py-3 px-3 text-right">{formatIV(group.totalPnl?.impliedVolatility)}</td>
          <td className="py-3 px-3 text-right">{formatMoney(group.totalPnl?.currentValue)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.delta)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.gamma)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.theta)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.vega)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.rho)}</td>
          <td className="py-3 px-3 text-right">{formatMoney(group.totalPnl?.pnlAmount)}</td>
          <td className="py-3 px-3 text-right">{formatPercent(group.totalPnl?.pnlPercent)}</td>
          <td className="py-3 px-3 text-right">{formatMoney(group.totalTheoreticalPnl?.pnlAmount)}</td>
          <td className="py-3 px-3 text-right">{formatPercent(group.totalTheoreticalPnl?.pnlPercent)}</td>
          <td></td>
        </tr>
        {group.positions.map(renderPositionRow)}
      </React.Fragment>
    ));
  };

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex justify-between items-center">
        <div className="flex space-x-4 items-center">
          <div className="flex items-center mr-4">
            <label htmlFor="daysForward" className="mr-2 text-sm text-gray-600">
              Days Forward:
            </label>
            <input
              id="daysForward"
              type="number"
              value={theoreticalPnLSettings.daysForward}
              onChange={(e) => handleTheoreticalSettingsChange({ daysForward: parseInt(e.target.value) || 0 })}
              className="w-16 px-2 py-1 border border-gray-300 rounded"
              min="0"
            />
          </div>
          <div className="flex items-center mr-4">
            <label htmlFor="priceChange" className="mr-2 text-sm text-gray-600">
              Price Change %:
            </label>
            <input
              id="priceChange"
              type="number"
              value={theoreticalPnLSettings.priceChangePercent}
              onChange={(e) => handleTheoreticalSettingsChange({ priceChangePercent: parseFloat(e.target.value) || 0 })}
              className="w-16 px-2 py-1 border border-gray-300 rounded"
              step="0.1"
            />
          </div>
          <div className="flex items-center mr-4">
            <label htmlFor="volatilityDays" className="mr-2 text-sm text-gray-600">
              Volatility Days:
            </label>
            <input
              id="volatilityDays"
              type="number"
              value={theoreticalPnLSettings.volatilityDays}
              onChange={(e) => handleTheoreticalSettingsChange({ volatilityDays: parseInt(e.target.value) || 30 })}
              className="w-16 px-2 py-1 border border-gray-300 rounded"
              min="1"
              max="252"
              title="Number of trading days to use for volatility calculation"
            />
          </div>
          <div className="flex space-x-2">
            <button 
              onClick={() => handleRecalculateGreeks(false)} 
              className={`px-4 py-2 bg-teal-500 text-white rounded hover:bg-teal-600 ${(calculatingAllGreeks || calculatingPnL || calculatingTheoreticalPnL) ? 'opacity-75 cursor-not-allowed' : ''}`}
              disabled={calculatingAllGreeks || calculatingPnL || calculatingTheoreticalPnL}
            >
              {(calculatingAllGreeks || calculatingPnL || calculatingTheoreticalPnL) ? (
                <>
                  <span className="inline-block animate-spin mr-2">⟳</span>
                  Recalculating...
                </>
              ) : 'Recalculate (Use Cache)'}
            </button>
            <button 
              onClick={() => handleRecalculateGreeks(true)} 
              className={`px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 font-bold ${(calculatingAllGreeks || calculatingPnL || calculatingTheoreticalPnL) ? 'opacity-75 cursor-not-allowed' : ''}`}
              disabled={calculatingAllGreeks || calculatingPnL || calculatingTheoreticalPnL}
              title="Forces complete recalculation from scratch, ignoring cache"
            >
              {(calculatingAllGreeks || calculatingPnL || calculatingTheoreticalPnL) ? (
                <>
                  <span className="inline-block animate-spin mr-2">⟳</span>
                  Recalculating...
                </>
              ) : 'Force Recalculate'}
            </button>
          </div>
          {/* Positions are now always grouped by underlying by default */}
        </div>
      </div>
      
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="py-3 px-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ticker</th>
              <th className="py-3 px-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Expiration</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Strike</th>
              <th className="py-3 px-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
              <th className="py-3 px-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Premium</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Cost Basis</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">IV</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Current Value</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Delta</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Gamma</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Theta</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Vega</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Rho</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Current P&L ($)</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Current P&L (%)</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Theo. P&L ($)</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Theo. P&L (%)</th>
              <th className="py-3 px-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {positions.length === 0 ? (
              <tr>
                <td colSpan={17} className="py-4 px-3 text-center text-sm text-gray-500">
                  No positions found. Add one to get started.
                </td>
              </tr>
            ) : (
              renderGroupedPositions()
            )}
          </tbody>
        </table>
      </div>
      
      {/* Toast Notification */}
      <Toast />
    </div>
  );
};

export default PositionTable;