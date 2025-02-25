'use client';

import React, { useState } from 'react';

export default function MarketDataPage() {
  const [ticker, setTicker] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Mock market data for demo purposes
  const mockMarketData = {
    currentPrice: 175.25,
    priceChange: 2.15,
    priceChangePercent: 1.24,
    volume: 45250000,
    marketCap: 2750000000000,
    pe: 28.5,
    dividend: 0.92,
    impliedVolatility: 0.28,
    historicalVolatility: 0.23,
  };
  
  // Mock option chain data
  const mockOptionChain = [
    {
      strike: 160,
      expiration: '2023-12-15',
      callBid: 16.25,
      callAsk: 16.50,
      callVolume: 1250,
      callOpenInterest: 5600,
      callIV: 0.26,
      putBid: 1.10,
      putAsk: 1.25,
      putVolume: 850,
      putOpenInterest: 3200,
      putIV: 0.29,
    },
    {
      strike: 165,
      expiration: '2023-12-15',
      callBid: 12.15,
      callAsk: 12.35,
      callVolume: 1850,
      callOpenInterest: 7200,
      callIV: 0.25,
      putBid: 1.85,
      putAsk: 2.05,
      putVolume: 950,
      putOpenInterest: 4100,
      putIV: 0.28,
    },
    {
      strike: 170,
      expiration: '2023-12-15',
      callBid: 8.25,
      callAsk: 8.50,
      callVolume: 2250,
      callOpenInterest: 9800,
      callIV: 0.24,
      putBid: 3.15,
      putAsk: 3.40,
      putVolume: 1850,
      putOpenInterest: 6300,
      putIV: 0.27,
    },
    {
      strike: 175,
      expiration: '2023-12-15',
      callBid: 5.15,
      callAsk: 5.35,
      callVolume: 3250,
      callOpenInterest: 12500,
      callIV: 0.23,
      putBid: 5.20,
      putAsk: 5.45,
      putVolume: 2850,
      putOpenInterest: 9200,
      putIV: 0.26,
    },
    {
      strike: 180,
      expiration: '2023-12-15',
      callBid: 2.85,
      callAsk: 3.05,
      callVolume: 2350,
      callOpenInterest: 10800,
      callIV: 0.25,
      putBid: 7.95,
      putAsk: 8.20,
      putVolume: 1950,
      putOpenInterest: 8500,
      putIV: 0.28,
    },
  ];
  
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!ticker) {
      setError('Please enter a ticker symbol');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    // Simulate API call
    setTimeout(() => {
      setIsLoading(false);
      
      // For demo purposes, we'll just show data for any ticker entered
      // In a real app, this would make an API call to fetch real data
    }, 500);
  };
  
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };
  
  const formatLargeNumber = (value: number) => {
    if (value >= 1000000000000) {
      return `${(value / 1000000000000).toFixed(2)}T`;
    }
    if (value >= 1000000000) {
      return `${(value / 1000000000).toFixed(2)}B`;
    }
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(2)}M`;
    }
    return value.toLocaleString();
  };
  
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Market Data</h1>
      
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-grow">
            <label htmlFor="ticker" className="form-label">Ticker Symbol</label>
            <input
              id="ticker"
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="e.g. AAPL"
              className="form-input"
            />
          </div>
          <div className="self-end">
            <button type="submit" className="btn-primary" disabled={isLoading}>
              {isLoading ? 'Loading...' : 'Search'}
            </button>
          </div>
        </form>
        
        {error && (
          <div className="mt-4 bg-red-100 border-l-4 border-red-500 text-red-700 p-4">
            <p>{error}</p>
          </div>
        )}
      </div>
      
      {ticker && !isLoading && (
        <>
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-2xl font-bold">{ticker}</h2>
                <p className="text-gray-500">Apple Inc.</p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold">{formatCurrency(mockMarketData.currentPrice)}</p>
                <p className={`text-lg ${mockMarketData.priceChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {mockMarketData.priceChange >= 0 ? '+' : ''}
                  {formatCurrency(mockMarketData.priceChange)} ({mockMarketData.priceChangePercent.toFixed(2)}%)
                </p>
              </div>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div>
                <p className="text-gray-500 text-sm">Volume</p>
                <p className="font-semibold">{formatLargeNumber(mockMarketData.volume)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Market Cap</p>
                <p className="font-semibold">{formatLargeNumber(mockMarketData.marketCap)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">P/E Ratio</p>
                <p className="font-semibold">{mockMarketData.pe.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Dividend Yield</p>
                <p className="font-semibold">{mockMarketData.dividend.toFixed(2)}%</p>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-gray-500 text-sm">Implied Volatility (30-day avg)</p>
                <p className="font-semibold">{(mockMarketData.impliedVolatility * 100).toFixed(2)}%</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Historical Volatility (30-day)</p>
                <p className="font-semibold">{(mockMarketData.historicalVolatility * 100).toFixed(2)}%</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
            <h2 className="text-lg font-semibold mb-4">Option Chain - Dec 15, 2023</h2>
            
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th colSpan={5} className="text-center bg-green-50 text-green-800 px-6 py-3 text-xs font-medium uppercase">Calls</th>
                    <th rowSpan={2} className="px-6 py-3 text-xs font-medium text-gray-500 uppercase">Strike</th>
                    <th colSpan={5} className="text-center bg-red-50 text-red-800 px-6 py-3 text-xs font-medium uppercase">Puts</th>
                  </tr>
                  <tr>
                    <th className="bg-green-50 px-6 py-3 text-left text-xs font-medium text-green-800 uppercase">Bid</th>
                    <th className="bg-green-50 px-6 py-3 text-left text-xs font-medium text-green-800 uppercase">Ask</th>
                    <th className="bg-green-50 px-6 py-3 text-left text-xs font-medium text-green-800 uppercase">Volume</th>
                    <th className="bg-green-50 px-6 py-3 text-left text-xs font-medium text-green-800 uppercase">OI</th>
                    <th className="bg-green-50 px-6 py-3 text-left text-xs font-medium text-green-800 uppercase">IV</th>
                    <th className="bg-red-50 px-6 py-3 text-left text-xs font-medium text-red-800 uppercase">Bid</th>
                    <th className="bg-red-50 px-6 py-3 text-left text-xs font-medium text-red-800 uppercase">Ask</th>
                    <th className="bg-red-50 px-6 py-3 text-left text-xs font-medium text-red-800 uppercase">Volume</th>
                    <th className="bg-red-50 px-6 py-3 text-left text-xs font-medium text-red-800 uppercase">OI</th>
                    <th className="bg-red-50 px-6 py-3 text-left text-xs font-medium text-red-800 uppercase">IV</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {mockOptionChain.map((option) => (
                    <tr key={option.strike} className={option.strike === 175 ? 'bg-blue-50' : ''}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(option.callBid)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(option.callAsk)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{option.callVolume.toLocaleString()}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{option.callOpenInterest.toLocaleString()}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{(option.callIV * 100).toFixed(2)}%</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 bg-gray-50">{formatCurrency(option.strike)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(option.putBid)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(option.putAsk)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{option.putVolume.toLocaleString()}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{option.putOpenInterest.toLocaleString()}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{(option.putIV * 100).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            <div className="mt-4 text-right">
              <p className="text-sm text-gray-500">*Current price row highlighted in blue. OI = Open Interest, IV = Implied Volatility</p>
            </div>
          </div>
        </>
      )}
      
      {!ticker && !isLoading && (
        <div className="bg-blue-50 p-6 rounded-lg border border-blue-100 text-center">
          <p className="text-gray-600 mb-4">
            Enter a ticker symbol above to view market data and option chains.
          </p>
          <p className="text-sm text-gray-500">
            In a full implementation, this would fetch real-time market data from the backend API,
            which would in turn fetch from services like Polygon.io.
          </p>
        </div>
      )}
    </div>
  );
} 