'use client'

import React, { useState, useMemo } from 'react'
import {
  Search,
  LayoutGrid,
  LayoutList,
  Newspaper,
  GitBranch,
  Code2,
  ClipboardList,
  Compass,
} from 'lucide-react'
import TaskCard from './TaskCard'
import { Button, Badge, EmptyState } from '@/components/core'
import { MARS_MODES, getModeDisplayName } from '@/lib/modes'

type TaskStatus = 'draft' | 'active' | 'archived'

interface TaskData {
  id: string
  name: string
  description: string
  mode: string
  status: TaskStatus
  lastRun?: string
  icon: React.ReactNode
  color: string
}

export interface TaskListProps {
  onSelectTask: (taskId: string) => void
}

const TASKS: TaskData[] = [
  {
    id: 'ai-weekly',
    name: 'AI Weekly Report',
    description: 'Generate comprehensive weekly AI technology reports with HITL',
    mode: 'hitl-interactive',
    status: 'active',
    lastRun: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    icon: <Newspaper className="w-5 h-5" />,
    color: 'from-blue-500 to-purple-500',
  },
  {
    id: 'release-notes',
    name: 'Release Notes',
    description: 'Automatically generate release notes from Git history',
    mode: 'one-shot',
    status: 'active',
    lastRun: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    icon: <GitBranch className="w-5 h-5" />,
    color: 'from-green-500 to-teal-500',
  },
  {
    id: 'code-review',
    name: 'Code Review',
    description: 'AI-powered code review assistant',
    mode: 'planning-control',
    status: 'active',
    lastRun: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    icon: <Code2 className="w-5 h-5" />,
    color: 'from-orange-500 to-red-500',
  },
  {
    id: 'product-discovery',
    name: 'Product Discovery',
    description: 'AI-powered product discovery assistant for workshops',
    mode: 'one-shot',
    status: 'active',
    lastRun: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    icon: <Compass className="w-5 h-5" />,
    color: 'from-cyan-500 to-blue-500',
  },
]

type SortKey = 'name' | 'updated'
type ViewMode = 'list' | 'grid'

export default function TaskList({ onSelectTask }: TaskListProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all')
  const [modeFilter, setModeFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<SortKey>('updated')
  const [viewMode, setViewMode] = useState<ViewMode>('list')

  const filteredTasks = useMemo(() => {
    let result = TASKS

    // Search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q)
      )
    }

    // Status filter
    if (statusFilter !== 'all') {
      result = result.filter((t) => t.status === statusFilter)
    }

    // Mode filter
    if (modeFilter !== 'all') {
      result = result.filter((t) => t.mode === modeFilter)
    }

    // Sort
    result = [...result].sort((a, b) => {
      if (sortBy === 'name') return a.name.localeCompare(b.name)
      // sort by lastRun descending (most recent first)
      const aTime = a.lastRun ? new Date(a.lastRun).getTime() : 0
      const bTime = b.lastRun ? new Date(b.lastRun).getTime() : 0
      return bTime - aTime
    })

    return result
  }, [searchQuery, statusFilter, modeFilter, sortBy])

  // Collect unique modes used by tasks
  const usedModes = useMemo(() => {
    const modes = new Set(TASKS.map((t) => t.mode))
    return MARS_MODES.filter((m) => modes.has(m.id))
  }, [])

  const statusOptions: { value: TaskStatus | 'all'; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'draft', label: 'Draft' },
    { value: 'archived', label: 'Archived' },
  ]

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div
          className="flex items-center gap-2 flex-1 min-w-[200px] max-w-sm h-9 px-3 rounded-mars-md border"
          style={{
            backgroundColor: 'var(--mars-color-surface)',
            borderColor: 'var(--mars-color-border)',
          }}
        >
          <Search
            className="w-4 h-4 flex-shrink-0"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          />
          <input
            type="text"
            placeholder="Search tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--mars-color-text)' }}
          />
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-1">
          {statusOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              className="px-3 py-1.5 text-xs font-medium rounded-mars-md transition-colors duration-mars-fast"
              style={{
                backgroundColor:
                  statusFilter === opt.value
                    ? 'var(--mars-color-primary-subtle)'
                    : 'transparent',
                color:
                  statusFilter === opt.value
                    ? 'var(--mars-color-primary-text)'
                    : 'var(--mars-color-text-secondary)',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Mode Filter */}
        <select
          value={modeFilter}
          onChange={(e) => setModeFilter(e.target.value)}
          className="h-9 px-3 text-xs rounded-mars-md border bg-transparent cursor-pointer"
          style={{
            borderColor: 'var(--mars-color-border)',
            color: 'var(--mars-color-text-secondary)',
          }}
        >
          <option value="all">All Modes</option>
          {usedModes.map((mode) => (
            <option key={mode.id} value={mode.id}>
              {mode.displayName}
            </option>
          ))}
        </select>

        {/* Sort */}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortKey)}
          className="h-9 px-3 text-xs rounded-mars-md border bg-transparent cursor-pointer"
          style={{
            borderColor: 'var(--mars-color-border)',
            color: 'var(--mars-color-text-secondary)',
          }}
        >
          <option value="updated">Last Updated</option>
          <option value="name">Name</option>
        </select>

        {/* View Toggle */}
        <div
          className="flex items-center rounded-mars-md border overflow-hidden"
          style={{ borderColor: 'var(--mars-color-border)' }}
        >
          <button
            onClick={() => setViewMode('list')}
            className="p-2 transition-colors duration-mars-fast"
            style={{
              backgroundColor:
                viewMode === 'list'
                  ? 'var(--mars-color-surface-overlay)'
                  : 'transparent',
              color:
                viewMode === 'list'
                  ? 'var(--mars-color-text)'
                  : 'var(--mars-color-text-tertiary)',
            }}
            aria-label="List view"
          >
            <LayoutList className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className="p-2 transition-colors duration-mars-fast"
            style={{
              backgroundColor:
                viewMode === 'grid'
                  ? 'var(--mars-color-surface-overlay)'
                  : 'transparent',
              color:
                viewMode === 'grid'
                  ? 'var(--mars-color-text)'
                  : 'var(--mars-color-text-tertiary)',
            }}
            aria-label="Grid view"
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Task Count */}
      <div className="flex items-center gap-2">
        <span
          className="text-xs"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          {filteredTasks.length} {filteredTasks.length === 1 ? 'task' : 'tasks'}
        </span>
      </div>

      {/* Task List / Grid */}
      {filteredTasks.length === 0 ? (
        <EmptyState
          icon={<ClipboardList className="w-6 h-6" />}
          title="No tasks found"
          description={
            searchQuery || statusFilter !== 'all' || modeFilter !== 'all'
              ? 'Try adjusting your search or filters'
              : 'No tasks have been configured yet'
          }
        />
      ) : (
        <div
          className={
            viewMode === 'grid'
              ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'
              : 'flex flex-col gap-3'
          }
        >
          {filteredTasks.map((task) => (
            <TaskCard
              key={task.id}
              id={task.id}
              name={task.name}
              description={task.description}
              mode={getModeDisplayName(task.mode)}
              status={task.status}
              lastRun={task.lastRun}
              icon={task.icon}
              color={task.color}
              onOpen={onSelectTask}
            />
          ))}
        </div>
      )}
    </div>
  )
}
