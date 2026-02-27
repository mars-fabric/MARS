'use client'

/**
 * ProductDiscoveryTask — 9-step wizard for Product Discovery Assistant (PDA)
 *
 * Replaces the standalone pda_6d3220af Vite app.  Uses the same MARS FastAPI
 * backend endpoints at /api/pda/* via lib/pda-api.ts.
 *
 * Steps:
 *   0 Intake  →  1 Research  →  2 Problem  →  3 Opportunity  →  4 Solution
 *   5 Features  →  6 Prompts  →  7 Slides  →  8 Summary
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  RefreshCw,
  Copy,
  Check,
  Download,
  Plus,
  RotateCcw,
  Loader2,
  TrendingUp,
  Users,
  Target,
  Lightbulb,
  Zap,
  Shield,
  AlertCircle,
  ListChecks,
  GitBranch,
  Sparkles,
} from 'lucide-react'

import { Button } from '@/components/core'

import {
  getClientDetails,
  generateResearchSummary,
  generateProblemDefinition,
  generateOpportunities,
  generateSolutionArchetypes,
  generateFeatures,
  generatePrompts,
  generateSlideContent,
} from '@/lib/pda-api'

import type {
  IntakeFormData,
  ResearchSummary,
  ProblemDefinition,
  OpportunityArea,
  SolutionArchetype,
  Feature,
  DiscoveryState,
} from '@/types/pda'

// ─── constants ───────────────────────────────────────────────────────────────
const STEP_LABELS = [
  'Intake',
  'Research',
  'Problem',
  'Opportunity',
  'Solution',
  'Features',
  'Prompts',
  'Slides',
  'Summary',
]

const STORAGE_KEY = 'pda-discovery-state'

const BUSINESS_FUNCTIONS = [
  'Store Ops',
  'Supply Chain',
  'Merchandising',
  'E-commerce',
  'HR',
  'Finance',
  'Manufacturing',
  'Marketing',
]

const DISCOVERY_TYPES = [
  'Problem',
  'Opportunity',
  'Pain Point',
  'Capability',
  'Open Discovery',
]

const OUTPUT_OPTIONS = ['Prototype Prompt', 'Slides', 'Opportunity Pack', 'All']

// ─── helpers ─────────────────────────────────────────────────────────────────
function cn(...classes: (string | boolean | undefined | null)[]) {
  return classes.filter(Boolean).join(' ')
}

/** Minimal Markdown → HTML renderer (headers, bold, italic, lists, links) */
function renderMarkdown(text: string): string {
  let html = text
  html = html.replace(
    /^### (.*$)/gim,
    '<h3 class="text-base font-semibold mt-3 mb-1">$1</h3>',
  )
  html = html.replace(
    /^## (.*$)/gim,
    '<h2 class="text-lg font-bold mt-4 mb-2">$1</h2>',
  )
  html = html.replace(
    /^# (.*$)/gim,
    '<h1 class="text-xl font-bold mt-5 mb-3">$1</h1>',
  )
  html = html.replace(
    /\*\*(.*?)\*\*/g,
    '<strong class="font-semibold">$1</strong>',
  )
  html = html.replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
  html = html.replace(/^\* (.*$)/gim, '<li class="ml-4 mb-1">• $1</li>')
  html = html.replace(/^- (.*$)/gim, '<li class="ml-4 mb-1">• $1</li>')
  html = html.replace(/^\d+\. (.*$)/gim, '<li class="ml-4 mb-1">$1</li>')
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" class="underline" style="color:var(--mars-color-primary)" target="_blank" rel="noopener noreferrer">$1</a>',
  )
  html = html.replace(/\n\n/g, '<br/><br/>')
  html = html.replace(/\n/g, '<br/>')
  return html
}

function Md({
  content,
  className = '',
}: {
  content: string
  className?: string
}) {
  return (
    <div
      className={`prose prose-sm max-w-none dark:prose-invert ${className}`}
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  )
}

// ─── Spinner ─────────────────────────────────────────────────────────────────
function Spinner({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <Loader2
        className="w-10 h-10 animate-spin mb-4"
        style={{ color: 'var(--mars-color-primary)' }}
      />
      <h3
        className="text-lg font-semibold mb-1"
        style={{ color: 'var(--mars-color-text)' }}
      >
        {label}
      </h3>
      <p
        className="text-sm"
        style={{ color: 'var(--mars-color-text-secondary)' }}
      >
        This may take a moment…
      </p>
    </div>
  )
}

// ─── Notification helper (simple toast replacement) ──────────────────────────
function notify(msg: string, type: 'success' | 'error' = 'success') {
  // Minimal in-page toast — could be replaced with a proper toast lib later
  const el = document.createElement('div')
  el.textContent = msg
  el.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    padding: 12px 20px; border-radius: 8px; font-size: 14px;
    color: #fff;
    background: ${type === 'success' ? '#22c55e' : '#ef4444'};
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    transition: opacity 0.3s;
  `
  document.body.appendChild(el)
  setTimeout(() => {
    el.style.opacity = '0'
    setTimeout(() => el.remove(), 300)
  }, 2500)
}

// ═══════════════════════════════════════════════════════════════════════════
// PROPS
// ═══════════════════════════════════════════════════════════════════════════
interface ProductDiscoveryTaskProps {
  onBack: () => void
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════
export default function ProductDiscoveryTask({
  onBack,
}: ProductDiscoveryTaskProps) {
  // ── state ────────────────────────────────────────────────────────────────
  const [state, setState] = useState<DiscoveryState>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        try {
          return JSON.parse(saved)
        } catch {
          /* ignore */
        }
      }
    }
    return emptyState()
  })

  // auto-save
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }, [state])

  // ── navigation ───────────────────────────────────────────────────────────
  const handleNext = () => {
    if (canGoNext()) {
      setState((s) => ({ ...s, currentStep: s.currentStep + 1 }))
    }
  }
  const handleBack = () => {
    setState((s) => ({
      ...s,
      currentStep: Math.max(0, s.currentStep - 1),
    }))
  }
  const handleReset = () => {
    localStorage.removeItem(STORAGE_KEY)
    setState(emptyState())
  }

  const canGoNext = (): boolean => {
    switch (state.currentStep) {
      case 0:
        return !!(
          state.intakeData &&
          state.intakeData.clientName &&
          state.intakeData.industry &&
          state.intakeData.subIndustry &&
          state.intakeData.clientContext &&
          state.intakeData.businessFunction &&
          state.intakeData.discoveryType &&
          state.intakeData.problemKeywords &&
          state.intakeData.expectedOutput.length > 0
        )
      case 1:
        return !!state.researchSummary
      case 2:
        return !!state.problemDefinition
      case 3:
        return !!state.selectedOpportunity
      case 4:
        return !!state.selectedArchetype
      case 5:
        return state.features.filter((f) => f.selected).length > 0
      case 6:
        return !!state.prompts?.lovable
      case 7:
        return !!state.slideContent
      case 8:
        return false
      default:
        return false
    }
  }

  // ── render ───────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div
        className="flex items-center gap-3 px-6 py-4 border-b flex-shrink-0"
        style={{
          backgroundColor: 'var(--mars-color-surface)',
          borderColor: 'var(--mars-color-border)',
        }}
      >
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-sm font-medium hover:opacity-80"
          style={{ color: 'var(--mars-color-primary)' }}
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <span
          className="text-sm"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          /
        </span>
        <h1
          className="text-lg font-semibold"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Product Discovery Assistant
        </h1>
        {state.currentStep > 0 && (
          <button
            onClick={() => {
              if (
                confirm(
                  'Start a new session? All current progress will be lost.',
                )
              ) {
                handleReset()
              }
            }}
            className="ml-auto flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-md border transition-colors hover:opacity-80"
            style={{
              color: 'var(--mars-color-error)',
              borderColor: 'var(--mars-color-error)',
            }}
          >
            <RotateCcw className="w-3.5 h-3.5" />
            New Session
          </button>
        )}
      </div>

      {/* Step indicator */}
      <StepIndicatorBar
        currentStep={state.currentStep}
        labels={STEP_LABELS}
      />

      {/* Step content */}
      <div className="flex-1 overflow-y-auto">
        {renderStep(state, setState)}
      </div>

      {/* Bottom nav */}
      {state.currentStep < 8 && (
        <div
          className="flex items-center justify-between px-6 py-3 border-t flex-shrink-0"
          style={{
            backgroundColor: 'var(--mars-color-surface)',
            borderColor: 'var(--mars-color-border)',
          }}
        >
          <button
            onClick={handleBack}
            disabled={state.currentStep === 0}
            className="flex items-center gap-1 text-sm font-medium disabled:opacity-30"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
          <button
            onClick={handleNext}
            disabled={!canGoNext()}
            className={cn(
              'flex items-center gap-1 px-5 py-2 rounded-md text-sm font-medium transition-colors',
              canGoNext() ? 'hover:opacity-90' : 'opacity-40 cursor-not-allowed',
            )}
            style={{
              backgroundColor: 'var(--mars-color-primary)',
              color: '#fff',
            }}
          >
            {state.currentStep === 0 ? 'Start Discovery' : 'Next'}
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP INDICATOR BAR
// ═══════════════════════════════════════════════════════════════════════════
function StepIndicatorBar({
  currentStep,
  labels,
}: {
  currentStep: number
  labels: string[]
}) {
  return (
    <div
      className="flex items-center gap-1 px-6 py-3 overflow-x-auto flex-shrink-0 border-b"
      style={{
        backgroundColor: 'var(--mars-color-surface)',
        borderColor: 'var(--mars-color-border)',
      }}
    >
      {labels.map((label, idx) => {
        const isComplete = idx < currentStep
        const isCurrent = idx === currentStep
        return (
          <React.Fragment key={idx}>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <div
                className={cn(
                  'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                  isComplete && 'text-white',
                  isCurrent && 'text-white',
                )}
                style={{
                  backgroundColor: isComplete
                    ? 'var(--mars-color-success, #22c55e)'
                    : isCurrent
                      ? 'var(--mars-color-primary)'
                      : 'var(--mars-color-surface-overlay)',
                  color:
                    isComplete || isCurrent
                      ? '#fff'
                      : 'var(--mars-color-text-tertiary)',
                }}
              >
                {isComplete ? <Check className="w-3.5 h-3.5" /> : idx + 1}
              </div>
              <span
                className="text-xs font-medium whitespace-nowrap"
                style={{
                  color: isCurrent
                    ? 'var(--mars-color-primary)'
                    : isComplete
                      ? 'var(--mars-color-text-secondary)'
                      : 'var(--mars-color-text-tertiary)',
                }}
              >
                {label}
              </span>
            </div>
            {idx < labels.length - 1 && (
              <div
                className="w-6 h-px flex-shrink-0"
                style={{
                  backgroundColor: isComplete
                    ? 'var(--mars-color-success, #22c55e)'
                    : 'var(--mars-color-border)',
                }}
              />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP ROUTER
// ═══════════════════════════════════════════════════════════════════════════
function renderStep(
  state: DiscoveryState,
  setState: React.Dispatch<React.SetStateAction<DiscoveryState>>,
) {
  switch (state.currentStep) {
    case 0:
      return (
        <IntakeStep
          initialData={state.intakeData ?? undefined}
          onUpdate={(data) => setState((s) => ({ ...s, intakeData: data }))}
        />
      )
    case 1:
      return state.intakeData ? (
        <ResearchStep
          intakeData={state.intakeData}
          initialData={state.researchSummary ?? undefined}
          onComplete={(data) =>
            setState((s) => ({ ...s, researchSummary: data }))
          }
        />
      ) : null
    case 2:
      return state.intakeData && state.researchSummary ? (
        <ProblemStep
          intakeData={state.intakeData}
          researchSummary={state.researchSummary}
          initialData={state.problemDefinition ?? undefined}
          onComplete={(data) =>
            setState((s) => ({ ...s, problemDefinition: data }))
          }
        />
      ) : null
    case 3:
      return state.intakeData && state.problemDefinition ? (
        <OpportunityStep
          intakeData={state.intakeData}
          problemDefinition={state.problemDefinition}
          initialData={
            state.opportunities.length > 0 ? state.opportunities : undefined
          }
          selectedId={state.selectedOpportunity ?? undefined}
          onComplete={(opportunities, selectedId) =>
            setState((s) => ({
              ...s,
              opportunities,
              selectedOpportunity: selectedId,
            }))
          }
        />
      ) : null
    case 4: {
      const opp = state.opportunities.find(
        (o) => o.id === state.selectedOpportunity,
      )
      return opp && state.intakeData ? (
        <SolutionStep
          opportunity={opp}
          intakeData={state.intakeData}
          initialData={
            state.solutionArchetypes.length > 0
              ? state.solutionArchetypes
              : undefined
          }
          selectedId={state.selectedArchetype ?? undefined}
          onComplete={(archetypes, selectedId) =>
            setState((s) => ({
              ...s,
              solutionArchetypes: archetypes,
              selectedArchetype: selectedId,
            }))
          }
        />
      ) : null
    }
    case 5: {
      const arch = state.solutionArchetypes.find(
        (a) => a.id === state.selectedArchetype,
      )
      const opp5 = state.opportunities.find(
        (o) => o.id === state.selectedOpportunity,
      )
      return arch && opp5 && state.intakeData ? (
        <FeatureStep
          archetype={arch}
          opportunity={opp5}
          intakeData={state.intakeData}
          initialData={state.features.length > 0 ? state.features : undefined}
          onComplete={(features) =>
            setState((s) => ({ ...s, features }))
          }
        />
      ) : null
    }
    case 6: {
      const arch6 = state.solutionArchetypes.find(
        (a) => a.id === state.selectedArchetype,
      )
      const opp6 = state.opportunities.find(
        (o) => o.id === state.selectedOpportunity,
      )
      return state.intakeData && opp6 && arch6 ? (
        <PromptStep
          intakeData={state.intakeData}
          opportunity={opp6}
          archetype={arch6}
          features={state.features}
          initialData={
            state.prompts?.lovable ? (state.prompts as any) : undefined
          }
          onComplete={(prompts) =>
            setState((s) => ({ ...s, prompts }))
          }
        />
      ) : null
    }
    case 7: {
      const arch7 = state.solutionArchetypes.find(
        (a) => a.id === state.selectedArchetype,
      )
      const opp7 = state.opportunities.find(
        (o) => o.id === state.selectedOpportunity,
      )
      return state.intakeData &&
        state.researchSummary &&
        state.problemDefinition &&
        opp7 &&
        arch7 ? (
        <SlideStep
          intakeData={state.intakeData}
          research={state.researchSummary}
          problem={state.problemDefinition}
          opportunity={opp7}
          archetype={arch7}
          features={state.features}
          initialData={state.slideContent ?? undefined}
          onComplete={(content) =>
            setState((s) => ({ ...s, slideContent: content }))
          }
        />
      ) : null
    }
    case 8:
      return <SummaryStep state={state} onReset={() => {
        localStorage.removeItem(STORAGE_KEY)
        setState(emptyState())
      }} />
    default:
      return null
  }
}

// ─── empty state factory ─────────────────────────────────────────────────────
function emptyState(): DiscoveryState {
  return {
    currentStep: 0,
    intakeData: null,
    researchSummary: null,
    problemDefinition: null,
    opportunities: [],
    selectedOpportunity: null,
    solutionArchetypes: [],
    selectedArchetype: null,
    features: [],
    selectedSolution: null,
    prompts: {},
    slideContent: null,
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// CARD helper — replaces shadcn Card with MARS-styled div
// ═══════════════════════════════════════════════════════════════════════════
function Card({
  children,
  className = '',
  onClick,
  style,
}: {
  children: React.ReactNode
  className?: string
  onClick?: () => void
  style?: React.CSSProperties
}) {
  return (
    <div
      className={`rounded-lg border ${className}`}
      style={{
        backgroundColor: 'var(--mars-color-surface)',
        borderColor: 'var(--mars-color-border)',
        ...style,
      }}
      onClick={onClick}
    >
      {children}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 0 — INTAKE FORM
// ═══════════════════════════════════════════════════════════════════════════
function IntakeStep({
  initialData,
  onUpdate,
}: {
  initialData?: IntakeFormData
  onUpdate: (data: IntakeFormData) => void
}) {
  const [form, setForm] = useState<IntakeFormData>(
    initialData || {
      clientName: '',
      industry: '',
      subIndustry: '',
      clientContext: '',
      businessFunction: '',
      discoveryType: '',
      processType: 'new',
      existingFunctionality: '',
      problemKeywords: '',
      expectedOutput: ['All'],
    },
  )
  const [loadingClient, setLoadingClient] = useState(false)
  const [suggestedFuncs, setSuggestedFuncs] = useState<string[]>([])

  const update = useCallback(
    (patch: Partial<IntakeFormData>) => {
      setForm((prev) => {
        const next = { ...prev, ...patch }
        onUpdate(next)
        return next
      })
    },
    [onUpdate],
  )

  // auto-detect client details
  useEffect(() => {
    if (!form.clientName || form.clientName.length < 3) return
    const timeout = setTimeout(async () => {
      setLoadingClient(true)
      try {
        const details = await getClientDetails(form.clientName)
        const patch: Partial<IntakeFormData> = {}
        if (details.industry && !form.industry) patch.industry = details.industry
        if (details.subIndustry && !form.subIndustry)
          patch.subIndustry = details.subIndustry
        if (Object.keys(patch).length) {
          update(patch)
          notify('Auto-populated industry details')
        }
        if (details.businessFunctions.length)
          setSuggestedFuncs(details.businessFunctions)
      } catch {
        /* ignore */
      } finally {
        setLoadingClient(false)
      }
    }, 1000)
    return () => clearTimeout(timeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.clientName])

  const toggleOutput = (opt: string) => {
    if (opt === 'All') {
      update({ expectedOutput: ['All'] })
    } else {
      const filtered = form.expectedOutput.filter((o) => o !== 'All')
      if (filtered.includes(opt)) {
        update({ expectedOutput: filtered.filter((o) => o !== opt) })
      } else {
        update({ expectedOutput: [...filtered, opt] })
      }
    }
  }

  const inputStyle: React.CSSProperties = {
    backgroundColor: 'var(--mars-color-surface)',
    borderColor: 'var(--mars-color-border)',
    color: 'var(--mars-color-text)',
  }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <Card className="p-6">
        <h2
          className="text-2xl font-bold mb-1"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Discovery Intake
        </h2>
        <p
          className="text-sm mb-6"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Fill in the details to start your product discovery session
        </p>

        <div className="space-y-5">
          {/* Client Name */}
          <Field label="Client Name *">
            <div className="relative">
              <input
                className="w-full h-9 px-3 border rounded-md text-sm"
                style={inputStyle}
                value={form.clientName}
                onChange={(e) => update({ clientName: e.target.value })}
                placeholder="Enter client name"
              />
              {loadingClient && (
                <Loader2
                  className="absolute right-3 top-2 w-4 h-4 animate-spin"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                />
              )}
            </div>
          </Field>

          {/* Industry / Sub-Industry */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Industry *">
              <input
                className="w-full h-9 px-3 border rounded-md text-sm"
                style={inputStyle}
                value={form.industry}
                onChange={(e) => update({ industry: e.target.value })}
                placeholder="e.g., Retail"
              />
            </Field>
            <Field label="Sub-Industry *">
              <input
                className="w-full h-9 px-3 border rounded-md text-sm"
                style={inputStyle}
                value={form.subIndustry}
                onChange={(e) => update({ subIndustry: e.target.value })}
                placeholder="e.g., Fashion Retail"
              />
            </Field>
          </div>

          {/* Client Context */}
          <Field label="Client Context *">
            <textarea
              className="w-full min-h-[100px] px-3 py-2 border rounded-md text-sm resize-y"
              style={inputStyle}
              value={form.clientContext}
              onChange={(e) => update({ clientContext: e.target.value })}
              placeholder="Company size, market position, digital maturity, strategic initiatives, current tech stack…"
            />
            <p
              className="text-xs mt-1"
              style={{ color: 'var(--mars-color-text-tertiary)' }}
            >
              This context will enhance research, problem framing, opportunity
              creation, and solution design throughout the discovery.
            </p>
          </Field>

          {/* Business Function */}
          <Field label="Business Function *">
            <select
              className="w-full h-9 px-3 border rounded-md text-sm"
              style={inputStyle}
              value={form.businessFunction}
              onChange={(e) => update({ businessFunction: e.target.value })}
            >
              <option value="">Select business function</option>
              {suggestedFuncs.length > 0 && (
                <optgroup label={`Suggested for ${form.clientName}`}>
                  {suggestedFuncs.map((fn) => (
                    <option key={fn} value={fn}>
                      ✨ {fn}
                    </option>
                  ))}
                </optgroup>
              )}
              <optgroup label="All Functions">
                {BUSINESS_FUNCTIONS.filter(
                  (fn) => !suggestedFuncs.includes(fn),
                ).map((fn) => (
                  <option key={fn} value={fn}>
                    {fn}
                  </option>
                ))}
              </optgroup>
            </select>
          </Field>

          {/* Discovery Type */}
          <Field label="Type of Discovery *">
            <select
              className="w-full h-9 px-3 border rounded-md text-sm"
              style={inputStyle}
              value={form.discoveryType}
              onChange={(e) => update({ discoveryType: e.target.value })}
            >
              <option value="">Select discovery type</option>
              {DISCOVERY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>

          {/* Process Type */}
          <Field label="Process Type *">
            <select
              className="w-full h-9 px-3 border rounded-md text-sm"
              style={inputStyle}
              value={form.processType}
              onChange={(e) =>
                update({ processType: e.target.value as 'new' | 'existing' })
              }
            >
              <option value="new">New Process</option>
              <option value="existing">Existing Process</option>
            </select>
          </Field>

          {form.processType === 'existing' && (
            <Field label="Existing Functionality *">
              <textarea
                className="w-full min-h-[100px] px-3 py-2 border rounded-md text-sm resize-y"
                style={inputStyle}
                value={form.existingFunctionality || ''}
                onChange={(e) =>
                  update({ existingFunctionality: e.target.value })
                }
                placeholder="Describe the existing functionality or process…"
              />
            </Field>
          )}

          {/* Problem Keywords */}
          <Field label="Problem Keywords / Notes *">
            <textarea
              className="w-full min-h-[100px] px-3 py-2 border rounded-md text-sm resize-y"
              style={inputStyle}
              value={form.problemKeywords}
              onChange={(e) => update({ problemKeywords: e.target.value })}
              placeholder="Describe the problem, pain points, or opportunity areas…"
            />
          </Field>

          {/* Expected Output */}
          <Field label="Expected Output *">
            <div className="space-y-2">
              {OUTPUT_OPTIONS.map((opt) => (
                <label
                  key={opt}
                  className="flex items-center gap-2 text-sm cursor-pointer"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  <input
                    type="checkbox"
                    checked={form.expectedOutput.includes(opt)}
                    onChange={() => toggleOutput(opt)}
                    className="rounded"
                  />
                  {opt}
                </label>
              ))}
            </div>
          </Field>
        </div>
      </Card>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 1 — RESEARCH SUMMARY
// ═══════════════════════════════════════════════════════════════════════════
function ResearchStep({
  intakeData,
  initialData,
  onComplete,
}: {
  intakeData: IntakeFormData
  initialData?: ResearchSummary
  onComplete: (data: ResearchSummary) => void
}) {
  const [loading, setLoading] = useState(!initialData)
  const [data, setData] = useState<ResearchSummary | null>(initialData ?? null)
  const calledRef = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await generateResearchSummary(intakeData)
      setData(result)
      onComplete(result)
      notify('Research summary generated')
    } catch {
      notify('Failed to generate research summary', 'error')
    } finally {
      setLoading(false)
    }
  }, [intakeData, onComplete])

  useEffect(() => {
    if (!initialData && !calledRef.current) {
      calledRef.current = true
      load()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading) return <Spinner label="Generating Research Summary" />
  if (!data) return null

  const sections: {
    key: keyof ResearchSummary
    title: string
    icon: React.ElementType
    color: string
  }[] = [
    {
      key: 'marketTrends',
      title: 'Market Trends',
      icon: TrendingUp,
      color: 'text-blue-500',
    },
    {
      key: 'competitorMoves',
      title: 'Competitor Moves',
      icon: Users,
      color: 'text-purple-500',
    },
    {
      key: 'industryPainPoints',
      title: 'Industry Pain Points',
      icon: Target,
      color: 'text-red-500',
    },
    {
      key: 'workshopAngles',
      title: 'Workshop Angles',
      icon: Lightbulb,
      color: 'text-amber-500',
    },
  ]

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-4">
      <StepHeader
        title="Research Summary"
        subtitle={`AI-generated insights for ${intakeData.clientName}`}
        onRegenerate={load}
      />
      {sections.map(({ key, title, icon: Icon, color }) => (
        <CollapsibleSection key={key} title={title} icon={<Icon className={`w-5 h-5 ${color}`} />}>
          <div className="space-y-2">
            {(data[key] as string[])?.map((item, idx) => (
              <div key={idx} className="flex gap-3">
                <span
                  className="font-semibold text-sm flex-shrink-0"
                  style={{ color: 'var(--mars-color-primary)' }}
                >
                  {idx + 1}.
                </span>
                <Md content={item} className="text-sm flex-1" />
              </div>
            ))}
          </div>
        </CollapsibleSection>
      ))}
      {data.references?.length > 0 && (
        <CollapsibleSection title="References & Sources" icon={<span className="text-lg">📚</span>} defaultOpen={false}>
          <ul className="space-y-2">
            {data.references.map((ref, idx) => (
              <li key={idx} className="text-sm flex gap-3">
                <span className="font-semibold text-green-500 flex-shrink-0">
                  [{idx + 1}]
                </span>
                <Md content={ref} className="flex-1" />
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 2 — PROBLEM DEFINITION
// ═══════════════════════════════════════════════════════════════════════════
function ProblemStep({
  intakeData,
  researchSummary,
  initialData,
  onComplete,
}: {
  intakeData: IntakeFormData
  researchSummary: ResearchSummary
  initialData?: ProblemDefinition
  onComplete: (data: ProblemDefinition) => void
}) {
  const [loading, setLoading] = useState(!initialData)
  const [data, setData] = useState<ProblemDefinition | null>(
    initialData ?? null,
  )
  const calledRef = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await generateProblemDefinition(intakeData, researchSummary)
      setData(result)
      onComplete(result)
      notify('Problem definition generated')
    } catch {
      notify('Failed to generate problem definition', 'error')
    } finally {
      setLoading(false)
    }
  }, [intakeData, researchSummary, onComplete])

  useEffect(() => {
    if (!initialData && !calledRef.current) {
      calledRef.current = true
      load()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading) return <Spinner label="Defining the Problem" />
  if (!data) return null

  const sections: {
    key: keyof ProblemDefinition
    title: string
    icon: React.ElementType
    color: string
    isArray: boolean
  }[] = [
    {
      key: 'problemStatement',
      title: 'Problem Statement',
      icon: AlertCircle,
      color: 'text-red-500',
      isArray: false,
    },
    {
      key: 'supportingPoints',
      title: 'Supporting Points',
      icon: ListChecks,
      color: 'text-blue-500',
      isArray: true,
    },
    {
      key: 'personasAffected',
      title: 'Personas Affected',
      icon: Users,
      color: 'text-purple-500',
      isArray: true,
    },
    {
      key: 'kpisImpacted',
      title: 'KPIs Impacted',
      icon: TrendingUp,
      color: 'text-orange-500',
      isArray: true,
    },
    {
      key: 'rootCause',
      title: 'Root Cause',
      icon: GitBranch,
      color: 'text-indigo-500',
      isArray: false,
    },
    {
      key: 'reframingExamples',
      title: 'Reframing Examples',
      icon: Lightbulb,
      color: 'text-amber-500',
      isArray: true,
    },
  ]

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-4">
      <StepHeader
        title="Problem Definition"
        subtitle={`Structured problem analysis for ${intakeData.clientName}`}
        onRegenerate={load}
      />
      {sections.map(({ key, title, icon: Icon, color, isArray }) => {
        const val = data[key]
        return (
          <CollapsibleSection
            key={key}
            title={title}
            icon={<Icon className={`w-5 h-5 ${color}`} />}
          >
            {isArray && Array.isArray(val) ? (
              <div className="space-y-2">
                {(val as string[]).map((item, idx) => (
                  <div key={idx} className="flex gap-3">
                    <span
                      className="font-semibold text-sm flex-shrink-0"
                      style={{ color: 'var(--mars-color-primary)' }}
                    >
                      {idx + 1}.
                    </span>
                    <Md content={item} className="text-sm flex-1" />
                  </div>
                ))}
              </div>
            ) : (
              <Md content={(val as string) || ''} className="text-sm" />
            )}
          </CollapsibleSection>
        )
      })}
      {data.references?.length > 0 && (
        <CollapsibleSection title="References & Sources" icon={<span className="text-lg">📚</span>} defaultOpen={false}>
          <ul className="space-y-2">
            {data.references.map((ref, idx) => (
              <li key={idx} className="text-sm flex gap-3">
                <span className="font-semibold text-green-500 flex-shrink-0">
                  [{idx + 1}]
                </span>
                <Md content={ref} className="flex-1" />
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 3 — OPPORTUNITY AREAS
// ═══════════════════════════════════════════════════════════════════════════
function OpportunityStep({
  intakeData,
  problemDefinition,
  initialData,
  selectedId,
  onComplete,
}: {
  intakeData: IntakeFormData
  problemDefinition: ProblemDefinition
  initialData?: OpportunityArea[]
  selectedId?: string
  onComplete: (opportunities: OpportunityArea[], selectedId: string) => void
}) {
  const [loading, setLoading] = useState(!initialData)
  const [opportunities, setOpportunities] = useState<OpportunityArea[]>(
    initialData ?? [],
  )
  const [selected, setSelected] = useState<string | null>(selectedId ?? null)
  const calledRef = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const text =
        typeof problemDefinition === 'string'
          ? problemDefinition
          : (problemDefinition as any).problemStatement || JSON.stringify(problemDefinition)
      const result = await generateOpportunities(intakeData, text)
      setOpportunities(result)
      notify('Opportunity areas generated')
    } catch {
      notify('Failed to generate opportunities', 'error')
    } finally {
      setLoading(false)
    }
  }, [intakeData, problemDefinition])

  useEffect(() => {
    if (!initialData && !calledRef.current) {
      calledRef.current = true
      load()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSelect = (id: string) => {
    setSelected(id)
    onComplete(opportunities, id)
  }

  if (loading) return <Spinner label="Identifying Opportunities" />

  const valueIcons: Record<string, React.ElementType> = {
    Revenue: TrendingUp,
    Efficiency: Zap,
    Experience: Users,
    Risk: Shield,
  }

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <StepHeader
        title="Opportunity Areas"
        subtitle="Select the opportunity you'd like to explore"
        onRegenerate={load}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {opportunities.map((opp) => {
          const Icon = valueIcons[opp.valueCategory] || Target
          const isSel = selected === opp.id
          return (
            <Card
              key={opp.id}
              className={cn(
                'p-5 cursor-pointer transition-all hover:shadow-md',
                isSel && 'ring-2',
              )}
              onClick={() => handleSelect(opp.id)}
              style={
                isSel
                  ? { borderColor: 'var(--mars-color-primary)', boxShadow: '0 0 0 2px var(--mars-color-primary-subtle)' }
                  : {}
              }
            >
              <div className="flex items-start justify-between mb-3">
                <Icon
                  className="w-7 h-7"
                  style={{ color: 'var(--mars-color-primary)' }}
                />
                <span
                  className={cn(
                    'text-xs font-medium px-2 py-0.5 rounded-full',
                    isSel ? 'text-white' : '',
                  )}
                  style={{
                    backgroundColor: isSel
                      ? 'var(--mars-color-primary)'
                      : 'var(--mars-color-surface-overlay)',
                    color: isSel ? '#fff' : 'var(--mars-color-text-secondary)',
                  }}
                >
                  {opp.valueCategory}
                </span>
              </div>
              <h3
                className="text-lg font-semibold mb-1"
                style={{ color: 'var(--mars-color-text)' }}
              >
                {opp.title}
              </h3>
              <p
                className="text-sm mb-3"
                style={{ color: 'var(--mars-color-text-secondary)' }}
              >
                {opp.explanation}
              </p>
              <div className="mb-3">
                <h4
                  className="font-semibold text-xs mb-1"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  KPIs Influenced
                </h4>
                <ul className="space-y-0.5">
                  {opp.kpis.map((kpi, idx) => (
                    <li
                      key={idx}
                      className="text-xs flex items-start gap-1"
                      style={{ color: 'var(--mars-color-text-secondary)' }}
                    >
                      <span style={{ color: 'var(--mars-color-primary)' }}>
                        •
                      </span>
                      {kpi}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4
                  className="font-semibold text-xs mb-1"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  Why Now
                </h4>
                <p
                  className="text-xs"
                  style={{ color: 'var(--mars-color-text-secondary)' }}
                >
                  {opp.whyNow}
                </p>
              </div>
              {isSel && (
                <div
                  className="mt-3 text-center text-xs font-medium py-1 rounded"
                  style={{
                    backgroundColor: 'var(--mars-color-success, #22c55e)',
                    color: '#fff',
                  }}
                >
                  Selected
                </div>
              )}
            </Card>
          )
        })}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 4 — SOLUTION ARCHETYPES
// ═══════════════════════════════════════════════════════════════════════════
function SolutionStep({
  opportunity,
  intakeData,
  initialData,
  selectedId,
  onComplete,
}: {
  opportunity: OpportunityArea
  intakeData: IntakeFormData
  initialData?: SolutionArchetype[]
  selectedId?: string
  onComplete: (archetypes: SolutionArchetype[], selectedId: string) => void
}) {
  const [loading, setLoading] = useState(!initialData)
  const [archetypes, setArchetypes] = useState<SolutionArchetype[]>(
    initialData ?? [],
  )
  const [selected, setSelected] = useState<string | null>(selectedId ?? null)
  const calledRef = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await generateSolutionArchetypes(opportunity, intakeData)
      setArchetypes(result)
      notify('Solution archetypes generated')
    } catch {
      notify('Failed to generate archetypes', 'error')
    } finally {
      setLoading(false)
    }
  }, [opportunity, intakeData])

  useEffect(() => {
    if (!initialData && !calledRef.current) {
      calledRef.current = true
      load()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSelect = (id: string) => {
    setSelected(id)
    onComplete(archetypes, id)
  }

  if (loading) return <Spinner label="Creating Solution Archetypes" />

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <StepHeader
        title="Solution Archetypes"
        subtitle="Select the solution approach that fits best"
        onRegenerate={load}
      />
      <div className="space-y-5">
        {archetypes.map((arch) => {
          const isSel = selected === arch.id
          return (
            <Card
              key={arch.id}
              className={cn(
                'p-5 cursor-pointer transition-all hover:shadow-md',
                isSel && 'ring-2',
              )}
              onClick={() => handleSelect(arch.id)}
              style={
                isSel
                  ? { borderColor: 'var(--mars-color-primary)', boxShadow: '0 0 0 2px var(--mars-color-primary-subtle)' }
                  : {}
              }
            >
              <div className="flex items-start justify-between mb-2">
                <Sparkles
                  className="w-7 h-7"
                  style={{ color: 'var(--mars-color-primary)' }}
                />
                {isSel && (
                  <span
                    className="text-xs font-medium px-2 py-0.5 rounded-full text-white"
                    style={{
                      backgroundColor: 'var(--mars-color-success, #22c55e)',
                    }}
                  >
                    Selected
                  </span>
                )}
              </div>
              <h3
                className="text-xl font-semibold mb-1"
                style={{ color: 'var(--mars-color-text)' }}
              >
                {arch.title}
              </h3>
              <p
                className="text-sm mb-4"
                style={{ color: 'var(--mars-color-text-secondary)' }}
              >
                {arch.summary}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h4
                    className="font-semibold text-sm mb-2"
                    style={{ color: 'var(--mars-color-text)' }}
                  >
                    Target Personas
                  </h4>
                  <ul className="space-y-1">
                    {arch.personas.map((p, idx) => (
                      <li
                        key={idx}
                        className="text-sm flex items-start gap-1"
                        style={{ color: 'var(--mars-color-text-secondary)' }}
                      >
                        <span style={{ color: 'var(--mars-color-primary)' }}>
                          •
                        </span>
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4
                    className="font-semibold text-sm mb-2"
                    style={{ color: 'var(--mars-color-text)' }}
                  >
                    Expected Benefits
                  </h4>
                  <ul className="space-y-1">
                    {arch.benefits.map((b, idx) => (
                      <li
                        key={idx}
                        className="text-sm flex items-start gap-1"
                        style={{ color: 'var(--mars-color-text-secondary)' }}
                      >
                        <span
                          style={{
                            color: 'var(--mars-color-success, #22c55e)',
                          }}
                        >
                          ✓
                        </span>
                        {b}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 5 — FEATURE SET BUILDER
// ═══════════════════════════════════════════════════════════════════════════
function FeatureStep({
  archetype,
  opportunity,
  intakeData,
  initialData,
  onComplete,
}: {
  archetype: SolutionArchetype
  opportunity: OpportunityArea
  intakeData: IntakeFormData
  initialData?: Feature[]
  onComplete: (features: Feature[]) => void
}) {
  const [loading, setLoading] = useState(!initialData)
  const [features, setFeatures] = useState<Feature[]>(initialData ?? [])
  const [showAdd, setShowAdd] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const calledRef = useRef(false)
  const [newFeat, setNewFeat] = useState({
    name: '',
    description: '',
    strategicGoal: '',
    userStories: [''],
    successMetrics: [''],
    bucket: '',
    priority: 'Should' as 'Must' | 'Should' | 'Could',
  })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await generateFeatures(archetype, opportunity, intakeData)
      setFeatures(result)
      onComplete(result)
      notify('Feature set generated')
    } catch {
      notify('Failed to generate features', 'error')
    } finally {
      setLoading(false)
    }
  }, [archetype, opportunity, intakeData, onComplete])

  useEffect(() => {
    if (!initialData && !calledRef.current) {
      calledRef.current = true
      load()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const toggle = (id: string) => {
    const updated = features.map((f) =>
      f.id === id ? { ...f, selected: !f.selected } : f,
    )
    setFeatures(updated)
    onComplete(updated)
  }

  const addCustom = () => {
    if (!newFeat.name || !newFeat.description || !newFeat.bucket) {
      notify('Fill in name, description, and bucket', 'error')
      return
    }
    const feat: Feature = {
      id: `custom-${Date.now()}`,
      ...newFeat,
      userStories: newFeat.userStories.filter((s) => s.trim()),
      successMetrics: newFeat.successMetrics.filter((m) => m.trim()),
      selected: true,
    }
    const updated = [...features, feat]
    setFeatures(updated)
    onComplete(updated)
    setNewFeat({
      name: '',
      description: '',
      strategicGoal: '',
      userStories: [''],
      successMetrics: [''],
      bucket: '',
      priority: 'Should',
    })
    setShowAdd(false)
    notify('Custom feature added')
  }

  const toggleExpand = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  if (loading) return <Spinner label="Building Feature Set" />

  const byBucket = features.reduce(
    (acc, f) => {
      ;(acc[f.bucket] ??= []).push(f)
      return acc
    },
    {} as Record<string, Feature[]>,
  )
  const selectedCount = features.filter((f) => f.selected).length
  const inputStyle: React.CSSProperties = {
    backgroundColor: 'var(--mars-color-surface)',
    borderColor: 'var(--mars-color-border)',
    color: 'var(--mars-color-text)',
  }

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2
            className="text-2xl font-bold"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Feature Set Builder
          </h2>
          <p
            className="text-sm mt-1"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            {selectedCount} feature{selectedCount !== 1 ? 's' : ''} selected
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium border rounded-md hover:opacity-80"
            style={{
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text-secondary)',
            }}
            onClick={() => setShowAdd(!showAdd)}
          >
            <Plus className="w-4 h-4" /> Add Custom
          </button>
          <button
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium border rounded-md hover:opacity-80"
            style={{
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text-secondary)',
            }}
            onClick={load}
          >
            <RefreshCw className="w-4 h-4" /> Regenerate
          </button>
        </div>
      </div>

      {/* Add custom feature form */}
      {showAdd && (
        <Card className="p-5 space-y-4">
          <h3
            className="text-base font-semibold"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Add Custom Feature
          </h3>
          <input
            className="w-full h-9 px-3 border rounded-md text-sm"
            style={inputStyle}
            placeholder="Feature name"
            value={newFeat.name}
            onChange={(e) => setNewFeat({ ...newFeat, name: e.target.value })}
          />
          <textarea
            className="w-full min-h-[60px] px-3 py-2 border rounded-md text-sm resize-y"
            style={inputStyle}
            placeholder="Feature description"
            value={newFeat.description}
            onChange={(e) =>
              setNewFeat({ ...newFeat, description: e.target.value })
            }
          />
          <textarea
            className="w-full min-h-[40px] px-3 py-2 border rounded-md text-sm resize-y"
            style={inputStyle}
            placeholder="Strategic Goal"
            value={newFeat.strategicGoal}
            onChange={(e) =>
              setNewFeat({ ...newFeat, strategicGoal: e.target.value })
            }
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input
              className="h-9 px-3 border rounded-md text-sm"
              style={inputStyle}
              placeholder="Bucket / Category"
              value={newFeat.bucket}
              onChange={(e) =>
                setNewFeat({ ...newFeat, bucket: e.target.value })
              }
            />
            <select
              className="h-9 px-3 border rounded-md text-sm"
              style={inputStyle}
              value={newFeat.priority}
              onChange={(e) =>
                setNewFeat({
                  ...newFeat,
                  priority: e.target.value as 'Must' | 'Should' | 'Could',
                })
              }
            >
              <option value="Must">Must</option>
              <option value="Should">Should</option>
              <option value="Could">Could</option>
            </select>
          </div>
          <button
            className="px-4 py-2 text-sm font-medium rounded-md text-white"
            style={{ backgroundColor: 'var(--mars-color-primary)' }}
            onClick={addCustom}
          >
            Add Feature
          </button>
        </Card>
      )}

      {/* Features by bucket */}
      <div className="space-y-5">
        {Object.entries(byBucket).map(([bucket, bFeatures]) => (
          <Card key={bucket} className="overflow-hidden">
            <div
              className="px-5 py-3 border-b"
              style={{ borderColor: 'var(--mars-color-border)' }}
            >
              <h3
                className="font-semibold"
                style={{ color: 'var(--mars-color-text)' }}
              >
                {bucket}
              </h3>
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--mars-color-border)' }}>
              {bFeatures.map((feat) => {
                const isExp = expanded.has(feat.id)
                return (
                  <div key={feat.id} className="hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                    <div className="flex items-start gap-3 px-5 py-3">
                      <input
                        type="checkbox"
                        checked={feat.selected}
                        onChange={() => toggle(feat.id)}
                        className="mt-1 rounded"
                      />
                      <div className="flex-1">
                        <p
                          className="text-sm font-semibold"
                          style={{ color: 'var(--mars-color-text)' }}
                        >
                          {feat.name}
                        </p>
                        <p
                          className="text-xs mt-0.5"
                          style={{
                            color: 'var(--mars-color-text-secondary)',
                          }}
                        >
                          {feat.description}
                        </p>
                      </div>
                      <span
                        className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0"
                        style={{
                          backgroundColor:
                            feat.priority === 'Must'
                              ? 'var(--mars-color-primary-subtle)'
                              : 'var(--mars-color-surface-overlay)',
                          color:
                            feat.priority === 'Must'
                              ? 'var(--mars-color-primary-text)'
                              : 'var(--mars-color-text-secondary)',
                        }}
                      >
                        {feat.priority}
                      </span>
                      <button
                        onClick={() => toggleExpand(feat.id)}
                        className="flex-shrink-0"
                        style={{ color: 'var(--mars-color-text-tertiary)' }}
                      >
                        {isExp ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    {isExp && (
                      <div
                        className="px-5 pb-4 space-y-3 border-t pt-3"
                        style={{ borderColor: 'var(--mars-color-border)' }}
                      >
                        <DetailList
                          icon={<Target className="w-4 h-4" />}
                          title="Strategic Goal"
                          items={[feat.strategicGoal]}
                        />
                        <DetailList
                          icon={<Users className="w-4 h-4" />}
                          title="User Stories"
                          items={feat.userStories}
                        />
                        <DetailList
                          icon={<TrendingUp className="w-4 h-4" />}
                          title="Success Metrics"
                          items={feat.successMetrics}
                        />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 6 — PROMPT GENERATOR
// ═══════════════════════════════════════════════════════════════════════════
function PromptStep({
  intakeData,
  opportunity,
  archetype,
  features,
  initialData,
  onComplete,
}: {
  intakeData: IntakeFormData
  opportunity: OpportunityArea
  archetype: SolutionArchetype
  features: Feature[]
  initialData?: { lovable: string; googleAI: string; general: string }
  onComplete: (prompts: {
    lovable: string
    googleAI: string
    general: string
  }) => void
}) {
  const [loading, setLoading] = useState(!initialData)
  const [prompts, setPrompts] = useState(
    initialData ?? { lovable: '', googleAI: '', general: '' },
  )
  const [activeTab, setActiveTab] = useState<'lovable' | 'googleAI' | 'general'>(
    'lovable',
  )
  const [copied, setCopied] = useState<string | null>(null)
  const selectedFeatures = features.filter((f) => f.selected)
  const calledRef = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await generatePrompts(
        intakeData,
        opportunity,
        archetype,
        selectedFeatures,
      )
      setPrompts(result)
      onComplete(result)
      notify('Prompts generated')
    } catch {
      notify('Failed to generate prompts', 'error')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intakeData, opportunity, archetype, selectedFeatures])

  useEffect(() => {
    if (!initialData && !calledRef.current) {
      calledRef.current = true
      load()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const copyPrompt = async (key: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(key)
      notify('Copied to clipboard')
      setTimeout(() => setCopied(null), 2000)
    } catch {
      notify('Failed to copy', 'error')
    }
  }

  if (loading) return <Spinner label="Generating Prompts" />

  const tabs: { key: 'lovable' | 'googleAI' | 'general'; label: string; desc: string }[] = [
    { key: 'lovable', label: 'Lovable', desc: "Optimized for Lovable's AI app builder" },
    { key: 'googleAI', label: 'Google AI Studio', desc: "Optimized for Google's Gemini model" },
    { key: 'general', label: 'General LLM', desc: 'Works with any LLM platform' },
  ]

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <StepHeader
        title="Prototype Prompts"
        subtitle="Ready-to-use prompts for different platforms"
        onRegenerate={load}
      />

      {/* Tab bar */}
      <div
        className="flex border-b"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              activeTab === tab.key
                ? 'border-current'
                : 'border-transparent hover:opacity-80',
            )}
            style={{
              color:
                activeTab === tab.key
                  ? 'var(--mars-color-primary)'
                  : 'var(--mars-color-text-secondary)',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active tab content */}
      {tabs
        .filter((t) => t.key === activeTab)
        .map((tab) => (
          <Card key={tab.key} className="p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3
                  className="font-semibold"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  {tab.label} Prompt
                </h3>
                <p
                  className="text-xs"
                  style={{ color: 'var(--mars-color-text-secondary)' }}
                >
                  {tab.desc}
                </p>
              </div>
              <button
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium border rounded-md hover:opacity-80"
                style={{
                  borderColor: 'var(--mars-color-border)',
                  color: 'var(--mars-color-text-secondary)',
                }}
                onClick={() => copyPrompt(tab.key, prompts[tab.key])}
              >
                {copied === tab.key ? (
                  <Check className="w-3.5 h-3.5" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
                Copy
              </button>
            </div>
            <pre
              className="text-sm whitespace-pre-wrap p-4 rounded-lg overflow-auto max-h-[500px]"
              style={{
                backgroundColor: 'var(--mars-color-surface-overlay)',
                color: 'var(--mars-color-text)',
              }}
            >
              {prompts[tab.key]}
            </pre>
          </Card>
        ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 7 — SLIDE GENERATOR
// ═══════════════════════════════════════════════════════════════════════════
interface SlideSection {
  title: string
  content: string
  number: number
}

function SlideStep({
  intakeData,
  research,
  problem,
  opportunity,
  archetype,
  features,
  initialData,
  onComplete,
}: {
  intakeData: IntakeFormData
  research: ResearchSummary
  problem: ProblemDefinition
  opportunity: OpportunityArea
  archetype: SolutionArchetype
  features: Feature[]
  initialData?: string
  onComplete: (content: string) => void
}) {
  const [loading, setLoading] = useState(!initialData)
  const [content, setContent] = useState(initialData ?? '')
  const [slides, setSlides] = useState<SlideSection[]>([])
  const [copied, setCopied] = useState(false)
  const calledRef = useRef(false)

  const selectedFeatures = features.filter((f) => f.selected)

  const parseSlides = (md: string): SlideSection[] => {
    const sections: SlideSection[] = []
    const lines = md.split('\n')
    let cur: SlideSection | null = null
    let num = 1
    for (const line of lines) {
      const m = line.match(/^##\s+(?:Slide\s+\d+:\s+)?(.+)$/)
      if (m) {
        if (cur) sections.push(cur)
        cur = { title: m[1].trim(), content: '', number: num++ }
      } else if (cur && line.trim()) {
        cur.content += line + '\n'
      }
    }
    if (cur) sections.push(cur)
    return sections
  }

  useEffect(() => {
    if (content) setSlides(parseSlides(content))
  }, [content])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const researchStr =
        typeof research === 'string' ? research : JSON.stringify(research)
      const problemStr =
        typeof problem === 'string'
          ? problem
          : (problem as any).problemStatement || JSON.stringify(problem)
      const result = await generateSlideContent(
        intakeData,
        researchStr,
        problemStr,
        opportunity,
        archetype,
        selectedFeatures,
      )
      setContent(result)
      onComplete(result)
      notify('Slide content generated')
    } catch {
      notify('Failed to generate slide content', 'error')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intakeData, research, problem, opportunity, archetype, selectedFeatures])

  useEffect(() => {
    if (!initialData && !calledRef.current) {
      calledRef.current = true
      load()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const copyAll = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      notify('Copied to clipboard')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      notify('Failed to copy', 'error')
    }
  }

  if (loading) return <Spinner label="Generating Slide Content" />

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2
            className="text-2xl font-bold"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Presentation Slides
          </h2>
          <p
            className="text-sm mt-1"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            {slides.length} slides ready for your presentation
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium border rounded-md hover:opacity-80"
            style={{
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text-secondary)',
            }}
            onClick={copyAll}
          >
            {copied ? (
              <Check className="w-4 h-4" />
            ) : (
              <Copy className="w-4 h-4" />
            )}
            Copy All
          </button>
          <button
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium border rounded-md hover:opacity-80"
            style={{
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text-secondary)',
            }}
            onClick={load}
          >
            <RefreshCw className="w-4 h-4" /> Regenerate
          </button>
        </div>
      </div>

      <div className="space-y-5">
        {slides.map((slide) => (
          <Card
            key={slide.number}
            className="overflow-hidden"
            style={{
              borderLeftWidth: '4px',
              borderLeftColor: 'var(--mars-color-primary)',
            }}
          >
            <div className="px-5 py-4">
              <div className="flex items-start gap-4 mb-3">
                <div
                  className="flex items-center justify-center w-10 h-10 rounded-full text-sm font-bold flex-shrink-0"
                  style={{
                    backgroundColor: 'var(--mars-color-primary-subtle)',
                    color: 'var(--mars-color-primary)',
                  }}
                >
                  {slide.number}
                </div>
                <div className="flex-1">
                  <h3
                    className="text-lg font-semibold"
                    style={{ color: 'var(--mars-color-text)' }}
                  >
                    {slide.title}
                  </h3>
                  <p
                    className="text-xs"
                    style={{ color: 'var(--mars-color-text-tertiary)' }}
                  >
                    Slide {slide.number} of {slides.length}
                  </p>
                </div>
                <button
                  className="flex-shrink-0"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                  onClick={() => {
                    navigator.clipboard.writeText(slide.content)
                    notify(`Copied "${slide.title}"`)
                  }}
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
              <div
                className="rounded-lg p-4 border"
                style={{
                  backgroundColor: 'var(--mars-color-surface-overlay)',
                  borderColor: 'var(--mars-color-border)',
                }}
              >
                <Md content={slide.content.trim()} />
              </div>
            </div>
          </Card>
        ))}
      </div>

      {slides.length === 0 && content && (
        <Card className="p-5">
          <h3
            className="font-semibold mb-2"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Raw Content
          </h3>
          <div
            className="rounded-lg p-4 overflow-auto max-h-[600px] border"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <Md content={content} />
          </div>
        </Card>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 8 — SUMMARY
// ═══════════════════════════════════════════════════════════════════════════
function SummaryStep({
  state,
  onReset,
}: {
  state: DiscoveryState
  onReset: () => void
}) {
  const [copied, setCopied] = useState<string | null>(null)

  const selectedOpportunity = state.opportunities.find(
    (o) => o.id === state.selectedOpportunity,
  )
  const selectedArchetype = state.solutionArchetypes.find(
    (a) => a.id === state.selectedArchetype,
  )
  const selectedFeatures = state.features.filter((f) => f.selected)

  const generateFullSummary = () => `# Product Discovery Summary

## Client Information
- **Client:** ${state.intakeData?.clientName}
- **Industry:** ${state.intakeData?.industry} - ${state.intakeData?.subIndustry}
- **Business Function:** ${state.intakeData?.businessFunction}
- **Discovery Type:** ${state.intakeData?.discoveryType}

## Problem Statement
${state.problemDefinition?.problemStatement || ''}

## Selected Opportunity
**${selectedOpportunity?.title}**
${selectedOpportunity?.explanation}
- **Value Category:** ${selectedOpportunity?.valueCategory}
- **Why Now:** ${selectedOpportunity?.whyNow}

## Solution Archetype
**${selectedArchetype?.title}**
${selectedArchetype?.summary}

## Selected Features (${selectedFeatures.length})
${selectedFeatures.map((f) => `- ${f.name} (${f.priority})`).join('\n')}

## Prototype Prompts
### Lovable
${state.prompts?.lovable || ''}

### Google AI Studio
${state.prompts?.googleAI || ''}

### General LLM
${state.prompts?.general || ''}

## Presentation Slides
${state.slideContent || ''}
`

  const handleCopy = async (key: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(key)
      notify('Copied to clipboard')
      setTimeout(() => setCopied(null), 2000)
    } catch {
      notify('Failed to copy', 'error')
    }
  }

  const CopyBtn = ({
    id,
    label,
    content,
  }: {
    id: string
    label: string
    content: string
  }) => (
    <button
      className="w-full flex items-center gap-2 px-3 py-2 text-sm border rounded-md hover:opacity-80 transition-colors"
      style={{
        borderColor: 'var(--mars-color-border)',
        color: 'var(--mars-color-text-secondary)',
      }}
      onClick={() => handleCopy(id, content)}
    >
      {copied === id ? (
        <Check className="w-4 h-4" />
      ) : (
        <Copy className="w-4 h-4" />
      )}
      {label}
    </button>
  )

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2
            className="text-2xl font-bold"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Discovery Complete!
          </h2>
          <p
            className="text-sm mt-1"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            Here's your comprehensive product discovery summary
          </p>
        </div>
        <button
          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium border rounded-md hover:opacity-80"
          style={{
            borderColor: 'var(--mars-color-border)',
            color: 'var(--mars-color-text-secondary)',
          }}
          onClick={onReset}
        >
          <RotateCcw className="w-4 h-4" /> New Session
        </button>
      </div>

      {/* Overview card */}
      <Card className="p-5 space-y-4">
        <h3
          className="font-semibold"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Session Overview
        </h3>
        <div>
          <span
            className="text-xs font-semibold"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            Client
          </span>
          <p style={{ color: 'var(--mars-color-text)' }}>
            {state.intakeData?.clientName}
          </p>
          <p
            className="text-sm"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            {state.intakeData?.industry} - {state.intakeData?.subIndustry} •{' '}
            {state.intakeData?.businessFunction}
          </p>
        </div>
        <hr style={{ borderColor: 'var(--mars-color-border)' }} />
        <div>
          <span
            className="text-xs font-semibold"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            Selected Opportunity
          </span>
          <div className="flex items-start gap-2 mt-1">
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: 'var(--mars-color-primary-subtle)',
                color: 'var(--mars-color-primary-text)',
              }}
            >
              {selectedOpportunity?.valueCategory}
            </span>
            <span
              className="text-sm"
              style={{ color: 'var(--mars-color-text)' }}
            >
              {selectedOpportunity?.title}
            </span>
          </div>
        </div>
        <hr style={{ borderColor: 'var(--mars-color-border)' }} />
        <div>
          <span
            className="text-xs font-semibold"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            Solution Archetype
          </span>
          <p
            className="text-sm mt-1"
            style={{ color: 'var(--mars-color-text)' }}
          >
            {selectedArchetype?.title}
          </p>
        </div>
        <hr style={{ borderColor: 'var(--mars-color-border)' }} />
        <div>
          <span
            className="text-xs font-semibold"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            Features
          </span>
          <p
            className="text-sm mt-1"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            {selectedFeatures.length} features selected
          </p>
        </div>
      </Card>

      {/* Action cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-5 space-y-3">
          <h3
            className="font-semibold"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Prototype Prompts
          </h3>
          <CopyBtn
            id="lovable"
            label="Copy Lovable Prompt"
            content={state.prompts?.lovable || ''}
          />
          <CopyBtn
            id="googleAI"
            label="Copy Google AI Prompt"
            content={state.prompts?.googleAI || ''}
          />
          <CopyBtn
            id="general"
            label="Copy General Prompt"
            content={state.prompts?.general || ''}
          />
        </Card>

        <Card className="p-5 space-y-3">
          <h3
            className="font-semibold"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Export Options
          </h3>
          <CopyBtn
            id="slides"
            label="Copy Slide Content"
            content={state.slideContent || ''}
          />
          <CopyBtn
            id="full"
            label="Copy Full Summary"
            content={generateFullSummary()}
          />
          <button
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md text-white"
            style={{ backgroundColor: 'var(--mars-color-primary)' }}
            onClick={() => {
              const blob = new Blob([generateFullSummary()], {
                type: 'text/markdown',
              })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `discovery-${state.intakeData?.clientName?.replace(/\s+/g, '-').toLowerCase()}.md`
              a.click()
              notify('Downloaded summary')
            }}
          >
            <Download className="w-4 h-4" />
            Download as Markdown
          </button>
        </Card>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// SHARED UI PRIMITIVES
// ═══════════════════════════════════════════════════════════════════════════

/** Field wrapper with label */
function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <label
        className="text-sm font-medium"
        style={{ color: 'var(--mars-color-text)' }}
      >
        {label}
      </label>
      {children}
    </div>
  )
}

/** Collapsible section with icon + title */
function CollapsibleSection({
  title,
  icon,
  children,
  defaultOpen = true,
}: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Card>
      <button
        className="w-full flex items-center justify-between px-5 py-3 hover:opacity-90 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-3">
          {icon}
          <span
            className="font-semibold text-sm"
            style={{ color: 'var(--mars-color-text)' }}
          >
            {title}
          </span>
        </div>
        <ChevronDown
          className={cn(
            'w-4 h-4 transition-transform',
            open && 'rotate-180',
          )}
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        />
      </button>
      {open && (
        <div
          className="px-5 pb-4"
          style={{ borderTop: '1px solid var(--mars-color-border)' }}
        >
          <div
            className="mt-3 rounded-lg p-4"
            style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
          >
            {children}
          </div>
        </div>
      )}
    </Card>
  )
}

/** Step header with title, subtitle, and regenerate button */
function StepHeader({
  title,
  subtitle,
  onRegenerate,
}: {
  title: string
  subtitle: string
  onRegenerate: () => void
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2
          className="text-2xl font-bold"
          style={{ color: 'var(--mars-color-text)' }}
        >
          {title}
        </h2>
        <p
          className="text-sm mt-1"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          {subtitle}
        </p>
      </div>
      <button
        className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium border rounded-md hover:opacity-80"
        style={{
          borderColor: 'var(--mars-color-border)',
          color: 'var(--mars-color-text-secondary)',
        }}
        onClick={onRegenerate}
      >
        <RefreshCw className="w-4 h-4" /> Regenerate
      </button>
    </div>
  )
}

/** Detail list with icon heading */
function DetailList({
  icon,
  title,
  items,
}: {
  icon: React.ReactNode
  title: string
  items: string[]
}) {
  return (
    <div>
      <div
        className="flex items-center gap-2 text-sm font-semibold mb-1"
        style={{ color: 'var(--mars-color-text)' }}
      >
        <span style={{ color: 'var(--mars-color-primary)' }}>{icon}</span>
        {title}
      </div>
      <ul className="pl-6 space-y-0.5">
        {items.map((item, idx) => (
          <li
            key={idx}
            className="text-sm"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            • {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
