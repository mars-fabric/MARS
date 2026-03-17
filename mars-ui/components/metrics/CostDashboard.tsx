// components/metrics/CostDashboard.tsx

'use client';

import { CostSummaryCards } from './CostSummaryCards';
import { CostBreakdown } from './CostBreakdown';
import { CostChart } from './CostChart';
import { CostSummary, CostTimeSeries, BudgetConfig } from '@/types/cost';

interface CostDashboardProps {
  summary: CostSummary;
  timeSeries: CostTimeSeries[];
  budget?: BudgetConfig;
  previousRunCost?: number;
}

export function CostDashboard({
  summary,
  timeSeries,
  budget,
  previousRunCost,
}: CostDashboardProps) {
  return (
    <div className="space-y-4 p-5 h-full overflow-y-auto">
      {/* Budget Warning */}
      {budget && budget.current_usage > budget.warning_threshold && (
        <div className={`px-4 py-3 rounded-lg border text-sm ${
          budget.current_usage > budget.limit_threshold
            ? 'bg-red-500/10 border-red-500/30 text-red-400'
            : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
        }`}>
          <span className="font-medium">
            {budget.current_usage > budget.limit_threshold
              ? 'Budget limit exceeded!'
              : 'Approaching budget limit'}
          </span>
          <span className="ml-2 text-xs opacity-70">
            ${budget.current_usage.toFixed(4)} / ${budget.limit_threshold.toFixed(2)}
          </span>
        </div>
      )}

      {/* Summary Header */}
      <CostSummaryCards
        totalCost={summary.total_cost}
        totalTokens={summary.total_tokens}
        inputTokens={summary.input_tokens}
        outputTokens={summary.output_tokens}
        previousCost={previousRunCost}
        budgetLimit={budget?.limit_threshold}
      />

      {/* Breakdown (primary) */}
      <CostBreakdown
        modelBreakdown={summary.model_breakdown}
        agentBreakdown={summary.agent_breakdown}
        stepBreakdown={summary.step_breakdown}
        totalCost={summary.total_cost}
      />

      {/* Chart (only when there's time series data) */}
      {timeSeries.length > 1 && (
        <CostChart data={timeSeries} height={160} />
      )}
    </div>
  );
}
