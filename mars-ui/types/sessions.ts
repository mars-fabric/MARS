/**
 * TypeScript types for session detail views.
 */

export interface SessionDetail {
  session_id: string;
  name: string;
  mode: string;
  status: string;
  current_phase: string | null;
  current_step: number | null;
  created_at: string | null;
  updated_at: string | null;
  conversation_history: ConversationMessage[];
  context_variables: Record<string, any>;
  plan_data: any | null;
  config: Record<string, any>;
}

export interface ConversationMessage {
  role: string;
  content: string;
  agent?: string;
  timestamp?: string;
}

export interface SessionRun {
  id: string;
  mode: string;
  agent: string;
  model: string;
  status: string;
  task_description: string | null;
  started_at: string | null;
  completed_at: string | null;
  is_branch: boolean;
  meta: Record<string, any> | null;
}

export type SessionDetailTab =
  | "overview"
  | "results"
  | "plan"
  | "dag"
  | "console"
  | "events"
  | "costs"
  | "files"
  | "config";
