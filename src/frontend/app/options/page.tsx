'use client';

/**
 * Options Page
 * Demo page for the option chain selector
 */

import React, { useState } from 'react';
import OptionChainSelector from '../../components/OptionChainSelector';
import { OptionContract } from '../../lib/api/optionsApi';

export default function OptionsPage() {
  const [selectedOption, setSelectedOption] = useState<OptionContract | null>(null);
  
  const handleOptionSelect = (option: OptionContract) => {
    setSelectedOption(option);
    console.log('Selected option:', option);
  };
  
  return (
    <div className="container mx-auto p-4">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2">Option Chain Browser</h1>
        <p className="text-gray-600">
          Search for a ticker symbol and browse available options. Select an option to see its details.
        </p>
      </div>
      
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <OptionChainSelector 
            onSelect={handleOptionSelect}
            showGreeks={true}
          />
        </div>
        
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-xl font-bold mb-4">Selected Option</h2>
            
            {selectedOption ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div className="font-medium">Ticker:</div>
                  <div>{selectedOption.ticker}</div>
                  
                  <div className="font-medium">Type:</div>
                  <div className="capitalize">{selectedOption.optionType}</div>
                  
                  <div className="font-medium">Strike:</div>
                  <div>${selectedOption.strike.toFixed(2)}</div>
                  
                  <div className="font-medium">Expiration:</div>
                  <div>{new Date(selectedOption.expiration).toLocaleDateString()}</div>
                  
                  <div className="font-medium">Bid:</div>
                  <div>${selectedOption.bid.toFixed(2)}</div>
                  
                  <div className="font-medium">Ask:</div>
                  <div>${selectedOption.ask.toFixed(2)}</div>
                  
                  <div className="font-medium">Last:</div>
                  <div>${selectedOption.last?.toFixed(2) || 'N/A'}</div>
                  
                  <div className="font-medium">IV:</div>
                  <div>{selectedOption.impliedVolatility 
                    ? `${(selectedOption.impliedVolatility * 100).toFixed(2)}%` 
                    : 'N/A'}
                  </div>
                  
                  <div className="font-medium">Delta:</div>
                  <div>{selectedOption.delta?.toFixed(3) || 'N/A'}</div>
                  
                  <div className="font-medium">Gamma:</div>
                  <div>{selectedOption.gamma?.toFixed(3) || 'N/A'}</div>
                  
                  <div className="font-medium">Theta:</div>
                  <div>{selectedOption.theta?.toFixed(3) || 'N/A'}</div>
                  
                  <div className="font-medium">Vega:</div>
                  <div>{selectedOption.vega?.toFixed(3) || 'N/A'}</div>
                </div>
                
                <div className="pt-4 border-t mt-4">
                  <button 
                    className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                    onClick={() => {
                      // Here you would typically add this option to a position
                      alert('This would add the option to a position in a real implementation');
                    }}
                  >
                    Use This Option
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-gray-500 text-center py-8">
                No option selected. Click on an option in the chain to see details.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 