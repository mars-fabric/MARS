// components/metrics/CostChart.tsx

'use client';

import { useMemo } from 'react';
import { CostTimeSeries } from '@/types/cost';

interface CostChartProps {
  data: CostTimeSeries[];
  height?: number;
}

export function CostChart({ data, height = 200 }: CostChartProps) {
  const chartData = useMemo(() => {
    if (data.length === 0) return null;

    const maxCost = Math.max(...data.map((d) => d.cumulative_cost));
    const padding = 40;
    const chartWidth = 100; // percentage

    const points = data.map((d, i) => {
      const x = (i / (data.length - 1 || 1)) * (chartWidth - padding * 2 / 100) + padding / 100;
      const y = 100 - (d.cumulative_cost / maxCost) * 80 - 10;
      return { x: x * 100, y, data: d };
    });

    const pathD = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x}% ${p.y}%`)
      .join(' ');

    const areaD = `${pathD} L ${points[points.length - 1]?.x || 0}% 90% L ${points[0]?.x || 0}% 90% Z`;

    return { points, pathD, areaD, maxCost };
  }, [data]);

  if (!chartData || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-gray-800/50 rounded-xl"
        style={{ height }}
      >
        <span className="text-gray-400">No cost data available</span>
      </div>
    );
  }

  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-700 p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-4">Cost Over Time</h3>
      <div style={{ height }} className="relative">
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="w-full h-full"
        >
          {/* Grid lines */}
          {[0, 25, 50, 75, 100].map((y) => (
            <line
              key={y}
              x1="10%"
              y1={`${10 + y * 0.8}%`}
              x2="98%"
              y2={`${10 + y * 0.8}%`}
              stroke="#374151"
              strokeWidth="0.2"
            />
          ))}

          {/* Area fill */}
          <path
            d={chartData.areaD}
            fill="url(#costGradient)"
            opacity="0.3"
          />

          {/* Line */}
          <path
            d={chartData.pathD}
            fill="none"
            stroke="#3B82F6"
            strokeWidth="0.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Points */}
          {chartData.points.map((p, i) => (
            <circle
              key={i}
              cx={`${p.x}%`}
              cy={`${p.y}%`}
              r="1"
              fill="#3B82F6"
              className="hover:r-2 transition-all cursor-pointer"
            />
          ))}

          {/* Gradient definition */}
          <defs>
            <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
            </linearGradient>
          </defs>
        </svg>

        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 h-full flex flex-col justify-between text-xs text-gray-500">
          <span>${chartData.maxCost.toFixed(3)}</span>
          <span>${(chartData.maxCost / 2).toFixed(3)}</span>
          <span>$0</span>
        </div>
      </div>
    </div>
  );
}
