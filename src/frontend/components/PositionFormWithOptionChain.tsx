'use client';

import React, { useState, useEffect, useCallback } from 'react';
import PositionForm from './PositionForm';
import OptionChainSelector from './OptionChainSelector';
import { OptionContract } from '../lib/api/optionsApi';
import { useOptionChainStore } from '../lib/stores';
import { OptionPosition, usePositionStore } from '../lib/stores/positionStore';
import { ApiError } from '../lib/api/apiClient';

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
  
  // State to track if form has been modified by user (separate from initial loading)
  const [userModifiedForm, setUserModifiedForm] = useState<boolean>(false);
  
  // States for adding position directly to the positions table
  const [isAddingPosition, setIsAddingPosition] = useState<boolean>(false);
  const [addPositionError, setAddPositionError] = useState<string | null>(null);
  const [addPositionSuccess, setAddPositionSuccess] = useState<boolean>(false);
  
  // Get the addPosition function from the position store
  const { addPosition } = usePositionStore();
  
  // Convert option contract to position form data
  const mapOptionToFormData = useCallback((option: OptionContract): PositionFormData => {
    // Validate option data first
    if (!option || typeof option !== 'object') {
      console.error('Invalid option object provided to mapOptionToFormData:', option);
      // Return a placeholder to prevent crashes, but this should never happen
      // due to the validation in handleOptionSelect
      return {
        ticker: '',
        type: 'call',
        strike: 0,
        expiration: '',
        premium: 0,
        action: 'buy',
        quantity: 1,
      };
    }
    
    // Calculate mid price if both bid and ask are available
    const midPrice = option.bid && option.ask 
      ? (option.bid + option.ask) / 2 
      : option.lastPrice || 0; // Use lastPrice as fallback
    
    // Format expiration date for form
    let formattedExpDate = '';
    try {
      // Ensure we have a valid date object
      if (option.expiration) {
        const expDate = new Date(option.expiration);
        if (!isNaN(expDate.getTime())) {
          // Format as ISO string but truncate the time part
          // This ensures compatibility with the backend API
          formattedExpDate = expDate.toISOString().split('T')[0];
          console.log('Formatted expiration date:', formattedExpDate);
        } else {
          console.error('Invalid expiration date:', option.expiration);
        }
      } else {
        console.error('Missing expiration date in option data');
      }
    } catch (e) {
      console.error('Error formatting option expiration date:', e, option.expiration);
    }
    
    // Create the position data with proper fallbacks
    return {
      ticker: option.ticker || '',
      type: (option.optionType as 'call' | 'put') || 'call', // Add type assertion with fallback
      strike: option.strike || 0,
      expiration: formattedExpDate,
      premium: midPrice,
      // Default values for other fields
      action: 'buy',
      quantity: 1,
    };
  }, []);
  
  // Handle adding the selected option directly to positions
  const handleAddToPositions = useCallback(async () => {
    if (!selectedOption) {
      console.warn('No option selected for adding to positions');
      return;
    }
    
    try {
      setIsAddingPosition(true);
      setAddPositionError(null);
      
      // Double-check that the selected option has all required fields
      if (!selectedOption.ticker || !selectedOption.optionType || 
          !selectedOption.strike || !selectedOption.expiration) {
        throw new Error('Selected option is missing required fields');
      }
      
      // Map the selected option to position data
      const positionData = mapOptionToFormData(selectedOption);
      
      // Validate the position data before sending to API
      if (!positionData.ticker || !positionData.expiration || !positionData.type || !positionData.strike) {
        throw new Error('Invalid position data: Missing required fields');
      }
      
      console.log('Adding position directly to positions table:', positionData);
      
      // Add the position to the store with improved error handling
      try {
        // Use a more robust approach with proper error handling
        const result = await addPosition(positionData);
        console.log('Position added successfully:', result);
        
        // Show success message
        setAddPositionSuccess(true);
        
        // Reset form state
        setSelectedOption(null);
        setFormData(null);
        setHasUnsavedChanges(false);
        setUserModifiedForm(false);
        
        // Clear success message after 3 seconds
        setTimeout(() => {
          setAddPositionSuccess(false);
        }, 3000);
      } catch (error: unknown) {
        // More detailed API error handling
        console.error('API Error adding position:', error);
        let errorMessage = 'Failed to add position';
        
        if (error instanceof ApiError) {
          errorMessage = `API Error (${error.status}): ${error.message || error.statusText}`;
          console.error('API Error details:', { 
            status: error.status, 
            statusText: error.statusText, 
            message: error.message,
            name: error.name
          });
          
          // Don't show success message if there was an error
          setAddPositionSuccess(false);
        } else if (error instanceof Error) {
          errorMessage = `Error: ${error.message}`;
        } else {
          errorMessage = `Error: ${String(error)}`;
        }
        
        throw new Error(errorMessage);
      }
    } catch (error) {
      console.error('Error in position addition workflow:', error);
      setAddPositionError(`${error instanceof Error ? error.message : String(error)}`);
      setAddPositionSuccess(false); // Ensure success message is not shown
      
      // Clear error message after 5 seconds
      setTimeout(() => {
        setAddPositionError(null);
      }, 5000);
    } finally {
      setIsAddingPosition(false);
    }
  }, [selectedOption, mapOptionToFormData, addPosition]);
  
  // Handle option selection from the chain with improved performance
  const handleOptionSelect = useCallback((option: OptionContract) => {
    console.log('Option selected from chain:', option);
    
    // Validate option data before proceeding
    if (!option) {
      console.warn('No option provided to handleOptionSelect');
      return;
    }
    
    // Check for required fields
    if (!option.ticker || !option.optionType || !option.strike || !option.expiration) {
      console.error('Invalid option data received:', option);
      console.error('Missing required fields in option data');
      return;
    }
    
    // Use requestAnimationFrame to ensure UI updates before heavy operations
    requestAnimationFrame(() => {
      try {
        // First set the selected option
        setSelectedOption(option);
        
        // Map the option to form data
        const mappedData = mapOptionToFormData(option);
        console.log('Mapped option data:', mappedData);
        
        // Update form data
        setFormData(mappedData);
        // This is a system action, not a user modification, so we don't set userModifiedForm
        // But we do need to mark that the form has changed for React's state tracking
        setHasUnsavedChanges(true);
        
        // Safely access option properties with null checks
        const optionType = option.optionType ? option.optionType.toUpperCase() : '';
        const expirationDate = option.expiration ? option.expiration.split('T')[0] : '';
        const optionDescription = `${option.ticker} ${optionType} $${option.strike} ${expirationDate}`;
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
    setUserModifiedForm(true); // Mark that user has made changes
    
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
  
  // Allow smooth transitions between modes without confirmation dialog
  const handleModeToggle = useCallback(() => {
    // Auto-save the current state to prevent popup on next toggle
    // We'll use localStorage to remember the current form state for this ticker
    if (formData?.ticker) {
      try {
        // Save the current form state for this ticker
        localStorage.setItem(`optionForm_${formData.ticker}`, JSON.stringify(formData));
        console.log(`Saved form state for ${formData.ticker} to prevent future popups`);
      } catch (e) {
        console.error('Error saving form state to localStorage:', e);
      }
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
    
    // Reset the unsaved changes flags when toggling modes
    setHasUnsavedChanges(false);
    setUserModifiedForm(false); // Reset user modification flag
  }, [formData, setTicker, setSelectedExpiration]);
  
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
    setUserModifiedForm(false); // Reset user modification flag
    
    // Call the original onSuccess callback if provided
    if (props.onSuccess) {
      props.onSuccess();
    }
  }, [props.onSuccess]);
  
  // Convert form data to option position for the position form
  const getPositionFromFormData = (): Partial<OptionPosition> | undefined => {
    if (!formData) return undefined;
    
    // Create a position object without an ID to ensure we create a new position
    // rather than trying to update a non-existent one
    const position: Partial<OptionPosition> = {
      ...formData
    };
    
    return position;
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
              <div className={`w-11 h-6 ${useOptionChain ? 'bg-blue-600' : 'bg-gray-200'} rounded-full peer peer-focus:ring-4 peer-focus:ring-blue-300 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all ${useOptionChain ? 'after:translate-x-full' : ''}`}></div>
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
          
          {/* Success message */}
          {addPositionSuccess && (
            <div className="bg-green-100 border-l-4 border-green-500 p-4 mb-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-green-800">
                    Position added successfully! Check the positions table to see your new position.
                  </p>
                </div>
              </div>
            </div>
          )}
          
          {/* Error message */}
          {addPositionError && (
            <div className="bg-red-100 border-l-4 border-red-500 p-4 mb-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-red-800">
                    {addPositionError}
                  </p>
                </div>
              </div>
            </div>
          )}
          
          {/* Position Form with selected option data */}
          {selectedOption && (
            <div>
              <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-4">
                <div className="flex justify-between">
                  <div className="flex">
                    <div className="flex-shrink-0">
                      <svg className="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="ml-3">
                      <p className="text-sm font-medium text-green-800">
                        Option selected: {selectedOption.ticker} {selectedOption.optionType?.toUpperCase() || ''} ${selectedOption.strike} {selectedOption.expiration ? new Date(selectedOption.expiration).toLocaleDateString() : ''}
                      </p>
                      <p className="text-xs text-green-700 mt-1">
                        Bid: ${(selectedOption.bid || 0).toFixed(2)} | Ask: ${(selectedOption.ask || 0).toFixed(2)} | Mid: ${(((selectedOption.bid || 0) + (selectedOption.ask || 0)) / 2).toFixed(2)}
                      </p>
                    </div>
                  </div>
                  <div>
                    <button 
                      onClick={handleAddToPositions}
                      className={`px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors ${isAddingPosition ? 'opacity-75 cursor-not-allowed' : ''}`}
                      disabled={isAddingPosition}
                      title="Add this option directly to your positions table"
                    >
                      {isAddingPosition ? (
                        <span className="flex items-center">
                          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          Adding...
                        </span>
                      ) : 'Add to Positions'}
                    </button>
                  </div>
                </div>
              </div>
              
              <PositionForm 
                // Don't pass existingPosition when it's a new position from option chain
                // This ensures we create a new position instead of trying to update a non-existent one
                existingPosition={undefined}
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