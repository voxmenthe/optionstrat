'use client';

import React from 'react';
import PositionFormWithOptionChain from '../../components/PositionFormWithOptionChain';
import PositionTable from '../../components/PositionTable';
import { usePositionStore } from '../../lib/stores/positionStore';

export default function PositionsPage() {
  const { loading, error } = usePositionStore();
  
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Position Management</h1>
      
      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4">
          <p>{error}</p>
        </div>
      )}
      
      <PositionFormWithOptionChain />
      
      <PositionTable />
    </div>
  );
} 