'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react'
import { Eye, Edit3, Save, ArrowRight, ArrowLeft, Play, Loader2, Settings2 } from 'lucide-react'
import { Button } from '@/components/core'
import RefinementChat from './RefinementChat'
import ExecutionProgress from './ExecutionProgress'
import MarkdownRenderer from '@/components/files/MarkdownRenderer'
import StageAdvancedSettings from './StageAdvancedSettings'
import type { useDeepresearchTask } from '@/hooks/useDeepresearchTask'
import type { DeepresearchStageConfig } from '@/types/deepresearch'

interface ReviewPanelProps {
  hook: ReturnType<typeof useDeepresearchTask>
  stageNum: number
  stageName: string
  sharedKey: string
  onNext: () => void
  onBack: () => void
}

export default function ReviewPanel({
  hook,
  stageNum,
  stageName,
  sharedKey,
  onNext,
  onBack,
}: ReviewPanelProps) {
  const {
    taskState,
    editableContent,
    setEditableContent,
    refinementMessages,
    consoleOutput,
    isExecuting,
    executeStage,
    fetchStageContent,
    saveStageContent,
    refineContent,
    taskConfig,
    setTaskConfig,
  } = hook

  const [mode, setMode] = useState<'edit' | 'preview'>('edit')
  const [isSaving, setIsSaving] = useState(false)
  const [saveIndicator, setSaveIndicator] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [contentLoaded, setContentLoaded] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showNextSettings, setShowNextSettings] = useState(false)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const NEXT_STAGE_LABEL: Record<number, string> = {
    1: 'Run Methods',
    2: 'Run Experiment',
    3: 'Generate Paper',
  }

  const updateCfg = useCallback((patch: Partial<DeepresearchStageConfig>) => {
    setTaskConfig({ ...taskConfig, ...patch })
  }, [taskConfig, setTaskConfig])

  // Determine if stage is completed (has content to show)
  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isStageCompleted = stage?.status === 'completed'
  const isStageRunning = stage?.status === 'running' || isExecuting
  const isStageNotStarted = stage?.status === 'pending'
  const isStageFailed = stage?.status === 'failed'

  // Load content when stage is completed (or failed — content may still
  // be available on disk even if the DB persist step failed)
  useEffect(() => {
    if ((isStageCompleted || isStageFailed) && !contentLoaded) {
      fetchStageContent(stageNum).then(() => setContentLoaded(true))
    }
  }, [isStageCompleted, isStageFailed, contentLoaded, fetchStageContent, stageNum])

  // (stage is started manually via the Run button in the pre-execution UI)

  // Content is available for editing when stage is completed, or when
  // stage failed but content was recovered from disk
  const canEdit = isStageCompleted || (isStageFailed && !!editableContent)

  // Auto-save with debounce
  const handleContentChange = useCallback((value: string) => {
    setEditableContent(value)
    setSaveIndicator('idle')

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(async () => {
      if (canEdit) {
        setSaveIndicator('saving')
        await saveStageContent(stageNum, value, sharedKey)
        setSaveIndicator('saved')
        setTimeout(() => setSaveIndicator('idle'), 2000)
      }
    }, 1000)
  }, [canEdit, saveStageContent, setEditableContent, stageNum, sharedKey])

  // Manual save
  const handleSave = useCallback(async () => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    setIsSaving(true)
    await saveStageContent(stageNum, editableContent, sharedKey)
    setIsSaving(false)
    setSaveIndicator('saved')
    setTimeout(() => setSaveIndicator('idle'), 2000)
  }, [saveStageContent, stageNum, editableContent, sharedKey])

  // Refinement handler
  const handleRefine = useCallback(async (message: string) => {
    return refineContent(stageNum, message, editableContent)
  }, [refineContent, stageNum, editableContent])

  // Apply refined content from chat
  const handleApply = useCallback((content: string) => {
    setEditableContent(content)
    if (canEdit) {
      saveStageContent(stageNum, content, sharedKey)
    }
  }, [setEditableContent, canEdit, saveStageContent, stageNum, sharedKey])

  // Handle next with save — also auto-triggers next stage execution
  const handleNext = useCallback(async () => {
    if (canEdit) {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
      await saveStageContent(stageNum, editableContent, sharedKey)
    }
    // Fire-and-forget: start next stage immediately so user lands on running state
    const nextStageNum = stageNum + 1
    if (nextStageNum <= 4) {
      const nextStage = taskState?.stages.find(s => s.stage_number === nextStageNum)
      if (nextStage?.status === 'pending') {
        executeStage(nextStageNum)
      }
    }
    onNext()
  }, [canEdit, saveStageContent, stageNum, editableContent, sharedKey, taskState, executeStage, onNext])

  // Pre-execution: stage not started yet — compact header with gear icon
  if (isStageNotStarted && !isExecuting) {
    return (
      <div className="max-w-3xl mx-auto space-y-3">
        {/* Header bar */}
        <div className="flex items-center justify-between py-2">
          <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            {stageName}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(s => !s)}
              title="Advanced settings"
              className="p-1.5 rounded-mars-sm transition-colors"
              style={{
                color: showSettings ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)',
                backgroundColor: showSettings ? 'var(--mars-color-accent-subtle, rgba(99,102,241,0.1))' : 'transparent',
              }}
            >
              <Settings2 className="w-4 h-4" />
            </button>
            <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
              <Play className="w-3.5 h-3.5 mr-1.5" />
              Run {stageName}
            </Button>
          </div>
        </div>

        {/* Inline settings panel (collapsed by default) */}
        {showSettings && (
          <div
            className="p-4 rounded-mars-md border space-y-4"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <StageAdvancedSettings stageNum={stageNum} cfg={taskConfig} updateCfg={updateCfg} />
          </div>
        )}

        <div className="flex justify-start pt-1">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
        </div>
      </div>
    )
  }

  // Show failure state with retry option (only when no content was recovered)
  if (isStageFailed && !isExecuting && !editableContent) {
    return (
      <div className="max-w-3xl mx-auto space-y-3">
        {/* Header with gear icon */}
        <div className="flex items-center justify-between py-2">
          <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-error)' }}>
            {stageName} failed
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(s => !s)}
              title="Advanced settings"
              className="p-1.5 rounded-mars-sm transition-colors"
              style={{
                color: showSettings ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)',
                backgroundColor: showSettings ? 'var(--mars-color-accent-subtle, rgba(99,102,241,0.1))' : 'transparent',
              }}
            >
              <Settings2 className="w-4 h-4" />
            </button>
            <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
              <Play className="w-3.5 h-3.5 mr-1.5" />
              Retry
            </Button>
          </div>
        </div>

        {hook.error && (
          <p className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>{hook.error}</p>
        )}

        {/* Inline settings */}
        {showSettings && (
          <div
            className="p-4 rounded-mars-md border space-y-4"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <StageAdvancedSettings stageNum={stageNum} cfg={taskConfig} updateCfg={updateCfg} />
          </div>
        )}

        {consoleOutput.length > 0 && (
          <ExecutionProgress consoleOutput={consoleOutput} isExecuting={false} stageName={stageName} />
        )}
        <div className="flex justify-start pt-1">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
        </div>
      </div>
    )
  }

  // Show execution progress if stage is still running
  if (isStageRunning && !isStageCompleted) {
    return (
      <div className="max-w-3xl mx-auto">
        <ExecutionProgress
          consoleOutput={consoleOutput}
          isExecuting={true}
          stageName={stageName}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col" style={{ minHeight: '500px' }}>
      {/* Split view: Editor (60%) + Chat (40%) */}
      <div className="flex flex-1 gap-4" style={{ minHeight: '400px' }}>
        {/* Editor panel */}
        <div
          className="flex-[3] flex flex-col rounded-mars-md border overflow-hidden"
          style={{
            borderColor: 'var(--mars-color-border)',
            backgroundColor: 'var(--mars-color-surface)',
          }}
        >
          {/* Editor toolbar */}
          <div
            className="flex items-center justify-between px-4 py-2 border-b flex-shrink-0"
            style={{ borderColor: 'var(--mars-color-border)' }}
          >
            <div className="flex items-center gap-2">
              <span
                className="text-sm font-medium"
                style={{ color: 'var(--mars-color-text)' }}
              >
                {stageName}
              </span>

              {/* Save indicator */}
              {saveIndicator === 'saving' && (
                <span className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                  Saving...
                </span>
              )}
              {saveIndicator === 'saved' && (
                <span className="text-xs" style={{ color: 'var(--mars-color-success)' }}>
                  Saved
                </span>
              )}
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setMode('edit')}
                className="flex items-center gap-1 px-2 py-1 text-xs rounded-mars-sm transition-colors"
                style={{
                  backgroundColor: mode === 'edit' ? 'var(--mars-color-primary-subtle)' : 'transparent',
                  color: mode === 'edit' ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
                }}
              >
                <Edit3 className="w-3 h-3" />
                Edit
              </button>
              <button
                onClick={() => setMode('preview')}
                className="flex items-center gap-1 px-2 py-1 text-xs rounded-mars-sm transition-colors"
                style={{
                  backgroundColor: mode === 'preview' ? 'var(--mars-color-primary-subtle)' : 'transparent',
                  color: mode === 'preview' ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
                }}
              >
                <Eye className="w-3 h-3" />
                Preview
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="flex items-center gap-1 px-2 py-1 text-xs rounded-mars-sm transition-colors ml-2"
                style={{
                  color: 'var(--mars-color-text-secondary)',
                }}
              >
                <Save className="w-3 h-3" />
                Save
              </button>
            </div>
          </div>

          {/* Editor / Preview */}
          <div className="flex-1 overflow-y-auto">
            {mode === 'edit' ? (
              <textarea
                value={editableContent}
                onChange={(e) => handleContentChange(e.target.value)}
                className="w-full h-full p-4 font-mono text-sm resize-none outline-none bg-transparent"
                style={{ color: 'var(--mars-color-text)', minHeight: '100%' }}
                spellCheck={false}
              />
            ) : (
              <div className="p-4">
                <MarkdownRenderer content={editableContent} />
              </div>
            )}
          </div>
        </div>

        {/* Chat panel */}
        <div
          className="flex-[2] rounded-mars-md border overflow-hidden flex flex-col"
          style={{
            borderColor: 'var(--mars-color-border)',
            backgroundColor: 'var(--mars-color-surface)',
          }}
        >
          <RefinementChat
            messages={refinementMessages}
            onSend={handleRefine}
            onApply={handleApply}
          />
        </div>
      </div>

      {/* Navigation footer */}
      <div className="pt-4 mt-4 space-y-3">
        {/* Next-stage settings (only for stages 1-3) */}
        {stageNum < 4 && (
          <div>
            <div className="flex items-center justify-between">
              <span
                className="text-xs font-medium"
                style={{ color: 'var(--mars-color-text-secondary)' }}
              >
                Next: {NEXT_STAGE_LABEL[stageNum]} settings
              </span>
              <button
                onClick={() => setShowNextSettings(s => !s)}
                title={`Advanced settings for ${NEXT_STAGE_LABEL[stageNum]}`}
                className="p-1.5 rounded-mars-sm transition-colors"
                style={{
                  color: showNextSettings ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)',
                  backgroundColor: showNextSettings ? 'var(--mars-color-accent-subtle, rgba(99,102,241,0.1))' : 'transparent',
                }}
              >
                <Settings2 className="w-4 h-4" />
              </button>
            </div>
            {showNextSettings && (
              <div
                className="mt-2 p-4 rounded-mars-md border"
                style={{
                  backgroundColor: 'var(--mars-color-surface-overlay)',
                  borderColor: 'var(--mars-color-border)',
                }}
              >
                <StageAdvancedSettings
                  stageNum={stageNum + 1}
                  cfg={taskConfig}
                  updateCfg={updateCfg}
                />
              </div>
            )}
          </div>
        )}

        {/* Back / Next row */}
        <div className="flex items-center justify-between">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
          <Button
            onClick={handleNext}
            variant="primary"
            size="sm"
            disabled={!canEdit}
          >
            {stageNum < 4 ? NEXT_STAGE_LABEL[stageNum] : 'Next'}
            <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  )
}
