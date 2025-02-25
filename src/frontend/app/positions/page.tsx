'use client';

import React, { useEffect } from 'react';
import PositionForm from '../../components/PositionForm';
import PositionTable from '../../components/PositionTable';
import { usePositionStore } from '../../lib/stores/positionStore';

export default function PositionsPage() {
  const { fetchPositions, loading, error } = usePositionStore();
  
  useEffect(() => {
    // Fetch positions when the component mounts
    fetchPositions();
  }, [fetchPositions]);
  
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Position Management</h1>
      
      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4">
          <p>{error}</p>
        </div>
      )}
      
      <PositionForm />
      
      {loading ? (
        <div className="flex justify-center p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          <p className="ml-2">Loading positions...</p>
        </div>
      ) : (
        <PositionTable />
      )}
    </div>
  );
} 