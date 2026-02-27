'use client'

import { useState } from 'react'
import TaskList from '@/components/tasks/TaskList'
import AIWeeklyTaskEnhanced from '@/components/tasks/AIWeeklyTaskEnhanced'
import ReleaseNotesTask from '@/components/tasks/ReleaseNotesTask'
import CodeReviewTask from '@/components/tasks/CodeReviewTask'
import ProductDiscoveryTask from '@/components/tasks/ProductDiscoveryTask'

type ActiveTask = 'ai-weekly' | 'release-notes' | 'code-review' | 'product-discovery' | null

export default function TasksPage() {
  const [activeTask, setActiveTask] = useState<ActiveTask>(null)

  // When a task is opened, render its component
  if (activeTask === 'ai-weekly') {
    return <AIWeeklyTaskEnhanced onBack={() => setActiveTask(null)} />
  }
  if (activeTask === 'release-notes') {
    return <ReleaseNotesTask onBack={() => setActiveTask(null)} />
  }
  if (activeTask === 'code-review') {
    return <CodeReviewTask onBack={() => setActiveTask(null)} />
  }
  if (activeTask === 'product-discovery') {
    return <ProductDiscoveryTask onBack={() => setActiveTask(null)} />
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

      <TaskList onSelectTask={(id) => setActiveTask(id as ActiveTask)} />
    </div>
  )
}
