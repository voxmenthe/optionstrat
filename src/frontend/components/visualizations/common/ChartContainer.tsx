'use client';

import React, { ReactNode, useState, useEffect, useRef } from 'react';
import { ChartConfiguration } from '../../../types/visualization';
import { calculateDimensions } from './utils';

interface ChartContainerProps {
  children: ReactNode;
  config: ChartConfiguration;
  title?: string;
  isLoading?: boolean;
  error?: string | null;
  onConfigChange?: (newConfig: Partial<ChartConfiguration>) => void;
  className?: string;
  onResize?: (width: number, height: number) => void;
}

/**
 * A responsive container for all chart components
 * Handles loading states, errors, and consistent styling
 */
const ChartContainer: React.FC<ChartContainerProps> = ({
  children,
  config,
  title,
  isLoading = false,
  error = null,
  onConfigChange,
  className = '',
  onResize,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  // Handle responsive resizing
  useEffect(() => {
    if (!containerRef.current || !config.responsiveResize) return;

    const calculateSize = () => {
      if (!containerRef.current) return;
      
      const { width, height } = containerRef.current.getBoundingClientRect();
      const newDimensions = calculateDimensions(
        width, 
        height,
        16/9, // Default aspect ratio
        300,  // Minimum height
        800   // Maximum height
      );
      
      setDimensions(newDimensions);
      
      if (onResize) {
        onResize(newDimensions.width, newDimensions.height);
      }
    };

    // Calculate initial size
    calculateSize();

    // Set up resize observer
    const resizeObserver = new ResizeObserver(calculateSize);
    resizeObserver.observe(containerRef.current);

    return () => {
      if (containerRef.current) {
        resizeObserver.unobserve(containerRef.current);
      }
    };
  }, [config.responsiveResize, onResize]);

  // Render the chart with specified or calculated dimensions
  const chartWidth = config.width || dimensions.width;
  const chartHeight = config.height || dimensions.height;

  return (
    <div 
      ref={containerRef}
      className={`chart-container relative rounded-lg border border-gray-200 bg-white shadow-sm ${className}`}
    >
      {/* Chart header */}
      {(title || onConfigChange) && (
        <div className="chart-header flex items-center justify-between border-b border-gray-200 px-4 py-3">
          {title && <h3 className="text-lg font-medium text-gray-800">{title}</h3>}
          
          {/* Chart controls - could be expanded with actual controls */}
          {onConfigChange && (
            <div className="chart-controls">
              {/* Sample control - toggle grid lines */}
              <button 
                className={`mr-2 rounded px-2 py-1 text-sm ${config.showGridLines ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}
                onClick={() => onConfigChange({ showGridLines: !config.showGridLines })}
              >
                Grid
              </button>
              
              {/* Sample control - toggle legend */}
              <button 
                className={`rounded px-2 py-1 text-sm ${config.showLegend ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}
                onClick={() => onConfigChange({ showLegend: !config.showLegend })}
              >
                Legend
              </button>
            </div>
          )}
        </div>
      )}
      
      {/* Chart content area */}
      <div className="chart-content p-4">
        {/* Loading state */}
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-70 z-10">
            <div className="flex flex-col items-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
              <p className="mt-2 text-sm text-gray-600">Loading chart data...</p>
            </div>
          </div>
        )}
        
        {/* Error state */}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-90 z-10">
            <div className="mx-auto max-w-md rounded-lg bg-red-50 p-4 text-center">
              <p className="text-sm font-medium text-red-800">Error loading chart data</p>
              <p className="mt-1 text-xs text-red-700">{error}</p>
            </div>
          </div>
        )}
        
        {/* Chart content */}
        <div 
          className="chart-wrapper"
          style={{ 
            width: chartWidth || '100%', 
            height: chartHeight || 400,
            margin: '0 auto'
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
};

export default ChartContainer; 