'use client'

import React from 'react'
import type { DeepresearchStageConfig } from '@/types/deepresearch'
import { AVAILABLE_MODELS } from '@/types/deepresearch'

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

interface StageAdvancedSettingsProps {
  stageNum: number
  cfg: DeepresearchStageConfig
  updateCfg: (patch: Partial<DeepresearchStageConfig>) => void
}

/** Pure settings form — no toggle button. Parent controls visibility. */
export default function StageAdvancedSettings({ stageNum, cfg, updateCfg }: StageAdvancedSettingsProps) {
  return (
    <div className="space-y-4">

      {stageNum === 1 && (
        <>
          <ModelSelect label="Idea Maker Model" value={cfg.idea_maker_model} defaultValue="gpt-4o" onChange={(v) => updateCfg({ idea_maker_model: v || undefined })} />
          <ModelSelect label="Idea Critic Model" value={cfg.idea_hater_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ idea_hater_model: v || undefined })} />
          <ModelSelect label="Planner Model" value={cfg.planner_model} defaultValue="gpt-4o" onChange={(v) => updateCfg({ planner_model: v || undefined })} />
          <ModelSelect label="Plan Reviewer Model" value={cfg.plan_reviewer_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ plan_reviewer_model: v || undefined })} />
          <ModelSelect label="Orchestration Model" value={cfg.orchestration_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ orchestration_model: v || undefined })} />
          <ModelSelect label="Formatter Model" value={cfg.formatter_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ formatter_model: v || undefined })} />
        </>
      )}

      {stageNum === 2 && (
        <>
          <ModelSelect label="Researcher Model" value={cfg.researcher_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ researcher_model: v || undefined })} />
          <ModelSelect label="Planner Model" value={cfg.planner_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ planner_model: v || undefined })} />
          <ModelSelect label="Plan Reviewer Model" value={cfg.plan_reviewer_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ plan_reviewer_model: v || undefined })} />
          <ModelSelect label="Orchestration Model" value={cfg.orchestration_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ orchestration_model: v || undefined })} />
          <ModelSelect label="Formatter Model" value={cfg.formatter_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ formatter_model: v || undefined })} />
        </>
      )}

      {stageNum === 3 && (
        <>
          <ModelSelect label="Engineer Model" value={cfg.engineer_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ engineer_model: v || undefined })} />
          <ModelSelect label="Researcher Model" value={cfg.researcher_model} defaultValue="o3-mini" onChange={(v) => updateCfg({ researcher_model: v || undefined })} />
          <ModelSelect label="Planner Model" value={cfg.planner_model} defaultValue="gpt-4o" onChange={(v) => updateCfg({ planner_model: v || undefined })} />
          <ModelSelect label="Orchestration Model" value={cfg.orchestration_model} defaultValue="gpt-4.1" onChange={(v) => updateCfg({ orchestration_model: v || undefined })} />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--mars-color-text-secondary)' }}>
                Max Attempts <span className="font-normal opacity-60">(default: 10)</span>
              </label>
              <input
                type="number" min={1} max={50}
                value={cfg.max_n_attempts ?? ''}
                onChange={(e) => updateCfg({ max_n_attempts: e.target.value ? parseInt(e.target.value) : undefined })}
                placeholder="10"
                className="w-full rounded border px-2 py-1.5 text-xs outline-none"
                style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--mars-color-text-secondary)' }}>
                Max Steps <span className="font-normal opacity-60">(default: 6)</span>
              </label>
              <input
                type="number" min={1} max={20}
                value={cfg.max_n_steps ?? ''}
                onChange={(e) => updateCfg({ max_n_steps: e.target.value ? parseInt(e.target.value) : undefined })}
                placeholder="6"
                className="w-full rounded border px-2 py-1.5 text-xs outline-none"
                style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
              />
            </div>
          </div>
        </>
      )}

      {stageNum === 4 && (
        <>
          <ModelSelect label="LLM Model" value={cfg.llm_model} defaultValue="gemini-2.5-flash" onChange={(v) => updateCfg({ llm_model: v || undefined })} />
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Writer Style <span className="font-normal opacity-60">(default: scientist)</span>
            </label>
            <select
              value={cfg.writer ?? ''}
              onChange={(e) => updateCfg({ writer: e.target.value || undefined })}
              className="w-full rounded border px-2 py-1.5 text-xs outline-none transition-colors"
              style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
            >
              <option value="">— use default (scientist) —</option>
              <option value="scientist">Scientist</option>
              <option value="PhD student">PhD Student</option>
              <option value="science journalist">Science Journalist</option>
              <option value="engineer">Engineer</option>
              <option value="professor">Professor</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Journal / Format <span className="font-normal opacity-60">(default: none)</span>
            </label>
            <select
              value={cfg.journal ?? ''}
              onChange={(e) => updateCfg({ journal: e.target.value || undefined })}
              className="w-full rounded border px-2 py-1.5 text-xs outline-none transition-colors"
              style={{ backgroundColor: 'var(--mars-color-surface)', borderColor: 'var(--mars-color-border)', color: 'var(--mars-color-text)' }}
            >
              <option value="">— generic LaTeX (no journal template) —</option>
              <option value="AAS">AAS — Astrophysical Journal (ApJ)</option>
              <option value="APS">APS — Physical Review Letters / PRA</option>
              <option value="JHEP">JHEP / JCAP</option>
              <option value="ICML">ICML</option>
              <option value="NeurIPS">NeurIPS</option>
              <option value="PASJ">PASJ — Publications of the Astronomical Society of Japan</option>
            </select>
          </div>
          <label className="flex items-center gap-2 cursor-pointer text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>
            <input
              type="checkbox"
              checked={cfg.add_citations !== false}
              onChange={(e) => updateCfg({ add_citations: e.target.checked })}
              className="rounded"
            />
            Add citations via Perplexity (requires PERPLEXITY_API_KEY)
          </label>
        </>
      )}

    </div>
  )
}
