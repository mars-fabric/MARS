'use client'

import React, { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, DollarSign, Play, Settings2, Timer } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from '@/components/deepresearch/ExecutionProgress'
import NpStageAdvancedSettings from './NpStageAdvancedSettings'
import type { useNewsPulseTask } from '@/hooks/useNewsPulseTask'
import type { NewsPulseStageConfig } from '@/types/newspulse'

interface NpExecutionPanelProps {
  hook: ReturnType<typeof useNewsPulseTask>
  stageNum: number
  stageName: string
  onNext: () => void
  onBack: () => void
}

export default function NpExecutionPanel({
  hook,
  stageNum,
  stageName,
  onNext,
  onBack,
}: NpExecutionPanelProps) {
  const {
    taskState,
    consoleOutput,
    isExecuting,
    executeStage,
    taskConfig,
    setTaskConfig,
  } = hook

  const [elapsed, setElapsed] = useState(0)
  const [showSettings, setShowSettings] = useState(false)

  const updateCfg = useCallback((patch: Partial<NewsPulseStageConfig>) => {
    setTaskConfig({ ...taskConfig, ...patch })
  }, [taskConfig, setTaskConfig])

  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isCompleted = stage?.status === 'completed'
  const isFailed = stage?.status === 'failed'
  const isNotStarted = stage?.status === 'pending'

  // Timer
  useEffect(() => {
    if (!isExecuting) return
    const interval = setInterval(() => setElapsed(prev => prev + 1), 1000)
    return () => clearInterval(interval)
  }, [isExecuting])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  // Not started — compact header with gear icon (mirrors DeepResearch ExecutionPanel)
  if (isNotStarted && !isExecuting) {
    return (
      <div className="max-w-3xl mx-auto space-y-3">
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

        {showSettings && (
          <div
            className="p-4 rounded-mars-md border space-y-4"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <NpStageAdvancedSettings stageNum={stageNum} cfg={taskConfig} updateCfg={updateCfg} />
          </div>
        )}

        <div className="flex justify-start pt-1">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-4 h-4 mr-1" /> Back
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Stats bar */}
      <div className="flex items-center gap-6">
        {(isExecuting || elapsed > 0) && (
          <div
            className="flex items-center gap-2 text-xs"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <Timer className="w-3.5 h-3.5" />
            {formatTime(elapsed)}
          </div>
        )}
        {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
          <div
            className="flex items-center gap-2 text-xs"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <DollarSign className="w-3.5 h-3.5" />
            ${taskState.total_cost_usd.toFixed(4)}
          </div>
        )}
      </div>

      {/* Console */}
      <ExecutionProgress
        consoleOutput={consoleOutput}
        isExecuting={isExecuting}
        stageName={stageName}
      />

      {/* Error display */}
      {isFailed && stage?.error && (
        <div
          className="p-3 rounded-mars-md text-sm"
          style={{
            backgroundColor: 'var(--mars-color-danger-subtle)',
            color: 'var(--mars-color-danger)',
            border: '1px solid var(--mars-color-danger)',
          }}
        >
          {stage.error}
        </div>
      )}

      {/* Retry button for failed stages (with settings gear) */}
      {isFailed && (
        <div className="space-y-3">
          <div className="flex items-center justify-center gap-2">
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
              <Play className="w-4 h-4 mr-1" />
              Retry
            </Button>
          </div>
          {showSettings && (
            <div
              className="p-4 rounded-mars-md border space-y-4"
              style={{ backgroundColor: 'var(--mars-color-surface-overlay)', borderColor: 'var(--mars-color-border)' }}
            >
              <NpStageAdvancedSettings stageNum={stageNum} cfg={taskConfig} updateCfg={updateCfg} />
            </div>
          )}
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between pt-4">
        <Button onClick={onBack} variant="secondary" size="sm" disabled={isExecuting}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Back
        </Button>
        {isCompleted && (
          <Button onClick={onNext} variant="primary" size="sm">
            View Report <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        )}
      </div>
    </div>
  )
}
