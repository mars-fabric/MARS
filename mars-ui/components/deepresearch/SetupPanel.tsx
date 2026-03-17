'use client'

import React, { useState, useCallback } from 'react'
import { Sparkles, Search, Settings2, Loader2 } from 'lucide-react'
import { Button } from '@/components/core'
import FileUploadZone from './FileUploadZone'
import FileContextPanel from './FileContextPanel'
import StageAdvancedSettings from './StageAdvancedSettings'
import type { useDeepresearchTask } from '@/hooks/useDeepresearchTask'
import type { DeepresearchStageConfig } from '@/types/deepresearch'

interface SetupPanelProps {
  hook: ReturnType<typeof useDeepresearchTask>
  onNext: () => void
}

export default function SetupPanel({ hook, onNext }: SetupPanelProps) {
  const {
    autoCreateTask,
    createTask,
    uploadFile,
    uploadedFiles,
    isLoading,
    executeStage,
    taskConfig,
    setTaskConfig,
    fileContextOutput,
    fileContextStatus,
    fileContext,
    analyzeFiles,
    refineFileContext,
    saveFileContext,
    setFileContext,
  } = hook

  const [description, setDescription] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const updateCfg = useCallback((patch: Partial<DeepresearchStageConfig>) => {
    setTaskConfig({ ...taskConfig, ...patch })
  }, [taskConfig, setTaskConfig])

  // Note: task is auto-created lazily on first file drop (inside uploadFile)
  // Do NOT call autoCreateTask here — it races with resumeTask on history resume

  const handleAnalyze = useCallback(async () => {
    setIsAnalyzing(true)
    await analyzeFiles()
    setIsAnalyzing(false)
  }, [analyzeFiles])

  const handleSubmit = useCallback(async () => {
    if (!description.trim()) return
    // createTask updates the description if task already exists, or creates fresh
    const id = await createTask(description, undefined)
    if (id) await executeStage(1, id)
    onNext()
  }, [description, createTask, executeStage, onNext])

  const hasUploadedFiles = uploadedFiles.some(f => f.status === 'done')

  return (
    <div className="max-w-3xl mx-auto space-y-6">

      {/* Research description */}
      <div>
        <label
          className="block text-sm font-medium mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Research Description
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe your research question, area of investigation, or the study you want to pursue..."
          rows={5}
          className="w-full rounded-mars-md border p-3 text-sm resize-none outline-none transition-colors"
          style={{
            backgroundColor: 'var(--mars-color-surface)',
            borderColor: 'var(--mars-color-border)',
            color: 'var(--mars-color-text)',
          }}
        />
        <p
          className="text-xs mt-1"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          Be specific about your research goals. The AI will generate ideas based on this description and your uploaded data.
        </p>
      </div>

      {/* Research data files */}
      <div>
        <label
          className="block text-sm font-medium mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Research Data Files
          <span
            className="ml-2 text-xs font-normal"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            (CSV, FITS, HDF5, JSON, NPY, PDF, TXT and more — uploaded immediately)
          </span>
        </label>

        <FileUploadZone
          files={uploadedFiles}
          onUpload={uploadFile}
          disabled={isLoading}
        />

        {/* Understand My Data button */}
        {hasUploadedFiles && fileContextStatus === 'idle' && (
          <div className="mt-3 flex justify-end">
            <Button
              onClick={handleAnalyze}
              disabled={isAnalyzing}
              variant="secondary"
              size="sm"
            >
              <Search className="w-3.5 h-3.5 mr-2" />
              Understand My Data
            </Button>
          </div>
        )}

        {/* Re-analyze button after done / error */}
        {hasUploadedFiles && (fileContextStatus === 'done' || fileContextStatus === 'error') && (
          <div className="mt-3 flex justify-end">
            <Button
              onClick={handleAnalyze}
              disabled={isAnalyzing}
              variant="secondary"
              size="sm"
            >
              {isAnalyzing ? (
                <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />Re-analyzing...</>
              ) : (
                <><Search className="w-3.5 h-3.5 mr-2" />Re-analyze Files</>
              )}
            </Button>
          </div>
        )}

        {/* Streaming analysis + editable context panel */}
        {fileContextStatus !== 'idle' && (
          <div className="mt-3">
            <FileContextPanel
              fileContextOutput={fileContextOutput}
              fileContextStatus={fileContextStatus}
              fileContext={fileContext}
              onRefine={refineFileContext}
              onSave={saveFileContext}
              onContextChange={setFileContext}
            />
          </div>
        )}
      </div>

      {/* Stage 1 settings + submit */}
      <div className="space-y-3">
        {/* Settings row */}
        <div className="flex items-center justify-between">
          <span
            className="text-xs font-medium"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            Idea Generation settings
          </span>
          <button
            onClick={() => setShowSettings(s => !s)}
            title="Advanced settings for Idea Generation"
            className="p-1.5 rounded-mars-sm transition-colors"
            style={{
              color: showSettings ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)',
              backgroundColor: showSettings ? 'var(--mars-color-accent-subtle, rgba(99,102,241,0.1))' : 'transparent',
            }}
          >
            <Settings2 className="w-4 h-4" />
          </button>
        </div>

        {showSettings && (
          <div
            className="p-4 rounded-mars-md border"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <StageAdvancedSettings stageNum={1} cfg={taskConfig} updateCfg={updateCfg} />
          </div>
        )}

        <div className="flex justify-end">
          <Button
            onClick={handleSubmit}
            disabled={!description.trim() || isLoading}
            variant="primary"
            size="md"
          >
            {isLoading ? (
              <>Generating...</>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Generate Ideas
              </>
            )}
          </Button>
        </div>
      </div>

    </div>
  )
}

