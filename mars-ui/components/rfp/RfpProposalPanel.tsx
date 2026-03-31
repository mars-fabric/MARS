'use client'

import React, { useEffect, useState, useRef, useCallback } from 'react'
import { ArrowLeft, Download, CheckCircle, Play, FileText, Eye, X, Maximize2, Minimize2 } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from '@/components/deepresearch/ExecutionProgress'
import MarkdownRenderer from '@/components/files/MarkdownRenderer'
import type { useRfpTask } from '@/hooks/useRfpTask'
import { getApiUrl } from '@/lib/config'

interface RfpProposalPanelProps {
    hook: ReturnType<typeof useRfpTask>
    stageNum: number
    onBack: () => void
}

export default function RfpProposalPanel({ hook, stageNum, onBack }: RfpProposalPanelProps) {
    const {
        taskId,
        taskState,
        consoleOutput,
        isExecuting,
        executeStage,
        fetchStageContent,
        editableContent,
    } = hook

    const [contentLoaded, setContentLoaded] = useState(false)
    const [showFullView, setShowFullView] = useState(false)
    const [previewMaximized, setPreviewMaximized] = useState(false)
    const [previewSize, setPreviewSize] = useState({ width: 900, height: 700 })
    const resizingRef = useRef(false)
    const startPosRef = useRef({ x: 0, y: 0, w: 0, h: 0 })

    const stage = taskState?.stages.find(s => s.stage_number === stageNum)
    const isCompleted = stage?.status === 'completed'
    const isFailed = stage?.status === 'failed'
    const isNotStarted = stage?.status === 'pending'

    // Resize handlers for the preview modal
    const handleResizeStart = useCallback((e: React.MouseEvent) => {
        e.preventDefault()
        resizingRef.current = true
        startPosRef.current = { x: e.clientX, y: e.clientY, w: previewSize.width, h: previewSize.height }

        const handleResizeMove = (ev: MouseEvent) => {
            if (!resizingRef.current) return
            const dx = ev.clientX - startPosRef.current.x
            const dy = ev.clientY - startPosRef.current.y
            setPreviewSize({
                width: Math.max(600, startPosRef.current.w + dx),
                height: Math.max(400, startPosRef.current.h + dy),
            })
        }
        const handleResizeEnd = () => {
            resizingRef.current = false
            document.removeEventListener('mousemove', handleResizeMove)
            document.removeEventListener('mouseup', handleResizeEnd)
        }
        document.addEventListener('mousemove', handleResizeMove)
        document.addEventListener('mouseup', handleResizeEnd)
    }, [previewSize])

    // Load content when completed
    useEffect(() => {
        if (isCompleted && !contentLoaded) {
            fetchStageContent(stageNum).then(() => setContentLoaded(true))
        }
    }, [isCompleted, contentLoaded, fetchStageContent, stageNum])

    // Pre-execution
    if (isNotStarted && !isExecuting) {
        return (
            <div className="max-w-3xl mx-auto space-y-3">
                <div className="flex items-center justify-between py-2">
                    <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>
                        Proposal Compilation
                    </span>
                    <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
                        <Play className="w-3.5 h-3.5 mr-1.5" />
                        Generate Proposal
                    </Button>
                </div>
                <div className="flex justify-start pt-1">
                    <Button onClick={onBack} variant="secondary" size="sm">
                        <ArrowLeft className="w-4 h-4 mr-1" />
                        Back
                    </Button>
                </div>
            </div>
        )
    }

    // Running
    if (isExecuting || (stage?.status === 'running')) {
        return (
            <div className="max-w-4xl mx-auto space-y-4">
                <ExecutionProgress
                    consoleOutput={consoleOutput}
                    isExecuting={isExecuting}
                    stageName="Proposal Compilation"
                />
                <div className="flex justify-start">
                    <Button onClick={onBack} variant="secondary" size="sm" disabled={isExecuting}>
                        <ArrowLeft className="w-4 h-4 mr-1" />
                        Back
                    </Button>
                </div>
            </div>
        )
    }

    // Failed
    if (isFailed) {
        return (
            <div className="max-w-3xl mx-auto space-y-4">
                <ExecutionProgress
                    consoleOutput={consoleOutput}
                    isExecuting={false}
                    stageName="Proposal Compilation"
                />
                {stage?.error && (
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
                <div className="flex items-center gap-2">
                    <Button onClick={onBack} variant="secondary" size="sm">
                        <ArrowLeft className="w-4 h-4 mr-1" />
                        Back
                    </Button>
                    <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
                        <Play className="w-4 h-4 mr-1" />
                        Retry
                    </Button>
                </div>
            </div>
        )
    }

    // Completed — show the proposal
    return (
        <div className="max-w-4xl mx-auto space-y-6">
            {/* Success banner */}
            <div
                className="flex items-center gap-3 p-4 rounded-mars-md"
                style={{
                    backgroundColor: 'var(--mars-color-success-subtle, rgba(16,185,129,0.1))',
                    border: '1px solid var(--mars-color-success, #10b981)',
                }}
            >
                <CheckCircle className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--mars-color-success)' }} />
                <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--mars-color-success)' }}>
                        Proposal Generated Successfully
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--mars-color-text-secondary)' }}>
                        {taskState?.stages.filter(s => s.status === 'completed').length}/{taskState?.stages.length} stages completed
                        {taskState?.total_cost_usd != null && ` · Total cost: $${taskState.total_cost_usd.toFixed(4)}`}
                    </p>
                </div>
            </div>

            {/* Action buttons — PDF Download + View Online */}
            <div className="flex items-center gap-3">
                {taskId && (
                    <a
                        href={getApiUrl(`/api/rfp/${taskId}/download-pdf`)}
                        download="RFP_Proposal.pdf"
                    >
                        <Button variant="primary" size="sm">
                            <Download className="w-4 h-4 mr-1.5" />
                            Download PDF
                        </Button>
                    </a>
                )}
                <Button onClick={() => setShowFullView(true)} variant="secondary" size="sm">
                    <Eye className="w-4 h-4 mr-1.5" />
                    View Online
                </Button>
            </div>

            {/* Proposal preview (compact) */}
            <div
                className="rounded-mars-md border p-6 prose prose-sm max-w-none overflow-y-auto"
                style={{
                    backgroundColor: 'var(--mars-color-surface)',
                    borderColor: 'var(--mars-color-border)',
                    maxHeight: '500px',
                }}
            >
                <MarkdownRenderer content={editableContent || '(No content)'} />
            </div>

            {/* Download section — individual artifacts */}
            <div
                className="p-4 rounded-mars-md border"
                style={{
                    backgroundColor: 'var(--mars-color-surface-overlay)',
                    borderColor: 'var(--mars-color-border)',
                }}
            >
                <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--mars-color-text)' }}>
                    Generated Artifacts
                </h3>
                <div className="space-y-2">
                    {['requirements.md', 'tools.md', 'cloud.md', 'implementation.md', 'architecture.md', 'execution.md', 'proposal.md'].map((file) => (
                        <div
                            key={file}
                            className="flex items-center justify-between py-2 px-3 rounded-mars-sm"
                            style={{ backgroundColor: 'var(--mars-color-surface)' }}
                        >
                            <div className="flex items-center gap-2">
                                <FileText className="w-4 h-4" style={{ color: 'var(--mars-color-text-secondary)' }} />
                                <span className="text-sm" style={{ color: 'var(--mars-color-text)' }}>{file}</span>
                            </div>
                            {taskId && (
                                <a
                                    href={getApiUrl(`/api/rfp/${taskId}/download/${file}`)}
                                    className="text-xs font-medium hover:underline"
                                    style={{ color: 'var(--mars-color-primary)' }}
                                    download
                                >
                                    <Download className="w-3.5 h-3.5 inline mr-1" />
                                    Download
                                </a>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* Back */}
            <div className="flex justify-start">
                <Button onClick={onBack} variant="secondary" size="sm">
                    <ArrowLeft className="w-4 h-4 mr-1" />
                    Back
                </Button>
            </div>

            {/* Resizable PDF Preview modal */}
            {showFullView && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center"
                    style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
                    onClick={() => setShowFullView(false)}
                >
                    <div
                        className="relative flex flex-col rounded-lg shadow-2xl overflow-hidden"
                        style={{
                            backgroundColor: '#ffffff',
                            width: previewMaximized ? '100vw' : `${previewSize.width}px`,
                            height: previewMaximized ? '100vh' : `${previewSize.height}px`,
                            maxWidth: '100vw',
                            maxHeight: '100vh',
                            borderRadius: previewMaximized ? 0 : '8px',
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Modal header */}
                        <div
                            className="flex items-center justify-between px-5 py-3 border-b"
                            style={{ borderColor: '#e2e8f0', backgroundColor: '#f8fafc' }}
                        >
                            <h2 className="text-base font-semibold" style={{ color: '#1a202c' }}>
                                RFP Proposal — PDF Preview
                            </h2>
                            <div className="flex items-center gap-2">
                                {taskId && (
                                    <a href={getApiUrl(`/api/rfp/${taskId}/download-pdf`)} download="RFP_Proposal.pdf">
                                        <Button variant="primary" size="sm">
                                            <Download className="w-3.5 h-3.5 mr-1" />
                                            PDF
                                        </Button>
                                    </a>
                                )}
                                <Button
                                    onClick={() => setPreviewMaximized(!previewMaximized)}
                                    variant="secondary"
                                    size="sm"
                                >
                                    {previewMaximized
                                        ? <Minimize2 className="w-4 h-4" />
                                        : <Maximize2 className="w-4 h-4" />
                                    }
                                </Button>
                                <Button onClick={() => setShowFullView(false)} variant="secondary" size="sm">
                                    <X className="w-4 h-4" />
                                </Button>
                            </div>
                        </div>
                        {/* Modal body — PDF iframe */}
                        <div className="flex-1 overflow-hidden" style={{ backgroundColor: '#ffffff' }}>
                            {taskId ? (
                                <iframe
                                    src={getApiUrl(`/api/rfp/${taskId}/download-pdf?inline=true`) + '#toolbar=1&navpanes=0'}
                                    className="w-full h-full border-0"
                                    style={{ backgroundColor: '#ffffff' }}
                                    title="RFP Proposal PDF Preview"
                                />
                            ) : (
                                <div className="flex items-center justify-center h-full text-sm" style={{ color: '#718096' }}>
                                    No proposal available to preview
                                </div>
                            )}
                        </div>
                        {/* Resize handle (bottom-right corner) */}
                        {!previewMaximized && (
                            <div
                                className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
                                style={{
                                    background: 'linear-gradient(135deg, transparent 50%, #a0aec0 50%)',
                                    borderRadius: '0 0 8px 0',
                                }}
                                onMouseDown={handleResizeStart}
                            />
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
