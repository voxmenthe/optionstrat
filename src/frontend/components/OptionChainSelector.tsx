import React, { useState, useEffect, useRef } from 'react';
import { useOptionChainStore } from '../lib/stores/optionChainStore';
import { optionsApi } from '../lib/api/optionsApi';
import logger from '../utils/logger';

const OptionChainSelector: React.FC = () => {
  // Get state and actions from the store
  const { 
    ticker, 
    expirations, 
    selectedExpiration, 
    chain, 
    isLoading, 
    error,
    setTicker, 
    setSelectedExpiration 
  } = useOptionChainStore();
  
  // Local state for search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<string[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  
  // Debug logging for component state
  useEffect(() => {
    console.log('OptionChainSelector state:', {
      ticker,
      expirations: expirations?.length || 0,
      selectedExpiration,
      chainLength: chain?.length || 0,
      isLoading,
      error
    });
  }, [ticker, expirations, selectedExpiration, chain, isLoading, error]);

  // Handle search input change
  const handleSearchChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);
    setSearchError(null);
    
    if (query.trim().length < 1) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }
    
    try {
      console.log(`Searching for ticker: ${query}`);
      const results = await optionsApi.searchTicker(query);
      console.log(`Search results for ${query}:`, results);
      setSearchResults(results);
      setShowResults(true);
    } catch (err) {
      console.error('Error searching for ticker:', err);
      setSearchError(`Search failed: ${err instanceof Error ? err.message : String(err)}`);
      setSearchResults([]);
    }
  };

  // Handle ticker selection
  const handleTickerSelect = async (selected: string) => {
    console.log(`Ticker selected: ${selected}`);
    setSearchQuery(selected);
    setShowResults(false);
    
    try {
      console.log(`Setting ticker to ${selected}`);
      await setTicker(selected);
      
      // Log the state after setting ticker
      setTimeout(() => {
        const state = useOptionChainStore.getState();
        console.log('Option chain state after setting ticker:', {
          ticker: state.ticker,
          expirations: state.expirations?.length || 0,
          isLoading: state.isLoading,
          error: state.error
        });
        
        // Manually fetch expirations if they're not loaded
        if (!state.expirations || state.expirations.length === 0) {
          console.log('Manually fetching expirations for', selected);
          optionsApi.getExpirations(selected)
            .then(exps => {
              console.log(`Manually fetched ${exps.length} expirations for ${selected}`);
              if (exps.length > 0) {
                console.log('Setting first expiration:', exps[0].date);
                state.setSelectedExpiration(exps[0].date);
              }
            })
            .catch(err => console.error('Error manually fetching expirations:', err));
        }
      }, 1000);
    } catch (error) {
      console.error('Error in handleTickerSelect:', error);
    }
  };

  // Handle expiration selection
  const handleExpirationChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const expDate = e.target.value;
    console.log(`Expiration selected: ${expDate}`);
    setSelectedExpiration(expDate);
    
    // Log the state after setting expiration
    setTimeout(() => {
      const state = useOptionChainStore.getState();
      console.log('Option chain state after setting expiration:', {
        selectedExpiration: state.selectedExpiration,
        chainLength: state.chain?.length || 0
      });
    }, 1000);
  };

  // Close search results when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowResults(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <div className="option-chain-selector">
      <h3>Option Chain Selector</h3>
      
      {/* Search input */}
      <div className="search-container" ref={searchRef}>
        <input
          type="text"
          value={searchQuery}
          onChange={handleSearchChange}
          placeholder="Search ticker symbol..."
          className="search-input"
          onClick={() => searchQuery.trim() && setShowResults(true)}
        />
        
        {/* Search results dropdown */}
        {showResults && searchResults.length > 0 && (
          <ul className="search-results">
            {searchResults.map((result) => (
              <li key={result} onClick={() => handleTickerSelect(result)}>
                {result}
              </li>
            ))}
          </ul>
        )}
        
        {/* Search error */}
        {searchError && <div className="error-message">{searchError}</div>}
      </div>
      
      {/* Expiration date selector */}
      {ticker && expirations && expirations.length > 0 && (
        <div className="expiration-selector">
          <label htmlFor="expiration">Expiration Date:</label>
          <select
            id="expiration"
            value={selectedExpiration || ''}
            onChange={handleExpirationChange}
            disabled={isLoading}
          >
            {expirations.map((exp) => (
              <option key={exp.date} value={exp.date}>
                {exp.date} ({exp.daysToExpiration} days)
              </option>
            ))}
          </select>
        </div>
      )}
      
      {/* Loading indicator */}
      {isLoading && <div className="loading">Loading...</div>}
      
      {/* Error message */}
      {error && <div className="error-message">{error}</div>}
      
      {/* Debug info */}
      <div className="debug-info" style={{ fontSize: '0.8rem', color: '#666', marginTop: '1rem' }}>
        <div>Ticker: {ticker || 'None'}</div>
        <div>Expirations: {expirations?.length || 0}</div>
        <div>Selected Expiration: {selectedExpiration || 'None'}</div>
        <div>Chain Length: {chain?.length || 0}</div>
      </div>
    </div>
  );
};

export default OptionChainSelector; 