/**
 * OptionChainSelector Component
 * Main component that integrates ticker search, expiration selection,
 * option type toggle, strike filtering, and the option chain table.
 */

import React, { useState, useEffect } from 'react';
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
}

const OptionChainSelector: React.FC<OptionChainSelectorProps> = ({
  onSelect,
  initialTicker = '',
  showGreeks = false,
  compact = false
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
  
  // Handle ticker search/validation
  const handleSearchChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value.trim().toUpperCase();
    setSearchQuery(query);
    
    // If the input is empty, clear everything
    if (!query) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }
    
    // Basic client-side validation before sending to API
    const isValidFormat = /^[A-Z]{1,6}$/.test(query);
    if (!isValidFormat) {
      // Still set search results to empty but don't call API
      setSearchResults([]);
      setShowResults(false);
      return;
    }
    
    setIsSearching(true);
    try {
      // Instead of searching, we're now validating if the ticker exists
      const validTickers = await optionsApi.searchTickers(query);
      
      if (validTickers.length > 0) {
        // Valid ticker found
        setSearchResults(validTickers);
        setShowResults(true);
      } else {
        // Invalid ticker
        setSearchResults([]);
        setShowResults(false);
        
        // Optional: directly show error message
        console.warn(`Invalid ticker: ${query}`);
      }
    } catch (error) {
      console.error('Error validating ticker:', error);
      setSearchResults([]);
      setShowResults(false);
    } finally {
      setIsSearching(false);
    }
  };
  
  // Handle ticker selection - can be simplified since we're validating directly
  const handleTickerSelect = (selected: string) => {
    setSearchQuery(selected);
    setShowResults(false);
    setTicker(selected);
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
  
  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header with ticker search */}
      <div className="p-4 border-b">
        <div className="relative">
          <div className="flex">
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearchChange}
              placeholder="Search ticker symbol (e.g., AAPL, SPY)"
              className="block w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            />
            {isSearching && (
              <div className="absolute right-3 top-2">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-900"></div>
              </div>
            )}
          </div>
          
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
        <div className="p-4 bg-red-50 text-red-700 border-l-4 border-red-500">
          <p className="font-medium">Error</p>
          <p>{error}</p>
        </div>
      )}
      
      {/* Main content */}
      {ticker && !isLoading && !error && (
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