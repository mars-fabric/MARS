'use client'

/**
 * usePdaTask — React hook for the staged PDA wizard.
 *
 * Mirrors useNewsPulseTask / useDeepresearchTask:
 *   • Session + DB stage records via /api/pda
 *   • Background stage execution with WebSocket streaming
 *   • HITL content save/refine between stages
 *   • HTTP polling fallback every 5 s
 *   • Console output poll every 2 s
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { getApiUrl, getWsUrl, config } from '@/lib/config'
import { apiFetchWithRetry } from '@/lib/fetchWithRetry'
import type {
  PdaTaskState,
  PdaStageContent,
  PdaCreateResponse,
  PdaRefineResponse,
  PdaRefinementMessage,
  PdaWizardStep,
  IntakeFormData,
  OpportunityArea,
  SolutionArchetype,
  Feature,
} from '@/types/pda'

interface UsePdaTaskReturn {
  // State
  taskId: string | null
  taskState: PdaTaskState | null
  currentStep: PdaWizardStep
  isLoading: boolean
  error: string | null

  // Stage execution
  editableContent: string
  /** Map of stageNum → markdown content for all completed stages (populated on load/resume) */
  stageContents: Record<number, string>
  refinementMessages: PdaRefinementMessage[]
  consoleOutput: string[]
  isExecuting: boolean

  // Actions — task lifecycle
  createTask: (intakeData: IntakeFormData) => Promise<string | null>
  executeStage: (
    stageNum: number,
    inputData?: Record<string, unknown>,
    overrideId?: string,
  ) => Promise<void>
  fetchStageContent: (stageNum: number) => Promise<PdaStageContent | null>
  saveStageContent: (stageNum: number, content: string, field: string) => Promise<void>
  refineContent: (stageNum: number, message: string, content: string) => Promise<string | null>
  resumeTask: (taskId: string) => Promise<void>
  stopTask: () => Promise<void>
  deleteTask: () => Promise<void>

  // UI helpers
  setCurrentStep: (step: PdaWizardStep) => void
  setEditableContent: (content: string) => void
  setStageContent: (stageNum: number, content: string) => void
  clearError: () => void
}

export function usePdaTask(): UsePdaTaskReturn {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskState, setTaskState] = useState<PdaTaskState | null>(null)
  const [currentStep, setCurrentStep] = useState<PdaWizardStep>(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [editableContent, setEditableContent] = useState('')
  const [stageContents, setStageContents] = useState<Record<number, string>>({})
  const [refinementMessages, setRefinementMessages] = useState<PdaRefinementMessage[]>([])
  const [consoleOutput, setConsoleOutput] = useState<string[]>([])
  const [isExecuting, setIsExecuting] = useState(false)

  const setStageContent = useCallback((stageNum: number, content: string) => {
    setStageContents(prev => ({ ...prev, [stageNum]: content }))
  }, [])

  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consolePollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consoleIndexRef = useRef(0)
  const taskIdRef = useRef<string | null>(null)

  // Keep ref in sync
  useEffect(() => { taskIdRef.current = taskId }, [taskId])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
      if (consolePollRef.current) clearInterval(consolePollRef.current)
    }
  }, [])

  const clearError = useCallback(() => setError(null), [])

  // ---------------------------------------------------------------------------
  // API helper
  // ---------------------------------------------------------------------------

  const apiFetch = useCallback(async (path: string, options?: RequestInit) => {
    const resp = await apiFetchWithRetry(path, options)
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ detail: resp.statusText }))
      throw new Error(body.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
  }, [])

  // ---------------------------------------------------------------------------
  // Task state loader
  // ---------------------------------------------------------------------------

  const loadTaskState = useCallback(async (id: string) => {
    const state: PdaTaskState = await apiFetch(`/api/pda/${id}`)
    setTaskState(state)
    return state
  }, [apiFetch])

  // ---------------------------------------------------------------------------
  // Create task
  // ---------------------------------------------------------------------------

  const createTask = useCallback(async (intakeData: IntakeFormData): Promise<string | null> => {
    setIsLoading(true)
    setError(null)
    try {
      const resp: PdaCreateResponse = await apiFetch('/api/pda/create', {
        method: 'POST',
        body: JSON.stringify({
          client_name: intakeData.clientName,
          industry: intakeData.industry,
          sub_industry: intakeData.subIndustry,
          client_context: intakeData.clientContext,
          business_function: intakeData.businessFunction,
          discovery_type: intakeData.discoveryType,
          process_type: intakeData.processType,
          existing_functionality: intakeData.existingFunctionality || '',
          problem_keywords: intakeData.problemKeywords,
          expected_output: intakeData.expectedOutput,
          research_mode: intakeData.researchMode || 'one_shot',
          work_dir: config.workDir,
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

  // ---------------------------------------------------------------------------
  // Polling helpers
  // ---------------------------------------------------------------------------

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
          getApiUrl(`/api/pda/${id}/stages/${stageNum}/console?since=${consoleIndexRef.current}`)
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
    const url = getWsUrl(`/ws/pda/${id}/${stageNum}`)
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

  // ---------------------------------------------------------------------------
  // Execute stage
  // ---------------------------------------------------------------------------

  const executeStage = useCallback(async (
    stageNum: number,
    inputData?: Record<string, unknown>,
    overrideId?: string,
  ) => {
    const id = overrideId ?? taskId
    if (!id) return
    setIsExecuting(true)
    setError(null)
    setConsoleOutput([])

    try {
      await apiFetch(`/api/pda/${id}/stages/${stageNum}/execute`, {
        method: 'POST',
        body: JSON.stringify({ input_data: inputData || {} }),
      })
      connectWs(id, stageNum)
      startPolling(id, stageNum)
      startConsolePoll(id, stageNum)
      setConsoleOutput([`[PDA] Stage ${stageNum} execution started...`])
    } catch (e: unknown) {
      setIsExecuting(false)
      setError(e instanceof Error ? e.message : 'Failed to execute stage')
    }
  }, [taskId, apiFetch, connectWs, startPolling, startConsolePoll])

  // ---------------------------------------------------------------------------
  // Stage content
  // ---------------------------------------------------------------------------

  const fetchStageContent = useCallback(async (stageNum: number): Promise<PdaStageContent | null> => {
    if (!taskId) return null
    try {
      const content: PdaStageContent = await apiFetch(
        `/api/pda/${taskId}/stages/${stageNum}/content`
      )
      const md = content.content ?? ''
      setEditableContent(md)
      setStageContents(prev => ({ ...prev, [stageNum]: md }))
      return content
    } catch {
      return null
    }
  }, [taskId, apiFetch])

  const saveStageContent = useCallback(async (
    stageNum: number, content: string, field: string
  ) => {
    if (!taskId) return
    try {
      await apiFetch(`/api/pda/${taskId}/stages/${stageNum}/content`, {
        method: 'PUT',
        body: JSON.stringify({ content, field }),
      })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    }
  }, [taskId, apiFetch])

  const refineContent = useCallback(async (
    stageNum: number, message: string, content: string
  ): Promise<string | null> => {
    if (!taskId) return null

    const userMsg: PdaRefinementMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }
    setRefinementMessages(prev => [...prev, userMsg])

    try {
      const resp: PdaRefineResponse = await apiFetch(
        `/api/pda/${taskId}/stages/${stageNum}/refine`,
        { method: 'POST', body: JSON.stringify({ message, content }) }
      )
      const assistantMsg: PdaRefinementMessage = {
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

  // ---------------------------------------------------------------------------
  // Resume
  // ---------------------------------------------------------------------------

  const resumeTask = useCallback(async (id: string) => {
    setIsLoading(true)
    setError(null)
    taskIdRef.current = id
    try {
      setTaskId(id)
      taskIdRef.current = id
      const state = await loadTaskState(id)

      // ── Step 1: determine which wizard step to resume at ──────────────────
      let resumeStep: PdaWizardStep = 0
      let runningStage: number | null = null

      for (const stage of state.stages) {
        if (stage.status === 'running') {
          resumeStep = stage.stage_number as PdaWizardStep
          runningStage = stage.stage_number
          break
        }
        if (stage.status === 'completed') {
          resumeStep = Math.min(stage.stage_number + 1, 7) as PdaWizardStep
        } else if (stage.status === 'failed') {
          // Resume at the failed stage so the user can retry
          resumeStep = stage.stage_number as PdaWizardStep
          break
        } else {
          // pending — resume at this stage
          resumeStep = stage.stage_number as PdaWizardStep
          break
        }
      }

      // ── Step 2: pre-load content for every completed stage in parallel ────
      const completedStages = state.stages.filter(s => s.status === 'completed')
      const contentResults = await Promise.allSettled(
        completedStages.map(s =>
          fetch(
            `${getApiUrl(`/api/pda/${id}/stages/${s.stage_number}/content`)}`
          ).then(r => r.ok ? r.json() : null).catch(() => null)
        )
      )
      const newContents: Record<number, string> = {}
      completedStages.forEach((s, idx) => {
        const result = contentResults[idx]
        if (result.status === 'fulfilled' && result.value) {
          const md: string = result.value.content ?? ''
          if (md) newContents[s.stage_number] = md
        }
      })
      setStageContents(newContents)

      // ── Step 3: if a stage is currently running, attach to it ────────────
      if (runningStage !== null) {
        setIsExecuting(true)
        connectWs(id, runningStage)
        startPolling(id, runningStage)
        startConsolePoll(id, runningStage)
      }

      setCurrentStep(resumeStep)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to resume task')
    } finally {
      setIsLoading(false)
    }
  }, [loadTaskState, connectWs, startPolling, startConsolePoll])

  // ---------------------------------------------------------------------------
  // Stop / Delete
  // ---------------------------------------------------------------------------

  const stopTask = useCallback(async () => {
    if (!taskId) return
    try {
      await apiFetch(`/api/pda/${taskId}/stop`, { method: 'POST' })
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
      await apiFetch(`/api/pda/${taskId}`, { method: 'DELETE' })
      setTaskId(null)
      setTaskState(null)
      setCurrentStep(0)
      setEditableContent('')
      setStageContents({})
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
    editableContent,
    stageContents,
    refinementMessages,
    consoleOutput,
    isExecuting,
    createTask,
    executeStage,
    fetchStageContent,
    saveStageContent,
    refineContent,
    resumeTask,
    stopTask,
    deleteTask,
    setCurrentStep: setCurrentStep as (step: PdaWizardStep) => void,
    setEditableContent,
    setStageContent,
    clearError,
  }
}
