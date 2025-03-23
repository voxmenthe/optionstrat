'use client';

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { PayoffDiagramProps, PayoffDiagramData, ChartConfiguration } from '../../../types/visualization';
import { ChartContainer } from '../common';
import { formatCurrency } from '../common/utils';
import { Layout, Config, Data, PlotMarker } from 'plotly.js';

// Dynamically import Plotly to avoid SSR issues
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

// Default configuration
const defaultConfig: ChartConfiguration = {
  showLegend: true,
  colorScale: 'profits',
  showGridLines: true,
  showTooltips: true,
  responsiveResize: true,
};

/**
 * PayoffDiagram Component
 * Displays profit/loss at different underlying prices
 */
const PayoffDiagram: React.FC<PayoffDiagramProps> = ({
  data,
  config = defaultConfig,
  isLoading = false,
  error = null,
  onConfigChange,
  className,
}) => {
  // Track chart configuration
  const [chartConfig, setChartConfig] = useState(config);
  
  // Update local config when props change
  useEffect(() => {
    setChartConfig(config);
  }, [config]);
  
  // Handle chart configuration changes
  const handleConfigChange = (newConfig: Partial<typeof config>) => {
    const updatedConfig = { ...chartConfig, ...newConfig };
    setChartConfig(updatedConfig);
    
    if (onConfigChange) {
      onConfigChange(updatedConfig);
    }
  };

  // Log data to debug PUT option issues
  useEffect(() => {
    if (data && data.positions && data.positions[0]?.type === 'put') {
      console.log('PUT option data:', {
        prices: [...data.underlyingPrices.slice(0, 5), '...', ...data.underlyingPrices.slice(-5)],
        values: [...data.payoffValues.slice(0, 5), '...', ...data.payoffValues.slice(-5)],
        maxLoss: data.maxLoss,
        maxProfit: data.maxProfit
      });
    }
  }, [data]);
  
  // Prepare chart data with special handling for PUT options
  const prepareChartData = (data: PayoffDiagramData): Data[] => {
    const traces: Data[] = [];
    
    // Determine if we're dealing with a PUT option
    const isPut = data.positions && data.positions[0]?.type === 'put';
    
    // Add main payoff line - with special color handling for PUT options
    traces.push({
      x: data.underlyingPrices,
      y: data.payoffValues,
      type: 'scatter',
      mode: 'lines',
      name: 'P/L',
      line: {
        color: isPut ? '#ff4d4f' : '#1890ff', // Red for PUT, Blue for CALL
        width: 3,
      },
      hoverinfo: 'x+y',
      hovertemplate: 'Price: $%{x:.2f}<br>P/L: $%{y:.2f}<extra></extra>',
    });
    
    // Add break-even points if available
    if (data.breakEvenPoints && data.breakEvenPoints.length > 0) {
      traces.push({
        x: data.breakEvenPoints,
        y: Array(data.breakEvenPoints.length).fill(0),
        type: 'scatter',
        mode: 'markers',
        name: 'Break-even',
        marker: {
          symbol: 'circle',
          size: 10,
          color: '#faad14',
          line: {
            color: '#ffffff',
            width: 2,
          },
        } as PlotMarker,
        hoverinfo: 'x+text',
        text: data.breakEvenPoints.map(price => `Break-even: $${price.toFixed(2)}`),
        hovertemplate: '%{text}<extra></extra>',
      });
    }
    
    // Add current price marker if available
    if (data.currentPrice) {
      // Find the closest price in our data to the current price
      const closestIndex = data.underlyingPrices.reduce((closest, price, index) => {
        return Math.abs(price - data.currentPrice!) < Math.abs(data.underlyingPrices[closest] - data.currentPrice!)
          ? index
          : closest;
      }, 0);
      
      traces.push({
        x: [data.currentPrice],
        y: [data.payoffValues[closestIndex] || 0],
        type: 'scatter',
        mode: 'markers',
        name: 'Current Price',
        marker: {
          symbol: 'diamond',
          size: 12,
          color: '#52c41a',
          line: {
            color: '#ffffff',
            width: 2,
          },
        } as PlotMarker,
        hoverinfo: 'x+y',
        hovertemplate: 'Current Price: $%{x:.2f}<br>P/L: $%{y:.2f}<extra></extra>',
      });
    }
    
    // Add zero line for reference
    traces.push({
      x: [data.underlyingPrices[0], data.underlyingPrices[data.underlyingPrices.length - 1]],
      y: [0, 0],
      type: 'scatter',
      mode: 'lines',
      name: 'Break-even Line',
      line: {
        color: '#d9d9d9',
        width: 1,
        dash: 'dash',
      },
      hoverinfo: 'none',
      showlegend: false,
    });
    
    return traces;
  };
  
  // Create annotations for max profit/loss
  const createAnnotations = (data: PayoffDiagramData) => {
    const annotations = [];
    
    // Add max profit annotation if available
    if (data.maxProfit && data.maxProfit > 0) {
      const maxProfitIndex = data.payoffValues.indexOf(data.maxProfit);
      if (maxProfitIndex !== -1) {
        annotations.push({
          x: data.underlyingPrices[maxProfitIndex],
          y: data.maxProfit,
          text: `Max Profit: ${formatCurrency(data.maxProfit)}`,
          showarrow: true,
          arrowhead: 2,
          arrowsize: 1,
          arrowwidth: 2,
          arrowcolor: '#52c41a',
          ax: 0,
          ay: -40,
          font: {
            color: '#52c41a',
            size: 12,
          },
          bgcolor: 'rgba(255, 255, 255, 0.8)',
          bordercolor: '#52c41a',
          borderwidth: 1,
          borderpad: 4,
        });
      }
    }
    
    // Add max loss annotation if available
    if (data.maxLoss && data.maxLoss < 0) {
      const maxLossIndex = data.payoffValues.indexOf(data.maxLoss);
      if (maxLossIndex !== -1) {
        annotations.push({
          x: data.underlyingPrices[maxLossIndex],
          y: data.maxLoss,
          text: `Max Loss: ${formatCurrency(data.maxLoss)}`,
          showarrow: true,
          arrowhead: 2,
          arrowsize: 1,
          arrowwidth: 2,
          arrowcolor: '#ff4d4f',
          ax: 0,
          ay: 40,
          font: {
            color: '#ff4d4f',
            size: 12,
          },
          bgcolor: 'rgba(255, 255, 255, 0.8)',
          bordercolor: '#ff4d4f',
          borderwidth: 1,
          borderpad: 4,
        });
      }
    }
    
    return annotations;
  };

  // Calculate optimal axis ranges based on data
  const calculateAxisRanges = (data: PayoffDiagramData) => {
    // Determine if this is a PUT option
    const isPut = data.positions && data.positions[0]?.type === 'put';
    
    // For x-axis: Add proper padding based on option type
    const minPrice = Math.min(...data.underlyingPrices);
    const maxPrice = Math.max(...data.underlyingPrices);
    const priceRange = maxPrice - minPrice;
    
    // For PUT options, we need to ensure we show enough area below strike
    // For CALL options, we need to ensure we show enough area above strike
    const xPadding = priceRange * 0.1; // 10% padding
    
    // For y-axis: Calculate optimal y-axis range with proper padding
    const minValue = Math.min(...data.payoffValues);
    const maxValue = Math.max(...data.payoffValues);
    const valueRange = Math.max(Math.abs(maxValue), Math.abs(minValue));
    const yPadding = valueRange * 0.2; // 20% padding
    
    // Create ranges with special handling for zero crossing
    return {
      xaxis: {
        range: [minPrice - xPadding, maxPrice + xPadding]
      },
      yaxis: {
        // For PUT options, ensure we include sufficient negative space
        range: [
          isPut ? Math.min(-valueRange * 0.1, minValue - yPadding) : Math.min(0, minValue - yPadding),
          Math.max(0, maxValue + yPadding)
        ]
      }
    };
  };
  
  // Create layout configuration with special handling for PUT options
  const createLayout = (data: PayoffDiagramData): Partial<Layout> => {
    const isPut = data.positions && data.positions[0]?.type === 'put';
    const axisRanges = calculateAxisRanges(data);
    
    // Get strike price for marker
    const strikePrice = data.positions && data.positions[0]?.strike;

    // Base layout configuration
    const layout: Partial<Layout> = {
      title: config.title || 'Option Strategy Payoff Diagram',
      autosize: true,
      xaxis: {
        title: 'Underlying Price',
        gridcolor: chartConfig.showGridLines ? '#e9e9e9' : 'transparent',
        zeroline: false,
        tickformat: '$,.2f',
        range: axisRanges.xaxis.range,
        fixedrange: true, // Prevent user zooming
      },
      yaxis: {
        title: 'Profit/Loss',
        gridcolor: chartConfig.showGridLines ? '#e9e9e9' : 'transparent',
        zeroline: true,
        zerolinecolor: '#888888',
        zerolinewidth: 1,
        tickformat: '$,.2f',
        range: axisRanges.yaxis.range,
        fixedrange: true, // Prevent user zooming
      },
      hovermode: 'closest',
      showlegend: chartConfig.showLegend,
      legend: {
        x: 0.01,
        y: 0.99,
        orientation: 'h',
        bgcolor: 'rgba(255, 255, 255, 0.7)',
        bordercolor: '#e8e8e8',
        borderwidth: 1,
        xanchor: 'left',
        yanchor: 'top',
      },
      margin: { l: 60, r: 20, t: 40, b: 60, pad: 0 },
      annotations: createAnnotations(data),
      shapes: [
        // Profit region (green tint above zero line)
        {
          type: 'rect',
          xref: 'paper',
          yref: 'y',
          x0: 0,
          y0: 0,
          x1: 1,
          y1: axisRanges.yaxis.range[1],
          fillcolor: 'rgba(82, 196, 26, 0.05)',
          line: { width: 0 },
        },
        // Loss region (red tint below zero line)
        {
          type: 'rect',
          xref: 'paper',
          yref: 'y',
          x0: 0,
          y0: axisRanges.yaxis.range[0],
          x1: 1,
          y1: 0,
          fillcolor: 'rgba(255, 77, 79, 0.05)',
          line: { width: 0 },
        }
      ],
      plot_bgcolor: 'white',
      paper_bgcolor: 'white',
    };

    return layout;
  };
  
  // Plotly config - disable most interactivity for simpler, more reliable rendering
  const plotlyConfig: Partial<Config> = {
    displayModeBar: false, // Hide the mode bar completely
    responsive: true,
    staticPlot: true, // Make the plot static (no interactions)
  };
  
  // If we're still loading or have an error, return appropriate UI
  if (isLoading) {
    return (
      <ChartContainer 
        config={chartConfig}
        title={chartConfig.title}
        isLoading={true}
        className={className}
      >
        <div className="flex items-center justify-center h-full">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
      </ChartContainer>
    );
  }
  
  if (error) {
    return (
      <ChartContainer 
        config={chartConfig}
        title={chartConfig.title}
        error={error}
        className={className}
      >
        <div className="flex items-center justify-center h-full">
          <div className="text-red-500">Error: {error}</div>
        </div>
      </ChartContainer>
    );
  }
  
  return (
    <ChartContainer
      config={chartConfig}
      title={chartConfig.title}
      isLoading={isLoading}
      error={error}
      onConfigChange={handleConfigChange}
      className={className}
    >
      {/* New implementation with multiple wrapper divs to contain all visual elements */}
      <div className="w-full h-full relative">
        <div className="absolute inset-0 overflow-hidden">
          <div 
            className="w-full h-full" 
            style={{ 
              // Use isolation to prevent visual elements from escaping
              isolation: 'isolate', 
              // Use CSS containment for better performance
              contain: 'paint layout'  
            }}
          >
            <Plot
              data={prepareChartData(data)}
              layout={createLayout(data)}
              config={plotlyConfig}
              style={{
                width: '100%',
                height: '100%',
                // Ensure nothing renders outside bounds
                overflow: 'hidden'
              }}
              useResizeHandler={true}
            />
          </div>
        </div>
      </div>
    </ChartContainer>
  );
};

export default PayoffDiagram; 