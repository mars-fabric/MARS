'use client'

import React, { useState, useCallback } from 'react'
import { Sparkles, Calendar, Settings2 } from 'lucide-react'
import { Button } from '@/components/core'
import type { UseAIWeeklyTaskReturn } from '@/hooks/useAIWeeklyTask'
import { useModelConfig } from '@/hooks/useModelConfig'

interface AIWeeklySetupPanelProps {
    hook: UseAIWeeklyTaskReturn
    onNext: () => void
}

const AVAILABLE_TOPICS = [
    { id: 'llm', label: 'Large Language Models' },
    { id: 'cv', label: 'Computer Vision' },
    { id: 'rl', label: 'Reinforcement Learning' },
    { id: 'robotics', label: 'Robotics and Quantum' },
    { id: 'ml-open-ai', label: 'Machine Learning Open AI' },
    { id: 'ai', label: 'Artificial Intelligence' },
]

const AVAILABLE_SOURCES = [
    { id: 'github', label: 'GitHub Releases' },
    { id: 'press-releases', label: 'Press Releases' },
    { id: 'company-announcements', label: 'Company Announcements' },
    { id: 'curated-ai-websites', label: 'Curated AI Websites / Blogs' },
]

export default function AIWeeklySetupPanel({ hook, onNext }: AIWeeklySetupPanelProps) {
    const { createTask, executeStage, isLoading, stageConfig, setStageConfig } = hook
    const { availableModels } = useModelConfig()

    const [dateFrom, setDateFrom] = useState(() => {
        const d = new Date(); d.setDate(d.getDate() - 7)
        return d.toISOString().split('T')[0]
    })
    const [dateTo, setDateTo] = useState(() => new Date().toISOString().split('T')[0])
    const [topics, setTopics] = useState<string[]>(['llm', 'cv'])
    const [sources, setSources] = useState<string[]>([
        'github', 'press-releases', 'company-announcements', 'major-releases', 'curated-ai-websites',
    ])
    const [style, setStyle] = useState<'concise' | 'detailed' | 'technical'>('concise')
    const [submitted, setSubmitted] = useState(false)
    const [showModelSettings, setShowModelSettings] = useState(false)

    const toggle = (arr: string[], id: string, setter: (v: string[]) => void) => {
        setter(arr.includes(id) ? arr.filter(x => x !== id) : [...arr, id])
    }

    const canSubmit = topics.length > 0 && sources.length > 0 && dateFrom && dateTo && dateFrom <= dateTo && !isLoading && !submitted

    const handleSubmit = useCallback(async () => {
        if (!canSubmit) return
        setSubmitted(true)
        const id = await createTask({ date_from: dateFrom, date_to: dateTo, topics, sources, style })
        if (id) await executeStage(1, id)
        onNext()
    }, [canSubmit, dateFrom, dateTo, topics, sources, style, createTask, executeStage, onNext])

    const chipClass = (active: boolean) =>
        `px-3 py-1.5 rounded-mars-sm text-xs font-medium cursor-pointer transition-colors border ${active
            ? 'bg-[var(--mars-color-primary)] text-white border-transparent'
            : 'border-[var(--mars-color-border)] text-[var(--mars-color-text-secondary)]'
        }`

    return (
        <div className="max-w-3xl mx-auto space-y-6">
            {/* Date range */}
            <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--mars-color-text)' }}>
                    <Calendar className="w-4 h-4 inline mr-1.5" />
                    Coverage Window
                </label>
                <div className="flex items-center gap-3">
                    <input
                        type="date" value={dateFrom}
                        onChange={e => setDateFrom(e.target.value)}
                        className="rounded-mars-md border px-3 py-2 text-sm outline-none"
                        style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
                    />
                    <span style={{ color: 'var(--mars-color-text-secondary)' }}>to</span>
                    <input
                        type="date" value={dateTo}
                        onChange={e => setDateTo(e.target.value)}
                        className="rounded-mars-md border px-3 py-2 text-sm outline-none"
                        style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
                    />
                </div>
            </div>

            {/* Topics */}
            <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--mars-color-text)' }}>
                    Topics
                </label>
                <div className="flex flex-wrap gap-2">
                    {AVAILABLE_TOPICS.map(t => (
                        <button key={t.id} className={chipClass(topics.includes(t.id))} onClick={() => toggle(topics, t.id, setTopics)}>
                            {t.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Sources */}
            <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--mars-color-text)' }}>
                    Sources
                </label>
                <div className="flex flex-wrap gap-2">
                    {AVAILABLE_SOURCES.map(s => (
                        <button key={s.id} className={chipClass(sources.includes(s.id))} onClick={() => toggle(sources, s.id, setSources)}>
                            {s.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Style */}
            <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--mars-color-text)' }}>
                    Report Style
                </label>
                <div className="flex gap-2">
                    {(['concise', 'detailed', 'technical'] as const).map(s => (
                        <button key={s} className={chipClass(style === s)} onClick={() => setStyle(s)}>
                            {s.charAt(0).toUpperCase() + s.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Submit */}
            <div className="flex justify-end pt-2">
                <Button onClick={handleSubmit} disabled={!canSubmit} variant="primary" size="md">
                    <Sparkles className="w-4 h-4 mr-2" />
                    Generate Report
                </Button>
            </div>

            {/* Model Settings (collapsible) */}
            <div className="border rounded-mars-md overflow-hidden" style={{ borderColor: 'var(--mars-color-border)' }}>
                <button
                    onClick={() => setShowModelSettings(!showModelSettings)}
                    className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium"
                    style={{ color: 'var(--mars-color-text)', backgroundColor: 'var(--mars-color-surface)' }}
                >
                    <span className="flex items-center gap-2">
                        <Settings2 className="w-4 h-4" />
                        Model Settings
                    </span>
                    <span className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>
                        {stageConfig.model || 'gpt-4o (default)'}
                    </span>
                </button>
                {showModelSettings && (
                    <div className="px-4 py-3 space-y-3 border-t" style={{ borderColor: 'var(--mars-color-border)' }}>
                        <p className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>
                            Configure LLM models for Stages 2–4 (Data Collection uses no LLM).
                        </p>
                        {/* Primary Model */}
                        <div>
                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--mars-color-text)' }}>
                                Primary Model (Generation)
                            </label>
                            <select
                                value={stageConfig.model || ''}
                                onChange={e => setStageConfig({ ...stageConfig, model: e.target.value || undefined })}
                                className="w-full rounded-mars-sm border px-2 py-1.5 text-sm outline-none"
                                style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
                            >
                                <option value="">Default (gpt-4o)</option>
                                {availableModels.map(m => (
                                    <option key={m.value} value={m.value}>{m.label}</option>
                                ))}
                            </select>
                        </div>
                        {/* Review Model */}
                        <div>
                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--mars-color-text)' }}>
                                Review Model (Quality Check)
                            </label>
                            <select
                                value={stageConfig.review_model || ''}
                                onChange={e => setStageConfig({ ...stageConfig, review_model: e.target.value || undefined })}
                                className="w-full rounded-mars-sm border px-2 py-1.5 text-sm outline-none"
                                style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
                            >
                                <option value="">Same as Primary</option>
                                {availableModels.map(m => (
                                    <option key={m.value} value={m.value}>{m.label}</option>
                                ))}
                            </select>
                        </div>
                        {/* Specialist Model */}
                        <div>
                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--mars-color-text)' }}>
                                Specialist Model (Fact-Check)
                            </label>
                            <select
                                value={stageConfig.specialist_model || ''}
                                onChange={e => setStageConfig({ ...stageConfig, specialist_model: e.target.value || undefined })}
                                className="w-full rounded-mars-sm border px-2 py-1.5 text-sm outline-none"
                                style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
                            >
                                <option value="">Same as Primary</option>
                                {availableModels.map(m => (
                                    <option key={m.value} value={m.value}>{m.label}</option>
                                ))}
                            </select>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
