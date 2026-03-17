// components/metrics/CostSummaryCards.tsx

'use client';

import { DollarSign, ArrowUp, ArrowDown } from 'lucide-react';

interface CostSummaryCardsProps {
  totalCost: number;
  totalTokens: number;
  inputTokens: number;
  outputTokens: number;
  previousCost?: number;
  budgetLimit?: number;
}

export function CostSummaryCards({
  totalCost,
  totalTokens,
  inputTokens,
  outputTokens,
  previousCost,
}: CostSummaryCardsProps) {
  const costChange = previousCost
    ? ((totalCost - previousCost) / previousCost) * 100
    : null;
  const costPerKToken = totalTokens > 0 ? (totalCost / totalTokens) * 1000 : 0;

  return (
    <div className="flex items-stretch gap-4">
      {/* Total Cost - Hero */}
      <div className="flex-1 bg-gradient-to-br from-blue-500/15 to-blue-600/5 rounded-xl border border-blue-500/20 p-5">
        <div className="flex items-center gap-2 mb-1">
          <DollarSign className="w-4 h-4 text-blue-400" />
          <span className="text-xs font-medium text-blue-300/70 uppercase tracking-wider">Total Cost</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-white tabular-nums">${totalCost.toFixed(4)}</span>
          {costChange !== null && costChange !== 0 && (
            <span className={`flex items-center text-xs font-medium ${
              costChange > 0 ? 'text-red-400' : 'text-emerald-400'
            }`}>
              {costChange > 0 ? <ArrowUp className="w-3 h-3 mr-0.5" /> : <ArrowDown className="w-3 h-3 mr-0.5" />}
              {Math.abs(costChange).toFixed(1)}%
            </span>
          )}
        </div>
        <span className="text-xs text-gray-500 mt-1">${costPerKToken.toFixed(4)} / 1K tokens</span>
      </div>

      {/* Token Summary */}
      <div className="flex-1 bg-gray-800/40 rounded-xl border border-gray-700/50 p-5">
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Tokens</span>
        <div className="text-2xl font-bold text-white mt-1 tabular-nums">
          {totalTokens.toLocaleString()}
        </div>
        <div className="flex items-center gap-3 mt-2">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-cyan-400" />
            <span className="text-xs text-gray-400">
              <span className="text-gray-300 font-medium tabular-nums">{inputTokens.toLocaleString()}</span> in
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-orange-400" />
            <span className="text-xs text-gray-400">
              <span className="text-gray-300 font-medium tabular-nums">{outputTokens.toLocaleString()}</span> out
            </span>
          </div>
        </div>
        {/* Token ratio bar */}
        {totalTokens > 0 && (
          <div className="flex h-1.5 mt-2 rounded-full overflow-hidden bg-gray-700/50">
            <div
              className="bg-cyan-400/70 rounded-l-full"
              style={{ width: `${(inputTokens / totalTokens) * 100}%` }}
            />
            <div
              className="bg-orange-400/70 rounded-r-full"
              style={{ width: `${(outputTokens / totalTokens) * 100}%` }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
