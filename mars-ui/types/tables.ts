// types/tables.ts

export interface Column<T> {
  id: string;
  header: string;
  accessor: keyof T | ((row: T) => React.ReactNode);
  sortable?: boolean;
  width?: string;
  align?: 'left' | 'center' | 'right';
}

export interface TableState {
  page: number;
  pageSize: number;
  sortColumn: string | null;
  sortDirection: 'asc' | 'desc';
  searchQuery: string;
  filters: Record<string, any>;
}

export interface PaginationInfo {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export interface SessionRow {
  id: string;
  name: string;
  created_at: string;
  last_active_at?: string;
  status: string;
  workflow_count: number;
  total_cost: number;
}

export interface WorkflowRow {
  id: string;
  session_id: string;
  task_description: string;
  status: string;
  agent: string;
  model: string;
  started_at?: string;
  completed_at?: string;
  total_cost: number;
  step_count: number;
}

export interface StepRow {
  id: string;
  run_id: string;
  step_number: number;
  description: string;
  agent: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  cost: number;
  retry_count: number;
}
