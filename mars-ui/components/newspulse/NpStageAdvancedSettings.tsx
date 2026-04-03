'use client'

import React from 'react'
import type { NewsPulseStageConfig } from '@/types/newspulse'
import { AVAILABLE_MODELS } from '@/types/newspulse'

function ModelSelect({
  label,
  value,
  defaultValue,
  onChange,
}: {
  label: string
  value: string | undefined
  defaultValue: string
  onChange: (v: string) => void
}) {
  return (
    <div>
      <label
        className="block text-xs font-medium mb-1"
        style={{ color: 'var(--mars-color-text-secondary)' }}
      >
        {label}
        <span className="ml-1 font-normal opacity-60">(default: {defaultValue})</span>
      </label>
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border px-2 py-1.5 text-xs outline-none transition-colors"
        style={{
          backgroundColor: 'var(--mars-color-surface)',
          borderColor: 'var(--mars-color-border)',
          color: 'var(--mars-color-text)',
        }}
      >
        <option value="">— use default ({defaultValue}) —</option>
        {AVAILABLE_MODELS.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </select>
    </div>
  )
}

interface NpStageAdvancedSettingsProps {
  stageNum: number
  cfg: NewsPulseStageConfig
  updateCfg: (patch: Partial<NewsPulseStageConfig>) => void
}

/** Pure settings form — no toggle button. Parent controls visibility. */
export default function NpStageAdvancedSettings({ stageNum, cfg, updateCfg }: NpStageAdvancedSettingsProps) {
  return (
    <div className="space-y-4">

      {/* Stage 2 — News Discovery */}
      {stageNum === 2 && (
        <>
          <ModelSelect label="Researcher Model" value={cfg.researcher_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ researcher_model: v || undefined })} />
          <ModelSelect label="Planner Model" value={cfg.planner_model} defaultValue="gpt-4o" onChange={(v) => updateCfg({ planner_model: v || undefined })} />
          <ModelSelect label="Plan Reviewer Model" value={cfg.plan_reviewer_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ plan_reviewer_model: v || undefined })} />
          <ModelSelect label="Orchestration Model" value={cfg.orchestration_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ orchestration_model: v || undefined })} />
          <ModelSelect label="Formatter Model" value={cfg.formatter_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ formatter_model: v || undefined })} />
        </>
      )}

      {/* Stage 3 — Deep Analysis */}
      {stageNum === 3 && (
        <>
          <ModelSelect label="Researcher Model" value={cfg.researcher_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ researcher_model: v || undefined })} />
          <ModelSelect label="Planner Model" value={cfg.planner_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ planner_model: v || undefined })} />
          <ModelSelect label="Plan Reviewer Model" value={cfg.plan_reviewer_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ plan_reviewer_model: v || undefined })} />
          <ModelSelect label="Orchestration Model" value={cfg.orchestration_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ orchestration_model: v || undefined })} />
          <ModelSelect label="Formatter Model" value={cfg.formatter_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ formatter_model: v || undefined })} />
        </>
      )}

      {/* Stage 4 — Final Report + PDF */}
      {stageNum === 4 && (
        <>
          <ModelSelect label="Report LLM Model" value={cfg.researcher_model} defaultValue="gpt-4o" onChange={(v) => updateCfg({ researcher_model: v || undefined })} />
        </>
      )}

    </div>
  )
}
