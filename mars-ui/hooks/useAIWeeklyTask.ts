'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { getWsUrl, config } from '@/lib/config'
import { apiFetchWithRetry } from '@/lib/fetchWithRetry'
import type {
    AIWeeklyTaskState,
    AIWeeklyCreateResponse,
    AIWeeklyRefineResponse,
    AIWeeklyRefinementMessage,
    AIWeeklyWizardStep,
    AIWeeklyStageConfig,
} from '@/types/aiweekly'

const apiFetch = async (url: string, options?: RequestInit) => {
    const resp = await apiFetchWithRetry(url, {
        ...options,
        headers: { 'Content-Type': 'application/json', ...options?.headers },
    })
    if (!resp.ok) throw new Error(`API ${resp.status}: ${await resp.text()}`)
    return resp.json()
}

export interface UseAIWeeklyTaskReturn {
    taskId: string | null
    taskState: AIWeeklyTaskState | null
    currentStep: AIWeeklyWizardStep
    setCurrentStep: (step: AIWeeklyWizardStep) => void
    isLoading: boolean
    error: string | null
    clearError: () => void
    editableContent: string
    setEditableContent: (v: string) => void
    refinementMessages: AIWeeklyRefinementMessage[]
    consoleOutput: string[]
    isExecuting: boolean
    stageConfig: AIWeeklyStageConfig
    setStageConfig: (cfg: AIWeeklyStageConfig) => void

    createTask: (config: {
        date_from: string; date_to: string
        topics: string[]; sources: string[]
        style: string
    }) => Promise<string>
    executeStage: (stageNum: number, taskId?: string) => Promise<void>
    fetchStageContent: (stageNum: number) => Promise<void>
    saveStageContent: (stageNum: number, content: string, field: string) => Promise<void>
    refineContent: (stageNum: number, message: string, content: string) => Promise<string | null>
    loadTaskState: (taskId: string) => Promise<void>
    resumeTask: (taskId: string) => Promise<void>
    resetFromStage: (stageNum: number) => Promise<void>
    deleteTask: () => Promise<void>
}

export function useAIWeeklyTask(): UseAIWeeklyTaskReturn {
    const [taskId, setTaskId] = useState<string | null>(null)
    const [taskState, setTaskState] = useState<AIWeeklyTaskState | null>(null)
    const [currentStep, setCurrentStep] = useState<AIWeeklyWizardStep>(0)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [editableContent, setEditableContent] = useState('')
    const [refinementMessages, setRefinementMessages] = useState<AIWeeklyRefinementMessage[]>([])
    const [consoleOutput, setConsoleOutput] = useState<string[]>([])
    const [isExecuting, setIsExecuting] = useState(false)
    const [stageConfig, setStageConfig] = useState<AIWeeklyStageConfig>({})

    const clearError = useCallback(() => setError(null), [])

    const wsRef = useRef<WebSocket | null>(null)
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const consolePollRef = useRef<ReturnType<typeof setInterval> | null>(null)

    // Cleanup
    useEffect(() => {
        return () => {
            wsRef.current?.close()
            if (pollRef.current) clearInterval(pollRef.current)
            if (consolePollRef.current) clearInterval(consolePollRef.current)
        }
    }, [])

    const createTask = useCallback(async (cfg: {
        date_from: string; date_to: string
        topics: string[]; sources: string[]
        style: string
    }) => {
        setIsLoading(true)
        setError(null)
        try {
            const resp: AIWeeklyCreateResponse = await apiFetch('/api/aiweekly/create', {
                method: 'POST',
                body: JSON.stringify(cfg),
            })
            setTaskId(resp.task_id)
            setTaskState({
                task_id: resp.task_id,
                status: 'executing',
                progress: 0,
                stages: resp.stages as any,
            })
            return resp.task_id
        } catch (e: any) {
            setError(e.message)
            throw e
        } finally {
            setIsLoading(false)
        }
    }, [])

    const loadTaskState = useCallback(async (id: string) => {
        try {
            const state: AIWeeklyTaskState = await apiFetch(`/api/aiweekly/${id}`)
            setTaskId(id)
            setTaskState(state)
        } catch (e: any) {
            setError(e.message)
        }
    }, [])

    const resumeTask = useCallback(async (id: string) => {
        try {
            const state: AIWeeklyTaskState = await apiFetch(`/api/aiweekly/${id}`)
            setTaskId(id)
            setTaskState(state)
            // Jump to the latest relevant step
            const lastCompleted = state.stages
                .filter(s => s.status === 'completed')
                .sort((a, b) => b.stage_number - a.stage_number)[0]
            if (lastCompleted) {
                const nextStep = Math.min(lastCompleted.stage_number + 1, 4) as AIWeeklyWizardStep
                setCurrentStep(nextStep)
            } else {
                setCurrentStep(1)
            }
        } catch (e: any) {
            setError(e.message)
        }
    }, [])

    const startConsolePoll = useCallback((id: string, stageNum: number) => {
        if (consolePollRef.current) clearInterval(consolePollRef.current)
        let nextIndex = 0
        consolePollRef.current = setInterval(async () => {
            try {
                const data = await apiFetch(`/api/aiweekly/${id}/stages/${stageNum}/console?since=${nextIndex}`)
                if (data.lines?.length) {
                    setConsoleOutput(prev => [...prev, ...data.lines])
                    nextIndex = data.next_index
                }
            } catch { /* ignore */ }
        }, 2000)
    }, [])

    const startPolling = useCallback((id: string) => {
        if (pollRef.current) clearInterval(pollRef.current)
        pollRef.current = setInterval(async () => {
            try {
                const state: AIWeeklyTaskState = await apiFetch(`/api/aiweekly/${id}`)
                setTaskState(state)
                const stage = state.stages.find(s => s.status === 'running')
                if (!stage) {
                    setIsExecuting(false)
                    if (pollRef.current) clearInterval(pollRef.current)
                    if (consolePollRef.current) clearInterval(consolePollRef.current)
                }
            } catch { /* ignore */ }
        }, 5000)
    }, [])

    const executeStage = useCallback(async (stageNum: number, id?: string) => {
        const tid = id || taskId
        if (!tid) return
        setIsExecuting(true)
        setConsoleOutput([])
        setError(null)
        try {
            // Build config_overrides from stageConfig (skip stage 1 — no LLM)
            const config_overrides: Record<string, unknown> = {}
            if (stageNum >= 2) {
                for (const [k, v] of Object.entries(stageConfig)) {
                    if (v !== undefined && v !== '') config_overrides[k] = v
                }
            }
            await apiFetch(`/api/aiweekly/${tid}/stages/${stageNum}/execute`, {
                method: 'POST',
                body: JSON.stringify({ config_overrides }),
            })
            startConsolePoll(tid, stageNum)
            startPolling(tid)
        } catch (e: any) {
            setError(e.message)
            setIsExecuting(false)
        }
    }, [taskId, stageConfig, startConsolePoll, startPolling])

    const fetchStageContent = useCallback(async (stageNum: number) => {
        if (!taskId) return
        try {
            const data = await apiFetch(`/api/aiweekly/${taskId}/stages/${stageNum}/content`)
            setEditableContent(data.content || '')
        } catch (e: any) {
            setError(e.message)
        }
    }, [taskId])

    const saveStageContent = useCallback(async (stageNum: number, content: string, field: string) => {
        if (!taskId) return
        try {
            await apiFetch(`/api/aiweekly/${taskId}/stages/${stageNum}/content`, {
                method: 'PUT',
                body: JSON.stringify({ content, field }),
            })
        } catch (e: any) {
            setError(e.message)
        }
    }, [taskId])

    const refineContent = useCallback(async (stageNum: number, message: string, content: string) => {
        if (!taskId) return null
        setRefinementMessages(prev => [...prev, { id: (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36)), role: 'user', content: message, timestamp: Date.now() }])
        try {
            const resp: AIWeeklyRefineResponse = await apiFetch(`/api/aiweekly/${taskId}/stages/${stageNum}/refine`, {
                method: 'POST',
                body: JSON.stringify({ message, content }),
            })
            setRefinementMessages(prev => [...prev, { id: (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36)), role: 'assistant', content: resp.refined_content, timestamp: Date.now() }])
            return resp.refined_content
        } catch (e: any) {
            setError(e.message)
            return null
        }
    }, [taskId])

    const resetFromStage = useCallback(async (stageNum: number) => {
        if (!taskId) return
        try {
            await apiFetch(`/api/aiweekly/${taskId}/reset-from/${stageNum}`, { method: 'POST' })
            await loadTaskState(taskId)
        } catch (e: any) {
            setError(e.message)
        }
    }, [taskId, loadTaskState])

    const deleteTask = useCallback(async () => {
        if (!taskId) return
        try {
            await apiFetch(`/api/aiweekly/${taskId}`, { method: 'DELETE' })
            setTaskId(null)
            setTaskState(null)
            setEditableContent('')
        } catch (e: any) {
            setError(e.message)
        }
    }, [taskId])

    return {
        taskId, taskState, currentStep, setCurrentStep,
        isLoading, error, clearError,
        editableContent, setEditableContent,
        refinementMessages, consoleOutput, isExecuting,
        stageConfig, setStageConfig,
        createTask, executeStage, fetchStageContent,
        saveStageContent, refineContent, loadTaskState,
        resumeTask, resetFromStage, deleteTask,
    }
}
