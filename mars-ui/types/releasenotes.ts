/**
 * TypeScript types for the Release Notes wizard.
 * Mirrors the Deepresearch type pattern with staged execution.
 */

export type ReleaseNotesStageStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface ReleaseNotesStage {
  stage_number: number
  stage_name: string
  status: ReleaseNotesStageStatus
  started_at?: string | null
  completed_at?: string | null
  error?: string | null
}

export interface ReleaseNotesTaskState {
  task_id: string
  repo_url: string
  repo_name: string
  base_branch: string
  head_branch: string
  status: string
  work_dir?: string | null
  created_at?: string | null
  stages: ReleaseNotesStage[]
  current_stage?: number | null
  progress_percent: number
}

export interface ReleaseNotesStageContent {
  stage_number: number
  stage_name: string
  status: string
  content?: string | null
  shared_state?: Record<string, unknown> | null
  output_files?: string[] | null
  documents?: Record<string, string> | null
}

export interface ReleaseNotesCreateResponse {
  task_id: string
  work_dir: string
  stages: ReleaseNotesStage[]
}

export interface ReleaseNotesRefineResponse {
  refined_content: string
  message: string
}

export interface RefinementMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

/** Wizard step mapping (0-indexed for Stepper) */
export type ReleaseNotesWizardStep = 0 | 1 | 2 | 3 | 4 | 5
// 0 = Setup, 1 = Clone & Diff, 2 = Analysis, 3 = Release Notes, 4 = Migration, 5 = Package

export const RELEASE_NOTES_STEP_LABELS = [
  'Setup',
  'Clone & Diff',
  'AI Analysis',
  'Release Notes',
  'Migration',
  'Package',
] as const

/** Maps wizard step index to stage number (1-based) for API calls. Step 0 (setup) has no stage. */
export const WIZARD_STEP_TO_STAGE: Record<number, number | null> = {
  0: null,
  1: 1,
  2: 2,
  3: 3,
  4: 4,
  5: 5,
}

export const STAGE_SHARED_KEYS: Record<number, string> = {
  1: 'diff_context',
  2: 'analysis_comparison',
  3: 'release_notes',
  4: 'migration_script',
}

export const ANALYSIS_DOC_KEYS = [
  { key: 'analysis_base', label: 'Last Release Branch', file: 'analysis_base.md' },
  { key: 'analysis_head', label: 'Current Release Branch', file: 'analysis_head.md' },
  { key: 'analysis_comparison', label: 'Detailed Comparison', file: 'analysis_comparison.md' },
] as const

export type AnalysisDocKey = typeof ANALYSIS_DOC_KEYS[number]['key']
