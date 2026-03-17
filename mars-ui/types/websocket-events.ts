// types/websocket-events.ts

export enum WebSocketEventType {
  // Connection events
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  RECONNECTED = 'reconnected',

  // Workflow lifecycle events
  WORKFLOW_STARTED = 'workflow_started',
  WORKFLOW_STATE_CHANGED = 'workflow_state_changed',
  WORKFLOW_PAUSED = 'workflow_paused',
  WORKFLOW_RESUMED = 'workflow_resumed',
  WORKFLOW_COMPLETED = 'workflow_completed',
  WORKFLOW_FAILED = 'workflow_failed',

  // Step execution events
  STEP_STARTED = 'step_started',
  STEP_PROGRESS = 'step_progress',
  STEP_COMPLETED = 'step_completed',
  STEP_FAILED = 'step_failed',

  // Retry events
  STEP_RETRY_STARTED = 'step_retry_started',
  STEP_RETRY_BACKOFF = 'step_retry_backoff',
  STEP_RETRY_SUCCEEDED = 'step_retry_succeeded',
  STEP_RETRY_EXHAUSTED = 'step_retry_exhausted',

  // DAG events
  DAG_CREATED = 'dag_created',
  DAG_UPDATED = 'dag_updated',
  DAG_NODE_STATUS_CHANGED = 'dag_node_status_changed',

  // Branch events
  BRANCH_CREATED = 'branch_created',
  BRANCH_EXECUTING = 'branch_executing',
  BRANCH_COMPLETED = 'branch_completed',
  BRANCH_FAILED = 'branch_failed',

  // Agent events
  AGENT_MESSAGE = 'agent_message',
  AGENT_THINKING = 'agent_thinking',
  AGENT_TOOL_CALL = 'agent_tool_call',
  CODE_EXECUTION = 'code_execution',
  TOOL_CALL = 'tool_call',

  // Approval events
  APPROVAL_REQUESTED = 'approval_requested',
  APPROVAL_RECEIVED = 'approval_received',

  // Cost and metrics
  COST_UPDATE = 'cost_update',
  METRIC_UPDATE = 'metric_update',

  // File events
  FILE_CREATED = 'file_created',
  FILE_UPDATED = 'file_updated',
  FILES_UPDATED = 'files_updated',  // Batch file update notification

  // Error events
  ERROR_OCCURRED = 'error_occurred',

  // Heartbeat
  HEARTBEAT = 'heartbeat',
  PONG = 'pong',

  // Legacy (backward compatibility)
  OUTPUT = 'output',
  STATUS = 'status',
  RESULT = 'result',
  COMPLETE = 'complete',
}

export interface WebSocketEvent {
  event_type: WebSocketEventType | string;
  timestamp: string;
  run_id?: string;
  session_id?: string;
  data: Record<string, any>;
}

// Specific event data types
export interface WorkflowStartedData {
  run_id: string;
  task_description: string;
  agent: string;
  model: string;
  work_dir?: string;
}

export interface WorkflowStateChangedData {
  status: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface StepStartedData {
  step_id: string;
  step_number: number;
  step_description: string;
  agent: string;
}

export interface StepProgressData {
  step_id: string;
  step_number: number;
  progress_percentage: number;
  message: string;
}

export interface StepCompletedData {
  step_id: string;
  step_number: number;
  result?: string;
  output?: string;
}

export interface StepFailedData {
  step_id: string;
  step_number: number;
  error: string;
  traceback?: string;
}

export interface StepRetryStartedData {
  step_id: string;
  step_number: number;
  attempt_number: number;
  max_attempts: number;
  error_category: string;
  error_pattern?: string;
  success_probability?: number;
  strategy: string;
  suggestions: string[];
  has_user_feedback: boolean;
}

export interface DAGCreatedData {
  run_id: string;
  nodes: DAGNodeData[];
  edges: DAGEdgeData[];
  levels: number;
}

export interface DAGNodeData {
  id: string;
  label: string;
  type: string;
  status: string;
  agent?: string;
  step_number?: number;
  metadata?: Record<string, any>;
}

export interface DAGEdgeData {
  source: string;
  target: string;
  type?: string;
}

export interface DAGNodeStatusChangedData {
  node_id: string;
  old_status: string;
  new_status: string;
  error?: string;
}

export interface AgentMessageData {
  agent: string;
  message: string;
  role: string;
}

export interface ApprovalRequestedData {
  approval_id: string;
  step_id: string;
  action: string;
  description: string;
  message?: string;  // Alternative to description
  context: Record<string, any>;
  options?: string[];
  checkpoint_type?: string;
}

export interface ApprovalReceivedData {
  approval_id: string;
  approved: boolean;
  feedback?: string;
}

export interface CostUpdateData {
  run_id: string;
  agent?: string;
  step_id?: string;
  model: string;
  tokens: number;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd: number;
  total_cost_usd: number;
}

export interface ErrorOccurredData {
  error_type: string;
  message: string;
  step_id?: string;
  traceback?: string;
}

export interface CodeExecutionData {
  run_id: string;
  agent: string;
  code: string;
  language: string;
  result?: string;
}

export interface ToolCallData {
  run_id: string;
  agent: string;
  tool_name: string;
  arguments: Record<string, any>;
  result?: string;
}

export interface FilesUpdatedData {
  run_id: string;
  node_id?: string;
  step_id?: string;
  files_tracked: number;
}

// Branch event data types
export interface BranchCreatedData {
  branch_run_id: string;
  parent_run_id: string;
  branch_name: string;
  hypothesis?: string;
  new_instructions?: string;
  branched_from_step: string;
}

export interface BranchExecutingData {
  branch_run_id: string;
  parent_run_id: string;
  branch_name: string;
  augmented_task?: string;
}

export interface BranchCompletedData {
  branch_run_id: string;
  parent_run_id: string;
  branch_name: string;
  result?: Record<string, any>;
}

export interface BranchFailedData {
  branch_run_id: string;
  parent_run_id: string;
  branch_name: string;
  error: string;
}
