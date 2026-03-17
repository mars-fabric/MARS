// types/branching.ts

export interface Branch {
  branch_id: string;
  run_id: string;
  parent_branch_id?: string;
  branch_point_step_id?: string;
  hypothesis?: string;
  name: string;
  created_at: string;
  status: string;
  is_main: boolean;
  children?: Branch[];
}

export interface BranchComparison {
  branch_a: BranchSummary;
  branch_b: BranchSummary;
  differences: BranchDifference[];
  files_comparison?: FileComparison[];
}

export interface BranchSummary {
  branch_id: string;
  name: string;
  hypothesis?: string;
  total_steps: number;
  completed_steps: number;
  failed_steps: number;
  total_cost: number;
  total_time_seconds: number;
  final_status: string;
}

export interface BranchDifference {
  step_number: number;
  step_id_a?: string;
  step_id_b?: string;
  description_a?: string;
  description_b?: string;
  status_a?: string;
  status_b?: string;
  output_differs: boolean;
}

export interface FileComparison {
  file_path: string;
  in_branch_a: boolean;
  in_branch_b: boolean;
  differs: boolean;
  diff_preview?: string;
}

export interface ResumableNode {
  node_id: string;  // DAG node ID (e.g., "step_1", "planning")
  order_index: number;
  node_type: string;
  agent?: string;
  status: string;
  has_checkpoint: boolean;
  can_resume: boolean;
}
