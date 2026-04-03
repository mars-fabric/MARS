'use client'

import React, { useState, useCallback } from 'react'
import { ArrowRight, Loader2, Settings2, Sparkles } from 'lucide-react'
import { Button } from '@/components/core'
import { TIME_WINDOW_OPTIONS, SETUP_SUGGESTIONS } from '@/types/newspulse'
import type { useNewsPulseTask } from '@/hooks/useNewsPulseTask'
import type { NewsPulseStageConfig } from '@/types/newspulse'
import NpStageAdvancedSettings from './NpStageAdvancedSettings'

const REGION_OPTIONS = [
  'Global',
  'North America',
  'Europe',
  'Asia Pacific',
  'Middle East & Africa',
  'Latin America',
  'India',
  'China',
  'United States',
  'United Kingdom',
]

interface NpSetupPanelProps {
  hook: ReturnType<typeof useNewsPulseTask>
  onNext: () => void
}

export default function NpSetupPanel({ hook, onNext }: NpSetupPanelProps) {
  const { createTask, isLoading, error, taskConfig, setTaskConfig } = hook

  const [formData, setFormData] = useState({
    industry: '',
    companies: '',
    region: 'Global',
    time_window: '2026',
  })
  const [showSettings, setShowSettings] = useState(false)

  const updateCfg = useCallback((patch: Partial<NewsPulseStageConfig>) => {
    setTaskConfig({ ...taskConfig, ...patch })
  }, [taskConfig, setTaskConfig])

  const handleInputChange = useCallback(
    (field: keyof typeof formData, value: string) => {
      setFormData(prev => ({ ...prev, [field]: value }))
    },
    []
  )

  const applySuggestion = useCallback((suggestion: typeof SETUP_SUGGESTIONS[number]) => {
    setFormData({
      industry: suggestion.industry,
      companies: suggestion.companies,
      region: suggestion.region,
      time_window: suggestion.time_window,
    })
  }, [])

  const handleSubmit = useCallback(async () => {
    if (!formData.industry.trim()) {
      return
    }
    const taskId = await createTask({
      industry: formData.industry,
      companies: formData.companies || undefined,
      region: formData.region || undefined,
      time_window: formData.time_window || undefined,
    })
    if (taskId) {
      // Execute stage 1 (Setup — completes instantly) then stage 2 (News Discovery)
      await hook.executeStage(1, taskId)
      onNext()
      await hook.executeStage(2, taskId)
    }
  }, [formData, createTask, hook, onNext])

  const selectStyle = {
    backgroundColor: 'var(--mars-color-surface-overlay)',
    borderColor: 'var(--mars-color-border)',
    color: 'var(--mars-color-text)',
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="space-y-6 p-6 rounded-mars-lg" style={{ backgroundColor: 'var(--mars-color-surface)' }}>
        <div>
          <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--mars-color-text)' }}>
            Configure Your Analysis
          </h3>
          <p style={{ color: 'var(--mars-color-text-secondary)' }} className="text-sm">
            Set up the industry, region, and time period for your news intelligence report.
            All research will be strictly limited to your chosen year and region.
          </p>
        </div>

        {/* Quick-start suggestions */}
        <div>
          <label className="block text-xs font-medium mb-2" style={{ color: 'var(--mars-color-text-tertiary)' }}>
            <Sparkles className="w-3 h-3 inline mr-1" />
            Quick Start — Click a template to pre-fill
          </label>
          <div className="flex flex-wrap gap-2">
            {SETUP_SUGGESTIONS.map((s) => (
              <button
                key={s.label}
                onClick={() => applySuggestion(s)}
                disabled={isLoading}
                className="px-3 py-1.5 text-xs rounded-mars-sm border transition-colors hover:opacity-80"
                style={{
                  borderColor: 'var(--mars-color-border)',
                  backgroundColor: 'var(--mars-color-surface-overlay)',
                  color: 'var(--mars-color-text-secondary)',
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div
            className="p-3 rounded-mars-md text-sm"
            style={{
              backgroundColor: 'var(--mars-color-danger-subtle)',
              color: 'var(--mars-color-danger)',
              border: '1px solid var(--mars-color-danger)',
            }}
          >
            {error}
          </div>
        )}

        <div className="space-y-4">
          {/* Industry */}
          <div>
            <label
              htmlFor="industry"
              className="block text-sm font-medium mb-2"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Industry / Sector *
            </label>
            <input
              id="industry"
              type="text"
              placeholder="e.g., Artificial Intelligence, Healthcare, Electric Vehicles"
              value={formData.industry}
              onChange={e => handleInputChange('industry', e.target.value)}
              disabled={isLoading}
              className="w-full px-3 py-2 rounded-mars-md border text-sm outline-none"
              style={selectStyle}
            />
          </div>

          {/* Companies */}
          <div>
            <label
              htmlFor="companies"
              className="block text-sm font-medium mb-2"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Companies (Optional)
            </label>
            <input
              id="companies"
              type="text"
              placeholder="e.g., Apple, Microsoft, Google (comma-separated)"
              value={formData.companies}
              onChange={e => handleInputChange('companies', e.target.value)}
              disabled={isLoading}
              className="w-full px-3 py-2 rounded-mars-md border text-sm outline-none"
              style={selectStyle}
            />
            <p className="text-xs mt-1" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              Leave blank for general industry coverage
            </p>
          </div>

          {/* Region — Dropdown */}
          <div>
            <label
              htmlFor="region"
              className="block text-sm font-medium mb-2"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Geographic Region *
            </label>
            <select
              id="region"
              value={formData.region}
              onChange={e => handleInputChange('region', e.target.value)}
              disabled={isLoading}
              className="w-full px-3 py-2 rounded-mars-md border text-sm outline-none"
              style={selectStyle}
            >
              {REGION_OPTIONS.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <p className="text-xs mt-1" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              Research and analysis will focus exclusively on this region
            </p>
          </div>

          {/* Time Window — Dropdown */}
          <div>
            <label
              htmlFor="time_window"
              className="block text-sm font-medium mb-2"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Time Period *
            </label>
            <select
              id="time_window"
              value={formData.time_window}
              onChange={e => handleInputChange('time_window', e.target.value)}
              disabled={isLoading}
              className="w-full px-3 py-2 rounded-mars-md border text-sm outline-none"
              style={selectStyle}
            >
              {TIME_WINDOW_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <p className="text-xs mt-1" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              All search queries will be constrained to this period — no results from other years
            </p>
          </div>
        </div>

        {/* Summary preview */}
        {formData.industry.trim() && (
          <div
            className="p-3 rounded-mars-md text-xs"
            style={{
              backgroundColor: 'var(--mars-color-primary-subtle, rgba(15,52,96,0.08))',
              border: '1px solid var(--mars-color-primary)',
              color: 'var(--mars-color-text-secondary)',
            }}
          >
            <strong style={{ color: 'var(--mars-color-text)' }}>Research scope:</strong>{' '}
            {formData.industry} in <strong>{formData.region}</strong> for{' '}
            <strong>{TIME_WINDOW_OPTIONS.find(o => o.value === formData.time_window)?.label || formData.time_window}</strong>
            {formData.companies && <> — focusing on {formData.companies}</>}
          </div>
        )}

        {/* Submit Button */}
        <div className="space-y-3">
          {/* News Discovery settings row */}
          <div className="flex items-center justify-between">
            <span
              className="text-xs font-medium"
              style={{ color: 'var(--mars-color-text-secondary)' }}
            >
              News Discovery settings
            </span>
            <button
              onClick={() => setShowSettings(s => !s)}
              title="Advanced model settings for News Discovery"
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
              <NpStageAdvancedSettings stageNum={2} cfg={taskConfig} updateCfg={updateCfg} />
            </div>
          )}

          <Button
            onClick={handleSubmit}
            disabled={isLoading || !formData.industry.trim()}
            className="w-full"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Creating Task...
              </>
            ) : (
              <>
                Continue to News Discovery
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
