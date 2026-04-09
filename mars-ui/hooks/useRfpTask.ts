'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { getApiUrl, getWsUrl, config } from '@/lib/config'
import { apiFetchWithRetry } from '@/lib/fetchWithRetry'
import type {
    RfpTaskState,
    RfpStageContent,
    RfpCreateResponse,
    RfpRefineResponse,
    RfpRefinementMessage,
    RfpUploadedFile,
    RfpWizardStep,
    RfpStageConfig,
} from '@/types/rfp'

interface UseRfpTaskReturn {
    // State
    taskId: string | null
    taskState: RfpTaskState | null
    currentStep: RfpWizardStep
    isLoading: boolean
    error: string | null

    // Stage content
    editableContent: string
    refinementMessages: RfpRefinementMessage[]
    consoleOutput: string[]
    isExecuting: boolean

    // Files
    uploadedFiles: RfpUploadedFile[]
    lastExtractedText: string | null

    // Config
    taskConfig: RfpStageConfig
    setTaskConfig: (config: RfpStageConfig) => void

    // Actions
    createTask: (task: string, rfpContext?: string, stageConfig?: RfpStageConfig) => Promise<string | null>
    autoCreateTask: () => Promise<string | null>
    executeStage: (stageNum: number, overrideId?: string) => Promise<void>
    fetchStageContent: (stageNum: number) => Promise<RfpStageContent | null>
    saveStageContent: (stageNum: number, content: string, field: string) => Promise<void>
    refineContent: (stageNum: number, message: string, content: string) => Promise<string | null>
    uploadFile: (file: File) => Promise<void>
    setCurrentStep: (step: RfpWizardStep) => void
    setEditableContent: (content: string) => void
    resumeTask: (taskId: string) => Promise<void>
    deleteTask: () => Promise<void>
    resetFromStage: (stageNum: number) => Promise<void>
    clearError: () => void
}

export function useRfpTask(): UseRfpTaskReturn {
    const [taskId, setTaskId] = useState<string | null>(null)
    const [taskState, setTaskState] = useState<RfpTaskState | null>(null)
    const [currentStep, setCurrentStep] = useState<RfpWizardStep>(0)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const [editableContent, setEditableContent] = useState('')
    const [refinementMessages, setRefinementMessages] = useState<RfpRefinementMessage[]>([])
    const [consoleOutput, setConsoleOutput] = useState<string[]>([])
    const [isExecuting, setIsExecuting] = useState(false)
    const [uploadedFiles, setUploadedFiles] = useState<RfpUploadedFile[]>([])
    const [lastExtractedText, setLastExtractedText] = useState<string | null>(null)
    const [taskConfig, setTaskConfig] = useState<RfpStageConfig>({})

    const wsRef = useRef<WebSocket | null>(null)
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const consolePollRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const consoleIndexRef = useRef(0)
    const taskIdRef = useRef<string | null>(null)
    const autoCreateLockRef = useRef<Promise<string | null> | null>(null)

    useEffect(() => { taskIdRef.current = taskId }, [taskId])

    useEffect(() => {
        return () => {
            wsRef.current?.close()
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
        const state: RfpTaskState = await apiFetch(`/api/rfp/${id}`)
        setTaskState(state)
        return state
    }, [apiFetch])

    const createTask = useCallback(async (
        task: string,
        rfpContext?: string,
        stageConfig?: RfpStageConfig,
    ) => {
        setIsLoading(true)
        setError(null)
        try {
            const existingId = taskIdRef.current
            if (existingId) {
                // Task was auto-created for file uploads — update description
                await apiFetch(`/api/rfp/${existingId}/description`, {
                    method: 'PATCH',
                    body: JSON.stringify({ task, rfp_context: rfpContext }),
                }).catch(() => {
                    // If PATCH endpoint doesn't exist, that's ok
                })
                if (stageConfig) setTaskConfig(stageConfig)
                return existingId
            }

            const resp: RfpCreateResponse = await apiFetch('/api/rfp/create', {
                method: 'POST',
                body: JSON.stringify({
                    task,
                    rfp_context: rfpContext,
                    config: stageConfig,
                    work_dir: config.workDir,
                }),
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

    const autoCreateTask = useCallback(async (): Promise<string | null> => {
        if (taskIdRef.current) return taskIdRef.current
        if (autoCreateLockRef.current) return autoCreateLockRef.current
        const p = apiFetch('/api/rfp/create', {
            method: 'POST',
            body: JSON.stringify({ task: '', work_dir: config.workDir }),
        }).then((resp: RfpCreateResponse) => {
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
                // ignore
            }
        }, 5000)
    }, [loadTaskState])

    const startConsolePoll = useCallback((id: string, stageNum: number) => {
        if (consolePollRef.current) clearInterval(consolePollRef.current)
        consoleIndexRef.current = 0
        consolePollRef.current = setInterval(async () => {
            try {
                const resp = await fetch(
                    getApiUrl(`/api/rfp/${id}/stages/${stageNum}/console?since=${consoleIndexRef.current}`)
                )
                if (!resp.ok) return
                const data = await resp.json()
                if (data.lines && data.lines.length > 0) {
                    setConsoleOutput(prev => [...prev, ...data.lines])
                    consoleIndexRef.current = data.next_index
                }
            } catch {
                // ignore
            }
        }, 2000)
    }, [])

    const connectWs = useCallback((id: string, stageNum: number) => {
        wsRef.current?.close()
        const url = getWsUrl(`/ws/rfp/${id}/${stageNum}`)
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
            } catch {
                // ignore
            }
        }
        ws.onerror = () => { }
        ws.onclose = () => { }
    }, [loadTaskState])

    const executeStage = useCallback(async (stageNum: number, overrideId?: string) => {
        const id = overrideId ?? taskId
        if (!id) return
        setIsExecuting(true)
        setError(null)
        setConsoleOutput([])

        const config_overrides: Record<string, unknown> = {}
        if (taskConfig.model) config_overrides.model = taskConfig.model

        try {
            await apiFetch(`/api/rfp/${id}/stages/${stageNum}/execute`, {
                method: 'POST',
                body: JSON.stringify({ config_overrides }),
            })

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

    const fetchStageContent = useCallback(async (stageNum: number): Promise<RfpStageContent | null> => {
        if (!taskId) return null
        try {
            const content: RfpStageContent = await apiFetch(`/api/rfp/${taskId}/stages/${stageNum}/content`)
            setEditableContent(content.content ?? '')
            return content
        } catch {
            return null
        }
    }, [taskId, apiFetch])

    const saveStageContent = useCallback(async (stageNum: number, content: string, field: string) => {
        if (!taskId) return
        try {
            await apiFetch(`/api/rfp/${taskId}/stages/${stageNum}/content`, {
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

        const userMsg: RfpRefinementMessage = {
            id: `u-${Date.now()}`,
            role: 'user',
            content: message,
            timestamp: Date.now(),
        }
        setRefinementMessages(prev => [...prev, userMsg])

        try {
            const resp: RfpRefineResponse = await apiFetch(`/api/rfp/${taskId}/stages/${stageNum}/refine`, {
                method: 'POST',
                body: JSON.stringify({ message, content }),
            })

            const assistantMsg: RfpRefinementMessage = {
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

    const uploadFile = useCallback(async (file: File) => {
        const entry: RfpUploadedFile = { name: file.name, size: file.size, status: 'uploading' }
        setUploadedFiles(prev => [...prev, entry])

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
            if (data.extracted_text) {
                setLastExtractedText(data.extracted_text)
            }
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

    // ---- Resume ----

    const resumeTask = useCallback(async (id: string) => {
        setIsLoading(true)
        setError(null)
        taskIdRef.current = id
        setTaskId(id)
        try {
            const state = await loadTaskState(id)
            // Determine which step to resume at
            let resumeStep: RfpWizardStep = 0
            for (const stage of state.stages) {
                if (stage.status === 'running') {
                    resumeStep = stage.stage_number as RfpWizardStep
                    setIsExecuting(true)
                    connectWs(id, stage.stage_number)
                    startPolling(id, stage.stage_number)
                    startConsolePoll(id, stage.stage_number)
                    break
                }
                if (stage.status === 'completed') {
                    resumeStep = Math.min(stage.stage_number + 1, 7) as RfpWizardStep
                }
                if (stage.status === 'failed' || stage.status === 'pending') {
                    resumeStep = stage.stage_number as RfpWizardStep
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

    // ---- Reset from stage ----

    const resetFromStage = useCallback(async (stageNum: number) => {
        const id = taskIdRef.current
        if (!id) return
        try {
            await apiFetch(`/api/rfp/${id}/reset-from/${stageNum}`, { method: 'POST' })
            await loadTaskState(id)
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to reset stages')
        }
    }, [apiFetch, loadTaskState])

    // ---- Delete ----

    const deleteTask = useCallback(async () => {
        const id = taskIdRef.current
        if (!id) return
        try {
            await apiFetch(`/api/rfp/${id}`, { method: 'DELETE' })
            setTaskId(null)
            taskIdRef.current = null
            setTaskState(null)
            setCurrentStep(0)
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to delete task')
        }
    }, [apiFetch])

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
        lastExtractedText,
        taskConfig,
        setTaskConfig,
        createTask,
        autoCreateTask,
        executeStage,
        fetchStageContent,
        saveStageContent,
        refineContent,
        uploadFile,
        setCurrentStep,
        setEditableContent,
        resumeTask,
        deleteTask,
        resetFromStage,
        clearError,
    }
}
