'use client';

import React, { useState, useEffect, useRef } from 'react';
import { usePositionStore, OptionPosition } from '../lib/stores/positionStore';
import { ApiError } from '../lib/api';

type PositionFormData = {
  ticker: string;
  expiration: string;
  strike: number;
  type: 'call' | 'put';
  action: 'buy' | 'sell';
  quantity: number;
  premium?: number;
};

const initialPosition: PositionFormData = {
  ticker: '',
  expiration: '',
  strike: 0,
  type: 'call',
  action: 'buy',
  quantity: 1,
  premium: undefined
};

interface PositionFormProps {
  existingPosition?: OptionPosition;
  onSuccess?: () => void;
  onChange?: (data: PositionFormData) => void;
  readonlyFields?: Array<keyof PositionFormData>;
}

// Safe date formatting function - defined outside the component
const formatExpirationDate = (dateStr: string | Date): string => {
  if (!dateStr) return '';
  
  try {
    // If it's already a properly formatted yyyy-mm-dd string, return it
    if (typeof dateStr === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      return dateStr;
    }
    
    const date = new Date(dateStr);
    // Check if date is valid
    if (isNaN(date.getTime())) {
      console.error('Invalid date format:', dateStr);
      return '';
    }
    return date.toISOString().split('T')[0];
  } catch (e) {
    console.error('Error formatting date:', e);
    return '';
  }
};

export default function PositionForm({ 
  existingPosition, 
  onSuccess, 
  onChange,
  readonlyFields = [] 
}: PositionFormProps) {
  const { addPosition, updatePosition, loading: storeLoading, error: storeError } = usePositionStore();
  
  // Initialize with the existing position or default values
  const initialPositionValue = existingPosition ? {
    ticker: existingPosition.ticker,
    expiration: formatExpirationDate(existingPosition.expiration),
    strike: existingPosition.strike,
    type: existingPosition.type,
    action: existingPosition.action,
    quantity: existingPosition.quantity,
    premium: existingPosition.premium,
  } : initialPosition;
  
  const [position, setPosition] = useState<PositionFormData>(initialPositionValue);
  
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const isInitialRender = useRef(true);
  const prevExistingPositionRef = useRef(existingPosition);
  
  // Update position when existingPosition changes
  useEffect(() => {
    // Skip the initial render
    if (isInitialRender.current) {
      isInitialRender.current = false;
      return;
    }
    
    // Skip if the existingPosition hasn't changed
    if (
      existingPosition === prevExistingPositionRef.current ||
      JSON.stringify(existingPosition) === JSON.stringify(prevExistingPositionRef.current)
    ) {
      return;
    }
    
    // Update reference
    prevExistingPositionRef.current = existingPosition;
    
    if (existingPosition) {
      const newPosition = {
        ticker: existingPosition.ticker,
        expiration: formatExpirationDate(existingPosition.expiration),
        strike: existingPosition.strike,
        type: existingPosition.type,
        action: existingPosition.action,
        quantity: existingPosition.quantity,
        premium: existingPosition.premium,
      };
      
      // Only update if something actually changed
      const hasChanged = JSON.stringify(newPosition) !== JSON.stringify(position);
      
      if (hasChanged) {
        setPosition(newPosition);
      }
    }
  }, [existingPosition, position]);
  
  // Notify parent of changes if onChange is provided
  useEffect(() => {
    // Skip the first render
    if (isInitialRender.current) {
      return;
    }
    
    if (onChange) {
      onChange(position);
    }
  }, [position, onChange]);
  
  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    
    if (!position.ticker) {
      newErrors.ticker = 'Ticker is required';
    } else if (!/^[A-Z]{1,5}$/.test(position.ticker)) {
      newErrors.ticker = 'Ticker must be 1-5 uppercase letters';
    }
    
    if (!position.expiration) {
      newErrors.expiration = 'Expiration date is required';
    } else {
      const expirationDate = new Date(position.expiration);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      
      if (isNaN(expirationDate.getTime())) {
        newErrors.expiration = 'Invalid expiration date format';
      } else if (expirationDate < today) {
        newErrors.expiration = 'Expiration date cannot be in the past';
      }
    }
    
    if (!position.strike || position.strike <= 0) {
      newErrors.strike = 'Strike must be greater than 0';
    }
    
    if (position.quantity === undefined || position.quantity === 0) {
      newErrors.quantity = 'Quantity cannot be zero';
    } else if (!Number.isInteger(position.quantity)) {
      newErrors.quantity = 'Quantity must be a whole number';
    }
    
    if (position.premium !== undefined && position.premium < 0) {
      newErrors.premium = 'Premium cannot be negative';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    
    if (validateForm()) {
      setIsSubmitting(true);
      try {
        // Check if this is a valid existing position with ID (for updates)
        // or if it's a new position
        if (existingPosition && existingPosition.id !== null && existingPosition.id !== undefined) {
          // Update existing position
          await updatePosition(existingPosition.id, position);
          if (onSuccess) {
            onSuccess();
          }
        } else {
          // Create new position
          await addPosition(position);
          setPosition(initialPosition); // Reset form after successful submission
          if (onSuccess) {
            onSuccess();
          }
        }
      } catch (error) {
        if (error instanceof ApiError) {
          setFormError(`API Error (${error.status}): ${error.message}`);
        } else {
          const action = existingPosition && existingPosition.id !== null && existingPosition.id !== undefined ? 'updating' : 'adding';
          setFormError(`Error ${action} position: ${error instanceof Error ? error.message : String(error)}`);
        }
      } finally {
        setIsSubmitting(false);
      }
    }
  };
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target as HTMLInputElement;
    
    // Skip changes to readonly fields
    if (readonlyFields.includes(name as keyof PositionFormData)) {
      return;
    }
    
    // Clear the specific error when the user starts typing in a field
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
    
    // Clear form error when user makes any change
    if (formError) {
      setFormError(null);
    }
    
    // Handle special logic for quantity and action synchronization
    if (name === 'quantity') {
      const quantityValue = value === '' ? '' : parseFloat(value);
      
      // Only process if it's a valid number
      if (quantityValue !== '' && !isNaN(quantityValue)) {
        if (quantityValue < 0) {
          // If quantity is negative, automatically set action to 'sell'
          setPosition(prev => ({
            ...prev,
            quantity: quantityValue as number,
            action: 'sell'
          }));
        } else {
          // Just update the quantity without changing action
          setPosition(prev => ({
            ...prev,
            quantity: quantityValue as number
          }));
        }
      } else {
        // Handle empty or invalid input - set to 0 by default
        setPosition(prev => ({
          ...prev,
          quantity: value === '' ? 0 : 0
        }));
      }
    } else if (name === 'action') {
      // If action changes to 'sell', make quantity negative if it's positive
      // If action changes to 'buy', make quantity positive if it's negative
      setPosition(prev => {
        const currentQuantity = prev.quantity || 0;
        let newQuantity = currentQuantity;
        
        if (value === 'sell' && currentQuantity > 0) {
          newQuantity = -Math.abs(currentQuantity);
        } else if (value === 'buy' && currentQuantity < 0) {
          newQuantity = Math.abs(currentQuantity);
        }
        
        return {
          ...prev,
          action: value as 'buy' | 'sell',
          quantity: newQuantity
        };
      });
    } else {
      // Handle all other fields normally
      setPosition(prev => ({
        ...prev,
        [name]: type === 'number' ? (value === '' ? '' : parseFloat(value)) : value
      }));
    }
  };
  
  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
      <h2 className="text-xl font-semibold mb-4">{existingPosition ? 'Edit Position' : 'Add New Position'}</h2>
      
      {formError && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4">
          <p>{formError}</p>
        </div>
      )}
      
      {storeError && !formError && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4">
          <p>{storeError}</p>
        </div>
      )}
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div>
          <label htmlFor="ticker" className="form-label">Ticker</label>
          <input
            id="ticker"
            type="text"
            name="ticker"
            value={position.ticker}
            onChange={handleChange}
            className={`form-input ${errors.ticker ? 'border-red-500' : ''} ${readonlyFields.includes('ticker') ? 'bg-gray-100' : ''}`}
            placeholder="e.g. AAPL"
            disabled={isSubmitting || storeLoading || readonlyFields.includes('ticker')}
            readOnly={readonlyFields.includes('ticker')}
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
            className={`form-input ${errors.expiration ? 'border-red-500' : ''} ${readonlyFields.includes('expiration') ? 'bg-gray-100' : ''}`}
            disabled={isSubmitting || storeLoading || readonlyFields.includes('expiration')}
            readOnly={readonlyFields.includes('expiration')}
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
            className={`form-input ${errors.strike ? 'border-red-500' : ''} ${readonlyFields.includes('strike') ? 'bg-gray-100' : ''}`}
            placeholder="e.g. 150.00"
            disabled={isSubmitting || storeLoading || readonlyFields.includes('strike')}
            readOnly={readonlyFields.includes('strike')}
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
            className={`form-select ${readonlyFields.includes('type') ? 'bg-gray-100' : ''}`}
            disabled={isSubmitting || storeLoading || readonlyFields.includes('type')}
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
            className={`form-select ${readonlyFields.includes('action') ? 'bg-gray-100' : ''}`}
            disabled={isSubmitting || storeLoading || readonlyFields.includes('action')}
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
            step="1"
            className={`form-input ${errors.quantity ? 'border-red-500' : ''} ${readonlyFields.includes('quantity') ? 'bg-gray-100' : ''}`}
            disabled={isSubmitting || storeLoading || readonlyFields.includes('quantity')}
            placeholder="Enter positive or negative number"
            readOnly={readonlyFields.includes('quantity')}
          />
          {errors.quantity && <p className="text-red-500 text-xs mt-1">{errors.quantity}</p>}
        </div>
        
        <div>
          <label htmlFor="premium" className="form-label">Premium (Optional)</label>
          <input
            id="premium"
            type="number"
            name="premium"
            value={position.premium === undefined ? '' : position.premium}
            onChange={handleChange}
            step="0.01"
            className={`form-input ${errors.premium ? 'border-red-500' : ''} ${readonlyFields.includes('premium') ? 'bg-gray-100' : ''}`}
            placeholder="e.g. 3.25"
            disabled={isSubmitting || storeLoading || readonlyFields.includes('premium')}
            readOnly={readonlyFields.includes('premium')}
          />
          {errors.premium && <p className="text-red-500 text-xs mt-1">{errors.premium}</p>}
        </div>
      </div>
      
      <div className="mt-6">
        <button
          type="submit"
          className="btn-primary"
          disabled={isSubmitting || storeLoading}
        >
          {isSubmitting || storeLoading ? (
            <span className="flex items-center">
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {existingPosition ? 'Updating...' : 'Adding...'}
            </span>
          ) : existingPosition ? 'Update Position' : 'Add Position'}
        </button>
      </div>
    </form>
  );
} 