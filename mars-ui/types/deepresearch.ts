/**
 * TypeScript types for the Deepresearch Research Paper wizard.
 */

export type DeepresearchStageStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface DeepresearchStage {
  stage_number: number
  stage_name: string
  status: DeepresearchStageStatus
  started_at?: string | null
  completed_at?: string | null
  error?: string | null
}

export interface DeepresearchTaskState {
  task_id: string
  task: string
  status: string
  work_dir?: string | null
  created_at?: string | null
  stages: DeepresearchStage[]
  current_stage?: number | null
  progress_percent: number
  total_cost_usd?: number | null
}

export interface DeepresearchStageContent {
  stage_number: number
  stage_name: string
  status: string
  content?: string | null
  shared_state?: Record<string, unknown> | null
  output_files?: string[] | null
}

export interface DeepresearchCreateResponse {
  task_id: string
  work_dir: string
  stages: DeepresearchStage[]
}

export interface DeepresearchRefineResponse {
  refined_content: string
  message: string
}

export interface RefinementMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface UploadedFile {
  name: string
  size: number
  path?: string
  status: 'pending' | 'uploading' | 'done' | 'error'
  error?: string
}

/** Wizard step mapping (0-indexed for Stepper) */
export type DeepresearchWizardStep = 0 | 1 | 2 | 3 | 4
// 0 = Setup, 1 = Idea Review, 2 = Method Review, 3 = Experiment, 4 = Paper

export const DEEPRESEARCH_STEP_LABELS = [
  'Setup',
  'Idea Generation',
  'Method Development',
  'Experiment',
  'Paper',
] as const

/** Maps wizard step index to stage number (1-based) for API calls. Step 0 (setup) has no stage. */
export const WIZARD_STEP_TO_STAGE: Record<number, number | null> = {
  0: null,
  1: 1,
  2: 2,
  3: 3,
  4: 4,
}

export const STAGE_SHARED_KEYS: Record<number, string> = {
  1: 'research_idea',
  2: 'methodology',
  3: 'results',
}

/** Available model options for stage configuration */
export interface ModelOption {
  value: string
  label: string
}

export const AVAILABLE_MODELS: ModelOption[] = [
  { value: 'gpt-4.1-2025-04-14', label: 'GPT-4.1' },
  { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-4o-mini-2024-07-18', label: 'GPT-4o Mini' },
  { value: 'gpt-4.5-preview-2025-02-27', label: 'GPT-4.5 Preview' },
  { value: 'gpt-5-2025-08-07', label: 'GPT-5' },
  { value: 'o3-mini-2025-01-31', label: 'o3-mini' },
  { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
  { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
  { value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4' },
  { value: 'claude-3.5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
]

/** Config overrides for all Deepresearch stages */
export interface DeepresearchStageConfig {
  // Stage 1 - Idea Generation
  idea_maker_model?: string
  idea_hater_model?: string
  // Stage 2 - Method Development
  researcher_model?: string
  // Stage 3 - Experiment
  engineer_model?: string
  max_n_attempts?: number
  max_n_steps?: number
  // Stage 4 - Paper
  llm_model?: string
  writer?: string
  journal?: string
  add_citations?: boolean
  // Shared across stages 1-3
  planner_model?: string
  plan_reviewer_model?: string
  orchestration_model?: string
  formatter_model?: string
}
