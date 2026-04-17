'use client'

import { useState, useEffect, useCallback } from 'react'
import { FileText, ArrowRight, X, TrendingUp, GitBranch, Lightbulb } from 'lucide-react'
import TaskList from '@/components/tasks/TaskList'
import AIWeeklyReportTask from '@/components/tasks/AIWeeklyReportTask'
import ReleaseNotesTask from '@/components/tasks/ReleaseNotesTask'
import CodeReviewTask from '@/components/tasks/CodeReviewTask'
import ProductDiscoveryTask from '@/components/tasks/ProductDiscoveryTask'
import DeepresearchResearchTask from '@/components/tasks/DeepresearchResearchTask'
import NewsPulseTask from '@/components/tasks/NewsPulseTask'
import RfpProposalTask from '@/components/tasks/RfpProposalTask'
import { getApiUrl } from '@/lib/config'

type ActiveTask = 'ai-weekly' | 'release-notes' | 'code-review' | 'product-discovery' | 'deepresearch-research' | 'newspulse' | 'rfp-proposal' | null

interface RecentDeepresearchTask {
  task_id: string
  task: string
  status: string
  created_at: string | null
  current_stage: number | null
  progress_percent: number
}

interface RecentNewsPulseTask {
  task_id: string
  task: string
  status: string
  created_at: string | null
  current_stage: number | null
  progress_percent: number
}

interface RecentReleaseNotesTask {
  task_id: string
  repo_name: string
  base_branch: string
  head_branch: string
  status: string
  created_at: string | null
  current_stage: number | null
  progress_percent: number
}

interface RecentPdaTask {
  task_id: string
  task: string
  status: string
  created_at: string | null
  current_stage: number | null
  progress_percent: number
  client_name?: string | null
  industry?: string | null
}

const STAGE_NAMES: Record<number, string> = {
  1: 'Idea Generation',
  2: 'Method Development',
  3: 'Experiment',
  4: 'Paper',
}

const NP_STAGE_NAMES: Record<number, string> = {
  1: 'Setup',
  2: 'Initial Research',
  3: 'Review & Refine',
  4: 'Final Report',
}

const RN_STAGE_NAMES: Record<number, string> = {
  1: 'Clone & Diff',
  2: 'AI Analysis',
  3: 'Release Notes',
  4: 'Migration',
  5: 'Package',
}

const PDA_STAGE_NAMES: Record<number, string> = {
  1: 'Market Research',
  2: 'Problem Definition',
  3: 'Opportunities',
  4: 'Solution Archetypes',
  5: 'Features',
  6: 'Builder Prompts',
  7: 'Slide Content',
}

export default function TasksPage() {
  const [activeTask, setActiveTask] = useState<ActiveTask>(null)
  const [resumeTaskId, setResumeTaskId] = useState<string | null>(null)
  const [recentTasks, setRecentTasks] = useState<RecentDeepresearchTask[]>([])
  const [recentNpTasks, setRecentNpTasks] = useState<RecentNewsPulseTask[]>([])
  const [recentRnTasks, setRecentRnTasks] = useState<RecentReleaseNotesTask[]>([])
  const [recentPdaTasks, setRecentPdaTasks] = useState<RecentPdaTask[]>([])
  const [loadingRecent, setLoadingRecent] = useState(false)

  const fetchRecentTasks = useCallback(async () => {
    setLoadingRecent(true)
    try {
      const [drResp, npResp, rnResp, pdaResp] = await Promise.all([
        fetch(getApiUrl('/api/deepresearch/recent')),
        fetch(getApiUrl('/api/newspulse/recent')),
        fetch(getApiUrl('/api/release-notes/recent')),
        fetch(getApiUrl('/api/pda/recent')),
      ])
      if (drResp.ok) {
        const data: RecentDeepresearchTask[] = await drResp.json()
        setRecentTasks(data)
      }
      if (npResp.ok) {
        const data: RecentNewsPulseTask[] = await npResp.json()
        setRecentNpTasks(data)
      }
      if (rnResp.ok) {
        const data: RecentReleaseNotesTask[] = await rnResp.json()
        setRecentRnTasks(data)
      }
      if (pdaResp.ok) {
        const data: RecentPdaTask[] = await pdaResp.json()
        setRecentPdaTasks(data)
      }
    } catch {
      // ignore
    } finally {
      setLoadingRecent(false)
    }
  }, [])

  useEffect(() => {
    if (!activeTask) {
      fetchRecentTasks()
    }
  }, [activeTask, fetchRecentTasks])

  const handleResume = useCallback((taskId: string) => {
    setResumeTaskId(taskId)
    setActiveTask('deepresearch-research')
  }, [])

  const handleResumeNp = useCallback((taskId: string) => {
    setResumeTaskId(taskId)
    setActiveTask('newspulse')
  }, [])

  const handleResumeRn = useCallback((taskId: string) => {
    setResumeTaskId(taskId)
    setActiveTask('release-notes')
  }, [])

  const handleResumePda = useCallback((taskId: string) => {
    setResumeTaskId(taskId)
    setActiveTask('product-discovery')
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

  const handleDeleteNpTask = useCallback(async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this task? This will remove all data and files.')) return
    try {
      await fetch(getApiUrl(`/api/newspulse/${taskId}`), { method: 'DELETE' })
      setRecentNpTasks(prev => prev.filter(t => t.task_id !== taskId))
    } catch {
      // ignore — user can retry
    }
  }, [])

  const handleDeleteRnTask = useCallback(async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this task? This will remove all data and files.')) return
    try {
      await fetch(getApiUrl(`/api/release-notes/${taskId}`), { method: 'DELETE' })
      setRecentRnTasks(prev => prev.filter(t => t.task_id !== taskId))
    } catch {
      // ignore — user can retry
    }
  }, [])

  const handleDeletePdaTask = useCallback(async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this Product Discovery task? This will remove all data and files.')) return
    try {
      await fetch(getApiUrl(`/api/pda/${taskId}`), { method: 'DELETE' })
      setRecentPdaTasks(prev => prev.filter(t => t.task_id !== taskId))
    } catch {
      // ignore — user can retry
    }
  }, [])

  // When a task is opened, render its component
  if (activeTask === 'ai-weekly') {
    return <AIWeeklyReportTask onBack={handleBack} />
  }
  if (activeTask === 'release-notes') {
    return <ReleaseNotesTask onBack={handleBack} resumeTaskId={resumeTaskId} />
  }
  if (activeTask === 'code-review') {
    return <CodeReviewTask onBack={handleBack} />
  }
  if (activeTask === 'product-discovery') {
    return <ProductDiscoveryTask onBack={handleBack} resumeTaskId={resumeTaskId} />
  }
  if (activeTask === 'deepresearch-research') {
    return (
      <DeepresearchResearchTask
        onBack={handleBack}
        resumeTaskId={resumeTaskId}
      />
    )
  }
  if (activeTask === 'newspulse') {
    return (
      <NewsPulseTask
        onBack={handleBack}
        resumeTaskId={resumeTaskId}
      />
    )
  }
  if (activeTask === 'rfp-proposal') {
    return (
      <RfpProposalTask
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

      {/* In-progress tasks banners */}
      {!loadingRecent && (recentTasks.length > 0 || recentNpTasks.length > 0 || recentRnTasks.length > 0 || recentPdaTasks.length > 0) && (
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
          {/* News Pulse recent tasks */}
          {recentNpTasks.map((task) => (
            <button
              key={task.task_id}
              onClick={() => handleResumeNp(task.task_id)}
              className="w-full flex items-center gap-3 p-3 rounded-mars-md border transition-colors hover:border-[var(--mars-color-primary)]"
              style={{
                borderColor: 'var(--mars-color-border)',
                backgroundColor: 'var(--mars-color-surface)',
              }}
            >
              <div
                className="flex-shrink-0 w-8 h-8 rounded-mars-md flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, #10b981, #14b8a6)' }}
              >
                <TrendingUp className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 text-left min-w-0">
                <p
                  className="text-sm font-medium truncate"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  Industry News & Sentiment Pulse
                  {task.task ? ` — ${task.task}` : ''}
                </p>
                <p
                  className="text-xs"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                >
                  {task.current_stage
                    ? `Stage ${task.current_stage}: ${NP_STAGE_NAMES[task.current_stage] || ''}`
                    : 'Starting...'}
                  {' '}&middot;{' '}
                  {Math.round(task.progress_percent)}% complete
                </p>
              </div>
              <div
                className="flex-shrink-0 w-20 h-1.5 rounded-full overflow-hidden"
                style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.max(5, task.progress_percent)}%`,
                    background: 'linear-gradient(90deg, #10b981, #14b8a6)',
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
                onClick={(e) => handleDeleteNpTask(task.task_id, e)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleDeleteNpTask(task.task_id, e as unknown as React.MouseEvent) }}
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
          {/* Product Discovery recent tasks */}
          {recentPdaTasks.map((task) => (
            <button
              key={task.task_id}
              onClick={() => handleResumePda(task.task_id)}
              className="w-full flex items-center gap-3 p-3 rounded-mars-md border transition-colors hover:border-[var(--mars-color-primary)]"
              style={{
                borderColor: 'var(--mars-color-border)',
                backgroundColor: 'var(--mars-color-surface)',
              }}
            >
              <div
                className="flex-shrink-0 w-8 h-8 rounded-mars-md flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, #f59e0b, #f97316)' }}
              >
                <Lightbulb className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 text-left min-w-0">
                <p
                  className="text-sm font-medium truncate"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  Product Discovery
                  {task.client_name ? ` — ${task.client_name}` : task.task ? ` — ${task.task}` : ''}
                  {task.industry ? ` (${task.industry})` : ''}
                </p>
                <p
                  className="text-xs"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                >
                  {task.status === 'completed'
                    ? 'All stages completed'
                    : task.status === 'failed'
                    ? `Stage ${task.current_stage ?? '?'}: ${PDA_STAGE_NAMES[task.current_stage ?? 0] || ''} · Failed`
                    : task.current_stage
                    ? `Stage ${task.current_stage}: ${PDA_STAGE_NAMES[task.current_stage] || ''}`
                    : 'Starting...'}
                  {' '}&middot;{' '}
                  {task.status === 'completed' ? '100' : Math.round(task.progress_percent)}% complete
                </p>
              </div>
              <div
                className="flex-shrink-0 w-20 h-1.5 rounded-full overflow-hidden"
                style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${task.status === 'completed' ? 100 : Math.max(5, task.progress_percent)}%`,
                    background: task.status === 'completed'
                      ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                      : task.status === 'failed'
                      ? 'linear-gradient(90deg, #ef4444, #dc2626)'
                      : 'linear-gradient(90deg, #f59e0b, #f97316)',
                  }}
                />
              </div>
              {task.status === 'completed' ? (
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>Done</span>
              ) : task.status === 'failed' ? (
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444' }}>Failed</span>
              ) : (
                <ArrowRight
                  className="w-4 h-4 flex-shrink-0"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                />
              )}
              <div
                role="button"
                tabIndex={0}
                onClick={(e) => handleDeletePdaTask(task.task_id, e)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleDeletePdaTask(task.task_id, e as unknown as React.MouseEvent) }}
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
          {/* Release Notes recent tasks */}
          {recentRnTasks.map((task) => (
            <button
              key={task.task_id}
              onClick={() => handleResumeRn(task.task_id)}
              className="w-full flex items-center gap-3 p-3 rounded-mars-md border transition-colors hover:border-[var(--mars-color-primary)]"
              style={{
                borderColor: 'var(--mars-color-border)',
                backgroundColor: 'var(--mars-color-surface)',
              }}
            >
              <div
                className="flex-shrink-0 w-8 h-8 rounded-mars-md flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, #f59e0b, #d97706)' }}
              >
                <GitBranch className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 text-left min-w-0">
                <p
                  className="text-sm font-medium truncate"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  Release Notes
                  {task.repo_name ? ` — ${task.repo_name}` : ''}
                </p>
                <p
                  className="text-xs"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                >
                  {task.status === 'completed'
                    ? 'All stages completed'
                    : task.status === 'failed'
                    ? `Stage ${task.current_stage ?? '?'}: ${RN_STAGE_NAMES[task.current_stage ?? 0] || ''} · Failed`
                    : task.current_stage
                    ? `Stage ${task.current_stage}: ${RN_STAGE_NAMES[task.current_stage] || ''}`
                    : 'Starting...'}
                  {' '}&middot;{' '}
                  {task.status === 'completed' ? '100' : Math.round(task.progress_percent)}% complete
                  {task.base_branch && task.head_branch
                    ? ` · ${task.base_branch} → ${task.head_branch}`
                    : ''}
                </p>
              </div>
              <div
                className="flex-shrink-0 w-20 h-1.5 rounded-full overflow-hidden"
                style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${task.status === 'completed' ? 100 : Math.max(5, task.progress_percent)}%`,
                    background: task.status === 'completed'
                      ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                      : task.status === 'failed'
                      ? 'linear-gradient(90deg, #ef4444, #dc2626)'
                      : 'linear-gradient(90deg, #f59e0b, #d97706)',
                  }}
                />
              </div>
              {task.status === 'completed' ? (
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>Done</span>
              ) : task.status === 'failed' ? (
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444' }}>Failed</span>
              ) : (
                <ArrowRight
                  className="w-4 h-4 flex-shrink-0"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                />
              )}
              <div
                role="button"
                tabIndex={0}
                onClick={(e) => handleDeleteRnTask(task.task_id, e)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleDeleteRnTask(task.task_id, e as unknown as React.MouseEvent) }}
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
