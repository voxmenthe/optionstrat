'use client';

import React from 'react';
import PositionFormWithOptionChain from '../../components/PositionFormWithOptionChain';
import EditablePositionTable from '../../components/EditablePositionTable';
import { usePositionStore } from '../../lib/stores/positionStore';

export default function PositionsPage() {
  const { loading, error } = usePositionStore();
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Position Management</h1>
      </div>
      
      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4">
          <p>{error}</p>
        </div>
      )}
      
      <div className="mb-6 p-4 bg-blue-50 border-l-4 border-blue-500 text-blue-700">
        <h2 className="font-bold mb-2">Editable Positions</h2>
        <p>Click on any editable field (expiration, strike, type, action, quantity, premium) to edit it directly.</p>
        <p>Changes are saved automatically and will trigger recalculation of Greeks and P&L values.</p>
      </div>
      
      <PositionFormWithOptionChain />
      
      <EditablePositionTable />
    </div>
  );
}