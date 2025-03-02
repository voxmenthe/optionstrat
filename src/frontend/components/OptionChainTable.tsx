/**
 * OptionChainTable Component
 * Displays option chain data in a tabular format with calls on left, 
 * puts on right, and strikes in the middle.
 * Supports selection, ITM/OTM highlighting, and greek display.
 */

import React, { useMemo } from 'react';
import { OptionContract } from '../lib/api/optionsApi';

interface OptionChainTableProps {
  options: OptionContract[];
  selectedOption: OptionContract | null;
  onSelect: (option: OptionContract) => void;
  showGreeks?: boolean;
  underlyingPrice?: number;
}

const OptionChainTable: React.FC<OptionChainTableProps> = ({
  options,
  selectedOption,
  onSelect,
  showGreeks = false,
  underlyingPrice
}) => {
  // Separate and organize options by type and strike
  const { callsByStrike, putsByStrike, strikes } = useMemo(() => {
    const callsByStrike: Record<number, OptionContract> = {};
    const putsByStrike: Record<number, OptionContract> = {};
    const strikeSet = new Set<number>();
    
    // Organize options by type and strike
    options.forEach(option => {
      const strike = option.strike;
      strikeSet.add(strike);
      
      if (option.optionType === 'call') {
        callsByStrike[strike] = option;
      } else {
        putsByStrike[strike] = option;
      }
    });
    
    // Sort strikes in ascending order
    const strikes = Array.from(strikeSet).sort((a, b) => a - b);
    
    return { callsByStrike, putsByStrike, strikes };
  }, [options]);
  
  // Determine if an option is in the money
  const isInTheMoney = (option: OptionContract): boolean => {
    if (option.inTheMoney !== undefined) {
      return option.inTheMoney;
    }
    
    if (underlyingPrice) {
      return option.optionType === 'call' 
        ? underlyingPrice > option.strike 
        : underlyingPrice < option.strike;
    }
    
    return false;
  };
  
  // Format price with commas and fixed precision
  const formatPrice = (price?: number): string => {
    if (price === undefined || price === null) return '-';
    return price.toFixed(2);
  };
  
  // Format greek value
  const formatGreek = (value?: number): string => {
    if (value === undefined || value === null) return '-';
    return value.toFixed(3);
  };
  
  // Handle option selection
  const handleSelect = (option: OptionContract) => {
    onSelect(option);
  };
  
  // Render individual option cell
  const renderOptionCell = (option: OptionContract | undefined) => {
    if (!option) return <td className="px-2 py-2 text-center text-gray-400">-</td>;
    
    const isSelected = selectedOption && 
      selectedOption.ticker === option.ticker && 
      selectedOption.strike === option.strike && 
      selectedOption.expiration === option.expiration && 
      selectedOption.optionType === option.optionType;
    
    const itm = isInTheMoney(option);
    
    return (
      <td 
        className={`px-2 py-2 cursor-pointer hover:bg-gray-100 ${
          isSelected ? 'bg-blue-100' : ''
        } ${
          itm ? 'font-medium' : ''
        }`}
        onClick={() => handleSelect(option)}
      >
        <div className="flex justify-between">
          <span className="mr-2">{formatPrice(option.bid)}</span>
          <span className="mr-2">{formatPrice(option.ask)}</span>
          <span>{formatPrice(option.last)}</span>
        </div>
        
        {showGreeks && (
          <div className="flex justify-between text-xs text-gray-600 mt-1">
            <span title="Delta">{formatGreek(option.delta)}</span>
            <span title="Gamma">{formatGreek(option.gamma)}</span>
            <span title="Theta">{formatGreek(option.theta)}</span>
            <span title="Vega">{formatGreek(option.vega)}</span>
          </div>
        )}
      </td>
    );
  };
  
  // If no options, show empty state
  if (strikes.length === 0) {
    return (
      <div className="text-center p-4 text-gray-500">
        No options available for the selected criteria.
      </div>
    );
  }
  
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th 
              scope="col" 
              className="px-2 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              colSpan={3}
            >
              CALLS
            </th>
            <th 
              scope="col" 
              className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              STRIKE
            </th>
            <th 
              scope="col" 
              className="px-2 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              colSpan={3}
            >
              PUTS
            </th>
          </tr>
          <tr className="bg-gray-50">
            <th 
              scope="col" 
              className="px-2 py-1 text-left text-xs font-medium text-gray-500 tracking-wider"
              colSpan={3}
            >
              <div className="flex justify-between">
                <span>Bid</span>
                <span>Ask</span>
                <span>Last</span>
              </div>
              {showGreeks && (
                <div className="flex justify-between text-xs">
                  <span>Δ</span>
                  <span>γ</span>
                  <span>θ</span>
                  <span>ν</span>
                </div>
              )}
            </th>
            <th 
              scope="col" 
              className="px-2 py-1 text-center text-xs font-medium text-gray-500 tracking-wider"
            ></th>
            <th 
              scope="col" 
              className="px-2 py-1 text-left text-xs font-medium text-gray-500 tracking-wider"
              colSpan={3}
            >
              <div className="flex justify-between">
                <span>Bid</span>
                <span>Ask</span>
                <span>Last</span>
              </div>
              {showGreeks && (
                <div className="flex justify-between text-xs">
                  <span>Δ</span>
                  <span>γ</span>
                  <span>θ</span>
                  <span>ν</span>
                </div>
              )}
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {strikes.map((strike) => (
            <tr key={strike} className="hover:bg-gray-50">
              {renderOptionCell(callsByStrike[strike])}
              <td className={`px-2 py-2 text-center font-medium ${
                underlyingPrice && strike === Math.round(underlyingPrice) 
                  ? 'bg-yellow-50' 
                  : ''
              }`}>
                {strike.toFixed(2)}
              </td>
              {renderOptionCell(putsByStrike[strike])}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default OptionChainTable; 