'use client';

import dynamic from 'next/dynamic';
import type { Config, Data, Layout, Shape } from 'plotly.js';
import type { IndicatorDashboardComputeResponse } from '../../lib/api/securityScanApi';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

function signalColor(signalType: string): string {
  const normalized = signalType.toLowerCase();
  if (
    normalized.includes('down') ||
    normalized.includes('below') ||
    normalized.includes('low')
  ) {
    return '#dc2626';
  }
  if (
    normalized.includes('up') ||
    normalized.includes('above') ||
    normalized.includes('high')
  ) {
    return '#16a34a';
  }
  return '#2563eb';
}

function signalSymbol(signalType: string): string {
  const normalized = signalType.toLowerCase();
  if (
    normalized.includes('down') ||
    normalized.includes('below') ||
    normalized.includes('low')
  ) {
    return 'triangle-down';
  }
  if (
    normalized.includes('up') ||
    normalized.includes('above') ||
    normalized.includes('high')
  ) {
    return 'triangle-up';
  }
  return 'circle';
}

function buildTraceValueIndex(
  result: IndicatorDashboardComputeResponse
): Map<string, Map<string, number>> {
  const traceValues = new Map<string, Map<string, number>>();
  for (const panel of result.indicator.panels) {
    for (const trace of panel.traces) {
      traceValues.set(
        trace.key,
        new Map(trace.points.map((point) => [point.date, point.value]))
      );
    }
  }
  return traceValues;
}

function buildPlotData(result: IndicatorDashboardComputeResponse): Data[] {
  const data: Data[] = [
    {
      type: 'scatter',
      mode: 'lines',
      name: result.price.label,
      x: result.price.points.map((point) => point.date),
      y: result.price.points.map((point) => point.value),
      line: { color: '#111827', width: 2 },
      hovertemplate: '%{x}<br>Close: %{y:.2f}<extra></extra>',
      xaxis: 'x',
      yaxis: 'y',
    },
  ];

  for (const panel of result.indicator.panels) {
    for (const trace of panel.traces) {
      data.push({
        type: 'scatter',
        mode: 'lines',
        name: trace.label,
        x: trace.points.map((point) => point.date),
        y: trace.points.map((point) => point.value),
        line: { color: trace.color || '#0f766e', width: 2 },
        hovertemplate: `%{x}<br>${trace.label}: %{y:.4f}<extra></extra>`,
        xaxis: 'x2',
        yaxis: 'y2',
      });
    }
  }

  const traceValueIndex = buildTraceValueIndex(result);
  const signalsByType = new Map<string, typeof result.signals>();
  for (const signal of result.signals) {
    signalsByType.set(signal.type, [
      ...(signalsByType.get(signal.type) || []),
      signal,
    ]);
  }

  for (const [signalType, signals] of Array.from(signalsByType.entries())) {
    const markerX: string[] = [];
    const markerY: number[] = [];
    const markerText: string[] = [];
    const legendLabel = signals[0]?.label || signalType;
    for (const signal of signals) {
      const yValue = traceValueIndex.get(signal.target_trace)?.get(signal.date);
      if (yValue === undefined) {
        continue;
      }
      markerX.push(signal.date);
      markerY.push(yValue);
      markerText.push(`${signal.label}<br>${JSON.stringify(signal.metadata)}`);
    }
    if (!markerX.length) {
      continue;
    }
    data.push({
      type: 'scatter',
      mode: 'markers',
      name: legendLabel,
      x: markerX,
      y: markerY,
      text: markerText,
      marker: {
        color: signalColor(signalType),
        size: 10,
        symbol: signalSymbol(signalType),
        line: { color: '#ffffff', width: 1 },
      },
      hovertemplate: '%{text}<extra></extra>',
      xaxis: 'x2',
      yaxis: 'y2',
    });
  }

  return data;
}

function buildPlotLayout(result: IndicatorDashboardComputeResponse): Partial<Layout> {
  const shapes: Partial<Shape>[] = [];
  const signalDates = new Set(result.signals.map((signal) => signal.date));
  for (const signalDate of Array.from(signalDates)) {
    shapes.push({
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: signalDate,
      x1: signalDate,
      y0: 0,
      y1: 1,
      line: { color: 'rgba(37, 99, 235, 0.18)', width: 1, dash: 'dot' },
    });
  }

  const primaryPanel = result.indicator.panels[0];
  for (const referenceLine of primaryPanel?.reference_lines || []) {
    shapes.push({
      type: 'line',
      xref: 'paper',
      yref: 'y2',
      x0: 0,
      x1: 1,
      y0: referenceLine,
      y1: referenceLine,
      line: { color: 'rgba(17, 24, 39, 0.35)', width: 1, dash: 'dash' },
    });
  }

  return {
    autosize: true,
    height: 680,
    margin: { l: 64, r: 28, t: 24, b: 72 },
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    hovermode: 'x unified',
    showlegend: true,
    legend: { orientation: 'h', x: 0, y: -0.12 },
    xaxis: {
      domain: [0, 1],
      anchor: 'y',
      matches: 'x2',
      showticklabels: false,
      showgrid: false,
    },
    yaxis: {
      domain: [0.58, 1],
      title: { text: 'Close' },
      gridcolor: '#e5e7eb',
      zeroline: false,
    },
    xaxis2: {
      domain: [0, 1],
      anchor: 'y2',
      title: { text: 'Date' },
      gridcolor: '#f3f4f6',
    },
    yaxis2: {
      domain: [0, 0.44],
      title: { text: primaryPanel?.label || 'Indicator' },
      gridcolor: '#e5e7eb',
      zeroline: false,
    },
    shapes,
  };
}

const plotConfig: Partial<Config> = {
  responsive: true,
  displaylogo: false,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
};

interface IndicatorDashboardChartProps {
  result: IndicatorDashboardComputeResponse;
}

export function IndicatorDashboardChart({ result }: IndicatorDashboardChartProps) {
  return (
    <Plot
      data={buildPlotData(result)}
      layout={buildPlotLayout(result)}
      config={plotConfig}
      style={{ width: '100%', height: '680px' }}
      useResizeHandler
    />
  );
}
