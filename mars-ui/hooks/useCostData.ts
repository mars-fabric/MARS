import { useState, useEffect, useCallback } from 'react';
import { CostSummary } from '@/types/cost';

interface DatabaseCostData {
  run_id: string;
  resolved_run_id: string;
  total_cost_usd: number;
  total_tokens: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  record_count: number;
  model_breakdown: Array<{
    model: string;
    cost: number;
    tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    call_count: number;
  }>;
  agent_breakdown: Array<{
    agent: string;
    model: string;
    cost: number;
    tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    call_count: number;
  }>;
  step_breakdown: Array<{
    step_id: string;
    cost: number;
    tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
  }>;
}

/**
 * Hook to fetch cost data from database API
 * This provides persistent cost data that survives page refreshes
 */
export function useCostData(runId: string | null) {
  const [costData, setCostData] = useState<DatabaseCostData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCostData = useCallback(async () => {
    if (!runId) {
      setCostData(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/runs/${runId}/costs`);
      
      if (!response.ok) {
        if (response.status === 404) {
          // No cost data yet - this is fine for new runs
          setCostData(null);
          return;
        }
        throw new Error(`Failed to fetch cost data: ${response.status}`);
      }

      const data = await response.json();
      setCostData(data);
    } catch (err) {
      console.error('Error fetching cost data:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  // Fetch on mount and when runId changes
  useEffect(() => {
    fetchCostData();
  }, [fetchCostData]);

  // Convert database format to CostSummary format for UI components
  const costSummary: CostSummary | null = costData ? {
    total_cost: costData.total_cost_usd,
    total_tokens: costData.total_tokens,
    input_tokens: costData.total_prompt_tokens,
    output_tokens: costData.total_completion_tokens,
    model_breakdown: costData.model_breakdown.map(m => ({
      model: m.model,
      cost: m.cost,
      tokens: m.tokens,
      input_tokens: m.prompt_tokens,
      output_tokens: m.completion_tokens,
      call_count: m.call_count
    })),
    agent_breakdown: (costData.agent_breakdown || []).map(a => ({
      agent: a.agent,
      model: a.model,
      cost: a.cost,
      tokens: a.tokens,
      input_tokens: a.prompt_tokens,
      output_tokens: a.completion_tokens,
      call_count: a.call_count
    })),
    step_breakdown: costData.step_breakdown.map(s => ({
      step_id: s.step_id,
      step_number: parseInt(s.step_id.replace(/\D/g, '')) || 0,
      description: s.step_id,
      cost: s.cost,
      tokens: s.tokens
    }))
  } : null;

  return {
    costData,
    costSummary,
    loading,
    error,
    refetch: fetchCostData
  };
}
