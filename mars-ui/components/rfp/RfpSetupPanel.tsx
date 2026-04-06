'use client'

import React, { useState, useCallback, useEffect } from 'react'
import { Sparkles, Upload, FileText, Settings2 } from 'lucide-react'
import { Button } from '@/components/core'
import FileUploadZone from '@/components/deepresearch/FileUploadZone'
import RfpStageAdvancedSettings from './RfpStageAdvancedSettings'
import type { useRfpTask } from '@/hooks/useRfpTask'
import type { RfpStageConfig } from '@/types/rfp'

interface RfpSetupPanelProps {
    hook: ReturnType<typeof useRfpTask>
    onNext: () => void
}

export default function RfpSetupPanel({ hook, onNext }: RfpSetupPanelProps) {
    const {
        createTask,
        uploadFile,
        uploadedFiles,
        lastExtractedText,
        isLoading,
        executeStage,
        taskConfig,
        setTaskConfig,
    } = hook

    const [rfpText, setRfpText] = useState('')
    const [rfpContext, setRfpContext] = useState('')
    const [submitted, setSubmitted] = useState(false)
    const [showSettings, setShowSettings] = useState(false)

    const updateCfg = useCallback((patch: Partial<RfpStageConfig>) => {
        setTaskConfig({ ...taskConfig, ...patch })
    }, [taskConfig, setTaskConfig])

    // Auto-populate the textarea when PDF text is extracted from an upload
    useEffect(() => {
        if (lastExtractedText && !rfpText.trim()) {
            setRfpText(lastExtractedText)
        }
    }, [lastExtractedText])

    const hasContent = rfpText.trim().length > 0
    const hasFiles = uploadedFiles.some(f => f.status === 'done')
    const canSubmit = (hasContent || hasFiles) && !isLoading && !submitted

    const handleSubmit = useCallback(async () => {
        if (!canSubmit) return
        setSubmitted(true)
        // Use extracted/typed text, or a placeholder noting files are the source
        const taskText = rfpText.trim() || '(See uploaded RFP documents)'
        const id = await createTask(taskText, rfpContext || undefined)
        if (id) await executeStage(1, id)
        onNext()
    }, [canSubmit, rfpText, rfpContext, createTask, executeStage, onNext])

    return (
        <div className="max-w-3xl mx-auto space-y-6">

            {/* RFP Document Upload — moved above text area for upload-first flow */}
            <div>
                <label
                    className="block text-sm font-medium mb-2"
                    style={{ color: 'var(--mars-color-text)' }}
                >
                    Upload RFP Documents
                    <span
                        className="ml-2 text-xs font-normal"
                        style={{ color: 'var(--mars-color-text-tertiary)' }}
                    >
                        (PDF, DOCX, TXT — upload your RFP and text will be extracted automatically)
                    </span>
                </label>

                <FileUploadZone
                    files={uploadedFiles}
                    onUpload={uploadFile}
                    disabled={isLoading}
                />
            </div>

            {/* RFP Content */}
            <div>
                <label
                    className="block text-sm font-medium mb-2"
                    style={{ color: 'var(--mars-color-text)' }}
                >
                    RFP Content
                    <span
                        className="ml-2 text-xs font-normal"
                        style={{ color: 'var(--mars-color-text-tertiary)' }}
                    >
                        {hasFiles
                            ? '(Auto-filled from uploaded PDF — edit if needed)'
                            : '(Or paste the RFP text / describe project requirements manually)'}
                    </span>
                </label>
                <textarea
                    value={rfpText}
                    onChange={(e) => setRfpText(e.target.value)}
                    placeholder="Upload a PDF above to auto-extract text, or paste the RFP content here manually..."
                    rows={10}
                    className="w-full rounded-mars-md border p-3 text-sm resize-none outline-none transition-colors"
                    style={{
                        backgroundColor: 'var(--mars-color-surface)',
                        borderColor: 'var(--mars-color-border)',
                        color: 'var(--mars-color-text)',
                    }}
                />
            </div>

            {/* Additional Context */}
            <div>
                <label
                    className="block text-sm font-medium mb-2"
                    style={{ color: 'var(--mars-color-text)' }}
                >
                    Additional Context
                    <span
                        className="ml-2 text-xs font-normal"
                        style={{ color: 'var(--mars-color-text-tertiary)' }}
                    >
                        (Optional — organization info, budget range, preferences)
                    </span>
                </label>
                <textarea
                    value={rfpContext}
                    onChange={(e) => setRfpContext(e.target.value)}
                    placeholder="Any additional context that would help create a better proposal...&#10;&#10;Example: 'We prefer AWS cloud, budget is $500K–$1M, timeline is 6 months, team of 8 engineers available...'"
                    rows={4}
                    className="w-full rounded-mars-md border p-3 text-sm resize-none outline-none transition-colors"
                    style={{
                        backgroundColor: 'var(--mars-color-surface)',
                        borderColor: 'var(--mars-color-border)',
                        color: 'var(--mars-color-text)',
                    }}
                />
            </div>

            {/* Model Settings */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <span
                        className="text-xs font-medium"
                        style={{ color: 'var(--mars-color-text-secondary)' }}
                    >
                        Model settings
                    </span>
                    <button
                        onClick={() => setShowSettings(s => !s)}
                        title="Advanced model settings"
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
                        <RfpStageAdvancedSettings cfg={taskConfig} updateCfg={updateCfg} />
                    </div>
                )}
            </div>

            {/* Submit */}
            <div className="flex justify-end pt-2">
                <Button
                    onClick={handleSubmit}
                    disabled={!canSubmit}
                    variant="primary"
                    size="md"
                >
                    <Sparkles className="w-4 h-4 mr-2" />
                    Analyze Requirements
                </Button>
            </div>
        </div>
    )
}
