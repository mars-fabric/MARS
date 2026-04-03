/**
 * Product Discovery Assistant (PDA) type definitions — staged architecture
 *
 * Mirrors NewsPulse / DeepResearch patterns:
 *   • Session + WorkflowRun + TaskStage DB records
 *   • Background execution per stage with WS streaming
 *   • HITL review between stages
 */

// ---------------------------------------------------------------------------
// Intake / step-0 types (still used for the setup form)
// ---------------------------------------------------------------------------

export type ResearchMode = 'one_shot' | 'planning_and_control'

export interface IntakeFormData {
  clientName: string
  industry: string
  subIndustry: string
  clientContext: string
  businessFunction: string
  discoveryType: string
  processType: 'new' | 'existing'
  existingFunctionality?: string
  problemKeywords: string
  expectedOutput: string[]
  researchMode: ResearchMode
}

// ---------------------------------------------------------------------------
// Stage content types (structured output from each stage)
// ---------------------------------------------------------------------------

export interface ResearchSummary {
  marketTrends: string[]
  competitorMoves: string[]
  industryPainPoints: string[]
  workshopAngles: string[]
  references: string[]
}

export interface ProblemDefinition {
  problemStatement: string
  supportingPoints: string | string[]
  personasAffected: string | string[]
  kpisImpacted: string | string[]
  rootCause: string
  reframingExamples: string | string[]
  references: string[]
}

export interface OpportunityArea {
  id: string
  title: string
  explanation: string
  valueCategory: 'Revenue' | 'Efficiency' | 'Experience' | 'Risk'
  kpis: string[]
  whyNow: string
  references?: string[]
}

export interface SolutionArchetype {
  id: string
  title: string
  summary: string
  personas: string[]
  benefits: string[]
  references?: string[]
}

export interface Feature {
  id: string
  name: string
  description: string
  strategicGoal: string
  userStories: string[]
  successMetrics: string[]
  bucket: string
  priority: 'Must' | 'Should' | 'Could'
  selected: boolean
}

// ---------------------------------------------------------------------------
// Task / stage state types (mirrors NewsPulse types)
// ---------------------------------------------------------------------------

export type PdaStageStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface PdaStageInfo {
  stage_number: number
  stage_name: string
  status: PdaStageStatus
  started_at?: string | null
  completed_at?: string | null
  error?: string | null
}

export interface PdaTaskState {
  task_id: string
  task: string
  status: string
  work_dir?: string | null
  created_at?: string | null
  stages: PdaStageInfo[]
  current_stage?: number | null
  progress_percent: number
  total_cost_usd?: number | null
  client_name?: string | null
  industry?: string | null
}

export interface PdaCreateResponse {
  task_id: string
  work_dir: string
  stages: PdaStageInfo[]
}

export interface PdaStageContent {
  stage_number: number
  stage_name: string
  status: string
  content?: string | null
  shared_state?: Record<string, unknown> | null
  output_files?: string[] | null
}

export interface PdaRefineResponse {
  refined_content: string
  message: string
}

export interface PdaRefinementMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

// Wizard step type (0 = intake, 1-7 = stage steps)
export type PdaWizardStep = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7

// ---------------------------------------------------------------------------
// Legacy DiscoveryState (kept for backward compat with old components)
// ---------------------------------------------------------------------------

export interface DiscoveryState {
  currentStep: number
  intakeData: IntakeFormData | null
  researchSummary: ResearchSummary | null
  problemDefinition: ProblemDefinition | null
  opportunities: OpportunityArea[]
  selectedOpportunity: string | null
  solutionArchetypes: SolutionArchetype[]
  selectedArchetype: string | null
  features: Feature[]
  selectedSolution: string | null
  prompts: {
    lovable?: string
    googleAI?: string
    general?: string
  }
  slideContent: string | null
}

