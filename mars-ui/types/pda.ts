/**
 * Product Discovery Assistant (PDA) type definitions
 * Extracted from pda_6d3220af/src/types/discovery.ts
 */

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
