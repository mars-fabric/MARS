// types/dag.ts

import { Node, Edge, NodeProps } from '@xyflow/react';

export type NodeStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'paused'
  | 'waiting_approval'
  | 'retrying'
  | 'skipped';

export type NodeType =
  | 'planning'
  | 'control'
  | 'agent'
  | 'approval'
  | 'parallel'
  | 'terminator';

export interface GeneratedPlan {
  sub_tasks?: Array<{
    sub_task?: string;
    sub_task_agent?: string;
    bullet_points?: string[];
  }>;
  steps?: Array<{
    step_number?: number;
    description?: string;
    title?: string;
  }>;
  step_count?: number;
  mode?: string;
  breakdown?: string;
}

export interface DAGNodeData {
  id: string;
  label: string;
  type: NodeType;
  status: NodeStatus;
  agent?: string;
  stepNumber?: number;
  description?: string;  // Full description including instructions
  task?: string;  // Primary task description
  insights?: string;  // Detailed instructions as text (bullet points joined)
  goal?: string;  // Step goal/objective
  summary?: string;  // Human-readable summary of what was accomplished
  bulletPoints?: string[];  // Raw bullet points array for structured display
  startedAt?: string;
  completedAt?: string;
  error?: string;
  retryInfo?: {
    attemptNumber: number;
    maxAttempts: number;
  };
  runId?: string;  // Run ID for API calls
  run_id?: string;  // Alternative naming convention
  generated_plan?: GeneratedPlan;  // For planning nodes - the generated plan data
  // Index signature to satisfy Record<string, unknown> compatibility
  [key: string]: unknown;
}

export type DAGNode = Node<DAGNodeData, 'dagNode'>;
export type DAGEdge = Edge;

export interface DAGState {
  nodes: DAGNode[];
  edges: DAGEdge[];
  selectedNodeId: string | null;
  layout: 'horizontal' | 'vertical';
}

export interface DAGLayoutOptions {
  direction: 'TB' | 'LR';  // Top-Bottom or Left-Right
  nodeSpacing: number;
  levelSpacing: number;
}

// Status colors for nodes
export const statusColors: Record<NodeStatus, string> = {
  pending: '#6B7280',      // gray-500
  running: '#3B82F6',      // blue-500
  completed: '#10B981',    // green-500
  failed: '#EF4444',       // red-500
  paused: '#F59E0B',       // yellow-500
  waiting_approval: '#8B5CF6', // purple-500
  retrying: '#F97316',     // orange-500
  skipped: '#9CA3AF',      // gray-400
};

// Node type icons (Lucide icon names)
export const nodeTypeIcons: Record<NodeType, string> = {
  planning: 'ClipboardList',
  control: 'Settings2',
  agent: 'Bot',
  approval: 'UserCheck',
  parallel: 'GitBranch',
  terminator: 'CheckCircle',
};
