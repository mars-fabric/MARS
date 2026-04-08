'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { ArrowLeft, Trash2, RotateCcw, ArrowRight, X, BookOpen } from 'lucide-react'
import { Button } from '@/components/core'
import Stepper from '@/components/core/Stepper'
import type { StepperStep } from '@/components/core/Stepper'
import { useRfpTask } from '@/hooks/useRfpTask'
import { RFP_STEP_LABELS, RFP_WIZARD_STEP_TO_STAGE, RFP_STAGE_SHARED_KEYS, RFP_STAGE_NAMES } from '@/types/rfp'
import type { RfpWizardStep } from '@/types/rfp'
import RfpSetupPanel from '@/components/rfp/RfpSetupPanel'
import RfpReviewPanel from '@/components/rfp/RfpReviewPanel'
import RfpExecutionPanel from '@/components/rfp/RfpExecutionPanel'
import RfpProposalPanel from '@/components/rfp/RfpProposalPanel'
import { getApiUrl } from '@/lib/config'

interface RecentRfpTask {
    task_id: string
    task: string
    status: string
    created_at: string | null
    current_stage: number | null
    progress_percent: number
}

const RFP_STAGE_LABEL_MAP: Record<number, string> = {
    1: 'Requirements Analysis',
    2: 'Tools & Technology',
    3: 'Cloud & Infrastructure',
    4: 'Implementation Plan',
    5: 'Architecture Design',
    6: 'Execution Strategy',
    7: 'Proposal Compilation',
}

interface RfpProposalTaskProps {
    onBack: () => void
    resumeTaskId?: string | null
}

export default function RfpProposalTask({ onBack, resumeTaskId }: RfpProposalTaskProps) {
    const hook = useRfpTask()
    const {
        taskId,
        taskState,
        currentStep,
        error,
        isExecuting,
        setCurrentStep,
        resumeTask,
        deleteTask,
        resetFromStage,
        clearError,
    } = hook

    const [recentTasks, setRecentTasks] = useState<RecentRfpTask[]>([])

    // Fetch recent in-progress tasks (always, not just when no active task)
    useEffect(() => {
        if (resumeTaskId) return
        let cancelled = false
        fetch(getApiUrl('/api/rfp/recent'))
            .then(r => r.ok ? r.json() : [])
            .then((data: RecentRfpTask[]) => { if (!cancelled) setRecentTasks(data) })
            .catch(() => { })
        return () => { cancelled = true }
    }, [resumeTaskId])

    // Resume on mount
    useEffect(() => {
        if (resumeTaskId) {
            resumeTask(resumeTaskId)
        }
    }, [resumeTaskId, resumeTask])

    const handleResumeRecent = useCallback((id: string) => {
        resumeTask(id)
    }, [resumeTask])

    const handleDeleteRecent = useCallback(async (id: string, e: React.MouseEvent) => {
        e.stopPropagation()
        if (!confirm('Delete this RFP Proposal task? This will remove all data and files.')) return
        try {
            await fetch(getApiUrl(`/api/rfp/${id}`), { method: 'DELETE' })
            setRecentTasks(prev => prev.filter(t => t.task_id !== id))
        } catch { /* ignore */ }
    }, [])

    // Build stepper steps
    const stepperSteps: StepperStep[] = RFP_STEP_LABELS.map((label, idx) => {
        const stageNum = RFP_WIZARD_STEP_TO_STAGE[idx]
        let status: StepperStep['status'] = 'pending'

        // Base status from task state
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

        if (idx === 0 && taskId) {
            status = 'completed'
        }

        // Mark the currently-viewed step as active
        if (idx === currentStep && status !== 'failed') {
            status = 'active'
        }

        return { id: `step-${idx}`, label, status }
    })

    const goNext = useCallback(() => {
        if (currentStep < 7) {
            setCurrentStep((currentStep + 1) as RfpWizardStep)
        }
    }, [currentStep, setCurrentStep])

    const goBack = useCallback(() => {
        if (currentStep > 0 && !isExecuting) {
            setCurrentStep((currentStep - 1) as RfpWizardStep)
        }
    }, [currentStep, isExecuting, setCurrentStep])

    const handleDelete = useCallback(async () => {
        if (!confirm('Delete this task? This will remove all data and files.')) return
        await deleteTask()
        onBack()
    }, [deleteTask, onBack])

    // Navigate to a step via stepper click
    const handleStepClick = useCallback((index: number) => {
        if (isExecuting) return
        setCurrentStep(index as RfpWizardStep)
    }, [isExecuting, setCurrentStep])

    // Check if there are completed stages after the current step
    const hasLaterCompletedStages = useCallback(() => {
        if (!taskState) return false
        const currentStageNum = RFP_WIZARD_STEP_TO_STAGE[currentStep]
        if (!currentStageNum) return false
        return taskState.stages.some(
            s => s.stage_number > currentStageNum && s.status === 'completed'
        )
    }, [taskState, currentStep])

    const handleResetFromHere = useCallback(async () => {
        const stageNum = RFP_WIZARD_STEP_TO_STAGE[currentStep]
        if (!stageNum) return
        const nextStage = stageNum + 1
        if (nextStage > 7) return
        if (!confirm(`Reset all stages from Stage ${nextStage} onwards? Their output will be deleted.`)) return
        await resetFromStage(nextStage)
    }, [currentStep, resetFromStage])

    // Filter out the currently active task from recent list
    const visibleRecentTasks = recentTasks.filter(t => t.task_id !== taskId)

    return (
        <div className="p-6 max-w-7xl mx-auto">
            {/* In-progress tasks section */}
            {currentStep === 0 && visibleRecentTasks.length > 0 && (
                <div className="mb-6">
                    <h3 className="text-xs font-medium uppercase tracking-wider mb-2"
                        style={{ color: 'var(--mars-color-text-tertiary)' }}>
                        In Progress
                    </h3>
                    <div className="space-y-2" style={{ maxHeight: '320px', overflowY: 'auto' }}>
                        {visibleRecentTasks.map((task) => (
                            <button key={task.task_id} onClick={() => handleResumeRecent(task.task_id)}
                                className="w-full flex items-center gap-3 p-3 rounded-mars-md border transition-colors hover:border-[var(--mars-color-primary)]"
                                style={{ borderColor: 'var(--mars-color-border)', backgroundColor: 'var(--mars-color-surface)' }}>
                                <div className="flex-shrink-0 w-8 h-8 rounded-mars-md flex items-center justify-center"
                                    style={{ background: 'linear-gradient(135deg, #ec4899, #f43f5e)' }}>
                                    <BookOpen className="w-4 h-4 text-white" />
                                </div>
                                <div className="flex-1 text-left min-w-0">
                                    <p className="text-sm font-medium truncate" style={{ color: 'var(--mars-color-text)' }}>
                                        RFP Proposal{task.task ? ` — ${task.task}` : ''}
                                    </p>
                                    <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                                        {task.current_stage
                                            ? `Stage ${task.current_stage}: ${RFP_STAGE_LABEL_MAP[task.current_stage] || ''}`
                                            : 'Starting...'}
                                        {' '}&middot;{' '}
                                        {Math.round(task.progress_percent)}% complete
                                    </p>
                                </div>
                                <div className="flex-shrink-0 w-20 h-1.5 rounded-full overflow-hidden"
                                    style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}>
                                    <div className="h-full rounded-full transition-all"
                                        style={{ width: `${Math.max(5, task.progress_percent)}%`, background: 'linear-gradient(90deg, #ec4899, #f43f5e)' }} />
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
                </div>
            )}

            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
                <button
                    onClick={onBack}
                    className="p-2 rounded-mars-md transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
                    style={{ color: 'var(--mars-color-text-secondary)' }}
                >
                    <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                    <h2
                        className="text-2xl font-semibold"
                        style={{ color: 'var(--mars-color-text)' }}
                    >
                        RFP Proposal Generator
                    </h2>
                    <p
                        className="text-sm mt-0.5"
                        style={{ color: 'var(--mars-color-text-secondary)' }}
                    >
                        Generate a complete technical proposal from an RFP through 7 interactive stages
                    </p>
                </div>
                {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
                    <div
                        className="ml-auto text-xs px-3 py-1.5 rounded-mars-md"
                        style={{
                            backgroundColor: 'var(--mars-color-surface-overlay)',
                            color: 'var(--mars-color-text-secondary)',
                        }}
                    >
                        Cost: ${taskState.total_cost_usd.toFixed(4)}
                    </div>
                )}
                {taskId && (
                    <div className={`flex items-center gap-2 ${taskState?.total_cost_usd ? '' : 'ml-auto'}`}>
                        <Button
                            onClick={handleDelete}
                            variant="secondary"
                            size="sm"
                            disabled={isExecuting}
                        >
                            <Trash2 className="w-3.5 h-3.5 mr-1" />
                            Delete
                        </Button>
                    </div>
                )}
            </div>

            {/* Error banner */}
            {error && (
                <div
                    className="mb-4 p-3 rounded-mars-md flex items-center justify-between text-sm"
                    style={{
                        backgroundColor: 'var(--mars-color-danger-subtle)',
                        color: 'var(--mars-color-danger)',
                        border: '1px solid var(--mars-color-danger)',
                    }}
                >
                    <span>{error}</span>
                    <button onClick={clearError} className="ml-2 font-medium underline">
                        Dismiss
                    </button>
                </div>
            )}

            {/* Stepper */}
            <div className="mb-8">
                <Stepper steps={stepperSteps} orientation="horizontal" size="sm" onStepClick={taskId ? handleStepClick : undefined} />
            </div>

            {/* Reset from here banner */}
            {hasLaterCompletedStages() && !isExecuting && (
                <div
                    className="mb-4 p-3 rounded-mars-md flex items-center justify-between text-sm"
                    style={{
                        backgroundColor: 'var(--mars-color-warning-subtle, rgba(245,158,11,0.1))',
                        border: '1px solid var(--mars-color-warning, #f59e0b)',
                        color: 'var(--mars-color-text)',
                    }}
                >
                    <span style={{ color: 'var(--mars-color-text-secondary)' }}>
                        Stages after this one have already been completed. You can reset them to re-run from this point.
                    </span>
                    <button
                        onClick={handleResetFromHere}
                        className="ml-3 flex items-center gap-1.5 px-3 py-1.5 rounded-mars-sm text-xs font-medium transition-colors"
                        style={{
                            backgroundColor: 'var(--mars-color-warning, #f59e0b)',
                            color: '#fff',
                        }}
                    >
                        <RotateCcw className="w-3.5 h-3.5" />
                        Reset Later Stages
                    </button>
                </div>
            )}

            {/* Panel content */}
            <div>
                {currentStep === 0 && (
                    <RfpSetupPanel hook={hook} onNext={goNext} />
                )}
                {currentStep === 1 && (
                    <RfpReviewPanel
                        hook={hook}
                        stageNum={1}
                        stageName="Requirements Analysis"
                        sharedKey="requirements_analysis"
                        onNext={goNext}
                        onBack={goBack}
                    />
                )}
                {currentStep === 2 && (
                    <RfpReviewPanel
                        hook={hook}
                        stageNum={2}
                        stageName="Tools & Technology"
                        sharedKey="tools_technology"
                        onNext={goNext}
                        onBack={goBack}
                    />
                )}
                {currentStep === 3 && (
                    <RfpReviewPanel
                        hook={hook}
                        stageNum={3}
                        stageName="Cloud & Infrastructure"
                        sharedKey="cloud_infrastructure"
                        onNext={goNext}
                        onBack={goBack}
                    />
                )}
                {currentStep === 4 && (
                    <RfpReviewPanel
                        hook={hook}
                        stageNum={4}
                        stageName="Implementation Plan"
                        sharedKey="implementation_plan"
                        onNext={goNext}
                        onBack={goBack}
                    />
                )}
                {currentStep === 5 && (
                    <RfpReviewPanel
                        hook={hook}
                        stageNum={5}
                        stageName="Architecture Design"
                        sharedKey="architecture_design"
                        onNext={goNext}
                        onBack={goBack}
                    />
                )}
                {currentStep === 6 && (
                    <RfpReviewPanel
                        hook={hook}
                        stageNum={6}
                        stageName="Execution Strategy"
                        sharedKey="execution_strategy"
                        onNext={goNext}
                        onBack={goBack}
                    />
                )}
                {currentStep === 7 && (
                    <RfpProposalPanel
                        hook={hook}
                        stageNum={7}
                        onBack={goBack}
                    />
                )}
            </div>
        </div>
    )
}
