'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { getApiUrl, getWsUrl } from '@/lib/config'
import type {
  NewsPulseTaskState,
  NewsPulseStageContent,
  NewsPulseCreateResponse,
  NewsPulseRefineResponse,
  NewsPulseRefinementMessage,
  NewsPulseWizardStep,
  NewsPulseStageConfig,
} from '@/types/newspulse'

interface UseNewsPulseTaskReturn {
  // State
  taskId: string | null
  taskState: NewsPulseTaskState | null
  currentStep: NewsPulseWizardStep
  isLoading: boolean
  error: string | null

  // Model config
  taskConfig: NewsPulseStageConfig
  setTaskConfig: (cfg: NewsPulseStageConfig) => void

  // Stage content
  editableContent: string
  refinementMessages: NewsPulseRefinementMessage[]
  consoleOutput: string[]
  isExecuting: boolean

  // Actions
  createTask: (params: {
    industry: string
    companies?: string
    region?: string
    time_window?: string
    config?: NewsPulseStageConfig
  }) => Promise<string | null>
  executeStage: (stageNum: number, overrideId?: string) => Promise<void>
  fetchStageContent: (stageNum: number) => Promise<NewsPulseStageContent | null>
  saveStageContent: (stageNum: number, content: string, field: string) => Promise<void>
  refineContent: (stageNum: number, message: string, content: string) => Promise<string | null>
  setCurrentStep: (step: NewsPulseWizardStep) => void
  setEditableContent: (content: string) => void
  resumeTask: (taskId: string) => Promise<void>
  stopTask: () => Promise<void>
  deleteTask: () => Promise<void>
  clearError: () => void
}

export function useNewsPulseTask(): UseNewsPulseTaskReturn {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskState, setTaskState] = useState<NewsPulseTaskState | null>(null)
  const [currentStep, setCurrentStep] = useState<NewsPulseWizardStep>(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [taskConfig, setTaskConfig] = useState<NewsPulseStageConfig>({})
  const [editableContent, setEditableContent] = useState('')
  const [refinementMessages, setRefinementMessages] = useState<NewsPulseRefinementMessage[]>([])
  const [consoleOutput, setConsoleOutput] = useState<string[]>([])
  const [isExecuting, setIsExecuting] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consolePollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consoleIndexRef = useRef(0)
  const taskIdRef = useRef<string | null>(null)

  useEffect(() => { taskIdRef.current = taskId }, [taskId])

  useEffect(() => {
    return () => {
      wsRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
      if (consolePollRef.current) clearInterval(consolePollRef.current)
    }
  }, [])

  const clearError = useCallback(() => setError(null), [])

  const apiFetch = useCallback(async (path: string, options?: RequestInit) => {
    const resp = await fetch(getApiUrl(path), {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ detail: resp.statusText }))
      throw new Error(body.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
  }, [])

  const loadTaskState = useCallback(async (id: string) => {
    const state: NewsPulseTaskState = await apiFetch(`/api/newspulse/${id}`)
    setTaskState(state)
    return state
  }, [apiFetch])

  // ---- Task lifecycle ----

  const createTask = useCallback(async (params: {
    industry: string
    companies?: string
    region?: string
    time_window?: string
    config?: NewsPulseStageConfig
  }) => {
    setIsLoading(true)
    setError(null)
    try {
      const resp: NewsPulseCreateResponse = await apiFetch('/api/newspulse/create', {
        method: 'POST',
        body: JSON.stringify({
          industry: params.industry,
          companies: params.companies,
          region: params.region,
          time_window: params.time_window,
          config: params.config,
        }),
      })
      setTaskId(resp.task_id)
      taskIdRef.current = resp.task_id
      await loadTaskState(resp.task_id)
      return resp.task_id
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create task')
      return null
    } finally {
      setIsLoading(false)
    }
  }, [apiFetch, loadTaskState])

  // ---- Execution ----

  const startPolling = useCallback((id: string, stageNum: number) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const state = await loadTaskState(id)
        const stage = state.stages.find(s => s.stage_number === stageNum)
        if (stage && (stage.status === 'completed' || stage.status === 'failed')) {
          setIsExecuting(false)
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
          if (consolePollRef.current) clearInterval(consolePollRef.current)
          consolePollRef.current = null
          wsRef.current?.close()
        }
      } catch { /* ignore */ }
    }, 5000)
  }, [loadTaskState])

  const startConsolePoll = useCallback((id: string, stageNum: number) => {
    if (consolePollRef.current) clearInterval(consolePollRef.current)
    consoleIndexRef.current = 0
    consolePollRef.current = setInterval(async () => {
      try {
        const resp = await fetch(
          getApiUrl(`/api/newspulse/${id}/stages/${stageNum}/console?since=${consoleIndexRef.current}`)
        )
        if (!resp.ok) return
        const data = await resp.json()
        if (data.lines && data.lines.length > 0) {
          setConsoleOutput(prev => [...prev, ...data.lines])
          consoleIndexRef.current = data.next_index
        }
      } catch { /* ignore */ }
    }, 2000)
  }, [])

  const connectWs = useCallback((id: string, stageNum: number) => {
    wsRef.current?.close()
    const url = getWsUrl(`/ws/newspulse/${id}/${stageNum}`)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.event_type === 'stage_completed') {
          setIsExecuting(false)
          if (consolePollRef.current) clearInterval(consolePollRef.current)
          consolePollRef.current = null
          loadTaskState(id)
          ws.close()
        } else if (msg.event_type === 'stage_failed') {
          setIsExecuting(false)
          setError(msg.data?.error || 'Stage failed')
          if (consolePollRef.current) clearInterval(consolePollRef.current)
          consolePollRef.current = null
          loadTaskState(id)
          ws.close()
        }
      } catch { /* ignore */ }
    }

    ws.onerror = () => {}
    ws.onclose = () => {}
  }, [loadTaskState])

  const executeStage = useCallback(async (stageNum: number, overrideId?: string) => {
    const id = overrideId ?? taskId
    if (!id) return
    setIsExecuting(true)
    setError(null)
    setConsoleOutput([])

    // Build config_overrides from stored taskConfig, filtered to relevant keys
    const cfg = taskConfig
    const config_overrides: Record<string, unknown> = Object.fromEntries(
      Object.entries(cfg).filter(([, v]) => v !== undefined && v !== '')
    )

    try {
      const resp = await apiFetch(`/api/newspulse/${id}/stages/${stageNum}/execute`, {
        method: 'POST',
        body: JSON.stringify({ config_overrides }),
      })

      // Stage 1 and 3 complete immediately
      if (resp.status === 'completed') {
        setIsExecuting(false)
        await loadTaskState(id)
        return
      }

      // Stages 2 and 4 run in background
      connectWs(id, stageNum)
      startPolling(id, stageNum)
      startConsolePoll(id, stageNum)
      setConsoleOutput([`Stage ${stageNum} execution started...`])
    } catch (e: unknown) {
      setIsExecuting(false)
      setError(e instanceof Error ? e.message : 'Failed to execute stage')
    }
  }, [taskId, apiFetch, connectWs, startPolling, startConsolePoll, loadTaskState])

  // ---- Content ----

  const fetchStageContent = useCallback(async (stageNum: number): Promise<NewsPulseStageContent | null> => {
    if (!taskId) return null
    try {
      const content: NewsPulseStageContent = await apiFetch(`/api/newspulse/${taskId}/stages/${stageNum}/content`)
      setEditableContent(content.content ?? '')
      return content
    } catch {
      return null
    }
  }, [taskId, apiFetch])

  const saveStageContent = useCallback(async (stageNum: number, content: string, field: string) => {
    if (!taskId) return
    try {
      await apiFetch(`/api/newspulse/${taskId}/stages/${stageNum}/content`, {
        method: 'PUT',
        body: JSON.stringify({ content, field }),
      })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    }
  }, [taskId, apiFetch])

  const refineContent = useCallback(async (
    stageNum: number,
    message: string,
    content: string,
  ): Promise<string | null> => {
    if (!taskId) return null

    const userMsg: NewsPulseRefinementMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }
    setRefinementMessages(prev => [...prev, userMsg])

    try {
      const resp: NewsPulseRefineResponse = await apiFetch(`/api/newspulse/${taskId}/stages/${stageNum}/refine`, {
        method: 'POST',
        body: JSON.stringify({ message, content }),
      })

      const assistantMsg: NewsPulseRefinementMessage = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: resp.refined_content,
        timestamp: Date.now(),
      }
      setRefinementMessages(prev => [...prev, assistantMsg])
      return resp.refined_content
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Refinement failed')
      return null
    }
  }, [taskId, apiFetch])

  // ---- Resume ----

  const resumeTask = useCallback(async (id: string) => {
    setIsLoading(true)
    setError(null)
    taskIdRef.current = id
    try {
      setTaskId(id)
      const state = await loadTaskState(id)

      let resumeStep: NewsPulseWizardStep = 0
      for (const stage of state.stages) {
        if (stage.status === 'running') {
          resumeStep = (stage.stage_number - 1) as NewsPulseWizardStep
          setIsExecuting(true)
          connectWs(id, stage.stage_number)
          startPolling(id, stage.stage_number)
          startConsolePoll(id, stage.stage_number)
          break
        }
        if (stage.status === 'completed') {
          resumeStep = Math.min(stage.stage_number, 3) as NewsPulseWizardStep
        } else {
          resumeStep = Math.max(0, stage.stage_number - 1) as NewsPulseWizardStep
          break
        }
      }

      setCurrentStep(resumeStep)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to resume task')
    } finally {
      setIsLoading(false)
    }
  }, [loadTaskState, connectWs, startPolling, startConsolePoll])

  // ---- Stop / Delete ----

  const stopTask = useCallback(async () => {
    if (!taskId) return
    try {
      await apiFetch(`/api/newspulse/${taskId}/stop`, { method: 'POST' })
      setIsExecuting(false)
      wsRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = null
      if (consolePollRef.current) clearInterval(consolePollRef.current)
      consolePollRef.current = null
      await loadTaskState(taskId)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to stop task')
    }
  }, [taskId, apiFetch, loadTaskState])

  const deleteTask = useCallback(async () => {
    if (!taskId) return
    try {
      await apiFetch(`/api/newspulse/${taskId}`, { method: 'DELETE' })
      setTaskId(null)
      setTaskState(null)
      setCurrentStep(0)
      setEditableContent('')
      setRefinementMessages([])
      setConsoleOutput([])
      setIsExecuting(false)
      setError(null)
      wsRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = null
      if (consolePollRef.current) clearInterval(consolePollRef.current)
      consolePollRef.current = null
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to delete task')
    }
  }, [taskId, apiFetch])

  return {
    taskId,
    taskState,
    currentStep,
    isLoading,
    error,
    taskConfig,
    setTaskConfig,
    editableContent,
    refinementMessages,
    consoleOutput,
    isExecuting,
    createTask,
    executeStage,
    fetchStageContent,
    saveStageContent,
    refineContent,
    setCurrentStep: setCurrentStep as (step: NewsPulseWizardStep) => void,
    setEditableContent,
    resumeTask,
    stopTask,
    deleteTask,
    clearError,
  }
}
