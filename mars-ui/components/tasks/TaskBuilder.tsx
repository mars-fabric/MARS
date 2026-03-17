'use client'

import React, { useState } from 'react'
import { ArrowLeft, Save } from 'lucide-react'
import { Button, Badge } from '@/components/core'
import { MARS_MODES, getModeConfig } from '@/lib/modes'

export interface TaskBuilderProps {
  taskId?: string
  onBack: () => void
  onSave?: (config: TaskBuilderConfig) => void
}

export interface TaskBuilderConfig {
  name: string
  mode: string
  model: string
  maxRounds: number
  approvalMode: 'none' | 'always' | 'on-failure'
}

const DEFAULT_CONFIG: TaskBuilderConfig = {
  name: '',
  mode: 'one-shot',
  model: 'gpt-4o',
  maxRounds: 10,
  approvalMode: 'none',
}

const MODELS = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo']

export default function TaskBuilder({ taskId, onBack, onSave }: TaskBuilderProps) {
  const [config, setConfig] = useState<TaskBuilderConfig>(DEFAULT_CONFIG)
  const [errors, setErrors] = useState<Partial<Record<keyof TaskBuilderConfig, string>>>({})

  const isEditMode = !!taskId

  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof TaskBuilderConfig, string>> = {}
    if (!config.name.trim()) {
      newErrors.name = 'Task name is required'
    }
    if (config.maxRounds < 1 || config.maxRounds > 100) {
      newErrors.maxRounds = 'Max rounds must be between 1 and 100'
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSave = () => {
    if (validate()) {
      onSave?.(config)
    }
  }

  const selectedMode = getModeConfig(config.mode)

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header
        className="border-b px-6 py-4 flex items-center gap-4"
        style={{
          borderColor: 'var(--mars-color-border)',
          backgroundColor: 'var(--mars-color-surface-raised)',
        }}
      >
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm transition-colors duration-mars-fast"
          style={{ color: 'var(--mars-color-text-secondary)' }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--mars-color-text)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--mars-color-text-secondary)'
          }}
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Tasks
        </button>
        <div className="flex-1" />
        <h1
          className="text-lg font-semibold"
          style={{ color: 'var(--mars-color-text)' }}
        >
          {isEditMode ? 'Edit Task' : 'New Task'}
        </h1>
      </header>

      {/* Form */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Task Name */}
          <div>
            <label
              className="block text-sm font-medium mb-1.5"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Task Name
            </label>
            <input
              type="text"
              placeholder="e.g. Weekly Research Summary"
              value={config.name}
              onChange={(e) => {
                setConfig({ ...config, name: e.target.value })
                if (errors.name) setErrors({ ...errors, name: undefined })
              }}
              className="w-full h-10 px-3 rounded-mars-md border text-sm outline-none transition-colors duration-mars-fast"
              style={{
                backgroundColor: 'var(--mars-color-surface)',
                borderColor: errors.name
                  ? 'var(--mars-color-danger)'
                  : 'var(--mars-color-border)',
                color: 'var(--mars-color-text)',
              }}
              onFocus={(e) => {
                if (!errors.name) {
                  e.currentTarget.style.borderColor = 'var(--mars-color-primary)'
                }
              }}
              onBlur={(e) => {
                if (!errors.name) {
                  e.currentTarget.style.borderColor = 'var(--mars-color-border)'
                }
              }}
            />
            {errors.name && (
              <p className="text-xs mt-1" style={{ color: 'var(--mars-color-danger)' }}>
                {errors.name}
              </p>
            )}
          </div>

          {/* Mode Selection */}
          <div>
            <label
              className="block text-sm font-medium mb-1.5"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Execution Mode
            </label>
            <div className="grid grid-cols-2 gap-2">
              {MARS_MODES.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setConfig({ ...config, mode: mode.id })}
                  className="flex items-start gap-3 p-3 rounded-mars-md border text-left transition-all duration-mars-fast"
                  style={{
                    backgroundColor:
                      config.mode === mode.id
                        ? 'var(--mars-color-primary-subtle)'
                        : 'var(--mars-color-surface)',
                    borderColor:
                      config.mode === mode.id
                        ? 'var(--mars-color-primary)'
                        : 'var(--mars-color-border)',
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className="text-sm font-medium truncate"
                        style={{
                          color:
                            config.mode === mode.id
                              ? 'var(--mars-color-primary-text)'
                              : 'var(--mars-color-text)',
                        }}
                      >
                        {mode.displayName}
                      </span>
                    </div>
                    <p
                      className="text-xs mt-0.5 line-clamp-2"
                      style={{ color: 'var(--mars-color-text-secondary)' }}
                    >
                      {mode.description}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Model */}
          <div>
            <label
              className="block text-sm font-medium mb-1.5"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Model
            </label>
            <select
              value={config.model}
              onChange={(e) => setConfig({ ...config, model: e.target.value })}
              className="w-full h-10 px-3 rounded-mars-md border text-sm bg-transparent cursor-pointer"
              style={{
                borderColor: 'var(--mars-color-border)',
                color: 'var(--mars-color-text)',
              }}
            >
              {MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          {/* Max Rounds */}
          <div>
            <label
              className="block text-sm font-medium mb-1.5"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Max Rounds
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={config.maxRounds}
              onChange={(e) => {
                setConfig({ ...config, maxRounds: parseInt(e.target.value) || 1 })
                if (errors.maxRounds) setErrors({ ...errors, maxRounds: undefined })
              }}
              className="w-full h-10 px-3 rounded-mars-md border text-sm outline-none"
              style={{
                backgroundColor: 'var(--mars-color-surface)',
                borderColor: errors.maxRounds
                  ? 'var(--mars-color-danger)'
                  : 'var(--mars-color-border)',
                color: 'var(--mars-color-text)',
              }}
            />
            {errors.maxRounds && (
              <p className="text-xs mt-1" style={{ color: 'var(--mars-color-danger)' }}>
                {errors.maxRounds}
              </p>
            )}
          </div>

          {/* Approval Mode */}
          <div>
            <label
              className="block text-sm font-medium mb-1.5"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Approval Mode
            </label>
            <div className="flex gap-2">
              {(
                [
                  { value: 'none', label: 'None', desc: 'No approval needed' },
                  { value: 'always', label: 'Always', desc: 'Approve every step' },
                  { value: 'on-failure', label: 'On Failure', desc: 'Only on errors' },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() =>
                    setConfig({ ...config, approvalMode: opt.value })
                  }
                  className="flex-1 p-3 rounded-mars-md border text-center transition-all duration-mars-fast"
                  style={{
                    backgroundColor:
                      config.approvalMode === opt.value
                        ? 'var(--mars-color-primary-subtle)'
                        : 'var(--mars-color-surface)',
                    borderColor:
                      config.approvalMode === opt.value
                        ? 'var(--mars-color-primary)'
                        : 'var(--mars-color-border)',
                  }}
                >
                  <div
                    className="text-sm font-medium"
                    style={{
                      color:
                        config.approvalMode === opt.value
                          ? 'var(--mars-color-primary-text)'
                          : 'var(--mars-color-text)',
                    }}
                  >
                    {opt.label}
                  </div>
                  <div
                    className="text-xs mt-0.5"
                    style={{ color: 'var(--mars-color-text-secondary)' }}
                  >
                    {opt.desc}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div
            className="flex items-center gap-3 pt-4 border-t"
            style={{ borderColor: 'var(--mars-color-border)' }}
          >
            <Button variant="primary" icon={<Save className="w-4 h-4" />} onClick={handleSave}>
              {isEditMode ? 'Save Changes' : 'Create Task'}
            </Button>
            <Button variant="secondary" onClick={onBack}>
              Cancel
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
