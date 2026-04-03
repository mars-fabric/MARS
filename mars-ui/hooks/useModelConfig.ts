'use client'

/**
 * useModelConfig — fetches centralized model configuration from /api/models/config.
 *
 * Returns:
 *   availableModels  — list of {value, label} for all UI dropdowns
 *   globalDefaults   — global role → model name map
 *   workflowDefaults — per-workflow, per-stage model defaults
 *   isLoading        — true on first fetch
 *
 * Falls back to the static AVAILABLE_MODELS from types/deepresearch.ts
 * if the API is unavailable (e.g. during SSR or backend down).
 *
 * Module-level cache ensures a single fetch per browser session.
 */

import { useState, useEffect } from 'react'
import { AVAILABLE_MODELS as STATIC_FALLBACK } from '@/types/deepresearch'

export interface ModelOption {
  value: string
  label: string
}

export interface ModelConfigResponse {
  available_models: ModelOption[]
  global_defaults: Record<string, string>
  workflow_defaults: Record<string, Record<string, Record<string, string>>>
}

// Module-level cache so all component instances share one fetch
let _cache: ModelConfigResponse | null = null
let _fetchPromise: Promise<ModelConfigResponse | null> | null = null

function fetchConfig(): Promise<ModelConfigResponse | null> {
  if (_fetchPromise) return _fetchPromise
  _fetchPromise = fetch('/api/models/config')
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json() as Promise<ModelConfigResponse>
    })
    .then((data) => {
      _cache = data
      return data
    })
    .catch(() => null) // never throws — graceful degradation
  return _fetchPromise
}

export function useModelConfig() {
  const [config, setConfig] = useState<ModelConfigResponse | null>(_cache)
  const [isLoading, setIsLoading] = useState(_cache === null)

  useEffect(() => {
    if (_cache) {
      setConfig(_cache)
      setIsLoading(false)
      return
    }
    fetchConfig().then((data) => {
      setConfig(data)
      setIsLoading(false)
    })
  }, [])

  return {
    availableModels: config?.available_models ?? STATIC_FALLBACK,
    globalDefaults: config?.global_defaults ?? {},
    workflowDefaults: config?.workflow_defaults ?? {},
    isLoading,
  }
}

/**
 * Helper: resolve the display-default for a specific workflow + stage + model role.
 * Used so the "(default: xxx)" labels shown in the UI stay in sync with the backend YAML.
 */
export function resolveStageDefault(
  workflowDefaults: Record<string, Record<string, Record<string, string>>>,
  workflow: string,
  stage: number | 'default',
  role: string,
  hardcodedFallback: string,
): string {
  const wf = workflowDefaults[workflow]
  if (!wf) return hardcodedFallback
  const stageKey = String(stage)
  return wf[stageKey]?.[role] ?? wf['default']?.[role] ?? hardcodedFallback
}
