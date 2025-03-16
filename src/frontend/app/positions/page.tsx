'use client';

import React from 'react';
import Link from 'next/link';
import PositionFormWithOptionChain from '../../components/PositionFormWithOptionChain';
import PositionTable from '../../components/PositionTable';
import { usePositionStore } from '../../lib/stores/positionStore';

export default function PositionsPage() {
  const { loading, error } = usePositionStore();
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Position Management</h1>
        <Link href="/positions/editable" className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
          Switch to Editable View
        </Link>
      </div>
      
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