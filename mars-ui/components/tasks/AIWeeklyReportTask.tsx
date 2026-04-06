'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { ArrowLeft, Trash2, RotateCcw, ArrowRight, X, Newspaper } from 'lucide-react'
import { Button } from '@/components/core'
import Stepper from '@/components/core/Stepper'
import type { StepperStep } from '@/components/core/Stepper'
import { useAIWeeklyTask } from '@/hooks/useAIWeeklyTask'
import {
    AIWEEKLY_STEP_LABELS,
    AIWEEKLY_WIZARD_STEP_TO_STAGE,
    AIWEEKLY_STAGE_SHARED_KEYS,
} from '@/types/aiweekly'
import type { AIWeeklyWizardStep } from '@/types/aiweekly'
import AIWeeklySetupPanel from '@/components/aiweekly/AIWeeklySetupPanel'
import AIWeeklyReviewPanel from '@/components/aiweekly/AIWeeklyReviewPanel'
import AIWeeklyReportPanel from '@/components/aiweekly/AIWeeklyReportPanel'
import { getApiUrl } from '@/lib/config'

interface RecentAiWeeklyTask {
    task_id: string
    task: string
    status: string
    created_at: string | null
    current_stage: number | null
    progress_percent: number
}

const AW_STAGE_NAMES: Record<number, string> = {
    1: 'Data Collection',
    2: 'Content Curation',
    3: 'Report Generation',
    4: 'Quality Review',
}

interface AIAIWeeklyReportTaskProps {
    onBack: () => void
    resumeTaskId?: string | null
}

export default function AIWeeklyReportTask({ onBack, resumeTaskId }: AIAIWeeklyReportTaskProps) {
    const hook = useAIWeeklyTask()
    const {
        taskId, taskState, currentStep, error, isExecuting,
        setCurrentStep, resumeTask, deleteTask, resetFromStage, clearError,
    } = hook

    const [recentTasks, setRecentTasks] = useState<RecentAiWeeklyTask[]>([])

    // Fetch recent in-progress tasks (always, not just when no active task)
    useEffect(() => {
        if (resumeTaskId) return
        let cancelled = false
        fetch(getApiUrl('/api/aiweekly/recent'))
            .then(r => r.ok ? r.json() : [])
            .then((data: RecentAiWeeklyTask[]) => { if (!cancelled) setRecentTasks(data) })
            .catch(() => { })
        return () => { cancelled = true }
    }, [resumeTaskId])

    useEffect(() => {
        if (resumeTaskId) resumeTask(resumeTaskId)
    }, [resumeTaskId, resumeTask])

    const handleResumeRecent = useCallback((id: string) => {
        resumeTask(id)
    }, [resumeTask])

    const handleDeleteRecent = useCallback(async (id: string, e: React.MouseEvent) => {
        e.stopPropagation()
        if (!confirm('Delete this task? This will remove all data and files.')) return
        try {
            await fetch(getApiUrl(`/api/aiweekly/${id}`), { method: 'DELETE' })
            setRecentTasks(prev => prev.filter(t => t.task_id !== id))
        } catch { /* ignore */ }
    }, [])

    // Stepper
    const stepperSteps: StepperStep[] = AIWEEKLY_STEP_LABELS.map((label, idx) => {
        const stageNum = AIWEEKLY_WIZARD_STEP_TO_STAGE[idx]
        let status: StepperStep['status'] = 'pending'

        if (taskState && stageNum) {
            const stage = taskState.stages.find(s => s.stage_number === stageNum)
            if (stage) {
                if (stage.status === 'completed') status = 'completed'
                else if (stage.status === 'failed') status = 'failed'
                else if (stage.status === 'running') status = 'active'
            }
        } else if (idx < currentStep) {
            status = 'completed'
        }

        if (idx === 0 && taskId) status = 'completed'
        if (idx === currentStep && status !== 'failed') status = 'active'

        return { id: `step-${idx}`, label, status }
    })

    const goNext = useCallback(() => {
        if (currentStep < 4) setCurrentStep((currentStep + 1) as AIWeeklyWizardStep)
    }, [currentStep, setCurrentStep])

    const goBack = useCallback(() => {
        if (currentStep > 0 && !isExecuting) setCurrentStep((currentStep - 1) as AIWeeklyWizardStep)
    }, [currentStep, isExecuting, setCurrentStep])

    const handleDelete = useCallback(async () => {
        if (!confirm('Delete this task? This will remove all data and files.')) return
        await deleteTask()
        onBack()
    }, [deleteTask, onBack])

    const handleStepClick = useCallback((index: number) => {
        if (isExecuting) return
        setCurrentStep(index as AIWeeklyWizardStep)
    }, [isExecuting, setCurrentStep])

    const hasLaterCompletedStages = useCallback(() => {
        if (!taskState) return false
        const currentStageNum = AIWEEKLY_WIZARD_STEP_TO_STAGE[currentStep]
        if (!currentStageNum) return false
        return taskState.stages.some(s => s.stage_number > currentStageNum && s.status === 'completed')
    }, [taskState, currentStep])

    const handleResetFromHere = useCallback(async () => {
        const stageNum = AIWEEKLY_WIZARD_STEP_TO_STAGE[currentStep]
        if (!stageNum) return
        const nextStage = stageNum + 1
        if (nextStage > 4) return
        if (!confirm(`Reset all stages from Stage ${nextStage} onwards?`)) return
        await resetFromStage(nextStage)
    }, [currentStep, resetFromStage])

    // Filter out the currently active task from recent list
    const visibleRecentTasks = recentTasks.filter(t => t.task_id !== taskId)

    return (
        <div className="p-6 max-w-7xl mx-auto">
            {/* In-progress tasks section */}
            {currentStep === 0 && visibleRecentTasks.length > 0 && (
                <div className="mb-6 space-y-2">
                    <h3 className="text-xs font-medium uppercase tracking-wider"
                        style={{ color: 'var(--mars-color-text-tertiary)' }}>
                        In Progress
                    </h3>
                    {visibleRecentTasks.map((task) => (
                        <button key={task.task_id} onClick={() => handleResumeRecent(task.task_id)}
                            className="w-full flex items-center gap-3 p-3 rounded-mars-md border transition-colors hover:border-[var(--mars-color-primary)]"
                            style={{ borderColor: 'var(--mars-color-border)', backgroundColor: 'var(--mars-color-surface)' }}>
                            <div className="flex-shrink-0 w-8 h-8 rounded-mars-md flex items-center justify-center"
                                style={{ background: 'linear-gradient(135deg, #3b82f6, #2563eb)' }}>
                                <Newspaper className="w-4 h-4 text-white" />
                            </div>
                            <div className="flex-1 text-left min-w-0">
                                <p className="text-sm font-medium truncate" style={{ color: 'var(--mars-color-text)' }}>
                                    AI Weekly Report{task.task ? ` — ${task.task}` : ''}
                                </p>
                                <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                                    {task.current_stage
                                        ? `Stage ${task.current_stage}: ${AW_STAGE_NAMES[task.current_stage] || ''}`
                                        : 'Starting...'}
                                    {' '}&middot;{' '}
                                    {Math.round(task.progress_percent)}% complete
                                </p>
                            </div>
                            <div className="flex-shrink-0 w-20 h-1.5 rounded-full overflow-hidden"
                                style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}>
                                <div className="h-full rounded-full transition-all"
                                    style={{ width: `${Math.max(5, task.progress_percent)}%`, background: 'linear-gradient(90deg, #3b82f6, #2563eb)' }} />
                            </div>
                            <ArrowRight className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--mars-color-text-tertiary)' }} />
                            <div role="button" tabIndex={0}
                                onClick={(e) => handleDeleteRecent(task.task_id, e)}
                                onKeyDown={(e) => { if (e.key === 'Enter') handleDeleteRecent(task.task_id, e as unknown as React.MouseEvent) }}
                                className="flex-shrink-0 p-1 rounded transition-colors hover:bg-[var(--mars-color-danger-subtle,rgba(239,68,68,0.1))]"
                                title="Delete task">
                                <X className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-tertiary)' }} />
                            </div>
                        </button>
                    ))}
                </div>
            )}

            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
                <button onClick={onBack}
                    className="p-2 rounded-mars-md transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
                    style={{ color: 'var(--mars-color-text-secondary)' }}>
                    <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                    <h2 className="text-2xl font-semibold" style={{ color: 'var(--mars-color-text)' }}>
                        AI Weekly Report
                    </h2>
                    <p className="text-sm mt-0.5" style={{ color: 'var(--mars-color-text-secondary)' }}>
                        Generate a publication-ready weekly AI report through 4 interactive stages
                    </p>
                </div>
                {taskId && (
                    <div className="ml-auto flex items-center gap-2">
                        <Button onClick={handleDelete} variant="secondary" size="sm" disabled={isExecuting}>
                            <Trash2 className="w-3.5 h-3.5 mr-1" />Delete
                        </Button>
                    </div>
                )}
            </div>

            {/* Error banner */}
            {error && (
                <div className="mb-4 p-3 rounded-mars-md flex items-center justify-between text-sm"
                    style={{ backgroundColor: 'var(--mars-color-danger-subtle)', color: 'var(--mars-color-danger)', border: '1px solid var(--mars-color-danger)' }}>
                    <span>{error}</span>
                    <button onClick={clearError} className="ml-2 font-medium underline">Dismiss</button>
                </div>
            )}

            {/* Stepper */}
            <div className="mb-8">
                <Stepper steps={stepperSteps} orientation="horizontal" size="sm" onStepClick={taskId ? handleStepClick : undefined} />
            </div>

            {/* Reset banner */}
            {hasLaterCompletedStages() && !isExecuting && (
                <div className="mb-4 p-3 rounded-mars-md flex items-center justify-between text-sm"
                    style={{ backgroundColor: 'var(--mars-color-warning-subtle, rgba(245,158,11,0.1))', border: '1px solid var(--mars-color-warning, #f59e0b)', color: 'var(--mars-color-text)' }}>
                    <span style={{ color: 'var(--mars-color-text-secondary)' }}>
                        Stages after this one have been completed. You can reset them to re-run.
                    </span>
                    <button onClick={handleResetFromHere}
                        className="ml-3 flex items-center gap-1.5 px-3 py-1.5 rounded-mars-sm text-xs font-medium transition-colors"
                        style={{ backgroundColor: 'var(--mars-color-warning, #f59e0b)', color: '#fff' }}>
                        <RotateCcw className="w-3.5 h-3.5" />Reset Later Stages
                    </button>
                </div>
            )}

            {/* Panel content */}
            <div>
                {currentStep === 0 && (
                    <AIWeeklySetupPanel hook={hook} onNext={goNext} />
                )}
                {currentStep === 1 && (
                    <AIWeeklyReviewPanel hook={hook} stageNum={1} stageName="Data Collection"
                        sharedKey="raw_collection" onNext={goNext} onBack={goBack} />
                )}
                {currentStep === 2 && (
                    <AIWeeklyReviewPanel hook={hook} stageNum={2} stageName="Content Curation"
                        sharedKey="curated_items" onNext={goNext} onBack={goBack} />
                )}
                {currentStep === 3 && (
                    <AIWeeklyReviewPanel hook={hook} stageNum={3} stageName="Report Generation"
                        sharedKey="draft_report" onNext={goNext} onBack={goBack} />
                )}
                {currentStep === 4 && (
                    <AIWeeklyReportPanel hook={hook} stageNum={4} onBack={goBack} />
                )}
            </div>
        </div>
    )
}
