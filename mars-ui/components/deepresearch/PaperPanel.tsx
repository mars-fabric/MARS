'use client'

import React, { useEffect, useCallback, useState } from 'react'
import { ArrowLeft, Download, FileText, Image, File, CheckCircle, Loader2, Play, Settings2, Eye, EyeOff, Pencil, X, Save, Wand2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from './ExecutionProgress'
import StageAdvancedSettings from './StageAdvancedSettings'
import type { useDeepresearchTask } from '@/hooks/useDeepresearchTask'
import type { DeepresearchStageConfig } from '@/types/deepresearch'
import { getApiUrl } from '@/lib/config'

interface PaperPanelProps {
  hook: ReturnType<typeof useDeepresearchTask>
  stageNum: number
  onBack: () => void
}

type EditorMode = 'manual' | 'ai'
type CompileState = 'idle' | 'compiling' | 'success' | 'error'

export default function PaperPanel({ hook, stageNum, onBack }: PaperPanelProps) {
  const {
    taskId,
    taskState,
    consoleOutput,
    isExecuting,
    executeStage,
    fetchStageContent,
    taskConfig,
    setTaskConfig,
  } = hook

  const [artifacts, setArtifacts] = useState<string[]>([])
  const [showSettings, setShowSettings] = useState(false)
  const [viewingPdf, setViewingPdf] = useState<string | null>(null)

  // .tex editor state
  const [editingTex, setEditingTex] = useState<string | null>(null)
  const [texContent, setTexContent] = useState<string>('')
  const [editorMode, setEditorMode] = useState<EditorMode>('manual')
  const [aiInstruction, setAiInstruction] = useState('')
  const [isAiEditing, setIsAiEditing] = useState(false)
  const [aiPreview, setAiPreview] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle')
  const [compileState, setCompileState] = useState<CompileState>('idle')
  const [compileLog, setCompileLog] = useState<string>('')
  const [pdfRefreshKey, setPdfRefreshKey] = useState(0)

  const updateCfg = useCallback((patch: Partial<DeepresearchStageConfig>) => {
    setTaskConfig({ ...taskConfig, ...patch })
  }, [taskConfig, setTaskConfig])

  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isCompleted = stage?.status === 'completed'
  const isFailed = stage?.status === 'failed'
  const isNotStarted = stage?.status === 'pending'

  useEffect(() => {
    if (isCompleted && taskId) {
      fetchStageContent(stageNum).then(content => {
        if (content?.output_files) setArtifacts(content.output_files)
      })
    }
  }, [isCompleted, taskId, fetchStageContent, stageNum])

  const getFileIcon = (path: string) => {
    if (path.endsWith('.tex') || path.endsWith('.pdf')) return <FileText className="w-4 h-4" />
    if (path.endsWith('.png') || path.endsWith('.jpg') || path.endsWith('.jpeg')) return <Image className="w-4 h-4" />
    return <File className="w-4 h-4" />
  }

  const getFileName = (path: string) => path.split('/').pop() || path

  const openTexEditor = async (path: string) => {
    setSaveStatus('idle')
    setAiPreview(null)
    setAiInstruction('')
    setEditorMode('manual')
    setCompileState('idle')
    setCompileLog('')
    try {
      const res = await fetch(getApiUrl(`/api/files/content?path=${encodeURIComponent(path)}`))
      const data = await res.json()
      setTexContent(data.content ?? '')
    } catch {
      setTexContent('')
    }
    setEditingTex(path)
  }

  const saveTexToDisk = async (path: string, content: string): Promise<boolean> => {
    setIsSaving(true)
    setSaveStatus('idle')
    try {
      const res = await fetch(
        getApiUrl(`/api/files/content?path=${encodeURIComponent(path)}`),
        { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) }
      )
      if (!res.ok) throw new Error()
      setSaveStatus('saved')
      return true
    } catch {
      setSaveStatus('error')
      return false
    } finally {
      setIsSaving(false)
    }
  }

  const handleManualSave = () => saveTexToDisk(editingTex!, texContent)

  const handleAiEdit = async () => {
    if (!editingTex || !aiInstruction.trim()) return
    setIsAiEditing(true)
    setAiPreview(null)
    try {
      const res = await fetch(
        getApiUrl(`/api/deepresearch/${taskId}/ai-edit-tex`),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tex_path: editingTex, instruction: aiInstruction }),
        }
      )
      if (!res.ok) throw new Error((await res.json()).detail || 'AI edit failed')
      const data = await res.json()
      setAiPreview(data.edited_content)
    } catch (e: any) {
      setAiPreview(null)
      alert(e.message || 'AI edit failed')
    } finally {
      setIsAiEditing(false)
    }
  }

  const applyAiPreview = () => {
    if (aiPreview === null) return
    setTexContent(aiPreview)
    setAiPreview(null)
    setSaveStatus('idle')
  }

  const handleCompile = async () => {
    if (!editingTex) return
    // Auto-save first
    const saved = await saveTexToDisk(editingTex, texContent)
    if (!saved) return
    setCompileState('compiling')
    setCompileLog('')
    try {
      const res = await fetch(
        getApiUrl(`/api/deepresearch/${taskId}/compile-tex`),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tex_path: editingTex }),
        }
      )
      const data = await res.json()
      setCompileLog(data.log || '')
      if (data.success) {
        setCompileState('success')
        // Refresh PDF viewer if open
        const pdfPath = editingTex.replace(/\.tex$/, '.pdf')
        if (viewingPdf === pdfPath) setPdfRefreshKey(k => k + 1)
        // Refresh artifact list
        fetchStageContent(stageNum).then(content => {
          if (content?.output_files) setArtifacts(content.output_files)
        })
      } else {
        setCompileState('error')
      }
    } catch (e: any) {
      setCompileLog(e.message || 'Compilation error')
      setCompileState('error')
    }
  }

  // ── Pre-execution view ──────────────────────────────────────────────────────
  if (isNotStarted && !isExecuting) {
    return (
      <div className="max-w-3xl mx-auto space-y-3">
        <div className="flex items-center justify-between py-2">
          <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>Deep Scientific Research</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowSettings(s => !s)} title="Advanced settings" className="p-1.5 rounded-mars-sm transition-colors" style={{ color: showSettings ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)', backgroundColor: showSettings ? 'var(--mars-color-accent-subtle, rgba(99,102,241,0.1))' : 'transparent' }}>
              <Settings2 className="w-4 h-4" />
            </button>
            <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
              <Play className="w-3.5 h-3.5 mr-1.5" />Generate Paper
            </Button>
          </div>
        </div>
        {showSettings && (
          <div className="p-4 rounded-mars-md border space-y-4" style={{ backgroundColor: 'var(--mars-color-surface-overlay)', borderColor: 'var(--mars-color-border)' }}>
            <StageAdvancedSettings stageNum={stageNum} cfg={taskConfig} updateCfg={updateCfg} />
          </div>
        )}
        <div className="flex justify-start pt-1">
          <Button onClick={onBack} variant="secondary" size="sm"><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
        </div>
      </div>
    )
  }

  // ── Running view ────────────────────────────────────────────────────────────
  if (isExecuting || (stage?.status === 'running' && !isCompleted)) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <ExecutionProgress consoleOutput={consoleOutput} isExecuting={true} stageName="Deep Scientific Research" />
        <div className="flex justify-start pt-4">
          <Button onClick={onBack} variant="secondary" size="sm" disabled={isExecuting}><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
        </div>
      </div>
    )
  }

  // ── Completion view ─────────────────────────────────────────────────────────
  return (
    <div className="max-w-3xl mx-auto space-y-6">

      {/* Success header */}
      {isCompleted && (
        <div className="flex items-center gap-3 p-4 rounded-mars-md" style={{ backgroundColor: 'var(--mars-color-success-subtle)', border: '1px solid var(--mars-color-success)' }}>
          <CheckCircle className="w-6 h-6" style={{ color: 'var(--mars-color-success)' }} />
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>Deep Scientific Research Complete</p>
            <p className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>All 4 stages completed successfully.</p>
          </div>
        </div>
      )}

      {/* Error / retry */}
      {isFailed && (
        <div className="p-4 rounded-mars-md" style={{ backgroundColor: 'var(--mars-color-danger-subtle)', border: '1px solid var(--mars-color-danger)' }}>
          <p className="text-sm font-medium" style={{ color: 'var(--mars-color-danger)' }}>Deep scientific research failed</p>
          {stage?.error && <p className="text-xs mt-1" style={{ color: 'var(--mars-color-text-secondary)' }}>{stage.error}</p>}
          <div className="flex items-center gap-2 mt-3">
            <button onClick={() => setShowSettings(s => !s)} title="Advanced settings" className="p-1.5 rounded-mars-sm transition-colors" style={{ color: showSettings ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)', backgroundColor: showSettings ? 'var(--mars-color-accent-subtle, rgba(99,102,241,0.1))' : 'transparent' }}>
              <Settings2 className="w-4 h-4" />
            </button>
            <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm"><Play className="w-4 h-4 mr-1" />Retry</Button>
          </div>
          {showSettings && (
            <div className="mt-3 p-4 rounded-mars-md border space-y-4" style={{ backgroundColor: 'var(--mars-color-surface-overlay)', borderColor: 'var(--mars-color-border)' }}>
              <StageAdvancedSettings stageNum={stageNum} cfg={taskConfig} updateCfg={updateCfg} />
            </div>
          )}
        </div>
      )}

      {/* Artifacts */}
      {artifacts.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--mars-color-text)' }}>Generated Artifacts</h3>
          <div className="space-y-2">
            {artifacts.map((path, i) => {
              const isPdf = path.toLowerCase().endsWith('.pdf')
              const isTex = path.toLowerCase().endsWith('.tex')
              const isViewingThis = viewingPdf === path
              const isEditingThis = editingTex === path

              return (
                <div key={i}>
                  {/* Row */}
                  <div
                    className="flex items-center gap-3 px-4 py-3 rounded-mars-md border"
                    style={{
                      backgroundColor: 'var(--mars-color-surface)',
                      borderColor: 'var(--mars-color-border)',
                      borderBottomLeftRadius: (isViewingThis || isEditingThis) ? 0 : undefined,
                      borderBottomRightRadius: (isViewingThis || isEditingThis) ? 0 : undefined,
                    }}
                  >
                    <span style={{ color: 'var(--mars-color-text-secondary)' }}>{getFileIcon(path)}</span>
                    <span className="flex-1 text-sm" style={{ color: 'var(--mars-color-text)' }}>{getFileName(path)}</span>

                    {isPdf && (
                      <button onClick={() => { setViewingPdf(isViewingThis ? null : path); setEditingTex(null) }} className="flex items-center gap-1 text-xs font-medium" style={{ color: 'var(--mars-color-text-secondary)' }}>
                        {isViewingThis ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        {isViewingThis ? 'Hide' : 'View'}
                      </button>
                    )}

                    {isTex && (
                      <button
                        onClick={() => { if (isEditingThis) { setEditingTex(null) } else { setViewingPdf(null); openTexEditor(path) } }}
                        className="flex items-center gap-1 text-xs font-medium"
                        style={{ color: 'var(--mars-color-text-secondary)' }}
                      >
                        {isEditingThis ? <X className="w-3.5 h-3.5" /> : <Pencil className="w-3.5 h-3.5" />}
                        {isEditingThis ? 'Close' : 'Edit'}
                      </button>
                    )}

                    <a href={getApiUrl(`/api/files/download?path=${encodeURIComponent(path)}`)} download={getFileName(path)} className="flex items-center gap-1 text-xs font-medium ml-2" style={{ color: 'var(--mars-color-primary)' }}>
                      <Download className="w-3.5 h-3.5" />Download
                    </a>
                  </div>

                  {/* PDF viewer */}
                  {isPdf && isViewingThis && (
                    <div className="border border-t-0" style={{ borderColor: 'var(--mars-color-border)', borderBottomLeftRadius: '6px', borderBottomRightRadius: '6px', height: '600px' }}>
                      <iframe key={pdfRefreshKey} src={getApiUrl(`/api/files/serve?path=${encodeURIComponent(path)}`)} className="w-full h-full" title={getFileName(path)} />
                    </div>
                  )}

                  {/* LaTeX editor */}
                  {isTex && isEditingThis && (
                    <div className="border border-t-0" style={{ borderColor: 'var(--mars-color-border)', borderBottomLeftRadius: '6px', borderBottomRightRadius: '6px', backgroundColor: 'var(--mars-color-surface-overlay)' }}>

                      {/* Mode tabs */}
                      <div className="flex border-b" style={{ borderColor: 'var(--mars-color-border)' }}>
                        {(['manual', 'ai'] as EditorMode[]).map(mode => (
                          <button
                            key={mode}
                            onClick={() => setEditorMode(mode)}
                            className="px-4 py-2 text-xs font-medium"
                            style={{
                              color: editorMode === mode ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)',
                              borderBottom: editorMode === mode ? '2px solid var(--mars-color-accent)' : '2px solid transparent',
                            }}
                          >
                            {mode === 'manual' ? <><Pencil className="w-3 h-3 inline mr-1" />Manual</> : <><Wand2 className="w-3 h-3 inline mr-1" />AI Edit</>}
                          </button>
                        ))}
                      </div>

                      {/* Manual editor */}
                      {editorMode === 'manual' && (
                        <>
                          <textarea
                            value={texContent}
                            onChange={e => { setTexContent(e.target.value); setSaveStatus('idle') }}
                            className="w-full p-3 font-mono text-xs bg-transparent resize-none focus:outline-none"
                            style={{ color: 'var(--mars-color-text)', minHeight: '480px', maxHeight: '700px', overflowY: 'auto' }}
                            spellCheck={false}
                          />
                          <div className="flex items-center justify-between px-3 py-2 border-t" style={{ borderColor: 'var(--mars-color-border)' }}>
                            <span className="text-xs" style={{ color: saveStatus === 'saved' ? 'var(--mars-color-success)' : saveStatus === 'error' ? 'var(--mars-color-danger)' : 'var(--mars-color-text-tertiary)' }}>
                              {saveStatus === 'saved' ? '✓ Saved' : saveStatus === 'error' ? 'Save failed' : 'Unsaved changes'}
                            </span>
                            <div className="flex items-center gap-2">
                              <button onClick={handleCompile} disabled={isSaving || compileState === 'compiling'}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-mars-sm text-xs font-medium border disabled:opacity-50"
                                style={{ borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
                              >
                                {compileState === 'compiling' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                                {compileState === 'compiling' ? 'Compiling…' : 'Save & Compile'}
                              </button>
                              <button onClick={handleManualSave} disabled={isSaving}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-mars-sm text-xs font-medium disabled:opacity-50"
                                style={{ backgroundColor: 'var(--mars-color-accent)', color: '#fff' }}
                              >
                                {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                                {isSaving ? 'Saving…' : 'Save'}
                              </button>
                            </div>
                          </div>
                        </>
                      )}

                      {/* AI Edit panel */}
                      {editorMode === 'ai' && (
                        <div className="p-4 space-y-4">
                          <div>
                            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--mars-color-text-secondary)' }}>
                              Describe the changes you want to make
                            </label>
                            <textarea
                              value={aiInstruction}
                              onChange={e => setAiInstruction(e.target.value)}
                              placeholder="e.g. Add a limitations section after the conclusion. Fix all passive voice in the introduction. Rewrite the abstract to be more concise."
                              className="w-full p-3 text-sm rounded-mars-sm border bg-transparent resize-none focus:outline-none"
                              style={{ color: 'var(--mars-color-text)', borderColor: 'var(--mars-color-border)', minHeight: '80px' }}
                            />
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={handleAiEdit}
                              disabled={isAiEditing || !aiInstruction.trim()}
                              className="flex items-center gap-1.5 px-4 py-2 rounded-mars-sm text-sm font-medium disabled:opacity-50"
                              style={{ backgroundColor: 'var(--mars-color-accent)', color: '#fff' }}
                            >
                              {isAiEditing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                              {isAiEditing ? 'Editing…' : 'Apply AI Edit'}
                            </button>
                          </div>

                          {/* AI preview */}
                          {aiPreview !== null && (
                            <div className="space-y-3">
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-medium" style={{ color: 'var(--mars-color-text)' }}>Preview of AI edits</span>
                                <button onClick={() => setAiPreview(null)} className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>Discard</button>
                              </div>
                              <textarea
                                value={aiPreview}
                                onChange={e => setAiPreview(e.target.value)}
                                className="w-full p-3 font-mono text-xs rounded-mars-sm border bg-transparent resize-none focus:outline-none"
                                style={{ color: 'var(--mars-color-text)', borderColor: 'var(--mars-color-accent)', minHeight: '360px', maxHeight: '600px', overflowY: 'auto' }}
                                spellCheck={false}
                              />
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={applyAiPreview}
                                  className="flex items-center gap-1.5 px-4 py-2 rounded-mars-sm text-sm font-medium"
                                  style={{ backgroundColor: 'var(--mars-color-success)', color: '#fff' }}
                                >
                                  <CheckCircle className="w-4 h-4" />Accept Changes
                                </button>
                                <button
                                  onClick={async () => { applyAiPreview(); await saveTexToDisk(editingTex!, aiPreview!) }}
                                  className="flex items-center gap-1.5 px-4 py-2 rounded-mars-sm text-sm font-medium border"
                                  style={{ borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
                                >
                                  <Save className="w-4 h-4" />Accept & Save
                                </button>
                                <button
                                  onClick={async () => { applyAiPreview(); const ok = await saveTexToDisk(editingTex!, aiPreview!); if (ok) handleCompile() }}
                                  className="flex items-center gap-1.5 px-4 py-2 rounded-mars-sm text-sm font-medium border"
                                  style={{ borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
                                >
                                  <RefreshCw className="w-4 h-4" />Accept, Save & Compile
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Compile status */}
                      {(compileState !== 'idle') && (
                        <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--mars-color-border)' }}>
                          <div className="flex items-center gap-2 mb-2">
                            {compileState === 'compiling' && <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--mars-color-accent)' }} />}
                            {compileState === 'success' && <CheckCircle className="w-4 h-4" style={{ color: 'var(--mars-color-success)' }} />}
                            {compileState === 'error' && <X className="w-4 h-4" style={{ color: 'var(--mars-color-danger)' }} />}
                            <span className="text-xs font-medium" style={{ color: compileState === 'success' ? 'var(--mars-color-success)' : compileState === 'error' ? 'var(--mars-color-danger)' : 'var(--mars-color-text)' }}>
                              {compileState === 'compiling' ? 'Compiling PDF…' : compileState === 'success' ? 'PDF compiled successfully' : 'Compilation failed'}
                            </span>
                          </div>
                          {compileLog && (
                            <pre className="text-xs p-2 rounded overflow-auto" style={{ maxHeight: '160px', backgroundColor: 'var(--mars-color-surface)', color: 'var(--mars-color-text-secondary)' }}>
                              {compileLog}
                            </pre>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Cost summary */}
      {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
        <div className="p-4 rounded-mars-md border" style={{ backgroundColor: 'var(--mars-color-surface-overlay)', borderColor: 'var(--mars-color-border)' }}>
          <h3 className="text-sm font-medium mb-2" style={{ color: 'var(--mars-color-text)' }}>Cost Summary</h3>
          <div className="flex items-center gap-6">
            <div>
              <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>Total Cost</p>
              <p className="text-lg font-semibold" style={{ color: 'var(--mars-color-text)' }}>${taskState.total_cost_usd.toFixed(4)}</p>
            </div>
            <div>
              <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>Stages</p>
              <p className="text-lg font-semibold" style={{ color: 'var(--mars-color-text)' }}>{taskState.stages.filter(s => s.status === 'completed').length}/4</p>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-4">
        <Button onClick={onBack} variant="secondary" size="sm"><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
      </div>
    </div>
  )
}

