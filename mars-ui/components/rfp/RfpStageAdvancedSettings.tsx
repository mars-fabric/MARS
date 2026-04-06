'use client'

import React from 'react'
import type { RfpStageConfig } from '@/types/rfp'
import { useModelConfig, resolveStageDefault, type ModelOption } from '@/hooks/useModelConfig'

function ModelSelect({
     label,
     value,
     defaultValue,
     onChange,
     models,
}: {
     label: string
     value: string | undefined
     defaultValue: string
     onChange: (v: string) => void
     models: ModelOption[]
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
                    {models.map((m) => (
                         <option key={m.value} value={m.value}>
                              {m.label}
                         </option>
                    ))}
               </select>
          </div>
     )
}

interface RfpStageAdvancedSettingsProps {
     cfg: RfpStageConfig
     updateCfg: (patch: Partial<RfpStageConfig>) => void
}

/** Model settings for RFP stages. All 7 stages share the same model. */
export default function RfpStageAdvancedSettings({ cfg, updateCfg }: RfpStageAdvancedSettingsProps) {
     const { availableModels, workflowDefaults } = useModelConfig()

     const d = (role: string, fallback: string) =>
          resolveStageDefault(workflowDefaults, 'rfp', 'default', role, fallback)

     return (
          <div className="space-y-4">
               <ModelSelect
                    label="LLM Model"
                    value={cfg.model}
                    defaultValue={d('model', 'gpt-4o')}
                    onChange={(v) => updateCfg({ model: v || undefined })}
                    models={availableModels}
               />
          </div>
     )
}
