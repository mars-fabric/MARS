'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { getApiUrl, config } from '@/lib/config'
import { apiFetchWithRetry } from '@/lib/fetchWithRetry'
import type {
  ReleaseNotesTaskState,
  ReleaseNotesStageContent,
  ReleaseNotesCreateResponse,
  ReleaseNotesRefineResponse,
  RefinementMessage,
  ReleaseNotesWizardStep,
} from '@/types/releasenotes'

interface UseReleaseNotesTaskReturn {
  // State
  taskId: string | null
  taskState: ReleaseNotesTaskState | null
  currentStep: ReleaseNotesWizardStep
  isLoading: boolean
  error: string | null

  // Stage content
  editableContent: string
  refinementMessages: RefinementMessage[]
  consoleOutput: string[]
  isExecuting: boolean
  stageDocuments: Record<string, string> | null

  // Actions
  createTask: (
    repoUrl: string,
    baseBranch: string,
    headBranch: string,
    authToken?: string,
    extraInstructions?: string,
  ) => Promise<string | null>
  executeStage: (stageNum: number, configOverrides?: Record<string, unknown>) => Promise<void>
  fetchStageContent: (stageNum: number) => Promise<ReleaseNotesStageContent | null>
  saveStageContent: (stageNum: number, content: string, field: string) => Promise<void>
  refineContent: (stageNum: number, message: string, content: string) => Promise<string | null>
  setCurrentStep: (step: ReleaseNotesWizardStep) => void
  setEditableContent: (content: string) => void
  setStageDocuments: (docs: Record<string, string> | null) => void
  resumeTask: (taskId: string) => Promise<void>
  clearError: () => void
}

export function useReleaseNotesTask(): UseReleaseNotesTaskReturn {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskState, setTaskState] = useState<ReleaseNotesTaskState | null>(null)
  const [currentStep, setCurrentStep] = useState<ReleaseNotesWizardStep>(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [editableContent, setEditableContent] = useState('')
  const [refinementMessages, setRefinementMessages] = useState<RefinementMessage[]>([])
  const [consoleOutput, setConsoleOutput] = useState<string[]>([])
  const [isExecuting, setIsExecuting] = useState(false)
  const [stageDocuments, setStageDocuments] = useState<Record<string, string> | null>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consolePollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consoleIndexRef = useRef(0)
  const taskIdRef = useRef<string | null>(null)

  useEffect(() => { taskIdRef.current = taskId }, [taskId])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      if (consolePollRef.current) clearInterval(consolePollRef.current)
    }
  }, [])

  const clearError = useCallback(() => setError(null), [])

  // ---- API helpers ----

  const apiFetch = useCallback(async (path: string, options?: RequestInit) => {
    const resp = await apiFetchWithRetry(path, options)
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ detail: resp.statusText }))
      throw new Error(body.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
  }, [])

  // ---- Task lifecycle ----

  const loadTaskState = useCallback(async (id: string) => {
    const state: ReleaseNotesTaskState = await apiFetch(`/api/release-notes/${id}`)
    setTaskState(state)
    return state
  }, [apiFetch])

  const createTask = useCallback(async (
    repoUrl: string,
    baseBranch: string,
    headBranch: string,
    authToken?: string,
    extraInstructions?: string,
  ) => {
    setIsLoading(true)
    setError(null)
    try {
      const resp: ReleaseNotesCreateResponse = await apiFetch('/api/release-notes/create', {
        method: 'POST',
        body: JSON.stringify({
          repo_url: repoUrl,
          base_branch: baseBranch,
          head_branch: headBranch,
          auth_token: authToken || null,
          extra_instructions: extraInstructions || null,
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

  // ---- Stage execution ----

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
        }
      } catch {
        // ignore polling errors
      }
    }, 5000)
  }, [loadTaskState])

  const startConsolePoll = useCallback((id: string, stageNum: number) => {
    if (consolePollRef.current) clearInterval(consolePollRef.current)
    consoleIndexRef.current = 0
    consolePollRef.current = setInterval(async () => {
      try {
        const resp = await fetch(
          getApiUrl(`/api/release-notes/${id}/stages/${stageNum}/console?since=${consoleIndexRef.current}`)
        )
        if (!resp.ok) return
        const data = await resp.json()
        if (data.lines && data.lines.length > 0) {
          setConsoleOutput(prev => [...prev, ...data.lines])
          consoleIndexRef.current = data.next_index
        }
      } catch {
        // ignore console poll errors
      }
    }, 2000)
  }, [])

  const executeStage = useCallback(async (stageNum: number, configOverrides?: Record<string, unknown>) => {
    const id = taskIdRef.current
    if (!id) return
    setIsExecuting(true)
    setError(null)
    setConsoleOutput([])

    try {
      await apiFetch(`/api/release-notes/${id}/stages/${stageNum}/execute`, {
        method: 'POST',
        body: JSON.stringify({ config_overrides: configOverrides || {} }),
      })
      startPolling(id, stageNum)
      startConsolePoll(id, stageNum)
      setConsoleOutput([`Stage ${stageNum} execution started...`])
    } catch (e: unknown) {
      setIsExecuting(false)
      setError(e instanceof Error ? e.message : 'Failed to execute stage')
    }
  }, [apiFetch, startPolling, startConsolePoll])

  // ---- Content ----

  const fetchStageContent = useCallback(async (stageNum: number): Promise<ReleaseNotesStageContent | null> => {
    const id = taskIdRef.current
    if (!id) return null
    try {
      const content: ReleaseNotesStageContent = await apiFetch(`/api/release-notes/${id}/stages/${stageNum}/content`)
      setEditableContent(content.content ?? '')
      setStageDocuments(content.documents ?? null)
      return content
    } catch {
      return null
    }
  }, [apiFetch])

  const saveStageContent = useCallback(async (stageNum: number, content: string, field: string) => {
    const id = taskIdRef.current
    if (!id) return
    try {
      await apiFetch(`/api/release-notes/${id}/stages/${stageNum}/content`, {
        method: 'PUT',
        body: JSON.stringify({ content, field }),
      })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    }
  }, [apiFetch])

  const refineContent = useCallback(async (
    stageNum: number,
    message: string,
    content: string,
  ): Promise<string | null> => {
    const id = taskIdRef.current
    if (!id) return null

    const userMsg: RefinementMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }
    setRefinementMessages(prev => [...prev, userMsg])

    try {
      const resp: ReleaseNotesRefineResponse = await apiFetch(`/api/release-notes/${id}/stages/${stageNum}/refine`, {
        method: 'POST',
        body: JSON.stringify({ message, content }),
      })

      const assistantMsg: RefinementMessage = {
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
  }, [apiFetch])

  // ---- Resume ----

  const resumeTask = useCallback(async (id: string) => {
    setIsLoading(true)
    setError(null)
    taskIdRef.current = id
    try {
      setTaskId(id)
      const state = await loadTaskState(id)

      let resumeStep: ReleaseNotesWizardStep = 0
      for (const stage of state.stages) {
        if (stage.status === 'running') {
          resumeStep = stage.stage_number as ReleaseNotesWizardStep
          setIsExecuting(true)
          startPolling(id, stage.stage_number)
          startConsolePoll(id, stage.stage_number)
          break
        }
        if (stage.status === 'completed') {
          resumeStep = Math.min(stage.stage_number + 1, 5) as ReleaseNotesWizardStep
        } else {
          resumeStep = stage.stage_number as ReleaseNotesWizardStep
          break
        }
      }

      setCurrentStep(resumeStep)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to resume task')
    } finally {
      setIsLoading(false)
    }
  }, [loadTaskState, startPolling, startConsolePoll])

  return {
    taskId,
    taskState,
    currentStep,
    isLoading,
    error,
    editableContent,
    refinementMessages,
    consoleOutput,
    isExecuting,
    stageDocuments,
    createTask,
    executeStage,
    fetchStageContent,
    saveStageContent,
    refineContent,
    setCurrentStep: setCurrentStep as (step: ReleaseNotesWizardStep) => void,
    setEditableContent,
    setStageDocuments,
    resumeTask,
    clearError,
  }
}
