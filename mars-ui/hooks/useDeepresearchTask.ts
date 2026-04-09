'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { getApiUrl, getWsUrl, config } from '@/lib/config'
import { apiFetchWithRetry } from '@/lib/fetchWithRetry'
import type {
  DeepresearchTaskState,
  DeepresearchStageContent,
  DeepresearchCreateResponse,
  DeepresearchRefineResponse,
  RefinementMessage,
  UploadedFile,
  DeepresearchWizardStep,
  DeepresearchStageConfig,
} from '@/types/deepresearch'

interface UseDeepresearchTaskReturn {
  // State
  taskId: string | null
  taskState: DeepresearchTaskState | null
  currentStep: DeepresearchWizardStep
  isLoading: boolean
  error: string | null

  // Stage content
  editableContent: string
  refinementMessages: RefinementMessage[]
  consoleOutput: string[]
  isExecuting: boolean

  // Files
  uploadedFiles: UploadedFile[]

  // File context (data understanding)
  fileContextOutput: string[]
  fileContextStatus: 'idle' | 'running' | 'done' | 'error'
  fileContext: string

  // Stage config
  taskConfig: DeepresearchStageConfig
  setTaskConfig: (config: DeepresearchStageConfig) => void

  // Actions
  autoCreateTask: () => Promise<string | null>
  createTask: (task: string, dataDescription?: string, config?: DeepresearchStageConfig) => Promise<string | null>
  executeStage: (stageNum: number, overrideId?: string) => Promise<void>
  fetchStageContent: (stageNum: number) => Promise<DeepresearchStageContent | null>
  saveStageContent: (stageNum: number, content: string, field: string) => Promise<void>
  refineContent: (stageNum: number, message: string, content: string) => Promise<string | null>
  uploadFile: (file: File) => Promise<void>
  analyzeFiles: () => Promise<void>
  refineFileContext: (message: string, content: string) => Promise<string | null>
  saveFileContext: (content: string) => Promise<void>
  setFileContext: (content: string) => void
  setCurrentStep: (step: DeepresearchWizardStep) => void
  setEditableContent: (content: string) => void
  resumeTask: (taskId: string) => Promise<void>
  stopTask: () => Promise<void>
  deleteTask: () => Promise<void>
  clearError: () => void
}

export function useDeepresearchTask(): UseDeepresearchTaskReturn {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskState, setTaskState] = useState<DeepresearchTaskState | null>(null)
  const [currentStep, setCurrentStep] = useState<DeepresearchWizardStep>(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [editableContent, setEditableContent] = useState('')
  const [refinementMessages, setRefinementMessages] = useState<RefinementMessage[]>([])
  const [consoleOutput, setConsoleOutput] = useState<string[]>([])
  const [isExecuting, setIsExecuting] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [taskConfig, setTaskConfig] = useState<DeepresearchStageConfig>({})

  // File context (data understanding)
  const [fileContextOutput, setFileContextOutput] = useState<string[]>([])
  const [fileContextStatus, setFileContextStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [fileContext, setFileContext] = useState('')

  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consolePollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const analyzeConsolePollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consoleIndexRef = useRef(0)

  // Stable refs to avoid stale closures for auto-create
  const taskIdRef = useRef<string | null>(null)
  const autoCreateLockRef = useRef<Promise<string | null> | null>(null)

  // Keep taskIdRef in sync with taskId state
  useEffect(() => { taskIdRef.current = taskId }, [taskId])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
      if (consolePollRef.current) clearInterval(consolePollRef.current)
      if (analyzeConsolePollRef.current) clearInterval(analyzeConsolePollRef.current)
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
    const state: DeepresearchTaskState = await apiFetch(`/api/deepresearch/${id}`)
    setTaskState(state)
    return state
  }, [apiFetch])

  const createTask = useCallback(async (
    task: string,
    dataDescription?: string,
    stageConfig?: DeepresearchStageConfig,
  ) => {
    setIsLoading(true)
    setError(null)
    try {
      // If a task was already auto-created, just update its description
      const existingId = taskIdRef.current
      if (existingId) {
        await apiFetch(`/api/deepresearch/${existingId}/description`, {
          method: 'PATCH',
          body: JSON.stringify({ task, data_description: dataDescription }),
        })
        if (stageConfig) setTaskConfig(stageConfig)
        return existingId
      }

      // Otherwise create fresh
      const resp: DeepresearchCreateResponse = await apiFetch('/api/deepresearch/create', {
        method: 'POST',
        body: JSON.stringify({ task, data_description: dataDescription, config: stageConfig, work_dir: config.workDir }),
      })
      setTaskId(resp.task_id)
      taskIdRef.current = resp.task_id
      if (stageConfig) setTaskConfig(stageConfig)
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
          wsRef.current?.close()
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
          getApiUrl(`/api/deepresearch/${id}/stages/${stageNum}/console?since=${consoleIndexRef.current}`)
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

  const connectWs = useCallback((id: string, stageNum: number) => {
    wsRef.current?.close()
    const url = getWsUrl(`/ws/deepresearch/${id}/${stageNum}`)
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
        // Console output is handled by REST poll to avoid duplication
      } catch {
        // ignore parse errors
      }
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

    // Build config_overrides from stored taskConfig, filtered by stage
    const cfg = taskConfig
    let config_overrides: Record<string, unknown> = {}
    if (stageNum <= 3) {
      // Stages 1-3 use stage_helpers which ignores unknown keys
      const { llm_model, writer, add_citations, ...sharedCfg } = cfg
      void llm_model; void writer; void add_citations
      config_overrides = Object.fromEntries(
        Object.entries(sharedCfg).filter(([, v]) => v !== undefined && v !== '')
      )
    } else {
      // Stage 4 (paper) uses DeepresearchPaperPhaseConfig — only pass valid fields
      const paperKeys: Array<keyof DeepresearchStageConfig> = ['llm_model', 'writer', 'journal', 'add_citations']
      for (const k of paperKeys) {
        if (cfg[k] !== undefined) config_overrides[k] = cfg[k]
      }
    }

    try {
      await apiFetch(`/api/deepresearch/${id}/stages/${stageNum}/execute`, {
        method: 'POST',
        body: JSON.stringify({ config_overrides }),
      })

      // Connect WS + start polling (status + console)
      connectWs(id, stageNum)
      startPolling(id, stageNum)
      startConsolePoll(id, stageNum)
      setConsoleOutput([`Stage ${stageNum} execution started...`])
    } catch (e: unknown) {
      setIsExecuting(false)
      setError(e instanceof Error ? e.message : 'Failed to execute stage')
    }
  }, [taskId, taskConfig, apiFetch, connectWs, startPolling, startConsolePoll])

  // ---- Content ----

  const fetchStageContent = useCallback(async (stageNum: number): Promise<DeepresearchStageContent | null> => {
    if (!taskId) return null
    try {
      const content: DeepresearchStageContent = await apiFetch(`/api/deepresearch/${taskId}/stages/${stageNum}/content`)
      // Always update editable content — use content from response,
      // or empty string as fallback (content may be null/undefined/empty)
      setEditableContent(content.content ?? '')
      return content
    } catch {
      return null
    }
  }, [taskId, apiFetch])

  const saveStageContent = useCallback(async (stageNum: number, content: string, field: string) => {
    if (!taskId) return
    try {
      await apiFetch(`/api/deepresearch/${taskId}/stages/${stageNum}/content`, {
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

    // Add user message
    const userMsg: RefinementMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }
    setRefinementMessages(prev => [...prev, userMsg])

    try {
      const resp: DeepresearchRefineResponse = await apiFetch(`/api/deepresearch/${taskId}/stages/${stageNum}/refine`, {
        method: 'POST',
        body: JSON.stringify({ message, content }),
      })

      // Add assistant response
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
  }, [taskId, apiFetch])

  // ---- File upload ----

  // Auto-create a task silently so files can be uploaded immediately.
  // Uses a lock to prevent double-creation on concurrent calls.
  const autoCreateTask = useCallback(async (): Promise<string | null> => {
    if (taskIdRef.current) return taskIdRef.current
    if (autoCreateLockRef.current) return autoCreateLockRef.current
    const p = apiFetch('/api/deepresearch/create', {
      method: 'POST',
      body: JSON.stringify({ task: '', work_dir: config.workDir }),
    }).then((resp: DeepresearchCreateResponse) => {
      taskIdRef.current = resp.task_id
      setTaskId(resp.task_id)
      autoCreateLockRef.current = null
      return resp.task_id as string | null
    }).catch((): null => {
      autoCreateLockRef.current = null
      return null
    })
    autoCreateLockRef.current = p
    return p
  }, [apiFetch])

  const uploadFile = useCallback(async (file: File) => {
    const entry: UploadedFile = {
      name: file.name,
      size: file.size,
      status: 'uploading',
    }
    setUploadedFiles(prev => [...prev, entry])

    // Ensure task exists before uploading
    let id = taskIdRef.current
    if (!id) {
      id = await autoCreateTask()
    }
    if (!id) {
      setUploadedFiles(prev =>
        prev.map(f => f.name === file.name ? { ...f, status: 'pending' as const } : f)
      )
      return
    }

    const formData = new FormData()
    formData.append('file', file)
    formData.append('task_id', id)
    formData.append('subfolder', 'input_files')

    try {
      const resp = await fetch(getApiUrl('/api/files/upload'), {
        method: 'POST',
        body: formData,
      })
      if (!resp.ok) throw new Error('Upload failed')
      const data = await resp.json()
      setUploadedFiles(prev =>
        prev.map(f => f.name === file.name ? { ...f, status: 'done' as const, path: data.path } : f)
      )
    } catch (e: unknown) {
      setUploadedFiles(prev =>
        prev.map(f => f.name === file.name ? {
          ...f,
          status: 'error' as const,
          error: e instanceof Error ? e.message : 'Upload failed',
        } : f)
      )
    }
  }, [autoCreateTask])

  // ---- File context (data understanding) ----

  const analyzeFiles = useCallback(async () => {
    const id = taskIdRef.current
    if (!id) return
    setFileContextStatus('running')
    setFileContextOutput([])

    try {
      await apiFetch(`/api/deepresearch/${id}/analyze-files`, { method: 'POST' })
    } catch (e: unknown) {
      setFileContextStatus('error')
      setFileContextOutput([e instanceof Error ? e.message : 'Failed to start analysis'])
      return
    }

    // Poll for progress
    let idx = 0
    if (analyzeConsolePollRef.current) clearInterval(analyzeConsolePollRef.current)
    analyzeConsolePollRef.current = setInterval(async () => {
      try {
        const resp = await fetch(
          getApiUrl(`/api/deepresearch/${id}/analyze-files/console?since=${idx}`)
        )
        if (!resp.ok) return
        const data = await resp.json()
        if (data.lines?.length > 0) {
          setFileContextOutput(prev => [...prev, ...data.lines])
          idx = data.next_index
        }
        if (data.is_done) {
          if (analyzeConsolePollRef.current) clearInterval(analyzeConsolePollRef.current)
          analyzeConsolePollRef.current = null
          if (data.has_error) {
            setFileContextStatus('error')
          } else {
            setFileContext(data.context_text || '')
            setFileContextStatus('done')
          }
        }
      } catch {
        // ignore transient poll errors
      }
    }, 2000)
  }, [apiFetch])

  const refineFileContext = useCallback(async (
    message: string,
    content: string,
  ): Promise<string | null> => {
    const id = taskIdRef.current
    if (!id) return null
    try {
      const resp = await apiFetch(`/api/deepresearch/${id}/refine-context`, {
        method: 'POST',
        body: JSON.stringify({ message, content }),
      })
      setFileContext(resp.refined_content)
      return resp.refined_content
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Context refinement failed')
      return null
    }
  }, [apiFetch])

  const saveFileContext = useCallback(async (content: string) => {
    const id = taskIdRef.current
    if (!id) return
    try {
      await apiFetch(`/api/deepresearch/${id}/context`, {
        method: 'PUT',
        body: JSON.stringify({ message: '', content }),
      })
      setFileContext(content)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save context')
    }
  }, [apiFetch])

  // ---- Resume ----

  const resumeTask = useCallback(async (id: string) => {
    setIsLoading(true)
    setError(null)
    // Set ref synchronously so any concurrent autoCreateTask calls see this ID
    // and bail out immediately instead of creating a new empty task
    taskIdRef.current = id
    try {
      setTaskId(id)
      const state = await loadTaskState(id)

      // Find the right step to resume at
      let resumeStep: DeepresearchWizardStep = 0
      for (const stage of state.stages) {
        if (stage.status === 'running') {
          // Stage is running - go to that step and reconnect
          resumeStep = stage.stage_number as DeepresearchWizardStep
          setIsExecuting(true)
          connectWs(id, stage.stage_number)
          startPolling(id, stage.stage_number)
          startConsolePoll(id, stage.stage_number)
          break
        }
        if (stage.status === 'completed') {
          // Completed - advance past it
          resumeStep = Math.min(stage.stage_number + 1, 4) as DeepresearchWizardStep
        } else {
          // Pending or failed - stop here
          resumeStep = stage.stage_number as DeepresearchWizardStep
          break
        }
      }

      setCurrentStep(resumeStep)

      // Restore file context if it was previously analysed
      try {
        const ctxResp = await fetch(getApiUrl(`/api/deepresearch/${id}/analyze-files/console?since=0`))
        if (ctxResp.ok) {
          const ctxData = await ctxResp.json()
          if (ctxData.is_done && ctxData.context_text) {
            setFileContext(ctxData.context_text)
            setFileContextStatus('done')
          }
        }
      } catch {
        // not critical — context panel just stays empty
      }
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
      await apiFetch(`/api/deepresearch/${taskId}/stop`, { method: 'POST' })
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
      await apiFetch(`/api/deepresearch/${taskId}`, { method: 'DELETE' })
      // Reset all state
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
    editableContent,
    refinementMessages,
    consoleOutput,
    isExecuting,
    uploadedFiles,
    fileContextOutput,
    fileContextStatus,
    fileContext,
    taskConfig,
    setTaskConfig,
    autoCreateTask,
    createTask,
    executeStage,
    fetchStageContent,
    saveStageContent,
    refineContent,
    uploadFile,
    analyzeFiles,
    refineFileContext,
    saveFileContext,
    setFileContext,
    setCurrentStep: setCurrentStep as (step: DeepresearchWizardStep) => void,
    setEditableContent,
    resumeTask,
    stopTask,
    deleteTask,
    clearError,
  }
}
