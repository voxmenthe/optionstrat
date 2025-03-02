/**
 * OptionExpirationSelector Component
 * Displays available option expirations for a selected ticker
 * Allows users to select an expiration date for option chain viewing
 */

import React, { useEffect } from 'react';
import { useOptionChainStore } from '../lib/stores';
import { OptionExpiration } from '../lib/api/optionsApi';

interface OptionExpirationSelectorProps {
  ticker: string;
  selectedExpiration: string | null;
  onSelect: (expirationDate: string) => void;
  showDTE?: boolean;
  maxVisible?: number;
}

const OptionExpirationSelector: React.FC<OptionExpirationSelectorProps> = ({
  ticker,
  selectedExpiration,
  onSelect,
  showDTE = true,
  maxVisible = 10
}) => {
  // Use the option chain store to fetch and display expirations
  const { 
    expirations, 
    isLoading, 
    error,
    setTicker 
  } = useOptionChainStore();

  // Load expirations when ticker changes
  useEffect(() => {
    if (ticker) {
      setTicker(ticker);
    }
  }, [ticker, setTicker]);

  // Calculate days to expiration if needed
  const calculateDTE = (expirationDate: string): number => {
    const today = new Date();
    const expDate = new Date(expirationDate);
    // Reset time to midnight for accurate day calculation
    today.setHours(0, 0, 0, 0);
    expDate.setHours(0, 0, 0, 0);
    
    // Calculate difference in days
    const diffTime = expDate.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  // Group expirations by month
  const groupByMonth = (expirations: OptionExpiration[]): Record<string, OptionExpiration[]> => {
    return expirations.reduce((acc, exp) => {
      const date = new Date(exp.date);
      const monthYear = `${date.toLocaleString('default', { month: 'short' })} ${date.getFullYear()}`;
      
      if (!acc[monthYear]) {
        acc[monthYear] = [];
      }
      
      acc[monthYear].push(exp);
      return acc;
    }, {} as Record<string, OptionExpiration[]>);
  };

  // Handle loading state
  if (isLoading) {
    return (
      <div className="flex justify-center p-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div className="text-red-500 p-2 text-sm">
        Error loading expirations: {error}
      </div>
    );
  }

  // Handle empty state
  if (!expirations || expirations.length === 0) {
    return (
      <div className="text-gray-500 p-2 text-sm">
        No expirations available for {ticker}
      </div>
    );
  }

  // Group expirations if we have more than the max visible
  const shouldGroup = expirations.length > maxVisible;
  const groupedExpirations = shouldGroup ? groupByMonth(expirations) : null;
  
  return (
    <div className="flex flex-col space-y-2 p-2">
      <h3 className="text-sm font-medium text-gray-700">Expiration Dates</h3>
      
      {shouldGroup ? (
        // Grouped by month view
        <div className="flex flex-col space-y-2">
          {Object.entries(groupedExpirations || {}).map(([monthYear, monthExpirations]) => (
            <div key={monthYear} className="border rounded-md overflow-hidden">
              <div className="bg-gray-100 px-3 py-1 font-medium text-sm">
                {monthYear}
              </div>
              <div className="p-2 grid grid-cols-2 gap-1 sm:grid-cols-3 md:grid-cols-4">
                {monthExpirations.map((exp) => (
                  <button
                    key={exp.date}
                    className={`text-xs py-1 px-2 rounded ${
                      selectedExpiration === exp.date
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 hover:bg-gray-200'
                    }`}
                    onClick={() => onSelect(exp.date)}
                  >
                    {exp.formattedDate}
                    {showDTE && (
                      <span className="ml-1 text-xs opacity-75">
                        ({calculateDTE(exp.date)}d)
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        // Simple list view
        <div className="grid grid-cols-2 gap-1 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {expirations.map((exp) => (
            <button
              key={exp.date}
              className={`text-xs py-1 px-2 rounded ${
                selectedExpiration === exp.date
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 hover:bg-gray-200'
              }`}
              onClick={() => onSelect(exp.date)}
            >
              {exp.formattedDate}
              {showDTE && (
                <span className="ml-1 text-xs opacity-75">
                  ({calculateDTE(exp.date)}d)
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default OptionExpirationSelector; 