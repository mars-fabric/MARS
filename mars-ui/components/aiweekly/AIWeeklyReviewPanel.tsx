'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react'
import { Eye, Edit3, ArrowRight, ArrowLeft, Play, Loader2 } from 'lucide-react'
import { Button } from '@/components/core'
import RefinementChat from '@/components/deepresearch/RefinementChat'
import ExecutionProgress from '@/components/deepresearch/ExecutionProgress'
import MarkdownRenderer from '@/components/files/MarkdownRenderer'
import type { UseAIWeeklyTaskReturn } from '@/hooks/useAIWeeklyTask'

interface AIWeeklyReviewPanelProps {
    hook: UseAIWeeklyTaskReturn
    stageNum: number
    stageName: string
    sharedKey: string
    onNext: () => void
    onBack: () => void
}

export default function AIWeeklyReviewPanel({
    hook, stageNum, stageName, sharedKey, onNext, onBack,
}: AIWeeklyReviewPanelProps) {
    const {
        taskState, editableContent, setEditableContent,
        refinementMessages, consoleOutput, isExecuting,
        executeStage, fetchStageContent, saveStageContent, refineContent,
    } = hook

    const [mode, setMode] = useState<'edit' | 'preview'>('edit')
    const [saveIndicator, setSaveIndicator] = useState<'idle' | 'saving' | 'saved'>('idle')
    const [contentLoaded, setContentLoaded] = useState(false)
    const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const stage = taskState?.stages.find(s => s.stage_number === stageNum)
    const isStageCompleted = stage?.status === 'completed'
    const isStageRunning = stage?.status === 'running' || isExecuting
    const isStageNotStarted = stage?.status === 'pending'
    const isStageFailed = stage?.status === 'failed'

    useEffect(() => {
        if ((isStageCompleted || isStageFailed) && !contentLoaded) {
            fetchStageContent(stageNum).then(() => setContentLoaded(true))
        }
    }, [isStageCompleted, isStageFailed, contentLoaded, fetchStageContent, stageNum])

    const canEdit = isStageCompleted || (isStageFailed && !!editableContent)

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

    const handleRefine = useCallback(async (message: string) => {
        return refineContent(stageNum, message, editableContent)
    }, [refineContent, stageNum, editableContent])

    const handleApply = useCallback((content: string) => {
        setEditableContent(content)
        if (canEdit) saveStageContent(stageNum, content, sharedKey)
    }, [setEditableContent, canEdit, saveStageContent, stageNum, sharedKey])

    const handleNext = useCallback(async () => {
        if (canEdit) {
            if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
            await saveStageContent(stageNum, editableContent, sharedKey)
        }
        const nextStageNum = stageNum + 1
        if (nextStageNum <= 4) {
            const nextStage = taskState?.stages.find(s => s.stage_number === nextStageNum)
            if (nextStage?.status === 'pending') executeStage(nextStageNum)
        }
        onNext()
    }, [canEdit, saveStageContent, stageNum, editableContent, sharedKey, taskState, executeStage, onNext])

    // Not started
    if (isStageNotStarted && !isExecuting) {
        return (
            <div className="max-w-3xl mx-auto space-y-3">
                <div className="flex items-center justify-between py-2">
                    <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>{stageName}</span>
                    <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
                        <Play className="w-3.5 h-3.5 mr-1.5" />Run {stageName}
                    </Button>
                </div>
                <div className="flex justify-start pt-1">
                    <Button onClick={onBack} variant="secondary" size="sm"><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
                </div>
            </div>
        )
    }

    // Running
    if (isStageRunning && !canEdit) {
        return (
            <div className="max-w-4xl mx-auto space-y-4">
                <ExecutionProgress consoleOutput={consoleOutput} isExecuting={isExecuting} stageName={stageName} />
                <div className="flex justify-start">
                    <Button onClick={onBack} variant="secondary" size="sm" disabled={isExecuting}><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
                </div>
            </div>
        )
    }

    // Failed
    if (isStageFailed && !canEdit) {
        return (
            <div className="max-w-3xl mx-auto space-y-4">
                <ExecutionProgress consoleOutput={consoleOutput} isExecuting={false} stageName={stageName} />
                {stage?.error && (
                    <div className="p-3 rounded-mars-md text-sm" style={{ backgroundColor: 'var(--mars-color-danger-subtle)', color: 'var(--mars-color-danger)', border: '1px solid var(--mars-color-danger)' }}>
                        {stage.error}
                    </div>
                )}
                <div className="flex items-center gap-2">
                    <Button onClick={onBack} variant="secondary" size="sm"><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
                    <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm"><Play className="w-4 h-4 mr-1" />Retry</Button>
                </div>
            </div>
        )
    }

    // Review — content available
    return (
        <div className="flex gap-4" style={{ minHeight: '600px' }}>
            {/* Main editor / preview */}
            <div className="flex-1 min-w-0 space-y-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1">
                        <button onClick={() => setMode('edit')}
                            className={`px-3 py-1.5 rounded-mars-sm text-xs font-medium transition-colors ${mode === 'edit' ? 'bg-[var(--mars-color-primary)] text-white' : ''}`}
                            style={mode !== 'edit' ? { color: 'var(--mars-color-text-secondary)' } : {}}>
                            <Edit3 className="w-3 h-3 inline mr-1" />Edit
                        </button>
                        <button onClick={() => setMode('preview')}
                            className={`px-3 py-1.5 rounded-mars-sm text-xs font-medium transition-colors ${mode === 'preview' ? 'bg-[var(--mars-color-primary)] text-white' : ''}`}
                            style={mode !== 'preview' ? { color: 'var(--mars-color-text-secondary)' } : {}}>
                            <Eye className="w-3 h-3 inline mr-1" />Preview
                        </button>
                    </div>
                    <span className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                        {saveIndicator === 'saving' && 'Saving...'}
                        {saveIndicator === 'saved' && '✓ Saved'}
                    </span>
                </div>

                {mode === 'edit' ? (
                    <textarea
                        value={editableContent}
                        onChange={e => handleContentChange(e.target.value)}
                        className="w-full rounded-mars-md border p-4 text-sm font-mono resize-none outline-none"
                        style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)', minHeight: '500px' }}
                    />
                ) : (
                    <div className="rounded-mars-md border p-4 prose prose-sm max-w-none overflow-y-auto"
                        style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', minHeight: '500px', maxHeight: '700px' }}>
                        <MarkdownRenderer content={editableContent} />
                    </div>
                )}

                {/* Navigation */}
                <div className="flex items-center justify-between pt-2">
                    <Button onClick={onBack} variant="secondary" size="sm"><ArrowLeft className="w-4 h-4 mr-1" />Back</Button>
                    <Button onClick={handleNext} variant="primary" size="sm">Next<ArrowRight className="w-4 h-4 ml-1" /></Button>
                </div>
            </div>

            {/* Refinement chat (40%) */}
            <div className="w-[380px] flex-shrink-0">
                <RefinementChat
                    messages={refinementMessages}
                    onSend={handleRefine}
                    onApply={handleApply}
                />
            </div>
        </div>
    )
}
