'use client';

import React, { FC, useState, useEffect } from 'react';
import { OptionPosition, usePositionStore, GroupedPosition, TheoreticalPnLSettings } from '../lib/stores/positionStore';
import PositionForm from './PositionForm';
import EditableCell from './EditableCell';
import { formatPrice } from '../lib/utils/optionPriceUtils';

// Configuration for which fields are editable and how
interface EditablePositionField {
  fieldName: string;
  editable: boolean;
  type: 'text' | 'number' | 'select' | 'date';
  validator?: (value: any) => boolean;
  formatter?: (value: any) => string;
  options?: Array<{value: any, label: string}>;
}

const EDITABLE_POSITION_FIELDS: Record<string, EditablePositionField> = {
  quantity: {
    fieldName: 'quantity',
    editable: true,
    type: 'number',
    validator: (value) => Number.isInteger(value) && value !== 0
  },
  strike: {
    fieldName: 'strike',
    editable: true,
    type: 'number',
    validator: (value) => value > 0
  },
  premium: {
    fieldName: 'premium',
    editable: true,
    type: 'number',
    validator: (value) => value >= 0
  },
  markPrice: {
    fieldName: 'markPrice',
    editable: true,
    type: 'number',
    validator: (value) => value >= 0,
    formatter: (value) => {
      // Debug log to see what's coming in
      console.log('markPrice formatter called with:', { value, type: typeof value, valueIsNaN: typeof value === 'number' && isNaN(value) });
      
      // Handle undefined, null, or NaN values
      if (value === undefined || value === null) {
        console.log('markPrice is undefined or null, returning N/A');
        return 'N/A';
      }
      
      // Try to convert to a number if it's not already
      let numericValue: number;
      if (typeof value !== 'number') {
        numericValue = Number(value);
        console.log(`Converted non-numeric value to number: ${value} → ${numericValue}`);
      } else {
        numericValue = value;
      }
      
      // Check if the value is NaN after conversion
      if (isNaN(numericValue)) {
        console.log('markPrice is NaN after conversion, returning N/A');
        return 'N/A';
      }
      
      // Format the valid number
      console.log(`markPrice is valid number: ${numericValue}, returning formatted value: ${numericValue.toFixed(2)}`);
      return numericValue.toFixed(2);
    }
  },
  expiration: {
    fieldName: 'expiration',
    editable: true,
    type: 'date',
    validator: (value) => Boolean(value && Date.parse(value))
  },
  type: {
    fieldName: 'type',
    editable: true,
    type: 'select',
    options: [
      { value: 'call', label: 'Call' },
      { value: 'put', label: 'Put' }
    ]
  },
  action: {
    fieldName: 'action',
    editable: true,
    type: 'select',
    options: [
      { value: 'buy', label: 'Buy' },
      { value: 'sell', label: 'Sell' }
    ]
  }
};

const EditablePositionTable: FC = () => {
  const {
    positions,
    fetchPositions,
    removePosition,
    updatePosition,
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
  const [isRecalculating, setIsRecalculating] = useState(false);

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
  }, [fetchPositions, recalculateAllGreeks, positions.length]);

  // Combined state for tracking recalculation status
  useEffect(() => {
    setIsRecalculating(calculatingAllGreeks || calculatingPnL || calculatingTheoreticalPnL);
  }, [calculatingAllGreeks, calculatingPnL, calculatingTheoreticalPnL]);
  
  // Debug effect to log positions and their mark prices
  useEffect(() => {
    if (positions.length > 0) {
      console.log('Current positions with mark prices:', positions.map(p => ({
        id: p.id,
        ticker: p.ticker,
        type: p.type,
        strike: p.strike,
        markPrice: p.markPrice,
        markPriceType: typeof p.markPrice,
        isOverride: p.markPriceOverride
      })));
    }
  }, [positions]);

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
      
      let pnlSuccess = true;
      let theoPnlSuccess = true;
      
      // Try to recalculate P&L, but handle missing endpoints gracefully
      try {
        // Use Promise.race with a timeout to prevent long-running requests
        const pnlPromise = recalculateAllPnL(forceRecalculate);
        await Promise.race([
          pnlPromise,
          new Promise((_, reject) => setTimeout(() => reject(new Error('P&L calculation timeout')), 5000))
        ]);
        
        // If we get here, the P&L calculation was successful
        pnlPromise.catch(() => {
          // Silently catch any errors that might occur after the race
          pnlSuccess = false;
        });
      } catch (pnlError) {
        // Don't log errors to console - they're already handled in the store
        pnlSuccess = false;
      }
      
      // Try to recalculate theoretical P&L, but handle missing endpoints gracefully
      try {
        // Use Promise.race with a timeout to prevent long-running requests
        const theoPnlPromise = recalculateAllTheoreticalPnL(forceRecalculate);
        await Promise.race([
          theoPnlPromise,
          new Promise((_, reject) => setTimeout(() => reject(new Error('Theoretical P&L calculation timeout')), 5000))
        ]);
        
        // If we get here, the theoretical P&L calculation was successful
        theoPnlPromise.catch(() => {
          // Silently catch any errors that might occur after the race
          theoPnlSuccess = false;
        });
      } catch (theoPnlError) {
        // Don't log errors to console - they're already handled in the store
        theoPnlSuccess = false;
      }
      
      // Customize success message based on what was successfully recalculated
      let successTitle = '';
      if (pnlSuccess && theoPnlSuccess) {
        successTitle = forceRecalculate 
          ? 'Forced complete recalculation of Greeks and P&L - all cache ignored'
          : 'Greeks and P&L recalculated (using cache where available)';
      } else if (!pnlSuccess && !theoPnlSuccess) {
        successTitle = 'Greeks recalculated successfully (P&L calculation not available)';
      } else {
        successTitle = 'Greeks recalculated successfully (some P&L calculations not available)';
      }
      
      setToastMessage({
        title: successTitle,
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
    
    // Try to recalculate theoretical P&L, but handle missing endpoints gracefully
    // Use requestAnimationFrame and setTimeout to keep UI responsive
    requestAnimationFrame(() => {
      setTimeout(() => {
        try {
          recalculateAllTheoreticalPnL().catch(() => {
            // Silent catch - errors are already handled in the store
          });
        } catch {
          // Silent catch - no need to log here as we're trying to avoid console noise
        }
      }, 100);
    });
  };

  const handleResetMarkPrice = async (position: OptionPosition) => {
    try {
      // Update the position to remove the mark price override
      await updatePosition(position.id, {
        markPriceOverride: false,
        markPrice: undefined // Clear the mark price so it will be recalculated
      });
      
      // Trigger recalculation to refresh the mark price
      requestAnimationFrame(() => {
        // Recalculate to refresh the data
        recalculateAllGreeks();
        
        // Try to recalculate P&L with the updated mark price
        try {
          setTimeout(() => {
            try {
              recalculateAllPnL().catch(() => {
                // Silent catch - errors are already handled in the store
              });
              
              recalculateAllTheoreticalPnL().catch(() => {
                // Silent catch - errors are already handled in the store
              });
            } catch {
              // Silent catch
            }
          }, 100);
        } catch {
          // Silent catch at the outer level
        }
      });
      
      // Show success message
      setToastMessage({
        title: 'Mark price reset',
        status: 'success'
      });
      
      // Auto clear toast after 2 seconds
      setTimeout(() => setToastMessage(null), 2000);
    } catch (error) {
      console.error('Error resetting mark price:', error);
      setToastMessage({
        title: 'Error resetting mark price',
        status: 'error',
        message: error instanceof Error ? error.message : String(error)
      });
      
      // Auto clear toast after 5 seconds
      setTimeout(() => setToastMessage(null), 5000);
    }
  };

  const handleCellEdit = async (position: OptionPosition, fieldName: string, newValue: any) => {
    try {
      // Create update object with just the changed field
      const updateData: Partial<OptionPosition> = {
        [fieldName]: newValue
      };
      
      // If editing mark price, set the override flag
      if (fieldName === 'markPrice') {
        updateData.markPriceOverride = true;
      }
      
      // Update the position
      await updatePosition(position.id, updateData);
      
      // Trigger recalculation with requestAnimationFrame to keep UI responsive
      requestAnimationFrame(() => {
        // Always recalculate Greeks as they should be implemented
        recalculateAllGreeks();
        
        // Only try to recalculate P&L if the endpoints are implemented
        // Wrap in try/catch to prevent unhandled promise rejections
        try {
          // We'll use a silent approach to prevent console errors
          // The position store will handle the errors internally
          setTimeout(() => {
            try {
              recalculateAllPnL().catch(err => {
                // Silent catch - errors are already handled in the store
              });
              
              recalculateAllTheoreticalPnL().catch(err => {
                // Silent catch - errors are already handled in the store
              });
            } catch (err) {
              // Silent catch - no need to log here as we're trying to avoid console noise
            }
          }, 100); // Small delay to ensure UI remains responsive
        } catch (err) {
          // Silent catch at the outer level
        }
      });
      
      // Show success message
      setToastMessage({
        title: 'Position updated',
        status: 'success'
      });
      
      // Auto clear toast after 2 seconds
      setTimeout(() => setToastMessage(null), 2000);
    } catch (error) {
      console.error('Error updating position:', error);
      setToastMessage({
        title: 'Error updating position',
        status: 'error',
        message: error instanceof Error ? error.message : String(error)
      });
      
      // Auto clear toast after 5 seconds
      setTimeout(() => setToastMessage(null), 5000);
    }
  };

  const formatGreeks = (value?: number) => {
    if (value === undefined) return 'N/A';
    
    // Values should already be properly normalized from the backend
    // We don't need to rescale them, just ensure consistent display format
    return value.toFixed(4);
  };

  const formatMoney = (value?: number, clientCalculated?: boolean) => {
    if (value === undefined || value === null) return '-';
    const formattedValue = `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return clientCalculated ? `${formattedValue}*` : formattedValue;
  };

  const formatPercent = (value?: number, clientCalculated?: boolean) => {
    if (value === undefined || value === null) return '-';
    const formattedValue = `${value.toFixed(2)}%`;
    return clientCalculated ? `${formattedValue}*` : formattedValue;
  };

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

  const renderPositionRow = (position: OptionPosition) => (
    <tr key={position.id} className="border-b hover:bg-gray-50">
      <td className="py-2 px-3">{position.ticker}</td>
      <td className="py-2 px-3">
        <EditableCell
          value={position.expiration}
          isEditable={EDITABLE_POSITION_FIELDS.expiration.editable}
          onEdit={(newValue) => handleCellEdit(position, 'expiration', newValue)}
          type={EDITABLE_POSITION_FIELDS.expiration.type}
          validator={EDITABLE_POSITION_FIELDS.expiration.validator}
          isCalculating={isRecalculating}
        />
      </td>
      <td className="py-2 px-3">
        <EditableCell
          value={position.strike}
          isEditable={EDITABLE_POSITION_FIELDS.strike.editable}
          onEdit={(newValue) => handleCellEdit(position, 'strike', newValue)}
          type={EDITABLE_POSITION_FIELDS.strike.type}
          validator={EDITABLE_POSITION_FIELDS.strike.validator}
          isCalculating={isRecalculating}
          align="right"
        />
      </td>
      <td className="py-2 px-3">
        <EditableCell
          value={position.type}
          isEditable={EDITABLE_POSITION_FIELDS.type.editable}
          onEdit={(newValue) => handleCellEdit(position, 'type', newValue)}
          type={EDITABLE_POSITION_FIELDS.type.type}
          options={EDITABLE_POSITION_FIELDS.type.options}
          isCalculating={isRecalculating}
        />
      </td>
      <td className="py-2 px-3">
        <EditableCell
          value={position.action}
          isEditable={EDITABLE_POSITION_FIELDS.action.editable}
          onEdit={(newValue) => handleCellEdit(position, 'action', newValue)}
          type={EDITABLE_POSITION_FIELDS.action.type}
          options={EDITABLE_POSITION_FIELDS.action.options}
          isCalculating={isRecalculating}
        />
      </td>
      <td className="py-2 px-3">
        <EditableCell
          value={position.quantity}
          isEditable={EDITABLE_POSITION_FIELDS.quantity.editable}
          onEdit={(newValue) => handleCellEdit(position, 'quantity', newValue)}
          type={EDITABLE_POSITION_FIELDS.quantity.type}
          validator={EDITABLE_POSITION_FIELDS.quantity.validator}
          isCalculating={isRecalculating}
          align="right"
        />
      </td>
      <td className="py-2 px-3">
        <EditableCell
          value={position.premium}
          isEditable={EDITABLE_POSITION_FIELDS.premium.editable}
          onEdit={(newValue) => handleCellEdit(position, 'premium', newValue)}
          type={EDITABLE_POSITION_FIELDS.premium.type}
          validator={EDITABLE_POSITION_FIELDS.premium.validator}
          formatter={(value) => value?.toString() || ''}
          isCalculating={isRecalculating}
          align="right"
        />
      </td>
      <td className="py-2 px-3">
        <div className="flex items-center">
          {/* Debug log for mark price - use useEffect to avoid React node issues */}
          <EditableCell
            value={position.markPrice}
            isEditable={EDITABLE_POSITION_FIELDS.markPrice.editable}
            onEdit={(newValue) => handleCellEdit(position, 'markPrice', newValue)}
            type={EDITABLE_POSITION_FIELDS.markPrice.type}
            validator={EDITABLE_POSITION_FIELDS.markPrice.validator}
            formatter={EDITABLE_POSITION_FIELDS.markPrice.formatter}
            isCalculating={isRecalculating}
            align="right"
          />
          {position.markPriceOverride && (
            <button
              onClick={() => handleResetMarkPrice(position)}
              className="ml-2 text-xs text-gray-500 hover:text-red-500"
              title="Reset to calculated mark price"
            >
              ↺
            </button>
          )}
        </div>
      </td>
      <td className="py-2 px-3 text-right">
        {position.action && position.premium ? 
          (position.action === 'buy' ? '-' : '+') + formatMoney(calculateCostBasis(position)).substring(1) : 
          formatMoney(calculateCostBasis(position))
        }
      </td>
      <td className="py-2 px-3 text-right">{formatIV(position.pnl?.impliedVolatility)}</td>
      <td className="py-2 px-3 text-right">{formatMoney(position.pnl?.currentValue, position.pnl?.clientCalculated)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.delta)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.gamma)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.theta)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.vega)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.rho)}</td>
      <td className="py-2 px-3 text-right">{formatMoney(position.pnl?.pnlAmount, position.pnl?.clientCalculated)}</td>
      <td className="py-2 px-3 text-right">{formatPercent(position.pnl?.pnlPercent, position.pnl?.clientCalculated)}</td>
      <td className="py-2 px-3 text-right">{formatMoney(position.theoreticalPnl?.pnlAmount, position.theoreticalPnl?.clientCalculated)}</td>
      <td className="py-2 px-3 text-right">{formatPercent(position.theoreticalPnl?.pnlPercent, position.theoreticalPnl?.clientCalculated)}</td>
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
          <td className="py-3 px-3 text-right">{formatMoney(group.totalPnl?.currentValue, group.totalPnl?.clientCalculated)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.delta)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.gamma)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.theta)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.vega)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.rho)}</td>
          <td className="py-3 px-3 text-right">{formatMoney(group.totalPnl?.pnlAmount, group.totalPnl?.clientCalculated)}</td>
          <td className="py-3 px-3 text-right">{formatPercent(group.totalPnl?.pnlPercent, group.totalPnl?.clientCalculated)}</td>
          <td className="py-3 px-3 text-right">{formatMoney(group.totalTheoreticalPnl?.pnlAmount, group.totalTheoreticalPnl?.clientCalculated)}</td>
          <td className="py-3 px-3 text-right">{formatPercent(group.totalTheoreticalPnl?.pnlPercent, group.totalTheoreticalPnl?.clientCalculated)}</td>
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
          <div className="flex space-x-2">
            <button 
              onClick={() => handleRecalculateGreeks(false)} 
              className={`px-4 py-2 bg-teal-500 text-white rounded hover:bg-teal-600 ${isRecalculating ? 'opacity-75 cursor-not-allowed' : ''}`}
              disabled={isRecalculating}
            >
              {isRecalculating ? (
                <>
                  <span className="inline-block animate-spin mr-2">⟳</span>
                  Recalculating...
                </>
              ) : 'Recalculate (Use Cache)'}
            </button>
            <button 
              onClick={() => handleRecalculateGreeks(true)} 
              className={`px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 font-bold ${isRecalculating ? 'opacity-75 cursor-not-allowed' : ''}`}
              disabled={isRecalculating}
              title="Forces complete recalculation from scratch, ignoring cache"
            >
              {isRecalculating ? (
                <>
                  <span className="inline-block animate-spin mr-2">⟳</span>
                  Recalculating...
                </>
              ) : 'Force Recalculate'}
            </button>
          </div>
        </div>
      </div>
      
      {/* Add a legend for client-side calculations */}
      <div className="text-sm text-gray-600 italic">
        * Values calculated client-side using mark prices when backend endpoints are unavailable
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
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Mark Price</th>
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
                <td colSpan={20} className="py-4 px-3 text-center text-sm text-gray-500">
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

export default EditablePositionTable;
