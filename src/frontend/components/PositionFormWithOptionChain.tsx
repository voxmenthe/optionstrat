'use client';

import React, { useState, useEffect, useCallback } from 'react';
import PositionForm from './PositionForm';
import OptionChainSelector from './OptionChainSelector';
import { OptionContract } from '../lib/api/optionsApi';
import { useOptionChainStore } from '../lib/stores';
import { OptionPosition } from '../lib/stores/positionStore';

// Define the props, extending from PositionForm
interface PositionFormWithOptionChainProps {
  existingPosition?: OptionPosition;
  onSuccess?: () => void;
}

// Type for the form data mapping from the option contract
type PositionFormData = {
  ticker: string;
  expiration: string;
  strike: number;
  type: 'call' | 'put';
  action: 'buy' | 'sell';
  quantity: number;
  premium?: number;
};

// Safe date formatting function
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

// Wrapper component that combines option chain selector with position form
const PositionFormWithOptionChain: React.FC<PositionFormWithOptionChainProps> = (props) => {
  // Access the option chain store for better synchronization
  const { 
    ticker: storeTicker, 
    selectedExpiration, 
    setTicker, 
    setSelectedExpiration 
  } = useOptionChainStore();
  
  // State for selection mode toggle
  const [useOptionChain, setUseOptionChain] = useState<boolean>(false);
  
  // State for selected option
  const [selectedOption, setSelectedOption] = useState<OptionContract | null>(null);
  
  // State for form data
  const [formData, setFormData] = useState<PositionFormData | null>(null);
  
  // State to track unsaved changes
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  
  // Convert option contract to position form data
  const mapOptionToFormData = useCallback((option: OptionContract): PositionFormData => {
    // Calculate mid price if both bid and ask are available
    const midPrice = option.bid && option.ask 
      ? (option.bid + option.ask) / 2 
      : option.last || 0;
    
    // Format expiration date for form
    let formattedExpDate = '';
    try {
      const expDate = new Date(option.expiration);
      if (!isNaN(expDate.getTime())) {
        formattedExpDate = `${expDate.getFullYear()}-${String(expDate.getMonth() + 1).padStart(2, '0')}-${String(expDate.getDate()).padStart(2, '0')}`;
      }
    } catch (e) {
      console.error('Error formatting option expiration date:', e);
    }
    
    return {
      ticker: option.ticker,
      type: option.optionType,
      strike: option.strike,
      expiration: formattedExpDate,
      premium: midPrice,
      // Default values for other fields
      action: 'buy',
      quantity: 1,
    };
  }, []);
  
  // Handle option selection from the chain
  const handleOptionSelect = useCallback((option: OptionContract) => {
    setSelectedOption(option);
    const mappedData = mapOptionToFormData(option);
    setFormData(mappedData);
    setHasUnsavedChanges(false);
  }, [mapOptionToFormData]);
  
  // Handle form changes from PositionForm
  const handleFormChange = useCallback((data: PositionFormData) => {
    // Prevent unnecessary state updates
    if (JSON.stringify(data) === JSON.stringify(formData)) {
      return;
    }
    
    setFormData(data);
    setHasUnsavedChanges(true);
    
    // Sync with option chain store if in option chain mode
    if (useOptionChain) {
      // Sync ticker changes with the option chain selector
      if (data.ticker && data.ticker !== storeTicker) {
        setTicker(data.ticker);
      }
      
      // Sync expiration changes with the option chain selector
      if (data.expiration && data.expiration !== selectedExpiration) {
        try {
          // Convert from yyyy-mm-dd to ISO format
          const formattedDate = formatExpirationDate(data.expiration);
          if (formattedDate && formattedDate !== selectedExpiration) {
            setSelectedExpiration(formattedDate);
          }
        } catch (e) {
          console.error('Error formatting expiration date:', e);
        }
      }
    }
  }, [useOptionChain, storeTicker, selectedExpiration, setTicker, setSelectedExpiration, formData]);
  
  // Prompt before switching modes if there are unsaved changes
  const handleModeToggle = useCallback(() => {
    if (hasUnsavedChanges) {
      const confirmed = window.confirm(
        "You have unsaved changes. Switching modes may cause you to lose these changes. Continue?"
      );
      if (!confirmed) return;
    }
    
    setUseOptionChain(prev => !prev);
    setHasUnsavedChanges(false);
  }, [hasUnsavedChanges]);
  
  // Initialize form data from existing position if provided
  useEffect(() => {
    // Only set form data if it's not already set and we have an existing position
    if (props.existingPosition && !formData) {
      const initialFormData = {
        ticker: props.existingPosition.ticker,
        expiration: formatExpirationDate(props.existingPosition.expiration),
        strike: props.existingPosition.strike,
        type: props.existingPosition.type,
        action: props.existingPosition.action,
        quantity: props.existingPosition.quantity,
        premium: props.existingPosition.premium,
      };
      
      setFormData(initialFormData);
      
      // Only initialize store values once
      const initializeStoreOnce = () => {
        // If we have an existing position, also set the ticker in the store
        if (props.existingPosition?.ticker) {
          setTicker(props.existingPosition.ticker);
        }
        
        // If we have an existing position with expiration, also set it in the store
        if (props.existingPosition?.expiration) {
          try {
            const formattedDate = formatExpirationDate(props.existingPosition.expiration);
            if (formattedDate) {
              setSelectedExpiration(formattedDate);
            }
          } catch (e) {
            console.error('Error setting expiration date in store:', e);
          }
        }
      };
      
      // Use a timeout to ensure this only happens once
      const timer = setTimeout(initializeStoreOnce, 0);
      return () => clearTimeout(timer);
    }
  }, [props.existingPosition, formData, setTicker, setSelectedExpiration]);
  
  // Handle form success (submission)
  const handleSuccess = useCallback(() => {
    // Reset the selected option and form data after successful submission
    setSelectedOption(null);
    setFormData(null);
    setHasUnsavedChanges(false);
    
    // Call the original onSuccess callback if provided
    if (props.onSuccess) {
      props.onSuccess();
    }
  }, [props.onSuccess]);
  
  // Convert form data to option position for the position form
  const getPositionFromFormData = (): Partial<OptionPosition> | undefined => {
    if (!formData) return undefined;
    
    return {
      ...formData,
      // Add an id if needed but only for display purposes, the real ID will be generated on the server
      id: props.existingPosition?.id || 'temp_id',
    };
  };
  
  return (
    <div className="mb-6">
      {/* Toggle switch between manual entry and option chain */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-4 border border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Position Creation</h2>
          <div className="flex items-center">
            <span className={`mr-3 text-sm font-medium ${!useOptionChain ? 'text-blue-600' : 'text-gray-500'}`}>
              Manual Entry
            </span>
            <label className="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                className="sr-only" 
                checked={useOptionChain}
                onChange={handleModeToggle}
              />
              <div className="w-11 h-6 bg-gray-200 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
            <span className={`ml-3 text-sm font-medium ${useOptionChain ? 'text-blue-600' : 'text-gray-500'}`}>
              Option Chain
            </span>
          </div>
        </div>
        
        {useOptionChain && (
          <div className="mt-2 text-sm text-gray-600">
            <p>
              Search for an option in the chain below and select it to auto-fill the position form.
              Option prices reflect real-time market data.
            </p>
          </div>
        )}
      </div>
      
      {/* Conditional Rendering based on mode */}
      {useOptionChain ? (
        <div className="space-y-4">
          {/* Option Chain Selector */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <OptionChainSelector 
              onSelect={handleOptionSelect}
              initialTicker={formData?.ticker || ''}
              compact={true}
              showGreeks={true}
            />
          </div>
          
          {/* Position Form with selected option data */}
          {selectedOption && (
            <div>
              <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-green-800">
                      Option selected: {selectedOption.ticker} {selectedOption.optionType.toUpperCase()} ${selectedOption.strike} {new Date(selectedOption.expiration).toLocaleDateString()}
                    </p>
                    <p className="text-xs text-green-700 mt-1">
                      Bid: ${selectedOption.bid.toFixed(2)} | Ask: ${selectedOption.ask.toFixed(2)} | Mid: ${((selectedOption.bid + selectedOption.ask) / 2).toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
              
              <PositionForm 
                {...props} 
                existingPosition={getPositionFromFormData() as any}
                onSuccess={handleSuccess}
                onChange={handleFormChange}
                readonlyFields={['ticker', 'type', 'strike', 'expiration']}
              />
            </div>
          )}
        </div>
      ) : (
        /* Standard Position Form */
        <PositionForm 
          {...props} 
          existingPosition={props.existingPosition || getPositionFromFormData() as any}
          onSuccess={handleSuccess}
          onChange={handleFormChange}
        />
      )}
    </div>
  );
};

export default PositionFormWithOptionChain; 