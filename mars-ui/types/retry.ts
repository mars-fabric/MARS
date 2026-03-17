// types/retry.ts

export type ErrorCategory =
  | 'NETWORK'
  | 'RATE_LIMIT'
  | 'API_ERROR'
  | 'VALIDATION'
  | 'TIMEOUT'
  | 'RESOURCE'
  | 'UNKNOWN';

export interface RetryInfo {
  step_id: string;
  step_number: number;
  attempt_number: number;
  max_attempts: number;
  error_category: ErrorCategory;
  error_pattern?: string;
  error_message: string;
  traceback?: string;
  success_probability?: number;
  strategy: string;
  suggestions: string[];
  has_user_feedback: boolean;
  backoff_seconds?: number;
  next_attempt_at?: string;
}

export interface RetryStatus {
  is_retrying: boolean;
  current_retry: RetryInfo | null;
  history: RetryHistoryItem[];
}

export interface RetryHistoryItem {
  attempt_number: number;
  error_message: string;
  timestamp: string;
  succeeded: boolean;
}
