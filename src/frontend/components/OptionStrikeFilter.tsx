/**
 * OptionStrikeFilter Component
 * Control for setting min/max strike range for filtering option chains
 */

import React, { useState, useEffect } from 'react';

interface OptionStrikeFilterProps {
  underlyingPrice: number;
  minStrike: number | null;
  maxStrike: number | null;
  onChange: (minStrike: number | null, maxStrike: number | null) => void;
  allowPercentMode?: boolean;
}

const OptionStrikeFilter: React.FC<OptionStrikeFilterProps> = ({
  underlyingPrice,
  minStrike,
  maxStrike,
  onChange,
  allowPercentMode = true
}) => {
  // State for input values
  const [minValue, setMinValue] = useState<string>(minStrike?.toString() || '');
  const [maxValue, setMaxValue] = useState<string>(maxStrike?.toString() || '');
  
  // State for percentage mode
  const [isPercentMode, setIsPercentMode] = useState<boolean>(false);
  
  // Quick selection options
  const quickRanges = [
    { label: '±5%', minPct: -5, maxPct: 5 },
    { label: '±10%', minPct: -10, maxPct: 10 },
    { label: '±20%', minPct: -20, maxPct: 20 },
    { label: 'All', minPct: null, maxPct: null }
  ];
  
  // Update input fields when props change
  useEffect(() => {
    if (!isPercentMode) {
      setMinValue(minStrike?.toString() || '');
      setMaxValue(maxStrike?.toString() || '');
    } else {
      // Convert to percentages from the stock price if in percent mode
      const minPct = minStrike ? ((minStrike / underlyingPrice) - 1) * 100 : '';
      const maxPct = maxStrike ? ((maxStrike / underlyingPrice) - 1) * 100 : '';
      
      setMinValue(minPct ? minPct.toFixed(0) : '');
      setMaxValue(maxPct ? maxPct.toFixed(0) : '');
    }
  }, [minStrike, maxStrike, underlyingPrice, isPercentMode]);
  
  // Handle min value change
  const handleMinChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setMinValue(value);
    
    if (value === '') {
      // If cleared, set to null
      onChange(null, maxStrike);
    } else {
      const numericValue = parseFloat(value);
      if (!isNaN(numericValue)) {
        if (isPercentMode) {
          // Convert from percentage to actual strike
          const calculatedStrike = underlyingPrice * (1 + numericValue / 100);
          onChange(calculatedStrike, maxStrike);
        } else {
          onChange(numericValue, maxStrike);
        }
      }
    }
  };
  
  // Handle max value change
  const handleMaxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setMaxValue(value);
    
    if (value === '') {
      // If cleared, set to null
      onChange(minStrike, null);
    } else {
      const numericValue = parseFloat(value);
      if (!isNaN(numericValue)) {
        if (isPercentMode) {
          // Convert from percentage to actual strike
          const calculatedStrike = underlyingPrice * (1 + numericValue / 100);
          onChange(minStrike, calculatedStrike);
        } else {
          onChange(minStrike, numericValue);
        }
      }
    }
  };
  
  // Toggle between absolute and percentage modes
  const togglePercentMode = () => {
    setIsPercentMode(!isPercentMode);
  };
  
  // Apply a quick selection range
  const applyQuickRange = (minPct: number | null, maxPct: number | null) => {
    if (minPct === null && maxPct === null) {
      // "All" option - clear filters
      onChange(null, null);
    } else {
      // Calculate actual strike prices from percentages
      const calculatedMinStrike = minPct !== null ? underlyingPrice * (1 + minPct / 100) : null;
      const calculatedMaxStrike = maxPct !== null ? underlyingPrice * (1 + maxPct / 100) : null;
      
      onChange(calculatedMinStrike, calculatedMaxStrike);
    }
  };
  
  return (
    <div className="flex flex-col space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-medium text-gray-700">Strike Range</h3>
        
        {allowPercentMode && (
          <button
            type="button"
            onClick={togglePercentMode}
            className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            {isPercentMode ? 'Use Absolute Values' : 'Use Percentages'}
          </button>
        )}
      </div>
      
      <div className="flex items-center space-x-2">
        <input
          type="number"
          value={minValue}
          onChange={handleMinChange}
          placeholder={isPercentMode ? "-10%" : "Min"}
          className="w-full px-3 py-2 placeholder-gray-400 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          step={isPercentMode ? 1 : 2.5}
        />
        <span className="text-gray-500">to</span>
        <input
          type="number"
          value={maxValue}
          onChange={handleMaxChange}
          placeholder={isPercentMode ? "+10%" : "Max"}
          className="w-full px-3 py-2 placeholder-gray-400 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          step={isPercentMode ? 1 : 2.5}
        />
        {isPercentMode && (
          <span className="text-gray-500">%</span>
        )}
      </div>
      
      {/* Underlying price display */}
      <div className="text-sm text-gray-600">
        Current price: ${underlyingPrice.toFixed(2)}
      </div>
      
      {/* Quick selection buttons */}
      <div className="flex flex-wrap gap-2">
        {quickRanges.map((range) => (
          <button
            key={range.label}
            className="px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            onClick={() => applyQuickRange(range.minPct, range.maxPct)}
          >
            {range.label}
          </button>
        ))}
      </div>
    </div>
  );
};

export default OptionStrikeFilter; 