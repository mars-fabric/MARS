// types/cost.ts

export interface CostSummary {
  total_cost: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  model_breakdown: ModelCost[];
  agent_breakdown: AgentCost[];
  step_breakdown: StepCost[];
}

export interface ModelCost {
  model: string;
  cost: number;
  tokens: number;
  input_tokens: number;
  output_tokens: number;
  call_count: number;
}

export interface AgentCost {
  agent: string;
  model: string;
  cost: number;
  tokens: number;
  input_tokens: number;
  output_tokens: number;
  call_count: number;
}

export interface StepCost {
  step_id: string;
  step_number: number;
  description: string;
  cost: number;
  tokens: number;
}

export interface CostTimeSeries {
  timestamp: string;
  cumulative_cost: number;
  step_cost: number;
  step_number?: number;
}

export interface BudgetConfig {
  warning_threshold: number;
  limit_threshold: number;
  current_usage: number;
}
