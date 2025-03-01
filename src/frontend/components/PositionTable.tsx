'use client';

import React, { FC, useState, useEffect } from 'react';
import { OptionPosition, usePositionStore, GroupedPosition } from '../lib/stores/positionStore';
import PositionForm from './PositionForm';

const PositionTable: FC = () => {
  const {
    positions,
    fetchPositions,
    removePosition,
    recalculateAllGreeks,
    calculatingAllGreeks,
    groupByUnderlying,
    toggleGrouping,
    getGroupedPositions,
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
    
    // Set up a refresh interval to periodically fetch positions and recalculate Greeks
    const intervalId = setInterval(() => {
      console.log('Refreshing positions and Greeks');
      fetchPositions()
        .then(() => {
          if (positions.length > 0) {
            return recalculateAllGreeks();
          }
        })
        .catch(console.error);
    }, 60000); // Refresh every minute
    
    return () => clearInterval(intervalId);
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

  const handleRecalculateGreeks = async () => {
    try {
      await recalculateAllGreeks();
      setToastMessage({
        title: 'Greeks recalculated successfully',
        status: 'success'
      });
      
      // Auto clear toast after 3 seconds
      setTimeout(() => setToastMessage(null), 3000);
    } catch (error) {
      setToastMessage({
        title: 'Error recalculating Greeks',
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
      <td className="py-2 px-3">{position.expiration}</td>
      <td className="py-2 px-3 text-right">{position.strike}</td>
      <td className="py-2 px-3">{position.type}</td>
      <td className="py-2 px-3">{position.action}</td>
      <td className="py-2 px-3 text-right">{position.quantity}</td>
      <td className="py-2 px-3 text-right">{position.premium}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.delta)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.gamma)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.theta)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.vega)}</td>
      <td className="py-2 px-3 text-right">{formatGreeks(position.greeks?.rho)}</td>
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
          <td colSpan={7} className="py-3 px-3">
            <span className="text-lg">
              {group.underlying} ({group.positions.length} positions)
            </span>
          </td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.delta)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.gamma)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.theta)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.vega)}</td>
          <td className="py-3 px-3 text-right">{formatGreeks(group.totalGreeks?.rho)}</td>
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
          <button 
            onClick={handleRecalculateGreeks} 
            className={`px-4 py-2 bg-teal-500 text-white rounded hover:bg-teal-600 ${calculatingAllGreeks ? 'opacity-75 cursor-not-allowed' : ''}`}
            disabled={calculatingAllGreeks}
          >
            {calculatingAllGreeks ? (
              <>
                <span className="inline-block animate-spin mr-2">⟳</span>
                Recalculating...
              </>
            ) : 'Recalculate Greeks'}
          </button>
          <div className="flex items-center space-x-2">
            <span>Group by underlying:</span>
            <div className="relative inline-block w-10 align-middle select-none transition duration-200 ease-in">
              <input 
                type="checkbox" 
                name="toggle" 
                id="toggle"
                className="toggle-checkbox absolute block w-6 h-6 rounded-full bg-white border-4 appearance-none cursor-pointer z-10"
                checked={groupByUnderlying}
                onChange={toggleGrouping}
              />
              <label 
                htmlFor="toggle" 
                className={`toggle-label block overflow-hidden h-6 rounded-full cursor-pointer ${groupByUnderlying ? 'bg-teal-500' : 'bg-gray-300'}`}
              ></label>
            </div>
            <style jsx>{`
              .toggle-checkbox {
                transition: transform 0.3s ease-in-out;
                border-color: #D1D5DB;
              }
              .toggle-checkbox:checked {
                right: 0;
                transform: translateX(100%);
                border-color: #0D9488;
              }
              .toggle-label {
                width: 2.5rem;
                transition: background-color 0.3s ease;
              }
            `}</style>
          </div>
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
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Delta</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Gamma</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Theta</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Vega</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Rho</th>
              <th className="py-3 px-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {positions.length === 0 ? (
              <tr>
                <td colSpan={13} className="py-4 px-3 text-center text-sm text-gray-500">
                  No positions found. Add one to get started.
                </td>
              </tr>
            ) : groupByUnderlying ? (
              renderGroupedPositions()
            ) : (
              positions.map(renderPositionRow)
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