/** Types for AI Weekly Report phase-based pipeline. */

export interface AIWeeklyStage {
    stage_number: number
    stage_name: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    error?: string
    started_at?: string
    completed_at?: string
}

export interface AIWeeklyTaskState {
    task_id: string
    status: string
    progress: number
    stages: AIWeeklyStage[]
    total_cost?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
    total_cost_usd?: number | null
}

export interface AIWeeklyCreateResponse {
    task_id: string
    work_dir: string
    stages: AIWeeklyStage[]
}

export interface AIWeeklyRefineResponse {
    refined_content: string
    message: string
}

export interface AIWeeklyRefinementMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: number
}

export const AIWEEKLY_STAGE_NAMES: Record<number, string> = {
    1: 'Data Collection',
    2: 'Content Curation',
    3: 'Report Generation',
    4: 'Quality Review',
}

/** Wizard step labels shown in the stepper. */
export const AIWEEKLY_STEP_LABELS = [
    'Setup',
    'Data Collection',
    'Content Curation',
    'Report Generation',
    'Quality Review',
]

/** Map wizard step index → backend stage number (null for setup). */
export const AIWEEKLY_WIZARD_STEP_TO_STAGE: Record<number, number | null> = {
    0: null,
    1: 1,
    2: 2,
    3: 3,
    4: 4,
}

/** Shared-state keys for each stage (used in save/refine endpoints). */
export const AIWEEKLY_STAGE_SHARED_KEYS: Record<number, string> = {
    1: 'raw_collection',
    2: 'curated_items',
    3: 'draft_report',
    4: 'final_report',
}

export type AIWeeklyWizardStep = 0 | 1 | 2 | 3 | 4

/** Model option for the AI Weekly model selectors (reuses deepresearch list). */
export interface AIWeeklyModelOption {
    value: string
    label: string
}

/** Available models for AI Weekly stages. */
export const AIWEEKLY_AVAILABLE_MODELS: AIWeeklyModelOption[] = [
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

/** Config overrides for AI Weekly LLM stages (Stages 2-4). */
export interface AIWeeklyStageConfig {
    /** Primary generation model (Stages 2-4) */
    model?: string
    /** Review pass model (defaults to primary model) */
    review_model?: string
    /** Specialist/fact-check model (defaults to primary model) */
    specialist_model?: string
    /** LLM temperature (0-1) */
    temperature?: number
    /** Number of review passes */
    n_reviews?: number
}
