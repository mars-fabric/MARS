/**
 * Product Discovery Assistant — API service
 * Calls the MARS FastAPI backend endpoints at /api/pda/*
 */

import { getApiUrl } from '@/lib/config'
import type {
  IntakeFormData,
  ResearchSummary,
  ProblemDefinition,
  OpportunityArea,
  SolutionArchetype,
  Feature,
} from '@/types/pda'

// ---------------------------------------------------------------------------
// Generic helper
// ---------------------------------------------------------------------------
async function callPDA<T = any>(
  endpoint: string,
  body: Record<string, any>,
): Promise<T> {
  const url = getApiUrl(`/api/pda${endpoint}`)
  console.log(`[PDA] POST ${url}`, body)

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const errText = await response.text().catch(() => response.statusText)
    throw new Error(`Backend error (${response.status}): ${errText}`)
  }

  return response.json()
}

// ---------------------------------------------------------------------------
// Step 0 — Client Details (auto-detect ALL fields)
// ---------------------------------------------------------------------------
export async function getClientDetails(
  clientName: string,
): Promise<{
  industry: string
  subIndustry: string
  clientContext: string
  businessFunctions: string[]
  suggestedDiscoveryTypes: string[]
  problemKeywords: string
  suggestedBusinessFunctions: string[]
}> {
  try {
    const result = await callPDA<{
      industry: string
      subIndustry: string
      clientContext: string
      businessFunctions: string[]
      suggestedDiscoveryTypes: string[]
      problemKeywords: string
      suggestedBusinessFunctions: string[]
    }>('/client-details', { clientName })
    return {
      industry: result.industry || '',
      subIndustry: result.subIndustry || '',
      clientContext: result.clientContext || '',
      businessFunctions: Array.isArray(result.businessFunctions)
        ? result.businessFunctions
        : [],
      suggestedDiscoveryTypes: Array.isArray(result.suggestedDiscoveryTypes)
        ? result.suggestedDiscoveryTypes
        : [],
      problemKeywords: result.problemKeywords || '',
      suggestedBusinessFunctions: Array.isArray(result.suggestedBusinessFunctions)
        ? result.suggestedBusinessFunctions
        : [],
    }
  } catch (error) {
    console.error('Failed to get client details:', error)
    return {
      industry: '', subIndustry: '', clientContext: '',
      businessFunctions: [], suggestedDiscoveryTypes: [],
      problemKeywords: '', suggestedBusinessFunctions: [],
    }
  }
}

// ---------------------------------------------------------------------------
// Step 1 — Research Summary (cmbagent researcher)
// ---------------------------------------------------------------------------
export async function generateResearchSummary(
  intakeData: IntakeFormData,
): Promise<ResearchSummary> {
  try {
    return await callPDA<ResearchSummary>('/research-summary', { intakeData })
  } catch (error) {
    console.error('Failed to generate research summary:', error)
    return {
      marketTrends: [],
      competitorMoves: [],
      industryPainPoints: [],
      workshopAngles: [],
      references: [],
    }
  }
}

// ---------------------------------------------------------------------------
// Step 2 — Problem Definition (cmbagent researcher)
// ---------------------------------------------------------------------------
export async function generateProblemDefinition(
  intakeData: IntakeFormData,
  researchSummary: ResearchSummary,
): Promise<ProblemDefinition> {
  try {
    return await callPDA<ProblemDefinition>('/problem-definition', {
      intakeData,
      researchSummary,
    })
  } catch (error) {
    console.error('Failed to generate problem definition:', error)
    return {
      problemStatement: '',
      supportingPoints: [],
      personasAffected: [],
      kpisImpacted: [],
      rootCause: '',
      reframingExamples: [],
      references: [],
    }
  }
}

// ---------------------------------------------------------------------------
// Step 3 — Opportunities
// ---------------------------------------------------------------------------
export async function generateOpportunities(
  intakeData: IntakeFormData,
  problemDefinition: string,
): Promise<OpportunityArea[]> {
  try {
    const result = await callPDA<OpportunityArea[]>('/opportunities', {
      intakeData,
      problemDefinition,
    })
    return Array.isArray(result) ? result : []
  } catch (error) {
    console.error('Failed to generate opportunities:', error)
    return []
  }
}

// ---------------------------------------------------------------------------
// Step 4 — Solution Archetypes
// ---------------------------------------------------------------------------
export async function generateSolutionArchetypes(
  selectedOpportunity: OpportunityArea,
  intakeData: IntakeFormData,
): Promise<SolutionArchetype[]> {
  try {
    const result = await callPDA<SolutionArchetype[]>('/solution-archetypes', {
      selectedOpportunity,
      intakeData,
    })
    return Array.isArray(result) ? result : []
  } catch (error) {
    console.error('Failed to generate archetypes:', error)
    return []
  }
}

// ---------------------------------------------------------------------------
// Step 5 — Features
// ---------------------------------------------------------------------------
export async function generateFeatures(
  selectedArchetype: SolutionArchetype,
  opportunity: OpportunityArea,
  intakeData: IntakeFormData,
): Promise<Feature[]> {
  try {
    const result = await callPDA<Feature[]>('/features', {
      selectedArchetype,
      opportunity,
      intakeData,
    })
    return Array.isArray(result) ? result : []
  } catch (error) {
    console.error('Failed to generate features:', error)
    return []
  }
}

// ---------------------------------------------------------------------------
// Step 6 — Prompts
// ---------------------------------------------------------------------------
export async function generatePrompts(
  intakeData: IntakeFormData,
  opportunity: OpportunityArea,
  archetype: SolutionArchetype,
  selectedFeatures: Feature[],
): Promise<{ lovable: string; googleAI: string; general: string }> {
  try {
    return await callPDA<{ lovable: string; googleAI: string; general: string }>(
      '/prompts',
      { intakeData, opportunity, archetype, selectedFeatures },
    )
  } catch (error) {
    console.error('Failed to generate prompts:', error)
    return { lovable: '', googleAI: '', general: '' }
  }
}

// ---------------------------------------------------------------------------
// Step 7 — Slide Content
// ---------------------------------------------------------------------------
export async function generateSlideContent(
  intakeData: IntakeFormData,
  research: string,
  problem: string,
  opportunity: OpportunityArea,
  archetype: SolutionArchetype,
  features: Feature[],
): Promise<string> {
  try {
    const result = await callPDA<{ content: string }>('/slide-content', {
      intakeData,
      research,
      problem,
      opportunity,
      archetype,
      features,
    })
    return result.content || ''
  } catch (error) {
    console.error('Failed to generate slide content:', error)
    return ''
  }
}
