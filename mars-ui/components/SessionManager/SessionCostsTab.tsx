"use client";

import { Loader2, AlertCircle } from "lucide-react";
import { CostDashboard } from "@/components/metrics";
import { useCostData } from "@/hooks/useCostData";

interface SessionCostsTabProps {
  runId: string;
}

export function SessionCostsTab({ runId }: SessionCostsTabProps) {
  const { costSummary, loading, error } = useCostData(runId);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span>Loading cost data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <AlertCircle className="w-10 h-10 mx-auto mb-3 text-gray-500" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  if (!costSummary) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <p className="text-sm">No cost data available for this run</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden bg-gray-900">
      <CostDashboard summary={costSummary} timeSeries={[]} />
    </div>
  );
}
