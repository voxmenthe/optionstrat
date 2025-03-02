/**
 * OptionTypeToggle Component
 * Toggle control for selecting option type (calls, puts, or both)
 */

import React from 'react';

interface OptionTypeToggleProps {
  value: 'call' | 'put' | 'all';
  onChange: (value: 'call' | 'put' | 'all') => void;
  showStatistics?: boolean;
  statistics?: {
    callVolume?: number;
    putVolume?: number;
    callOI?: number;
    putOI?: number;
  };
}

const OptionTypeToggle: React.FC<OptionTypeToggleProps> = ({
  value,
  onChange,
  showStatistics = false,
  statistics
}) => {
  return (
    <div className="flex flex-col space-y-2">
      <h3 className="text-sm font-medium text-gray-700">Option Type</h3>
      
      <div className="flex rounded-md shadow-sm" role="group">
        <button
          type="button"
          className={`py-2 px-4 text-sm font-medium rounded-l-lg focus:z-10 focus:ring-2 ${
            value === 'call'
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-white text-gray-900 border border-gray-300 hover:bg-gray-100'
          }`}
          onClick={() => onChange('call')}
        >
          Calls
          {showStatistics && statistics?.callVolume && (
            <span className="ml-1 text-xs opacity-75">
              (Vol: {statistics.callVolume.toLocaleString()})
            </span>
          )}
        </button>
        <button
          type="button"
          className={`py-2 px-4 text-sm font-medium focus:z-10 focus:ring-2 ${
            value === 'put'
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-white text-gray-900 border border-gray-300 hover:bg-gray-100'
          }`}
          onClick={() => onChange('put')}
        >
          Puts
          {showStatistics && statistics?.putVolume && (
            <span className="ml-1 text-xs opacity-75">
              (Vol: {statistics.putVolume.toLocaleString()})
            </span>
          )}
        </button>
        <button
          type="button"
          className={`py-2 px-4 text-sm font-medium rounded-r-lg focus:z-10 focus:ring-2 ${
            value === 'all'
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-white text-gray-900 border border-gray-300 hover:bg-gray-100'
          }`}
          onClick={() => onChange('all')}
        >
          Both
        </button>
      </div>
      
      {/* Optional statistics display */}
      {showStatistics && (
        <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
          {statistics?.callOI && statistics?.putOI && (
            <>
              <div>Call OI: {statistics.callOI.toLocaleString()}</div>
              <div>Put OI: {statistics.putOI.toLocaleString()}</div>
              {/* Calculate Put/Call Ratio if both values exist */}
              {statistics.callOI > 0 && (
                <div className="col-span-2">
                  P/C Ratio: {(statistics.putOI / statistics.callOI).toFixed(2)}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default OptionTypeToggle; 