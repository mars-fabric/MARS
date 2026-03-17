'use client'

import { useState, useEffect, useCallback } from 'react'
import { FileText, ArrowRight, X } from 'lucide-react'
import TaskList from '@/components/tasks/TaskList'
import AIWeeklyTaskEnhanced from '@/components/tasks/AIWeeklyTaskEnhanced'
import ReleaseNotesTask from '@/components/tasks/ReleaseNotesTask'
import CodeReviewTask from '@/components/tasks/CodeReviewTask'
import ProductDiscoveryTask from '@/components/tasks/ProductDiscoveryTask'
import DeepresearchResearchTask from '@/components/tasks/DeepresearchResearchTask'
import { getApiUrl } from '@/lib/config'

type ActiveTask = 'ai-weekly' | 'release-notes' | 'code-review' | 'product-discovery' | 'deepresearch-research' | null

interface RecentDeepresearchTask {
  task_id: string
  task: string
  status: string
  created_at: string | null
  current_stage: number | null
  progress_percent: number
}

const STAGE_NAMES: Record<number, string> = {
  1: 'Idea Generation',
  2: 'Method Development',
  3: 'Experiment',
  4: 'Paper',
}

export default function TasksPage() {
  const [activeTask, setActiveTask] = useState<ActiveTask>(null)
  const [resumeTaskId, setResumeTaskId] = useState<string | null>(null)
  const [recentTasks, setRecentTasks] = useState<RecentDeepresearchTask[]>([])
  const [loadingRecent, setLoadingRecent] = useState(false)

  const fetchRecentTasks = useCallback(async () => {
    setLoadingRecent(true)
    try {
      const resp = await fetch(getApiUrl('/api/deepresearch/recent'))
      if (resp.ok) {
        const data: RecentDeepresearchTask[] = await resp.json()
        setRecentTasks(data)
      }
    } catch {
      // ignore — banner just won't show
    } finally {
      setLoadingRecent(false)
    }
  }, [])

  // Fetch recent tasks on mount and when returning from a task
  useEffect(() => {
    if (!activeTask) {
      fetchRecentTasks()
    }
  }, [activeTask, fetchRecentTasks])

  const handleResume = useCallback((taskId: string) => {
    setResumeTaskId(taskId)
    setActiveTask('deepresearch-research')
  }, [])

  const handleBack = useCallback(() => {
    setActiveTask(null)
    setResumeTaskId(null)
  }, [])

  const handleDeleteTask = useCallback(async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation() // Don't trigger the resume click
    if (!confirm('Delete this task? This will remove all data and files.')) return
    try {
      await fetch(getApiUrl(`/api/deepresearch/${taskId}`), { method: 'DELETE' })
      setRecentTasks(prev => prev.filter(t => t.task_id !== taskId))
    } catch {
      // ignore — user can retry
    }
  }, [])

  // When a task is opened, render its component
  if (activeTask === 'ai-weekly') {
    return <AIWeeklyTaskEnhanced onBack={handleBack} />
  }
  if (activeTask === 'release-notes') {
    return <ReleaseNotesTask onBack={handleBack} />
  }
  if (activeTask === 'code-review') {
    return <CodeReviewTask onBack={handleBack} />
  }
  if (activeTask === 'product-discovery') {
    return <ProductDiscoveryTask onBack={handleBack} />
  }
  if (activeTask === 'deepresearch-research') {
    return (
      <DeepresearchResearchTask
        onBack={handleBack}
        resumeTaskId={resumeTaskId}
      />
    )
  }

  // Default: show task list
  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h2
          className="text-2xl font-semibold"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Tasks
        </h2>
        <p
          className="text-sm mt-1"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Manage and run configured automation tasks
        </p>
      </div>

      {/* In-progress Deepresearch tasks banner */}
      {!loadingRecent && recentTasks.length > 0 && (
        <div className="mb-6 space-y-2">
          <h3
            className="text-xs font-medium uppercase tracking-wider"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            In Progress
          </h3>
          {recentTasks.map((task) => (
            <button
              key={task.task_id}
              onClick={() => handleResume(task.task_id)}
              className="w-full flex items-center gap-3 p-3 rounded-mars-md border transition-colors hover:border-[var(--mars-color-primary)]"
              style={{
                borderColor: 'var(--mars-color-border)',
                backgroundColor: 'var(--mars-color-surface)',
              }}
            >
              <div
                className="flex-shrink-0 w-8 h-8 rounded-mars-md flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}
              >
                <FileText className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 text-left min-w-0">
                <p
                  className="text-sm font-medium truncate"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  Deep Scientific Research
                  {task.task ? ` — ${task.task}` : ''}
                </p>
                <p
                  className="text-xs"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                >
                  {task.current_stage
                    ? `Stage ${task.current_stage}: ${STAGE_NAMES[task.current_stage] || ''}`
                    : 'Starting...'}
                  {' '}&middot;{' '}
                  {Math.round(task.progress_percent)}% complete
                </p>
              </div>
              {/* Progress bar */}
              <div
                className="flex-shrink-0 w-20 h-1.5 rounded-full overflow-hidden"
                style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.max(5, task.progress_percent)}%`,
                    background: 'linear-gradient(90deg, #8b5cf6, #6366f1)',
                  }}
                />
              </div>
              <ArrowRight
                className="w-4 h-4 flex-shrink-0"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
              />
              <div
                role="button"
                tabIndex={0}
                onClick={(e) => handleDeleteTask(task.task_id, e)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleDeleteTask(task.task_id, e as unknown as React.MouseEvent) }}
                className="flex-shrink-0 p-1 rounded transition-colors hover:bg-[var(--mars-color-danger-subtle,rgba(239,68,68,0.1))]"
                title="Delete task"
              >
                <X
                  className="w-3.5 h-3.5"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                />
              </div>
            </button>
          ))}
        </div>
      )}

      <TaskList onSelectTask={(id) => setActiveTask(id as ActiveTask)} />
    </div>
  )
}
