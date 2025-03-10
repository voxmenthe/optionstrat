/**
 * OptionChainSelector Component
 * Main component that integrates ticker search, expiration selection,
 * option type toggle, strike filtering, and the option chain table.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useOptionChainStore } from '../lib/stores';
import { OptionContract, optionsApi } from '../lib/api/optionsApi';
import OptionExpirationSelector from './OptionExpirationSelector';
import OptionTypeToggle from './OptionTypeToggle';
import OptionStrikeFilter from './OptionStrikeFilter';
import OptionChainTable from './OptionChainTable';

interface OptionChainSelectorProps {
  onSelect: (option: OptionContract) => void;
  initialTicker?: string;
  showGreeks?: boolean;
  compact?: boolean;
  pageSize?: number;
}

const OptionChainSelector: React.FC<OptionChainSelectorProps> = ({
  onSelect,
  initialTicker = '',
  showGreeks = false,
  compact = false,
  pageSize = 20
}) => {
  // Local state for ticker search
  const [searchQuery, setSearchQuery] = useState<string>(initialTicker);
  const [searchResults, setSearchResults] = useState<string[]>([]);
  const [showResults, setShowResults] = useState<boolean>(false);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  
  // Get state and actions from option chain store
  const {
    ticker,
    expirations,
    selectedExpiration,
    chain,
    isLoading,
    error,
    filters,
    selectedOption,
    setTicker,
    setSelectedExpiration,
    setFilter,
    selectOption,
    clear
  } = useOptionChainStore();
  
  // Calculate statistics for option type toggle
  const statistics = React.useMemo(() => {
    if (!chain || chain.length === 0) return undefined;
    
    const callVolume = chain
      .filter(opt => opt.optionType === 'call' && opt.volume)
      .reduce((sum, opt) => sum + (opt.volume || 0), 0);
      
    const putVolume = chain
      .filter(opt => opt.optionType === 'put' && opt.volume)
      .reduce((sum, opt) => sum + (opt.volume || 0), 0);
      
    const callOI = chain
      .filter(opt => opt.optionType === 'call' && opt.openInterest)
      .reduce((sum, opt) => sum + (opt.openInterest || 0), 0);
      
    const putOI = chain
      .filter(opt => opt.optionType === 'put' && opt.openInterest)
      .reduce((sum, opt) => sum + (opt.openInterest || 0), 0);
      
    return { callVolume, putVolume, callOI, putOI };
  }, [chain]);
  
  // Get underlying price from first option in chain (if available)
  const underlyingPrice = React.useMemo(() => {
    if (!chain || chain.length === 0) return undefined;
    return chain[0].underlyingPrice;
  }, [chain]);
  
  // Initialize with initial ticker if provided
  useEffect(() => {
    if (initialTicker) {
      setTicker(initialTicker);
    }
    
    // Cleanup on unmount
    return () => {
      clear();
    };
  }, [initialTicker, setTicker, clear]);
  
  // Debounce reference for search
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Search function with debouncing to prevent UI freezing
  const searchTicker = useCallback(async (query: string) => {
    // Clear any existing timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
      searchTimeoutRef.current = null;
    }
    
    if (!query) {
      setSearchResults([]);
      setShowResults(false);
      console.log('Empty query, not searching');
      setIsSearching(false); // Ensure spinner is off
      return;
    }
    
    // Basic client-side validation before sending to API
    const isValidFormat = /^[A-Z0-9.]{1,6}$/.test(query); // Allow numbers and dots for tickers like BRK.B
    if (!isValidFormat) {
      setSearchResults([]);
      setShowResults(false);
      console.log('Invalid ticker format:', query);
      setIsSearching(false); // Ensure spinner is off
      return;
    }
    
    console.log('Starting search for ticker:', query);
    setIsSearching(true);
    
    // Use requestAnimationFrame to ensure UI updates before heavy operation
    requestAnimationFrame(async () => {
      // Debounce the search to prevent rapid API calls
      searchTimeoutRef.current = setTimeout(async () => {
        try {
          console.log('Calling API to search for ticker:', query);
          
          // Add a timeout to prevent hanging indefinitely
          const controller = new AbortController();
          const timeoutId = setTimeout(() => {
            controller.abort();
            console.error('Search request timed out after 5 seconds');
            // Update UI to show timeout error
            setIsSearching(false);
          }, 5000);
          
          // Make the API call with the abort controller
          const validTickers = await optionsApi.searchTickers(query, 10, controller.signal);
          clearTimeout(timeoutId);
          
          // Check if this is still the most recent search
          if (searchQuery === query) {
            console.log('API response for ticker search:', validTickers);
            
            if (validTickers && validTickers.length > 0) {
              console.log('Valid tickers found:', validTickers);
              setSearchResults(validTickers);
              setShowResults(true);
              
              // If only one result, select it automatically
              if (validTickers.length === 1) {
                handleTickerSelect(validTickers[0]);
              }
            } else {
              console.log('No valid tickers found for:', query);
              setSearchResults([]);
              setShowResults(false);
              console.warn(`Invalid ticker: ${query}`);
            }
          }
        } catch (error) {
          console.error('Error validating ticker:', error);
          setSearchResults([]);
          setShowResults(false);
        } finally {
          console.log('Search completed for:', query);
          setIsSearching(false);
        }
      }, 300); // 300ms debounce
    });
  }, []);
  
  // Handle ticker search input changes - just update the input field
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value.trim().toUpperCase();
    setSearchQuery(query);
    
    // If the input is empty, clear everything immediately
    if (!query) {
      setSearchResults([]);
      setShowResults(false);
    }
  };
  
  // Handle form submission for ticker search
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Search submitted for:', searchQuery);
    if (searchQuery) {
      searchTicker(searchQuery);
    }
  };
  
  // Handle ticker selection - can be simplified since we're validating directly
  const handleTickerSelect = (selected: string) => {
    console.log(`Ticker selected: ${selected}`);
    setSearchQuery(selected);
    setShowResults(false);
    
    // Use requestAnimationFrame to ensure UI updates before heavy operation
    requestAnimationFrame(async () => {
      try {
        console.log(`Setting ticker to ${selected}`);
        await setTicker(selected);
        
        // Add a small delay to ensure expirations are fetched
        setTimeout(async () => {
          try {
            // After setting the ticker, get available expirations and select the first one if available
            const state = useOptionChainStore.getState();
            console.log('Current option chain state:', {
              ticker: state.ticker,
              expirations: state.expirations?.length || 0,
              isLoading: state.isLoading,
              error: state.error
            });
            
            if (state.expirations && state.expirations.length > 0) {
              const firstExpiration = state.expirations[0].date;
              console.log(`Auto-selecting first expiration date: ${firstExpiration}`);
              await setSelectedExpiration(firstExpiration);
              
              // Log the chain data after setting expiration
              setTimeout(() => {
                const updatedState = useOptionChainStore.getState();
                console.log(`Chain data after setting expiration: ${updatedState.chain.length} options`);
              }, 500);
            } else {
              console.warn('No expirations available for ticker:', selected);
            }
          } catch (innerError) {
            console.error('Error selecting expiration:', innerError);
          }
        }, 300); // Small delay to ensure expirations are fetched
      } catch (error) {
        console.error('Error in handleTickerSelect:', error);
      }
    });
  };
  
  // Handle option type change
  const handleOptionTypeChange = (value: 'call' | 'put' | 'all') => {
    setFilter({ optionType: value });
  };
  
  // Handle strike range change
  const handleStrikeRangeChange = (minStrike: number | null, maxStrike: number | null) => {
    setFilter({ minStrike, maxStrike });
  };
  
  // Handle option selection
  const handleOptionSelect = (option: OptionContract) => {
    selectOption(option);
    onSelect(option);
  };
  
  // Handle expiration selection
  const handleExpirationSelect = (date: string) => {
    setSelectedExpiration(date);
  };
  
  // Add an error display component with available dates
  const ErrorWithAvailableDates: React.FC<{
    error: string;
    expirations?: { date: string; formattedDate: string }[];
    onSelectExpiration?: (date: string) => void;
  }> = ({ error, expirations, onSelectExpiration }) => {
    // Only show up to 5 dates to avoid overwhelming the user
    const showExpirations = expirations && expirations.length > 0 && expirations.slice(0, 5);
    
    return (
      <div className="text-red-500 p-3 bg-red-50 border border-red-200 rounded-md mb-4">
        <p className="font-medium">{error}</p>
        
        {showExpirations && (
          <div className="mt-2">
            <p className="text-sm font-medium text-gray-700">Available dates include:</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {showExpirations.map(exp => (
                <button
                  key={exp.date}
                  onClick={() => onSelectExpiration?.(exp.date)}
                  className="px-2 py-1 text-xs bg-blue-100 hover:bg-blue-200 text-blue-800 rounded"
                >
                  {exp.formattedDate}
                </button>
              ))}
              {expirations && expirations.length > 5 && (
                <span className="text-xs text-gray-500 self-center ml-1">
                  and {expirations.length - 5} more...
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };
  
  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header with ticker search */}
      <div className="p-4 border-b">
        <div className="relative">
          <form onSubmit={handleSearchSubmit} className="flex">
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearchChange}
              placeholder="Search ticker symbol (e.g., AAPL, SPY)"
              className="block w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            />
            <button 
              type="submit"
              className="ml-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isSearching}
            >
              Search
            </button>
            {isSearching && (
              <div className="absolute right-24 top-2">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-900"></div>
              </div>
            )}
          </form>
          
          {/* Search results dropdown */}
          {showResults && searchResults.length > 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white shadow-lg rounded-md border border-gray-200 max-h-60 overflow-auto">
              <ul className="py-1">
                {searchResults.map((result) => (
                  <li 
                    key={result}
                    className="px-4 py-2 hover:bg-gray-100 cursor-pointer"
                    onClick={() => handleTickerSelect(result)}
                  >
                    {result}
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {ticker && (
            <div className="text-sm text-gray-500 mt-1">
              Selected: <span className="font-medium">{ticker}</span>
              {underlyingPrice && (
                <span className="ml-2">
                  Price: <span className="font-medium">${underlyingPrice.toFixed(2)}</span>
                </span>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Loading indicator */}
      {isLoading && (
        <div className="flex justify-center p-8">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-gray-900"></div>
        </div>
      )}
      
      {/* Error message */}
      {error && (
        <ErrorWithAvailableDates
          error={error}
          expirations={expirations}
          onSelectExpiration={handleExpirationSelect}
        />
      )}
      
      {/* Main content */}
      {ticker && (
        <div className={compact ? "grid grid-cols-1" : "grid grid-cols-1 md:grid-cols-4 gap-4 p-4"}>
          {/* Filters sidebar */}
          <div className={compact ? "p-4 space-y-4" : "md:col-span-1 p-4 space-y-4 border-r"}>
            {/* Expiration selector */}
            <OptionExpirationSelector
              ticker={ticker}
              selectedExpiration={selectedExpiration}
              onSelect={setSelectedExpiration}
              showDTE={true}
              maxVisible={compact ? 5 : 10}
            />
            
            {/* Option type toggle */}
            <OptionTypeToggle
              value={filters.optionType}
              onChange={handleOptionTypeChange}
              showStatistics={true}
              statistics={statistics}
            />
            
            {/* Strike filter */}
            {underlyingPrice && (
              <OptionStrikeFilter
                underlyingPrice={underlyingPrice}
                minStrike={filters.minStrike}
                maxStrike={filters.maxStrike}
                onChange={handleStrikeRangeChange}
              />
            )}
          </div>
          
          {/* Option chain table */}
          <div className={compact ? "p-4" : "md:col-span-3 p-4"}>
            {chain.length > 0 ? (
              <OptionChainTable
                options={chain}
                selectedOption={selectedOption}
                onSelect={handleOptionSelect}
                showGreeks={showGreeks}
                underlyingPrice={underlyingPrice}
                pageSize={pageSize}
              />
            ) : (
              <div className="text-center p-8 text-gray-500">
                {selectedExpiration ? 
                  "No options available for the selected filters." : 
                  "Please select an expiration date to view options."}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default OptionChainSelector; 