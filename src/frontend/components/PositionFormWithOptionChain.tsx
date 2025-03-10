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
  
  // Handle option selection from the chain with improved performance
  const handleOptionSelect = useCallback((option: OptionContract) => {
    console.log('Option selected from chain:', option);
    
    // Use requestAnimationFrame to ensure UI updates before heavy operations
    requestAnimationFrame(() => {
      try {
        if (!option) {
          console.warn('No option provided to handleOptionSelect');
          return;
        }
        
        // First set the selected option
        setSelectedOption(option);
        
        // Map the option to form data
        const mappedData = mapOptionToFormData(option);
        console.log('Mapped option data:', mappedData);
        
        // Update form data
        setFormData(mappedData);
        setHasUnsavedChanges(true); // Mark as having changes to ensure form is updated
        
        // Provide user feedback
        const optionDescription = `${option.ticker} ${option.optionType.toUpperCase()} $${option.strike} ${option.expiration.split('T')[0]}`;
        console.log(`Selected: ${optionDescription}`);
        
        // Scroll to the form section for better UX
        const formElement = document.getElementById('position-form');
        if (formElement) {
          formElement.scrollIntoView({ behavior: 'smooth' });
        }
      } catch (error) {
        console.error('Error handling option selection:', error);
        console.error('Failed to process option selection. Please try again.');
      }
    });
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
      
      // Sync expiration changes with the option chain selector - with improved performance
      if (data.expiration && data.expiration !== selectedExpiration) {
        try {
          // Only proceed if the ticker is set first
          if (storeTicker) {
            // Convert from yyyy-mm-dd to ISO format
            const formattedDate = formatExpirationDate(data.expiration);
            if (formattedDate && formattedDate !== selectedExpiration) {
              // Use requestAnimationFrame to prevent UI freezing
              requestAnimationFrame(() => {
                // Set a loading indicator or message if needed
                // This helps users understand that something is happening
                
                // Use a small timeout to ensure UI updates before the heavy operation
                setTimeout(() => {
                  setSelectedExpiration(formattedDate);
                }, 0);
              });
            }
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
    
    // Toggle the mode
    setUseOptionChain(prev => {
      const newMode = !prev;
      
      // If switching to option chain mode and we have form data, initialize the option chain
      if (newMode && formData?.ticker) {
        // Use requestAnimationFrame to ensure UI updates before heavy operations
        requestAnimationFrame(async () => {
          try {
            console.log(`Setting ticker to ${formData.ticker} after mode toggle`);
            await setTicker(formData.ticker);
            
            // If we have an expiration date, try to set it
            if (formData.expiration) {
              const formattedDate = formatExpirationDate(formData.expiration);
              if (formattedDate) {
                console.log(`Setting expiration date to ${formattedDate} after mode toggle`);
                // Wait a moment for expirations to be fetched
                setTimeout(async () => {
                  try {
                    await setSelectedExpiration(formattedDate);
                  } catch (error) {
                    console.error('Error setting expiration after mode toggle:', error);
                  }
                }, 300);
              }
            }
          } catch (error) {
            console.error('Error initializing option chain after mode toggle:', error);
          }
        });
      }
      
      return newMode;
    });
    
    setHasUnsavedChanges(false);
  }, [hasUnsavedChanges, formData, setTicker, setSelectedExpiration]);
  
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
      
      // Only initialize store values once, with improved performance and error handling
      const initializeStoreOnce = async () => {
        try {
          // If we have an existing position, also set the ticker in the store
          if (props.existingPosition?.ticker) {
            // Use requestAnimationFrame to ensure UI updates before heavy operations
            requestAnimationFrame(async () => {
              try {
                // Set ticker first - this is a potentially heavy operation
                // Use optional chaining and nullish coalescing to handle undefined safely
                const ticker = props.existingPosition?.ticker || '';
                console.log(`Setting ticker to ${ticker}`);
                await setTicker(ticker);
                
                // Update the UI to show loading state
                // This could be done by setting a local loading state if needed
                
                // Wait a moment for expirations to be fetched before trying to set the expiration date
                // Use a shorter timeout for better responsiveness
                await new Promise(resolve => setTimeout(resolve, 300));
                
                // Now check if the expiration date from the existing position is valid
                if (props.existingPosition?.expiration) {
                  // Add an additional safety check to prevent infinite loops
                  let expirationFailedCount = 0;
                  const MAX_ATTEMPTS = 1; // Only try once
                  
                  try {
                    const formattedDate = formatExpirationDate(props.existingPosition.expiration);
                    if (formattedDate) {
                      console.log(`Setting expiration date to ${formattedDate}`);
                      
                      // Check if this expiration already caused an error
                      const currentError = useOptionChainStore.getState().error;
                      const isKnownInvalidExpiration = 
                        currentError && 
                        currentError.includes('Expiration date') && 
                        currentError.includes(formattedDate);
                      
                      // Only try to set the expiration if we haven't gotten an error for it yet
                      if (!isKnownInvalidExpiration && expirationFailedCount < MAX_ATTEMPTS) {
                        // Use another requestAnimationFrame to ensure UI updates
                        requestAnimationFrame(async () => {
                          try {
                            await setSelectedExpiration(formattedDate);
                            
                            // Check if this caused an error
                            const newError = useOptionChainStore.getState().error;
                            if (newError && newError.includes('Expiration date')) {
                              expirationFailedCount++;
                              console.warn('Invalid expiration date detected, will not retry:', newError);
                            }
                          } catch (e) {
                            console.error('Error setting expiration date:', e);
                          }
                        });
                      }
                    }
                  } catch (e) {
                    console.error('Error formatting expiration date:', e);
                    // If the expiration wasn't valid, don't try again
                  }
                }
              } catch (e) {
                console.error('Error setting ticker:', e);
              }
            });
          }
        } catch (e) {
          console.error('Error initializing store values:', e);
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
                aria-label="Toggle between manual entry and option chain selector"
                title="Toggle between manual entry and option chain selector"
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
            <div className="p-4 bg-blue-50 border-b border-blue-100">
              <h3 className="text-sm font-medium text-blue-800">Option Chain Selection</h3>
              <p className="text-xs text-blue-700 mt-1">
                Search for a ticker and select an option from the chain below. The selected option will automatically populate the position form.
              </p>
            </div>
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
                id="position-form"
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