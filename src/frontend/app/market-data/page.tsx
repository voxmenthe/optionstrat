'use client';

import React, { useState, useEffect } from 'react';
import { useMarketDataStore } from '../../lib/stores/marketDataStore';
import { ApiError } from '../../lib/api';
import { OptionChainItem } from '../../lib/api/marketDataApi';

// Define the market data interface based on what we need in the UI
interface MarketData {
  currentPrice: number;
  priceChange: number;
  priceChangePercent: number;
  volume: number;
  marketCap: number;
  pe: number;
  dividend: number;
  impliedVolatility: number;
  historicalVolatility: number;
  companyName?: string;
}

export default function MarketDataPage() {
  const { 
    getTickerInfo, 
    getStockPrice, 
    getOptionChain, 
    getExpirationDates,
    tickerInfo, 
    stockPrice, 
    optionChain, 
    expirationDates,
    selectedExpiration,
    loading, 
    error 
  } = useMarketDataStore();
  
  const [ticker, setTicker] = useState('');
  const [searchedTicker, setSearchedTicker] = useState('');
  const [searchError, setSearchError] = useState<string | null>(null);
  const [marketData, setMarketData] = useState<MarketData | null>(null);
  
  // Transform the API data into the format we need for the UI
  useEffect(() => {
    if (tickerInfo && stockPrice !== null) {
      // Mock some values that might not be available from the API
      setMarketData({
        currentPrice: stockPrice,
        priceChange: tickerInfo.last_price ? stockPrice - tickerInfo.last_price : 0,
        priceChangePercent: tickerInfo.change_percent || 0,
        volume: tickerInfo.volume || 0,
        marketCap: stockPrice * 1000000000, // Mock value
        pe: 25.5, // Mock value
        dividend: 1.2, // Mock value
        impliedVolatility: 0.25, // Mock value
        historicalVolatility: 0.22, // Mock value
        companyName: tickerInfo.name
      });
    }
  }, [tickerInfo, stockPrice]);
  
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!ticker) {
      setSearchError('Please enter a ticker symbol');
      return;
    }
    
    setSearchError(null);
    setSearchedTicker(ticker);
    
    try {
      await getTickerInfo(ticker);
      await getStockPrice(ticker);
      await getExpirationDates(ticker);
      
      // If we have expiration dates, get the option chain for the first one
      if (expirationDates.length > 0 && expirationDates[0].date) {
        await getOptionChain(ticker, expirationDates[0].date);
      }
    } catch (err) {
      console.error('Error fetching market data:', err);
      let errorMessage = 'Failed to fetch market data';
      if (err instanceof Error) {
        errorMessage = err.message;
      }
      setSearchError(errorMessage);
    }
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
  
  // Transform option chain data for display
  const transformedOptionChain = optionChain.reduce<Record<number, any>>((acc, option) => {
    const strike = option.strike;
    
    if (!acc[strike]) {
      acc[strike] = {
        strike,
        expiration: option.expiration,
        callBid: 0,
        callAsk: 0,
        callVolume: 0,
        callOpenInterest: 0,
        callIV: 0,
        putBid: 0,
        putAsk: 0,
        putVolume: 0,
        putOpenInterest: 0,
        putIV: 0
      };
    }
    
    if (option.option_type === 'call') {
      acc[strike].callBid = option.bid;
      acc[strike].callAsk = option.ask;
      acc[strike].callVolume = option.volume;
      acc[strike].callOpenInterest = option.open_interest;
      acc[strike].callIV = option.implied_volatility;
    } else {
      acc[strike].putBid = option.bid;
      acc[strike].putAsk = option.ask;
      acc[strike].putVolume = option.volume;
      acc[strike].putOpenInterest = option.open_interest;
      acc[strike].putIV = option.implied_volatility;
    }
    
    return acc;
  }, {});
  
  // Convert to array and sort by strike
  const displayOptionChain = Object.values(transformedOptionChain).sort((a, b) => a.strike - b.strike);
  
  // Handle error display
  const displayError = error ? (typeof error === 'string' ? error : 'An unknown error occurred') : null;
  
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
              disabled={loading}
            />
          </div>
          <div className="self-end">
            <button 
              type="submit" 
              className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-6 rounded-lg transition duration-150 disabled:opacity-50 disabled:cursor-not-allowed" 
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Loading...
                </span>
              ) : 'Search'}
            </button>
          </div>
        </form>
        
        {searchError && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            <p>{searchError}</p>
          </div>
        )}
        
        {displayError && !searchError && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            <p>{displayError}</p>
          </div>
        )}
      </div>
      
      {searchedTicker && !loading && marketData && (
        <>
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-2xl font-bold">{searchedTicker}</h2>
                <p className="text-gray-500">{marketData.companyName || 'Company Name Not Available'}</p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold">{formatCurrency(marketData.currentPrice)}</p>
                <p className={`text-lg ${marketData.priceChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {marketData.priceChange >= 0 ? '+' : ''}
                  {formatCurrency(marketData.priceChange)} ({marketData.priceChangePercent.toFixed(2)}%)
                </p>
              </div>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div>
                <p className="text-gray-500 text-sm">Volume</p>
                <p className="font-semibold">{formatLargeNumber(marketData.volume)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Market Cap</p>
                <p className="font-semibold">{formatLargeNumber(marketData.marketCap)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">P/E Ratio</p>
                <p className="font-semibold">{marketData.pe.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Dividend Yield</p>
                <p className="font-semibold">{marketData.dividend.toFixed(2)}%</p>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-gray-500 text-sm">Implied Volatility (30-day avg)</p>
                <p className="font-semibold">{(marketData.impliedVolatility * 100).toFixed(2)}%</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Historical Volatility (30-day)</p>
                <p className="font-semibold">{(marketData.historicalVolatility * 100).toFixed(2)}%</p>
              </div>
            </div>
          </div>
          
          {displayOptionChain.length > 0 && selectedExpiration && (
            <div className="bg-white rounded-lg shadow-sm p-6 mb-6 border border-gray-200">
              <h2 className="text-lg font-semibold mb-4">
                Option Chain - {new Date(selectedExpiration).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
              </h2>
              
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
                    {displayOptionChain.map((option) => (
                      <tr 
                        key={option.strike} 
                        className={option.strike === marketData.currentPrice ? 'bg-blue-50' : ''}
                      >
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
          )}
        </>
      )}
      
      {!searchedTicker && !loading && (
        <div className="bg-blue-50 p-6 rounded-lg border border-blue-100 text-center">
          <p className="text-gray-600 mb-4">
            Enter a ticker symbol above to view market data and option chains.
          </p>
          <p className="text-sm text-gray-500">
            This will fetch real-time market data from our API service.
          </p>
        </div>
      )}
      
      {loading && (
        <div className="flex justify-center items-center p-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          <p className="ml-3 text-lg text-gray-600">Loading market data...</p>
        </div>
      )}
    </div>
  );
} 