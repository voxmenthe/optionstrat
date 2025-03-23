'use client';

import React, { ReactNode, useState, useEffect, useRef } from 'react';
import { ChartConfiguration } from '../../../types/visualization';
import { calculateDimensions } from './utils';

/**
 * Chart Container Props interface
 */
interface ChartContainerProps {
  children: React.ReactNode;
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
    <div className={`relative bg-white rounded-lg border border-gray-200 ${className}`} 
         style={{ contain: 'paint layout', overflow: 'hidden' }}>
      {/* Chart Header */}
      <div className="px-4 py-3 border-b border-gray-200 flex justify-between items-center">
        <h3 className="text-md font-medium">{title || config.title || 'Chart'}</h3>
        
        {/* Chart Controls */}
        <div className="flex space-x-2">
          {config.showLegend !== undefined && onConfigChange && (
            <button
              className={`px-2 py-1 text-xs rounded ${
                config.showLegend ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
              }`}
              onClick={() => onConfigChange({ ...config, showLegend: !config.showLegend })}
            >
              Legend
            </button>
          )}
          
          {config.showGridLines !== undefined && onConfigChange && (
            <button
              className={`px-2 py-1 text-xs rounded ${
                config.showGridLines ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
              }`}
              onClick={() => onConfigChange({ ...config, showGridLines: !config.showGridLines })}
            >
              Grid
            </button>
          )}
        </div>
      </div>
      
      {/* Chart Content */}
      <div className="relative" style={{ minHeight: '300px', maxHeight: '600px', height: '400px' }}>
        {/* Loading Overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-white bg-opacity-70 flex items-center justify-center z-10">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div>
          </div>
        )}
        
        {/* Error Overlay */}
        {error && !isLoading && (
          <div className="absolute inset-0 bg-white bg-opacity-70 flex items-center justify-center z-10">
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg max-w-md">
              <h3 className="font-bold text-lg">Error</h3>
              <p>{typeof error === 'string' ? error : String(error)}</p>
            </div>
          </div>
        )}
        
        {/* Chart Content - Ensure all child elements are contained */}
        <div className="absolute inset-0 overflow-hidden">
          {children}
        </div>
      </div>
    </div>
  );
};

export default ChartContainer; 