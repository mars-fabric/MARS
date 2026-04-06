'use client'

/**
 * ProductDiscoveryTask — staged PDA wizard
 *
 * Architecture mirrors DeepResearch / NewsPulse:
 *   Step 0  Intake form  →  POST /api/pda/create  →  7 pending stages in DB
 *   Step 1  Research Summary       (background LLM + WS stream + HITL review)
 *   Step 2  Problem Definition     (background LLM + WS stream + HITL review)
 *   Step 3  Opportunity Areas      (background LLM + WS stream + select one)
 *   Step 4  Solution Archetypes    (background LLM + WS stream + select one)
 *   Step 5  Features               (background LLM + WS stream + select features)
 *   Step 6  Builder Prompts        (background LLM + WS stream + HITL review)
 *   Step 7  Slide Content          (background LLM + WS stream + view/download)
 *
 * Stage 0 (client-details) is a direct LLM call that auto-fills the intake form.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  ArrowLeft,
  ChevronRight,
  ChevronLeft,
  RefreshCw,
  Copy,
  Check,
  Download,
  Loader2,
  Sparkles,
  AlertCircle,
  Play,
  RotateCcw,
  Edit3,
  CheckSquare,
  Square,
  FileText,
  LayoutGrid,
  Maximize2,
  Minimize2,
  MessageSquare,
  Printer,
} from 'lucide-react'
import { Button } from '@/components/core'
import { usePdaTask } from '@/hooks/usePdaTask'
import { getClientDetails } from '@/lib/pda-api'

import type {
  IntakeFormData,
  OpportunityArea,
  SolutionArchetype,
  Feature,
  PdaWizardStep,
} from '@/types/pda'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEP_LABELS = [
  'Intake',
  'Research',
  'Problem',
  'Opportunities',
  'Solutions',
  'Features',
  'Prompts',
  'Slides',
]

const BUSINESS_FUNCTIONS = [
  'Store Ops', 'Supply Chain', 'Merchandising', 'E-commerce', 'HR',
  'Finance', 'Manufacturing', 'Marketing', 'Customer Service', 'R&D',
  'Data Analytics', 'IT Operations', 'Logistics', 'Sales', 'Product Management',
]

const DISCOVERY_TYPES = [
  'Problem', 'Opportunity', 'Pain Point', 'Capability', 'Open Discovery',
  'Process Optimization', 'Digital Transformation', 'Customer Experience',
  'Automation', 'Innovation',
]

const OUTPUT_OPTIONS = ['Prototype Prompt', 'Slides', 'Opportunity Pack', 'All']

const STAGE_NAME_MAP: Record<number, string> = {
  1: 'research_summary',
  2: 'problem_definition',
  3: 'opportunities',
  4: 'solution_archetypes',
  5: 'features',
  6: 'prompts',
  7: 'slide_content',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function cn(...classes: (string | boolean | undefined | null)[]) {
  return classes.filter(Boolean).join(' ')
}

function renderMarkdown(text: string): string {
  let html = text
  html = html.replace(/^---+$/gim, '<hr style="border:none;border-top:1px solid var(--mars-color-border,#e5e7eb);margin:20px 0" />')
  html = html.replace(/^#### (.*$)/gim, '<h4 style="font-size:0.875rem;font-weight:600;margin:12px 0 4px">$1</h4>')
  html = html.replace(/^### (.*$)/gim, '<h3 style="font-size:1rem;font-weight:700;margin:16px 0 6px;padding-bottom:4px;border-bottom:1px solid var(--mars-color-border,#e5e7eb)">$1</h3>')
  html = html.replace(/^## (.*$)/gim, '<h2 style="font-size:1.2rem;font-weight:800;margin:24px 0 8px;padding-bottom:6px;border-bottom:2px solid var(--mars-color-primary,#6366f1)">$1</h2>')
  html = html.replace(/^# (.*$)/gim, '<h1 style="font-size:1.5rem;font-weight:900;margin:28px 0 10px">$1</h1>')
  html = html.replace(/^\d+\. (.*$)/gim, '<li style="margin-left:20px;margin-bottom:6px;list-style-type:decimal">$1</li>')
  html = html.replace(/^[*-] (.*$)/gim, '<li style="margin-left:20px;margin-bottom:6px;list-style-type:disc">$1</li>')
  html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>')
  html = html.replace(/`([^`\n]+?)`/g, '<code style="background:var(--mars-color-surface-overlay,#f3f4f6);padding:1px 5px;border-radius:4px;font-family:monospace;font-size:0.85em">$1</code>')
  html = html.replace(/> (.*$)/gim, '<blockquote style="border-left:3px solid var(--mars-color-primary);padding-left:12px;color:var(--mars-color-text-secondary);margin:8px 0">$1</blockquote>')
  html = html.replace(/\n\n/g, '<br/><br/>')
  html = html.replace(/\n/g, '<br/>')
  return html
}

function Md({ content, className = '' }: { content: string; className?: string }) {
  return (
    <div
      className={`prose prose-sm max-w-none dark:prose-invert ${className}`}
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StageSpinner({ stageName, consoleOutput }: { stageName: string; consoleOutput: string[] }) {
  const consoleRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight
    }
  }, [consoleOutput])

  return (
    <div className="flex flex-col h-full">
      <div className="flex flex-col items-center justify-center py-10">
        <Loader2
          className="w-10 h-10 animate-spin mb-4"
          style={{ color: 'var(--mars-color-primary)' }}
        />
        <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--mars-color-text)' }}>
          Generating {stageName.replace(/_/g, ' ')}…
        </h3>
        <p className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
          AI is working — usually completes in under 2 minutes
        </p>
      </div>

      {consoleOutput.length > 0 && (
        <div
          ref={consoleRef}
          className="flex-1 overflow-y-auto rounded-lg p-4 font-mono text-xs"
          style={{
            background: 'var(--mars-color-surface-overlay, #0f172a)',
            color: '#86efac',
            maxHeight: '280px',
            border: '1px solid var(--mars-color-border)',
          }}
        >
          {consoleOutput.map((line, i) => (
            <div key={i} className="mb-0.5 leading-5">{line}</div>
          ))}
        </div>
      )}
    </div>
  )
}

function ReviewPanel({
  content,
  stageNum,
  stageName,
  onSave,
  onRefine,
}: {
  content: string
  stageNum: number
  stageName: string
  onSave: (content: string) => Promise<void>
  onRefine: (message: string, content: string) => Promise<string | null>
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(content)
  const [refineMsg, setRefineMsg] = useState('')
  const [isRefining, setIsRefining] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => { setDraft(content) }, [content])

  const handleSave = async () => {
    setIsSaving(true)
    await onSave(draft)
    setIsSaving(false)
    setEditing(false)
  }

  const handleRefine = async () => {
    if (!refineMsg.trim()) return
    setIsRefining(true)
    const refined = await onRefine(refineMsg, draft)
    if (refined) setDraft(refined)
    setRefineMsg('')
    setIsRefining(false)
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(draft)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-semibold text-base capitalize" style={{ color: 'var(--mars-color-text)' }}>
          {stageName.replace(/_/g, ' ')}
        </h3>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border"
            style={{
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text-secondary)',
            }}
          >
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            onClick={() => setEditing(!editing)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border"
            style={{
              borderColor: editing ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
              color: editing ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
            }}
          >
            <Edit3 className="w-3.5 h-3.5" />
            {editing ? 'Preview' : 'Edit'}
          </button>
          {editing && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Save'}
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <div
        className="flex-1 overflow-y-auto rounded-lg p-4"
        style={{
          background: 'var(--mars-color-surface)',
          border: '1px solid var(--mars-color-border)',
          minHeight: '300px',
        }}
      >
        {editing ? (
          <textarea
            value={draft}
            onChange={e => setDraft(e.target.value)}
            className="w-full h-full min-h-[300px] bg-transparent font-mono text-sm outline-none resize-none"
            style={{ color: 'var(--mars-color-text)' }}
          />
        ) : (
          <Md content={draft} />
        )}
      </div>

      {/* AI Refine */}
      <div
        className="flex gap-2 p-3 rounded-lg"
        style={{ background: 'var(--mars-color-surface-overlay, rgba(99,102,241,0.05))' }}
      >
        <Sparkles
          className="w-4 h-4 mt-0.5 flex-shrink-0"
          style={{ color: 'var(--mars-color-primary)' }}
        />
        <input
          type="text"
          placeholder="Ask AI to refine this content…"
          value={refineMsg}
          onChange={e => setRefineMsg(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleRefine()}
          className="flex-1 bg-transparent text-sm outline-none"
          style={{ color: 'var(--mars-color-text)' }}
          disabled={isRefining}
        />
        <Button
          variant="primary"
          size="sm"
          onClick={handleRefine}
          disabled={isRefining || !refineMsg.trim()}
        >
          {isRefining ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Refine'}
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// PromptsPanel — Stage 6: tabbed AI builder prompts
// ---------------------------------------------------------------------------

function PromptsPanel({
  content,
  onSave,
  onRefine,
}: {
  content: string
  onSave: (content: string) => Promise<void>
  onRefine: (message: string, content: string) => Promise<string | null>
}) {
  // Parse ## sections from the markdown
  const sections = React.useMemo(() => {
    const parts = content.split(/\n(?=## )/)
    return parts.map(part => {
      const lines = part.split('\n')
      const title = lines[0].replace(/^#+\s*/, '').trim()
      const body = lines.slice(1).join('\n').trim()
      return { title, body }
    }).filter(s => s.title && s.body)
  }, [content])

  const tabs = sections.length > 0 ? sections : [{ title: 'Content', body: content }]
  const [activeTab, setActiveTab] = useState(0)
  const [editing, setEditing] = useState(false)
  const [drafts, setDrafts] = useState<string[]>(() => tabs.map(t => t.body))
  const [refineMsg, setRefineMsg] = useState('')
  const [isRefining, setIsRefining] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => { setDrafts(tabs.map(t => t.body)) }, [content])

  const handleCopy = () => {
    navigator.clipboard.writeText(drafts[activeTab] || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSave = async () => {
    setIsSaving(true)
    const rebuilt = tabs.map((t, i) => `## ${t.title}\n${drafts[i]}`).join('\n\n')
    await onSave(rebuilt)
    setIsSaving(false)
    setEditing(false)
  }

  const handleRefine = async () => {
    if (!refineMsg.trim()) return
    setIsRefining(true)
    const refined = await onRefine(refineMsg, drafts[activeTab] || '')
    if (refined) setDrafts(prev => { const next = [...prev]; next[activeTab] = refined; return next })
    setRefineMsg('')
    setIsRefining(false)
  }

  const TAB_COLORS: Record<string, string> = {
    'lovable': '#a855f7',
    'bolt': '#f59e0b',
    'google': '#3b82f6',
    'general': '#22c55e',
  }
  const getTabColor = (title: string) => {
    const key = title.toLowerCase()
    if (key.includes('lovable')) return TAB_COLORS.lovable
    if (key.includes('bolt') || key.includes('stack')) return TAB_COLORS.bolt
    if (key.includes('google')) return TAB_COLORS.google
    return TAB_COLORS.general
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Tab bar */}
      <div className="flex gap-2 flex-wrap">
        {tabs.map((tab, i) => (
          <button
            key={i}
            onClick={() => { setActiveTab(i); setEditing(false) }}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all"
            style={{
              borderColor: activeTab === i ? getTabColor(tab.title) : 'var(--mars-color-border)',
              background: activeTab === i ? getTabColor(tab.title) + '18' : 'transparent',
              color: activeTab === i ? getTabColor(tab.title) : 'var(--mars-color-text-secondary)',
            }}
          >
            {tab.title.replace(/^(Lovable\.dev|Google AI Studio \/ Gemini|General Copilot \/ LLM|Bolt\.new \/ StackBlitz)\s*(Prompt)?/i, (_, g1) => g1 || tab.title)}
          </button>
        ))}
        <div className="ml-auto flex gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border"
            style={{ borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text-secondary)' }}
          >
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            onClick={() => setEditing(e => !e)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border"
            style={{
              borderColor: editing ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
              color: editing ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
            }}
          >
            <Edit3 className="w-3.5 h-3.5" />
            {editing ? 'Preview' : 'Edit'}
          </button>
          {editing && (
            <Button variant="primary" size="sm" onClick={handleSave} disabled={isSaving}>
              {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Save'}
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <div
        className="flex-1 overflow-y-auto rounded-lg p-4"
        style={{ background: 'var(--mars-color-surface)', border: '1px solid var(--mars-color-border)', minHeight: '300px' }}
      >
        {editing ? (
          <textarea
            value={drafts[activeTab] || ''}
            onChange={e => setDrafts(prev => { const next = [...prev]; next[activeTab] = e.target.value; return next })}
            className="w-full h-full min-h-[300px] bg-transparent font-mono text-sm outline-none resize-none"
            style={{ color: 'var(--mars-color-text)' }}
          />
        ) : (
          <div className="whitespace-pre-wrap text-sm" style={{ color: 'var(--mars-color-text)', fontFamily: 'monospace', lineHeight: '1.7' }}>
            {drafts[activeTab] || ''}
          </div>
        )}
      </div>

      {/* AI Refine */}
      <div className="flex gap-2 p-3 rounded-lg" style={{ background: 'var(--mars-color-surface-overlay, rgba(99,102,241,0.05))' }}>
        <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'var(--mars-color-primary)' }} />
        <input
          type="text"
          placeholder="Ask AI to refine this prompt…"
          value={refineMsg}
          onChange={e => setRefineMsg(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleRefine()}
          className="flex-1 bg-transparent text-sm outline-none"
          style={{ color: 'var(--mars-color-text)' }}
          disabled={isRefining}
        />
        <Button variant="primary" size="sm" onClick={handleRefine} disabled={isRefining || !refineMsg.trim()}>
          {isRefining ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Refine'}
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// SlidesPanel — Stage 7: slide viewer + PDF/Markdown export
// ---------------------------------------------------------------------------

interface ParsedSlide {
  number: number
  title: string
  bullets: string[]
  notes: string[]
  rawBullets: string
}

function parseSlidesFromMarkdown(md: string): ParsedSlide[] {
  if (!md) return []
  // Split on lines starting with ## (slide boundary)
  const chunks = md.split(/\n(?=## )/)
  const slides: ParsedSlide[] = []
  chunks.forEach((chunk, idx) => {
    const lines = chunk.split('\n')
    const titleLine = lines[0].replace(/^##\s*/, '').trim()
    if (!titleLine) return
    const bullets: string[] = []
    const notes: string[] = []
    lines.slice(1).forEach(line => {
      const stripped = line.trim()
      if (!stripped || stripped.startsWith('<!--')) return
      if (stripped.startsWith('> ')) notes.push(stripped.slice(2))
      else if (stripped.startsWith('>')) notes.push(stripped.slice(1).trim())
      else if (stripped.startsWith('- ')) bullets.push(stripped.slice(2))
      else if (stripped.startsWith('* ')) bullets.push(stripped.slice(2))
      else if (/^\d+\.\s/.test(stripped)) bullets.push(stripped.replace(/^\d+\.\s/, ''))
    })
    slides.push({
      number: idx + 1,
      title: titleLine,
      bullets,
      notes,
      rawBullets: bullets.join('\n'),
    })
  })
  return slides
}

function exportSlidesToPDF(slides: ParsedSlide[], clientName: string) {
  const escHtml = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const boldify = (s: string) => escHtml(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  const slidesHtml = slides.map(slide => `
    <div class="slide">
      <div class="slide-number">${slide.number} / ${slides.length}</div>
      <h1>${escHtml(slide.title)}</h1>
      <ul>
        ${slide.bullets.map(b => `<li>${boldify(b)}</li>`).join('')}
      </ul>
      ${slide.notes.length > 0 ? `
        <div class="notes">
          <div class="notes-label">Speaker Notes</div>
          ${slide.notes.map(n => `<div class="note">${boldify(n)}</div>`).join('')}
        </div>` : ''}
    </div>`).join('')

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>${escHtml(clientName)} — Product Discovery Presentation</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #fff; }
  .slide {
    width: 100%;
    min-height: 100vh;
    padding: 56px 72px;
    page-break-after: always;
    break-after: page;
    display: flex;
    flex-direction: column;
    border-bottom: 2px solid #f0f0f0;
    position: relative;
  }
  .slide:last-child { page-break-after: avoid; break-after: avoid; }
  .slide-number {
    position: absolute;
    top: 24px;
    right: 40px;
    font-size: 11px;
    color: #9ca3af;
    font-weight: 500;
  }
  h1 {
    font-size: 28px;
    font-weight: 800;
    color: #1e1b4b;
    margin-bottom: 28px;
    padding-bottom: 12px;
    border-bottom: 3px solid #6366f1;
    line-height: 1.3;
  }
  ul { list-style: none; flex: 1; }
  li {
    font-size: 15px;
    color: #374151;
    margin-bottom: 14px;
    padding-left: 20px;
    position: relative;
    line-height: 1.6;
  }
  li::before {
    content: '';
    position: absolute;
    left: 0;
    top: 9px;
    width: 8px;
    height: 8px;
    background: #6366f1;
    border-radius: 2px;
  }
  strong { color: #1e1b4b; font-weight: 700; }
  .notes {
    margin-top: 24px;
    padding: 12px 16px;
    background: #f8f7ff;
    border-left: 3px solid #6366f1;
    border-radius: 4px;
  }
  .notes-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6366f1;
    margin-bottom: 6px;
  }
  .note { font-size: 12px; color: #6b7280; line-height: 1.5; margin-bottom: 4px; }
  @media print {
    @page { size: A4 landscape; margin: 0; }
    .slide { min-height: 100vh; page-break-after: always; }
  }
</style>
</head>
<body>
${slidesHtml}
<script>
  window.onload = function() { window.print(); };
</script>
</body>
</html>`

  const blob = new Blob([html], { type: 'text/html' })
  const url = URL.createObjectURL(blob)
  const win = window.open(url, '_blank')
  if (win) {
    win.onafterprint = () => URL.revokeObjectURL(url)
  }
}

function SlidesPanel({
  content,
  clientName,
  onSave,
  onRefine,
}: {
  content: string
  clientName: string
  onSave: (content: string) => Promise<void>
  onRefine: (message: string, content: string) => Promise<string | null>
}) {
  const [draft, setDraft] = useState(content)
  const [slideIndex, setSlideIndex] = useState(0)
  const [showNotes, setShowNotes] = useState(true)
  const [viewMode, setViewMode] = useState<'presentation' | 'grid' | 'edit'>('presentation')
  const [refineMsg, setRefineMsg] = useState('')
  const [isRefining, setIsRefining] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => { setDraft(content); setSlideIndex(0) }, [content])

  const slides = React.useMemo(() => parseSlidesFromMarkdown(draft), [draft])
  const slide = slides[slideIndex]
  const total = slides.length

  const handleSave = async () => {
    setIsSaving(true)
    await onSave(draft)
    setIsSaving(false)
    setViewMode('presentation')
  }

  const handleRefine = async () => {
    if (!refineMsg.trim()) return
    setIsRefining(true)
    const refined = await onRefine(refineMsg, draft)
    if (refined) setDraft(refined)
    setRefineMsg('')
    setIsRefining(false)
  }

  const handleCopySlide = () => {
    if (!slide) return
    const text = `${slide.title}\n\n${slide.bullets.map(b => `• ${b}`).join('\n')}`
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExportMd = () => {
    const blob = new Blob([draft], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${clientName.replace(/\s+/g, '-').toLowerCase() || 'pda'}-slides.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── toolbar ──────────────────────────────────────────────────────────────
  const toolbar = (
    <div className="flex items-center justify-between flex-wrap gap-2 flex-shrink-0">
      <div className="flex items-center gap-2">
        {/* View mode switchers */}
        {(['presentation', 'grid', 'edit'] as const).map(mode => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border"
            style={{
              borderColor: viewMode === mode ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
              color: viewMode === mode ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
              background: viewMode === mode ? 'rgba(99,102,241,0.07)' : 'transparent',
            }}
            title={mode === 'presentation' ? 'Slide view' : mode === 'grid' ? 'Grid view' : 'Edit mode'}
          >
            {mode === 'presentation' && <Maximize2 className="w-3.5 h-3.5" />}
            {mode === 'grid' && <LayoutGrid className="w-3.5 h-3.5" />}
            {mode === 'edit' && <Edit3 className="w-3.5 h-3.5" />}
            <span className="capitalize">{mode}</span>
          </button>
        ))}
        {viewMode === 'presentation' && (
          <button
            onClick={() => setShowNotes(n => !n)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border"
            style={{
              borderColor: showNotes ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
              color: showNotes ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
              background: showNotes ? 'rgba(99,102,241,0.07)' : 'transparent',
            }}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            Notes
          </button>
        )}
      </div>

      <div className="flex items-center gap-2">
        {viewMode === 'edit' && (
          <Button variant="primary" size="sm" onClick={handleSave} disabled={isSaving}>
            {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Save'}
          </Button>
        )}
        <button
          onClick={handleCopySlide}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border"
          style={{ borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text-secondary)' }}
          title="Copy current slide"
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
        <button
          onClick={handleExportMd}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border"
          style={{ borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text-secondary)' }}
          title="Export as Markdown"
        >
          <FileText className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">MD</span>
        </button>
        <button
          onClick={() => exportSlidesToPDF(slides, clientName)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold border"
          style={{ borderColor: '#6366f1', color: '#6366f1', background: 'rgba(99,102,241,0.07)' }}
          title="Export as PDF"
        >
          <Printer className="w-3.5 h-3.5" />
          <span>PDF</span>
        </button>
      </div>
    </div>
  )

  // ── edit mode ─────────────────────────────────────────────────────────────
  if (viewMode === 'edit') {
    return (
      <div className="flex flex-col gap-4 h-full">
        {toolbar}
        <textarea
          value={draft}
          onChange={e => setDraft(e.target.value)}
          className="flex-1 rounded-lg p-4 font-mono text-sm outline-none resize-none"
          style={{
            background: 'var(--mars-color-surface)',
            border: '1px solid var(--mars-color-border)',
            color: 'var(--mars-color-text)',
            minHeight: '400px',
          }}
        />
        <div className="flex gap-2 p-3 rounded-lg" style={{ background: 'var(--mars-color-surface-overlay, rgba(99,102,241,0.05))' }}>
          <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'var(--mars-color-primary)' }} />
          <input
            type="text"
            placeholder="Ask AI to refine the slides content…"
            value={refineMsg}
            onChange={e => setRefineMsg(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleRefine()}
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--mars-color-text)' }}
            disabled={isRefining}
          />
          <Button variant="primary" size="sm" onClick={handleRefine} disabled={isRefining || !refineMsg.trim()}>
            {isRefining ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Refine'}
          </Button>
        </div>
      </div>
    )
  }

  // ── grid mode ─────────────────────────────────────────────────────────────
  if (viewMode === 'grid') {
    return (
      <div className="flex flex-col gap-4 h-full overflow-hidden">
        {toolbar}
        <p className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>
          {total} slides — click a slide to jump to presentation view
        </p>
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {slides.map((s, i) => (
              <button
                key={i}
                onClick={() => { setSlideIndex(i); setViewMode('presentation') }}
                className="text-left rounded-xl border p-3 transition-all hover:shadow-md"
                style={{
                  borderColor: slideIndex === i ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
                  background: slideIndex === i ? 'rgba(99,102,241,0.06)' : 'var(--mars-color-surface)',
                }}
              >
                <div className="text-[10px] font-bold mb-1" style={{ color: 'var(--mars-color-primary)' }}>
                  {s.number}
                </div>
                <div className="text-xs font-semibold mb-1.5 line-clamp-2" style={{ color: 'var(--mars-color-text)' }}>
                  {s.title}
                </div>
                <ul className="space-y-0.5">
                  {s.bullets.slice(0, 3).map((b, j) => (
                    <li key={j} className="text-[10px] line-clamp-1" style={{ color: 'var(--mars-color-text-secondary)' }}>
                      • {b}
                    </li>
                  ))}
                  {s.bullets.length > 3 && (
                    <li className="text-[10px]" style={{ color: 'var(--mars-color-primary)' }}>
                      +{s.bullets.length - 3} more
                    </li>
                  )}
                </ul>
              </button>
            ))}
          </div>
        </div>
        {/* refine bar */}
        <div className="flex gap-2 p-3 rounded-lg flex-shrink-0" style={{ background: 'var(--mars-color-surface-overlay, rgba(99,102,241,0.05))' }}>
          <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'var(--mars-color-primary)' }} />
          <input
            type="text"
            placeholder="Ask AI to refine the deck…"
            value={refineMsg}
            onChange={e => setRefineMsg(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleRefine()}
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--mars-color-text)' }}
            disabled={isRefining}
          />
          <Button variant="primary" size="sm" onClick={handleRefine} disabled={isRefining || !refineMsg.trim()}>
            {isRefining ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Refine'}
          </Button>
        </div>
      </div>
    )
  }

  // ── presentation mode ─────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-3 h-full overflow-hidden">
      {toolbar}

      {/* Slide navigation strip */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <button
          onClick={() => setSlideIndex(i => Math.max(0, i - 1))}
          disabled={slideIndex === 0}
          className="p-1.5 rounded-lg border disabled:opacity-30"
          style={{ borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
          {total > 0 ? `Slide ${slideIndex + 1} of ${total}` : 'No slides'}
        </span>
        <button
          onClick={() => setSlideIndex(i => Math.min(total - 1, i + 1))}
          disabled={slideIndex >= total - 1}
          className="p-1.5 rounded-lg border disabled:opacity-30"
          style={{ borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        {/* progress dots — max 10 shown */}
        <div className="flex gap-1 overflow-hidden">
          {slides.slice(0, 20).map((_, i) => (
            <button
              key={i}
              onClick={() => setSlideIndex(i)}
              className="rounded-full transition-all flex-shrink-0"
              style={{
                width: i === slideIndex ? 20 : 6,
                height: 6,
                background: i === slideIndex ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
              }}
            />
          ))}
          {total > 20 && <span className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>…</span>}
        </div>
      </div>

      {/* Slide card */}
      {slide ? (
        <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0">
          <div
            className="rounded-2xl p-6 flex-shrink-0"
            style={{
              background: 'var(--mars-color-surface)',
              border: '1px solid var(--mars-color-border)',
              boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
            }}
          >
            {/* Slide header */}
            <div className="flex items-start justify-between mb-4 gap-3">
              <h2 className="text-base font-bold leading-tight" style={{ color: 'var(--mars-color-text)' }}>
                {slide.title}
              </h2>
              <span
                className="text-xs px-2 py-0.5 rounded-full flex-shrink-0 font-semibold"
                style={{ background: 'rgba(99,102,241,0.12)', color: 'var(--mars-color-primary)' }}
              >
                {slide.number}/{total}
              </span>
            </div>
            {/* Bullets */}
            <ul className="space-y-2.5">
              {slide.bullets.map((b, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm" style={{ color: 'var(--mars-color-text)' }}>
                  <span
                    className="w-5 h-5 rounded flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
                    style={{ background: 'rgba(99,102,241,0.12)', color: 'var(--mars-color-primary)' }}
                  >
                    {i + 1}
                  </span>
                  <span
                    dangerouslySetInnerHTML={{
                      __html: b.replace(/\*\*(.+?)\*\*/g, '<strong style="color:var(--mars-color-text)">$1</strong>')
                    }}
                  />
                </li>
              ))}
            </ul>
          </div>

          {/* Speaker notes */}
          {showNotes && slide.notes.length > 0 && (
            <div
              className="rounded-xl p-4 flex-shrink-0"
              style={{
                background: 'rgba(99,102,241,0.04)',
                border: '1px solid rgba(99,102,241,0.2)',
              }}
            >
              <div className="flex items-center gap-1.5 mb-2">
                <MessageSquare className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-primary)' }} />
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--mars-color-primary)' }}>
                  Speaker Notes
                </span>
              </div>
              <div className="space-y-1.5">
                {slide.notes.map((n, i) => (
                  <p key={i} className="text-xs leading-relaxed" style={{ color: 'var(--mars-color-text-secondary)' }}>
                    {n}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* refine bar */}
          <div className="flex gap-2 p-3 rounded-lg flex-shrink-0" style={{ background: 'var(--mars-color-surface-overlay, rgba(99,102,241,0.05))' }}>
            <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'var(--mars-color-primary)' }} />
            <input
              type="text"
              placeholder="Ask AI to refine this slide or the whole deck…"
              value={refineMsg}
              onChange={e => setRefineMsg(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleRefine()}
              className="flex-1 bg-transparent text-sm outline-none"
              style={{ color: 'var(--mars-color-text)' }}
              disabled={isRefining}
            />
            <Button variant="primary" size="sm" onClick={handleRefine} disabled={isRefining || !refineMsg.trim()}>
              {isRefining ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Refine'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
            No slides parsed yet — the content may still be generating.
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ProductDiscoveryTaskProps {
  onBack: () => void
  resumeTaskId?: string | null
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function ProductDiscoveryTask({ onBack, resumeTaskId }: ProductDiscoveryTaskProps) {
  const hook = usePdaTask()

  // Intake form state
  const [intake, setIntake] = useState<IntakeFormData>({
    clientName: '',
    industry: '',
    subIndustry: '',
    clientContext: '',
    businessFunction: '',
    discoveryType: '',
    processType: 'new',
    existingFunctionality: '',
    problemKeywords: '',
    expectedOutput: [],
    researchMode: 'one_shot',
  })
  const [isDetecting, setIsDetecting] = useState(false)
  const [detectError, setDetectError] = useState<string | null>(null)

  // Per-stage content cache — managed by hook (populated on resume + after fetch)

  // User selections (needed as inputData for stages 4, 5, 6)
  const [selectedOpportunity, setSelectedOpportunity] = useState<OpportunityArea | null>(null)
  const [selectedArchetype, setSelectedArchetype] = useState<SolutionArchetype | null>(null)
  const [selectedFeatures, setSelectedFeatures] = useState<Feature[]>([])

  // Parsed structured data per stage (from shared_state)
  const [opportunities, setOpportunities] = useState<OpportunityArea[]>([])
  const [archetypes, setArchetypes] = useState<SolutionArchetype[]>([])
  const [features, setFeatures] = useState<Feature[]>([])

  const { currentStep, setCurrentStep, taskId, taskState, isExecuting, consoleOutput,
          error, isLoading, fetchStageContent, saveStageContent, refineContent,
          executeStage, createTask, resumeTask, stageContents, setStageContent } = hook

  // Track which stages we've already fetched content for (prevents infinite re-fetch when
  // content is empty string, and ensures structured data is populated after resume)
  const fetchedStagesRef = useRef(new Set<number>())

  // Resume from a previous session on mount
  useEffect(() => {
    if (resumeTaskId) {
      resumeTask(resumeTaskId)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeTaskId])

  // ---------------------------------------------------------------------------
  // Stage 0 — Auto-detect client details
  // ---------------------------------------------------------------------------

  const handleDetectClient = useCallback(async () => {
    if (!intake.clientName.trim()) return
    setIsDetecting(true)
    setDetectError(null)
    try {
      const details = await getClientDetails(intake.clientName)
      setIntake(prev => ({
        ...prev,
        industry: details.industry || prev.industry,
        subIndustry: details.subIndustry || prev.subIndustry,
        clientContext: details.clientContext || prev.clientContext,
        businessFunction: details.businessFunctions?.[0] || prev.businessFunction,
        discoveryType: details.suggestedDiscoveryTypes?.[0] || prev.discoveryType,
        problemKeywords: details.problemKeywords || prev.problemKeywords,
      }))
    } catch (e: unknown) {
      setDetectError(e instanceof Error ? e.message : 'Detection failed')
    } finally {
      setIsDetecting(false)
    }
  }, [intake.clientName])

  // ---------------------------------------------------------------------------
  // Start wizard — create task + execute stage 1
  // ---------------------------------------------------------------------------

  const handleStart = useCallback(async () => {
    const id = await createTask(intake)
    if (!id) return
    setCurrentStep(1)
    await executeStage(1, {}, id)
  }, [createTask, intake, executeStage, setCurrentStep])

  // ---------------------------------------------------------------------------
  // Load stage content when step changes or stage completes
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!taskId || currentStep < 1) return
    const stageNum = currentStep as number

    // Check if stage is completed
    const stage = taskState?.stages.find(s => s.stage_number === stageNum)
    if (stage?.status !== 'completed') return

    // Use a ref-based guard (not state) to prevent infinite loops when content is empty
    // and to ensure structured data is always extracted (including after resume)
    if (fetchedStagesRef.current.has(stageNum)) return
    fetchedStagesRef.current.add(stageNum)

    fetchStageContent(stageNum).then(content => {
      if (!content) return

      // Set text content (may be empty string if backend had no file)
      if (content.content) setStageContent(stageNum, content.content)

      // Always extract structured data for selection stages, even if content is empty
      if (stageNum === 3 && content.shared_state?.opportunities) {
        const opps = content.shared_state.opportunities
        setOpportunities(Array.isArray(opps) ? opps as OpportunityArea[] : [])
      }
      if (stageNum === 4 && content.shared_state?.solution_archetypes) {
        const archs = content.shared_state.solution_archetypes
        setArchetypes(Array.isArray(archs) ? archs as SolutionArchetype[] : [])
      }
      if (stageNum === 5 && content.shared_state?.features) {
        const feats = content.shared_state.features
        setFeatures(Array.isArray(feats) ? feats as Feature[] : [])
        setSelectedFeatures(
          (Array.isArray(feats) ? feats as Feature[] : []).filter(f => f.selected !== false)
        )
      }
    })
  // stageContents intentionally excluded — fetchedStagesRef is the guard
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, taskId, taskState, fetchStageContent])

  // ---------------------------------------------------------------------------
  // Navigation between steps
  // ---------------------------------------------------------------------------

  const canAdvance = useCallback((): boolean => {
    const stageNum = currentStep as number
    if (stageNum === 0) {
      return !!(
        intake.clientName && intake.industry && intake.subIndustry &&
        intake.clientContext && intake.businessFunction && intake.discoveryType &&
        intake.problemKeywords && intake.expectedOutput.length > 0
      )
    }
    const stage = taskState?.stages.find(s => s.stage_number === stageNum)
    if (!stage || stage.status !== 'completed') return false
    if (stageNum === 3) return !!selectedOpportunity
    if (stageNum === 4) return !!selectedArchetype
    if (stageNum === 5) return selectedFeatures.length > 0
    return true
  }, [currentStep, intake, taskState, selectedOpportunity, selectedArchetype, selectedFeatures])

  const handleNext = useCallback(async () => {
    if (!canAdvance() || isExecuting) return
    const nextStep = (currentStep + 1) as PdaWizardStep

    setCurrentStep(nextStep)

    // If next stage is already completed, just navigate — no need to re-execute
    const nextStageInfo = taskState?.stages.find(s => s.stage_number === nextStep)
    if (nextStageInfo?.status === 'completed') return

    // Execute the next stage with selections as input_data
    const inputData: Record<string, unknown> = {}
    if (currentStep === 3 && selectedOpportunity) {
      inputData.selected_opportunity = selectedOpportunity
    } else if (currentStep === 4 && selectedArchetype) {
      inputData.selected_archetype = selectedArchetype
      inputData.selected_opportunity = selectedOpportunity
    } else if (currentStep === 5) {
      inputData.selected_features = selectedFeatures
      inputData.selected_archetype = selectedArchetype
      inputData.selected_opportunity = selectedOpportunity
    }

    if (nextStep >= 1 && nextStep <= 7) {
      await executeStage(nextStep, inputData)
    }
  }, [
    canAdvance, isExecuting, currentStep, taskState, executeStage, setCurrentStep,
    selectedOpportunity, selectedArchetype, selectedFeatures,
  ])

  const handleRerun = useCallback(async () => {
    if (!taskId || isExecuting) return
    const stageNum = currentStep as number
    if (stageNum < 1 || stageNum > 7) return

    const inputData: Record<string, unknown> = {}
    if (selectedOpportunity) inputData.selected_opportunity = selectedOpportunity
    if (selectedArchetype) inputData.selected_archetype = selectedArchetype
    if (selectedFeatures.length > 0) inputData.selected_features = selectedFeatures

    setStageContent(stageNum, '')  // clear content cache so it reloads after rerun
    fetchedStagesRef.current.delete(stageNum)  // allow re-fetch after new execution
    // Also clear downstream structured data when re-running upstream stages
    if (stageNum <= 3) { setOpportunities([]); setSelectedOpportunity(null) }
    if (stageNum <= 4) { setArchetypes([]); setSelectedArchetype(null) }
    if (stageNum <= 5) { setFeatures([]); setSelectedFeatures([]) }
    await executeStage(stageNum, inputData)
  }, [taskId, isExecuting, currentStep, executeStage, selectedOpportunity, selectedArchetype, selectedFeatures, setStageContent])

  const handleSaveContent = useCallback(async (content: string) => {
    const stageNum = currentStep as number
    const field = STAGE_NAME_MAP[stageNum] || 'content'
    await saveStageContent(stageNum, content, field)
    setStageContent(stageNum, content)
  }, [currentStep, saveStageContent, setStageContent])

  const handleRefineContent = useCallback(async (
    message: string, content: string
  ) => {
    const stageNum = currentStep as number
    return refineContent(stageNum, message, content)
  }, [currentStep, refineContent])

  // ---------------------------------------------------------------------------
  // Feature toggle
  // ---------------------------------------------------------------------------

  const toggleFeature = useCallback((feat: Feature) => {
    setSelectedFeatures(prev => {
      const exists = prev.find(f => f.id === feat.id)
      return exists ? prev.filter(f => f.id !== feat.id) : [...prev, feat]
    })
  }, [])

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  const getStageStatus = (num: number) =>
    taskState?.stages.find(s => s.stage_number === num)?.status ?? 'pending'

  // ---------------------------------------------------------------------------
  // Render: Step 0 — Intake form
  // ---------------------------------------------------------------------------

  const renderIntake = () => (
    <div className="max-w-3xl mx-auto space-y-6 p-6">
      <div>
        <h2 className="text-xl font-bold mb-1" style={{ color: 'var(--mars-color-text)' }}>
          Product Discovery Setup
        </h2>
        <p className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
          Fill in the intake form. Type a client name and click "Auto-Detect" to pre-fill fields.
        </p>
      </div>

      {detectError && (
        <div
          className="flex items-center gap-2 p-3 rounded-lg text-sm"
          style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}
        >
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {detectError}
        </div>
      )}

      {/* Client name + auto-detect */}
      <div>
        <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--mars-color-text)' }}>
          Client / Company Name *
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={intake.clientName}
            onChange={e => setIntake(p => ({ ...p, clientName: e.target.value }))}
            placeholder="e.g. Walmart, HSBC, Siemens"
            className="flex-1 px-3 py-2 rounded-lg border text-sm outline-none"
            style={{
              background: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
            onKeyDown={e => e.key === 'Enter' && handleDetectClient()}
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDetectClient}
            disabled={isDetecting || !intake.clientName.trim()}
          >
            {isDetecting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <><Sparkles className="w-4 h-4 mr-1" /> Auto-Detect</>
            )}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Industry */}
        <div>
          <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--mars-color-text)' }}>
            Industry *
          </label>
          <input
            type="text"
            value={intake.industry}
            onChange={e => setIntake(p => ({ ...p, industry: e.target.value }))}
            placeholder="e.g. Retail, Healthcare"
            className="w-full px-3 py-2 rounded-lg border text-sm outline-none"
            style={{
              background: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
          />
        </div>

        {/* Sub-industry */}
        <div>
          <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--mars-color-text)' }}>
            Sub-Industry *
          </label>
          <input
            type="text"
            value={intake.subIndustry}
            onChange={e => setIntake(p => ({ ...p, subIndustry: e.target.value }))}
            placeholder="e.g. Fashion Retail"
            className="w-full px-3 py-2 rounded-lg border text-sm outline-none"
            style={{
              background: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
          />
        </div>
      </div>

      {/* Client context */}
      <div>
        <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--mars-color-text)' }}>
          Client Context *
        </label>
        <textarea
          value={intake.clientContext}
          onChange={e => setIntake(p => ({ ...p, clientContext: e.target.value }))}
          placeholder="Describe the client's current situation, challenges, and goals…"
          rows={4}
          className="w-full px-3 py-2 rounded-lg border text-sm outline-none resize-none"
          style={{
            background: 'var(--mars-color-surface)',
            borderColor: 'var(--mars-color-border)',
            color: 'var(--mars-color-text)',
          }}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Business function */}
        <div>
          <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--mars-color-text)' }}>
            Business Function *
          </label>
          <select
            value={intake.businessFunction}
            onChange={e => setIntake(p => ({ ...p, businessFunction: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border text-sm outline-none"
            style={{
              background: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
          >
            <option value="">Select function…</option>
            {BUSINESS_FUNCTIONS.map(f => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>

        {/* Discovery type */}
        <div>
          <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--mars-color-text)' }}>
            Discovery Type *
          </label>
          <select
            value={intake.discoveryType}
            onChange={e => setIntake(p => ({ ...p, discoveryType: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border text-sm outline-none"
            style={{
              background: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
          >
            <option value="">Select type…</option>
            {DISCOVERY_TYPES.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Problem keywords */}
      <div>
        <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--mars-color-text)' }}>
          Problem Keywords *
        </label>
        <input
          type="text"
          value={intake.problemKeywords}
          onChange={e => setIntake(p => ({ ...p, problemKeywords: e.target.value }))}
          placeholder="e.g. inventory, stockouts, demand forecasting"
          className="w-full px-3 py-2 rounded-lg border text-sm outline-none"
          style={{
            background: 'var(--mars-color-surface)',
            borderColor: 'var(--mars-color-border)',
            color: 'var(--mars-color-text)',
          }}
        />
      </div>

      {/* Process type */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--mars-color-text)' }}>
          Process Type
        </label>
        <div className="flex gap-3">
          {(['new', 'existing'] as const).map(pt => (
            <button
              key={pt}
              onClick={() => setIntake(p => ({ ...p, processType: pt }))}
              className="px-4 py-2 rounded-lg border text-sm font-medium transition-colors"
              style={{
                background: intake.processType === pt ? 'var(--mars-color-primary)' : 'var(--mars-color-surface)',
                borderColor: intake.processType === pt ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
                color: intake.processType === pt ? '#fff' : 'var(--mars-color-text)',
              }}
            >
              {pt === 'new' ? 'New Product' : 'Existing Feature'}
            </button>
          ))}
        </div>
      </div>

      {intake.processType === 'existing' && (
        <div>
          <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--mars-color-text)' }}>
            Existing Functionality
          </label>
          <textarea
            value={intake.existingFunctionality}
            onChange={e => setIntake(p => ({ ...p, existingFunctionality: e.target.value }))}
            placeholder="Describe current capabilities…"
            rows={3}
            className="w-full px-3 py-2 rounded-lg border text-sm outline-none resize-none"
            style={{
              background: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
          />
        </div>
      )}

      {/* Expected outputs */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--mars-color-text)' }}>
          Expected Outputs *
        </label>
        <div className="flex flex-wrap gap-2">
          {OUTPUT_OPTIONS.map(opt => {
            const selected = intake.expectedOutput.includes(opt)
            return (
              <button
                key={opt}
                onClick={() =>
                  setIntake(p => ({
                    ...p,
                    expectedOutput: selected
                      ? p.expectedOutput.filter(x => x !== opt)
                      : [...p.expectedOutput, opt],
                  }))
                }
                className="px-3 py-1.5 rounded-full border text-sm font-medium transition-colors"
                style={{
                  background: selected ? 'var(--mars-color-primary)' : 'transparent',
                  borderColor: selected ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
                  color: selected ? '#fff' : 'var(--mars-color-text-secondary)',
                }}
              >
                {opt}
              </button>
            )
          })}
        </div>
      </div>

      {/* Research mode selector */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--mars-color-text)' }}>
          Research Mode
        </label>
        <p className="text-xs mb-3" style={{ color: 'var(--mars-color-text-secondary)' }}>
          Choose how Stage 1 (Market Research) should be executed.
        </p>
        <div className="grid grid-cols-2 gap-3">
          {([
            {
              value: 'one_shot',
              label: 'One-Shot (Fast)',
              desc: 'Single researcher pass with web search. Faster, good for most cases.',
            },
            {
              value: 'planning_and_control',
              label: 'Deep Research',
              desc: 'Multi-step planner + researcher pipeline. More thorough, takes longer.',
            },
          ] as const).map(mode => (
            <button
              key={mode.value}
              onClick={() => setIntake(p => ({ ...p, researchMode: mode.value }))}
              className="flex flex-col items-start gap-1 p-3 rounded-lg border text-left transition-colors"
              style={{
                background: intake.researchMode === mode.value
                  ? 'var(--mars-color-primary-subtle, rgba(99,102,241,0.1))'
                  : 'transparent',
                borderColor: intake.researchMode === mode.value
                  ? 'var(--mars-color-primary)'
                  : 'var(--mars-color-border)',
                color: 'var(--mars-color-text)',
              }}
            >
              <span className="text-sm font-semibold">{mode.label}</span>
              <span className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>
                {mode.desc}
              </span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      <Button
        variant="primary"
        size="lg"
        onClick={handleStart}
        disabled={!canAdvance() || isLoading}
        className="w-full"
      >
        {isLoading ? (
          <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating session…</>
        ) : (
          <><Play className="w-4 h-4 mr-2" /> Start Product Discovery</>
        )}
      </Button>
    </div>
  )

  // ---------------------------------------------------------------------------
  // Render: Stages 1-7
  // ---------------------------------------------------------------------------

  const renderStageView = () => {
    const stageNum = currentStep as number
    const status = getStageStatus(stageNum)
    const content = stageContents[stageNum] ?? ''
    const stageName = STAGE_NAME_MAP[stageNum] ?? `stage_${stageNum}`

    // Running or actively executing — show spinner with console output
    if (status === 'running' || (isExecuting && !content)) {
      return (
        <StageSpinner
          stageName={stageName}
          consoleOutput={consoleOutput}
        />
      )
    }

    // Stage completed but content not yet fetched from API (brief transition state)
    if (status === 'completed' && stageContents[stageNum] === undefined) {
      return (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2
            className="w-8 h-8 animate-spin"
            style={{ color: 'var(--mars-color-primary)' }}
          />
          <p className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
            Loading results…
          </p>
        </div>
      )
    }

    // Failed
    if (status === 'failed') {
      const stage = taskState?.stages.find(s => s.stage_number === stageNum)
      return (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <AlertCircle className="w-12 h-12 text-red-500" />
          <h3 className="text-lg font-semibold text-red-500">Stage Failed</h3>
          <p className="text-sm text-center max-w-md" style={{ color: 'var(--mars-color-text-secondary)' }}>
            {stage?.error || 'An unexpected error occurred.'}
          </p>
          <Button variant="ghost" size="sm" onClick={handleRerun}>
            <RotateCcw className="w-4 h-4 mr-2" /> Retry
          </Button>
        </div>
      )
    }

    // Stage 3 — Opportunity selection
    if (stageNum === 3 && status === 'completed') {
      const opps = opportunities.length > 0
        ? opportunities
        : (() => {
            try {
              const arr = JSON.parse(content)
              return Array.isArray(arr) ? arr as OpportunityArea[] : []
            } catch { return [] }
          })()

      // JSON parse failed — show retry banner
      if (opps.length === 0) {
        return (
          <div className="space-y-4 p-4">
            <div className="flex items-start gap-3 p-4 rounded-xl border"
              style={{ borderColor: '#f59e0b', background: 'rgba(245,158,11,0.07)' }}>
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: '#f59e0b' }} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold mb-1" style={{ color: 'var(--mars-color-text)' }}>
                  Could not display structured opportunity areas
                </p>
                <p className="text-xs mb-3" style={{ color: 'var(--mars-color-text-secondary)' }}>
                  The AI response couldn't be parsed into opportunity cards. Click &ldquo;Re-run&rdquo; to try again.
                </p>
                <Button variant="ghost" size="sm" onClick={handleRerun} disabled={isExecuting}>
                  <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Re-run Stage
                </Button>
              </div>
            </div>
            {content && content.length > 50 && (
              <ReviewPanel
                content={content}
                stageNum={stageNum}
                stageName={stageName}
                onSave={handleSaveContent}
                onRefine={handleRefineContent}
              />
            )}
          </div>
        )
      }

      return (
        <div className="space-y-4 p-4">
          <div>
            <h3 className="text-lg font-bold mb-1" style={{ color: 'var(--mars-color-text)' }}>Select an Opportunity Area</h3>
            <p className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Choose the opportunity area to focus on for solution generation.
            </p>
          </div>
          {opps.map(opp => (
            <div
              key={opp.id}
              onClick={() => setSelectedOpportunity(opp)}
              className="p-4 rounded-xl border cursor-pointer transition-all"
              style={{
                borderColor: selectedOpportunity?.id === opp.id
                  ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
                background: selectedOpportunity?.id === opp.id
                  ? 'rgba(99,102,241,0.06)' : 'var(--mars-color-surface)',
                boxShadow: selectedOpportunity?.id === opp.id
                  ? '0 0 0 2px var(--mars-color-primary)' : 'none',
              }}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <h4 className="font-semibold text-sm" style={{ color: 'var(--mars-color-text)' }}>
                  {opp.title}
                </h4>
                <span
                  className="text-xs px-2 py-0.5 rounded-full flex-shrink-0"
                  style={{
                    background: 'rgba(99,102,241,0.12)',
                    color: 'var(--mars-color-primary)',
                  }}
                >
                  {opp.valueCategory}
                </span>
              </div>
              <p className="text-sm mb-2" style={{ color: 'var(--mars-color-text-secondary)' }}>
                {opp.explanation}
              </p>
              {opp.whyNow && (
                <p className="text-xs italic" style={{ color: 'var(--mars-color-text-secondary)' }}>
                  Why now: {opp.whyNow}
                </p>
              )}
            </div>
          ))}
        </div>
      )
    }

    // Stage 4 — Solution Archetype selection
    if (stageNum === 4 && status === 'completed') {
      const archs = archetypes.length > 0
        ? archetypes
        : (() => {
            try {
              const arr = JSON.parse(content)
              return Array.isArray(arr) ? arr as SolutionArchetype[] : []
            } catch { return [] }
          })()

      // JSON parse failed but we may have raw LLM text — show it + retry option
      if (archs.length === 0) {
        return (
          <div className="space-y-4 p-4">
            <div className="flex items-start gap-3 p-4 rounded-xl border"
              style={{ borderColor: '#f59e0b', background: 'rgba(245,158,11,0.07)' }}>
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: '#f59e0b' }} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold mb-1" style={{ color: 'var(--mars-color-text)' }}>
                  Could not display structured archetypes
                </p>
                <p className="text-xs mb-3" style={{ color: 'var(--mars-color-text-secondary)' }}>
                  The AI generated a response but it couldn't be parsed into cards (often due to a very large
                  response). Click &ldquo;Re-run&rdquo; to try again, or review the raw content below.
                </p>
                <Button variant="ghost" size="sm" onClick={handleRerun} disabled={isExecuting}>
                  <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Re-run Stage
                </Button>
              </div>
            </div>
            {content && content.length > 50 && (
              <ReviewPanel
                content={content}
                stageNum={stageNum}
                stageName={stageName}
                onSave={handleSaveContent}
                onRefine={handleRefineContent}
              />
            )}
          </div>
        )
      }

      return (
        <div className="space-y-4 p-4">
          <div>
            <h3 className="text-lg font-bold mb-1" style={{ color: 'var(--mars-color-text)' }}>Select a Solution Archetype</h3>
            <p className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Choose the solution approach to generate detailed features for.
            </p>
          </div>
          {archs.map(arch => (
            <div
              key={arch.id}
              onClick={() => setSelectedArchetype(arch)}
              className="p-4 rounded-xl border cursor-pointer transition-all"
              style={{
                borderColor: selectedArchetype?.id === arch.id
                  ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
                background: selectedArchetype?.id === arch.id
                  ? 'rgba(99,102,241,0.06)' : 'var(--mars-color-surface)',
                boxShadow: selectedArchetype?.id === arch.id
                  ? '0 0 0 2px var(--mars-color-primary)' : 'none',
              }}
            >
              <h4 className="font-semibold text-sm mb-2" style={{ color: 'var(--mars-color-text)' }}>
                {arch.title}
              </h4>
              <p className="text-sm mb-3" style={{ color: 'var(--mars-color-text-secondary)' }}>
                {arch.summary}
              </p>
              {(arch.benefits?.length ?? 0) > 0 && (
                <ul className="space-y-0.5">
                  {arch.benefits.slice(0, 3).map((b, i) => {
                    const label = typeof b === 'string' ? b : (b as any).benefit || (b as any).description || JSON.stringify(b)
                    return (
                      <li key={i} className="text-xs flex items-start gap-1.5" style={{ color: 'var(--mars-color-text-secondary)' }}>
                        <span style={{ color: 'var(--mars-color-primary)' }}>✓</span> {label}
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          ))}
        </div>
      )
    }

    // Stage 5 — Feature selection
    if (stageNum === 5 && status === 'completed') {
      const feats = features.length > 0
        ? features
        : (() => {
            try {
              const arr = JSON.parse(content)
              return Array.isArray(arr) ? arr as Feature[] : []
            } catch { return [] }
          })()

      // JSON parse failed — show retry banner + raw content
      if (feats.length === 0) {
        return (
          <div className="space-y-4 p-4">
            <div className="flex items-start gap-3 p-4 rounded-xl border"
              style={{ borderColor: '#f59e0b', background: 'rgba(245,158,11,0.07)' }}>
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: '#f59e0b' }} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold mb-1" style={{ color: 'var(--mars-color-text)' }}>
                  Could not display structured features
                </p>
                <p className="text-xs mb-3" style={{ color: 'var(--mars-color-text-secondary)' }}>
                  The AI response couldn't be parsed into feature cards. Click &ldquo;Re-run&rdquo; to try again.
                </p>
                <Button variant="ghost" size="sm" onClick={handleRerun} disabled={isExecuting}>
                  <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Re-run Stage
                </Button>
              </div>
            </div>
            {content && content.length > 50 && (
              <ReviewPanel
                content={content}
                stageNum={stageNum}
                stageName={stageName}
                onSave={handleSaveContent}
                onRefine={handleRefineContent}
              />
            )}
          </div>
        )
      }

      return (
        <div className="space-y-4 p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-lg font-bold mb-0.5" style={{ color: 'var(--mars-color-text)' }}>
                Select Features
              </h3>
              <p className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
                {selectedFeatures.length} of {feats.length} selected
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={() => setSelectedFeatures(feats)}>
                Select All
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setSelectedFeatures([])}>
                Clear
              </Button>
            </div>
          </div>

          {['Must', 'Should', 'Could'].map(priority => {
            const group = feats.filter(f => f.priority === priority)
            if (group.length === 0) return null
            return (
              <div key={priority}>
                <h4
                  className="text-xs font-semibold uppercase tracking-wide mb-2"
                  style={{ color: 'var(--mars-color-text-secondary)' }}
                >
                  {priority} Have
                </h4>
                <div className="space-y-2">
                  {group.map(feat => {
                    const isSel = selectedFeatures.some(f => f.id === feat.id)
                    return (
                      <div
                        key={feat.id}
                        onClick={() => toggleFeature(feat)}
                        className="flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all"
                        style={{
                          borderColor: isSel ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
                          background: isSel ? 'rgba(99,102,241,0.05)' : 'var(--mars-color-surface)',
                        }}
                      >
                        {isSel
                          ? <CheckSquare className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'var(--mars-color-primary)' }} />
                          : <Square className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'var(--mars-color-border)' }} />
                        }
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="font-medium text-sm" style={{ color: 'var(--mars-color-text)' }}>
                              {feat.name}
                            </span>
                            <span
                              className="text-xs px-1.5 py-0.5 rounded"
                              style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--mars-color-primary)' }}
                            >
                              {feat.bucket}
                            </span>
                          </div>
                          <p className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>
                            {feat.description}
                          </p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )
    }

    // Stage 6 — AI Builder Prompts (custom tabbed view)
    if (stageNum === 6 && status === 'completed') {
      return (
        <div className="p-4 h-full overflow-hidden flex flex-col">
          {content ? (
            <PromptsPanel
              content={content}
              onSave={handleSaveContent}
              onRefine={handleRefineContent}
            />
          ) : (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--mars-color-primary)' }} />
            </div>
          )}
        </div>
      )
    }

    // Stage 7 — Slide Content (presentation viewer + PDF export)
    if (stageNum === 7 && status === 'completed') {
      return (
        <div className="p-4 h-full overflow-hidden flex flex-col">
          {content ? (
            <SlidesPanel
              content={content}
              clientName={taskState?.client_name || intake.clientName || 'pda'}
              onSave={handleSaveContent}
              onRefine={handleRefineContent}
            />
          ) : (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--mars-color-primary)' }} />
            </div>
          )}
        </div>
      )
    }

    // Stages 1, 2 — HITL review panel
    if (status === 'completed' && content) {
      return (
        <div className="p-4 h-full">
          <ReviewPanel
            content={content}
            stageNum={stageNum}
            stageName={stageName}
            onSave={handleSaveContent}
            onRefine={handleRefineContent}
          />
        </div>
      )
    }

    // Completed but content is empty (LLM returned no usable output)
    if (status === 'completed') {
      return (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <AlertCircle className="w-10 h-10" style={{ color: '#f59e0b' }} />
          <h3 className="text-base font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            No content generated
          </h3>
          <p className="text-sm text-center max-w-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
            The stage completed but produced no output. This can happen with large or complex
            responses. Try re-running the stage.
          </p>
          <Button variant="ghost" size="sm" onClick={handleRerun}>
            <RotateCcw className="w-4 h-4 mr-2" /> Re-run Stage
          </Button>
        </div>
      )
    }

    // Pending — waiting to execute
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
          This stage will run once you advance from the previous step.
        </p>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Render: Progress indicator
  // ---------------------------------------------------------------------------

  const renderProgress = () => (
    <div className="flex items-center gap-1 overflow-x-auto pb-1">
      {STEP_LABELS.map((label, i) => {
        const isActive = currentStep === i
        const isDone = i < currentStep || (i > 0 && getStageStatus(i) === 'completed')
        const isFailed = i > 0 && getStageStatus(i) === 'failed'
        return (
          <React.Fragment key={i}>
            <button
              onClick={() => {
                if (isDone || isActive) setCurrentStep(i as PdaWizardStep)
              }}
              disabled={!isDone && !isActive}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition-colors"
              style={{
                background: isActive
                  ? 'var(--mars-color-primary)'
                  : isFailed
                  ? 'rgba(239,68,68,0.1)'
                  : isDone
                  ? 'rgba(99,102,241,0.1)'
                  : 'transparent',
                color: isActive
                  ? '#fff'
                  : isFailed
                  ? '#ef4444'
                  : isDone
                  ? 'var(--mars-color-primary)'
                  : 'var(--mars-color-text-secondary)',
              }}
            >
              <span
                className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0"
                style={{
                  background: isActive ? 'rgba(255,255,255,0.25)' : isDone ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
                  color: isActive || isDone ? '#fff' : 'var(--mars-color-text-secondary)',
                }}
              >
                {isFailed ? '!' : isDone ? '✓' : i}
              </span>
              {label}
            </button>
            {i < STEP_LABELS.length - 1 && (
              <ChevronRight className="w-3 h-3 flex-shrink-0" style={{ color: 'var(--mars-color-border)' }} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )

  // ---------------------------------------------------------------------------
  // Root render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div
        className="flex items-center justify-between gap-3 px-5 py-3 border-b flex-shrink-0"
        style={{
          backgroundColor: 'var(--mars-color-surface)',
          borderColor: 'var(--mars-color-border)',
        }}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-sm font-medium hover:opacity-80"
            style={{ color: 'var(--mars-color-primary)' }}
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
          <span style={{ color: 'var(--mars-color-border)' }}>|</span>
          <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            Product Discovery
          </span>
          {taskState?.client_name && (
            <span className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
              — {taskState.client_name}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {currentStep > 0 && currentStep <= 7 && (
            <button
              onClick={handleRerun}
              disabled={isExecuting}
              className="p-1.5 rounded-lg border text-xs flex items-center gap-1"
              style={{
                borderColor: 'var(--mars-color-border)',
                color: 'var(--mars-color-text-secondary)',
              }}
              title="Re-run this stage"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}
          {taskState?.total_cost_usd != null && (
            <span className="text-xs px-2 py-1 rounded" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--mars-color-primary)' }}>
              ${taskState.total_cost_usd.toFixed(4)}
            </span>
          )}
        </div>
      </div>

      {/* Progress */}
      {taskId && (
        <div
          className="px-5 py-2 border-b flex-shrink-0"
          style={{ borderColor: 'var(--mars-color-border)', backgroundColor: 'var(--mars-color-surface)' }}
        >
          {renderProgress()}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto" style={{ backgroundColor: 'var(--mars-color-background)' }}>
        {currentStep === 0 ? renderIntake() : renderStageView()}
      </div>

      {/* Bottom navigation */}
      {currentStep > 0 && (
        <div
          className="flex items-center justify-between px-5 py-3 border-t flex-shrink-0"
          style={{
            backgroundColor: 'var(--mars-color-surface)',
            borderColor: 'var(--mars-color-border)',
          }}
        >
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentStep((currentStep - 1) as PdaWizardStep)}
            disabled={currentStep <= 1}
          >
            <ArrowLeft className="w-4 h-4 mr-1.5" />
            Previous
          </Button>

          <div className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>
            Step {currentStep} of 7
          </div>

          {currentStep < 7 ? (
            <Button
              variant="primary"
              size="sm"
              onClick={handleNext}
              disabled={!canAdvance() || isExecuting}
            >
              {isExecuting ? (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              ) : (
                <>Next <ChevronRight className="w-4 h-4 ml-1" /></>
              )}
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const content = stageContents[7] ?? ''
                if (!content) return
                const slides = parseSlidesFromMarkdown(content)
                if (slides.length > 0) {
                  exportSlidesToPDF(slides, taskState?.client_name || '')
                }
              }}
              disabled={!stageContents[7]}
            >
              <Printer className="w-4 h-4 mr-1.5" /> Export PDF
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
