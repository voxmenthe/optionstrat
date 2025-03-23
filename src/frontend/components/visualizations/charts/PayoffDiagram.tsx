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
  
  // Prepare chart data
  const prepareChartData = (data: PayoffDiagramData): Data[] => {
    const traces: Data[] = [];
    
    // Add main payoff line
    traces.push({
      x: data.underlyingPrices,
      y: data.payoffValues,
      type: 'scatter',
      mode: 'lines',
      name: 'P/L',
      line: {
        color: data.payoffValues[Math.floor(data.payoffValues.length / 2)] >= 0 ? '#1890ff' : '#ff4d4f',
        width: 3,
      },
      hoverinfo: 'x+y',
      hovertemplate: 'Price: %{x}<br>P/L: $%{y:.2f}<extra></extra>',
    });
    
    // Add break-even points
    if (data.breakEvenPoints.length > 0) {
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
      traces.push({
        x: [data.currentPrice],
        y: [
          data.payoffValues[
            data.underlyingPrices.findIndex(price => 
              Math.abs(price - data.currentPrice!) < 0.001
            ) || 0
          ] || 0
        ],
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
          text: `Max Profit: $${data.maxProfit.toFixed(2)}`,
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
          text: `Max Loss: $${data.maxLoss.toFixed(2)}`,
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
  
  // Create layout configuration
  const layout: Partial<Layout> = {
    title: config.title || 'Option Strategy Payoff Diagram',
    xaxis: {
      title: 'Underlying Price',
      gridcolor: chartConfig.showGridLines ? '#e9e9e9' : 'transparent',
      zeroline: false,
      tickformat: '$,.2f',
      autorange: true,
    },
    yaxis: {
      title: 'Profit/Loss',
      gridcolor: chartConfig.showGridLines ? '#e9e9e9' : 'transparent',
      zeroline: false,
      tickformat: '$,.2f',
      autorange: true,
    },
    hovermode: 'closest',
    showlegend: chartConfig.showLegend,
    legend: {
      x: 0,
      y: 1,
      orientation: 'h',
      bgcolor: 'rgba(255, 255, 255, 0.5)',
    },
    margin: chartConfig.margin ? 
      { l: chartConfig.margin.left, r: chartConfig.margin.right, t: chartConfig.margin.top, b: chartConfig.margin.bottom } : 
      { l: 50, r: 50, t: 50, b: 50 },
    annotations: createAnnotations(data),
    // Divide the chart into profit (green) and loss (red) regions with a light fill
    shapes: [
      // Profit region
      {
        type: 'rect',
        xref: 'paper',
        yref: 'y',
        x0: 0,
        y0: 0,
        x1: 1,
        y1: data.maxProfit || 1000000, // Use a large value to ensure it covers the chart
        fillcolor: 'rgba(82, 196, 26, 0.05)',
        line: {
          width: 0,
        },
      },
      // Loss region
      {
        type: 'rect',
        xref: 'paper',
        yref: 'y',
        x0: 0,
        y0: data.maxLoss || -1000000, // Use a large negative value to ensure it covers the chart
        x1: 1,
        y1: 0,
        fillcolor: 'rgba(255, 77, 79, 0.05)',
        line: {
          width: 0,
        },
      },
    ],
  };
  
  // Plotly config options
  const plotlyConfig: Partial<Config> = {
    displayModeBar: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'] as any[],
    responsive: true,
  };
  
  return (
    <ChartContainer
      config={chartConfig}
      title={chartConfig.title}
      isLoading={isLoading}
      error={error}
      onConfigChange={handleConfigChange}
      className={className}
    >
      <Plot
        data={prepareChartData(data)}
        layout={layout}
        config={plotlyConfig}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler={true}
      />
    </ChartContainer>
  );
};

export default PayoffDiagram; 