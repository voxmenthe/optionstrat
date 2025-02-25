'use client';

import React, { useState } from 'react';
import { usePositionStore, OptionPosition } from '../lib/stores/positionStore';

type PositionFormData = Omit<OptionPosition, 'id'>;

const initialPosition: PositionFormData = {
  ticker: '',
  expiration: '',
  strike: 0,
  type: 'call',
  action: 'buy',
  quantity: 1,
  premium: undefined
};

export default function PositionForm() {
  const { addPosition } = usePositionStore();
  const [position, setPosition] = useState<PositionFormData>(initialPosition);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    
    if (!position.ticker) {
      newErrors.ticker = 'Ticker is required';
    }
    
    if (!position.expiration) {
      newErrors.expiration = 'Expiration date is required';
    }
    
    if (position.strike <= 0) {
      newErrors.strike = 'Strike must be greater than 0';
    }
    
    if (position.quantity <= 0) {
      newErrors.quantity = 'Quantity must be greater than 0';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (validateForm()) {
      setIsSubmitting(true);
      try {
        await addPosition(position);
        setPosition(initialPosition); // Reset form after successful submission
      } catch (error) {
        // Error handling is done inside the store
      } finally {
        setIsSubmitting(false);
      }
    }
  };
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target as HTMLInputElement;
    
    setPosition(prev => ({
      ...prev,
      [name]: type === 'number' ? parseFloat(value) : value
    }));
  };
  
  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
      <h2 className="text-xl font-semibold mb-4">Add New Position</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div>
          <label htmlFor="ticker" className="form-label">Ticker</label>
          <input
            id="ticker"
            type="text"
            name="ticker"
            value={position.ticker}
            onChange={handleChange}
            className={`form-input ${errors.ticker ? 'border-red-500' : ''}`}
            placeholder="e.g. AAPL"
          />
          {errors.ticker && <p className="text-red-500 text-xs mt-1">{errors.ticker}</p>}
        </div>
        
        <div>
          <label htmlFor="expiration" className="form-label">Expiration Date</label>
          <input
            id="expiration"
            type="date"
            name="expiration"
            value={position.expiration}
            onChange={handleChange}
            className={`form-input ${errors.expiration ? 'border-red-500' : ''}`}
          />
          {errors.expiration && <p className="text-red-500 text-xs mt-1">{errors.expiration}</p>}
        </div>
        
        <div>
          <label htmlFor="strike" className="form-label">Strike Price</label>
          <input
            id="strike"
            type="number"
            name="strike"
            value={position.strike || ''}
            onChange={handleChange}
            step="0.01"
            className={`form-input ${errors.strike ? 'border-red-500' : ''}`}
            placeholder="e.g. 150.00"
          />
          {errors.strike && <p className="text-red-500 text-xs mt-1">{errors.strike}</p>}
        </div>
        
        <div>
          <label htmlFor="type" className="form-label">Option Type</label>
          <select
            id="type"
            name="type"
            value={position.type}
            onChange={handleChange}
            className="form-select"
          >
            <option value="call">Call</option>
            <option value="put">Put</option>
          </select>
        </div>
        
        <div>
          <label htmlFor="action" className="form-label">Action</label>
          <select
            id="action"
            name="action"
            value={position.action}
            onChange={handleChange}
            className="form-select"
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </div>
        
        <div>
          <label htmlFor="quantity" className="form-label">Quantity</label>
          <input
            id="quantity"
            type="number"
            name="quantity"
            value={position.quantity || ''}
            onChange={handleChange}
            min="1"
            className={`form-input ${errors.quantity ? 'border-red-500' : ''}`}
          />
          {errors.quantity && <p className="text-red-500 text-xs mt-1">{errors.quantity}</p>}
        </div>
        
        <div>
          <label htmlFor="premium" className="form-label">Premium (Optional)</label>
          <input
            id="premium"
            type="number"
            name="premium"
            value={position.premium || ''}
            onChange={handleChange}
            step="0.01"
            className="form-input"
            placeholder="e.g. 3.25"
          />
        </div>
      </div>
      
      <div className="mt-6">
        <button
          type="submit"
          className="btn-primary"
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Adding...' : 'Add Position'}
        </button>
      </div>
    </form>
  );
} 