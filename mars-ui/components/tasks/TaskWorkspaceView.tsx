'use client'

import { useState } from 'react'
import { Network, Code, ChevronDown, ChevronUp } from 'lucide-react'
import { DAGWorkspace } from '@/components/dag'
import ConsoleOutput from '@/components/ConsoleOutput'

interface TaskWorkspaceViewProps {
  dagData: any
  currentRunId?: string
  consoleOutput: string[]
  costSummary?: any
  costTimeSeries?: any[]
  isCollapsible?: boolean
  defaultCollapsed?: boolean
  showProgress?: boolean
  isRunning?: boolean
}

export default function TaskWorkspaceView({
  dagData,
  currentRunId,
  consoleOutput,
  costSummary,
  costTimeSeries,
  isCollapsible = true,
  defaultCollapsed = false,
  showProgress = true,
  isRunning = false
}: TaskWorkspaceViewProps) {
  const [workspaceView, setWorkspaceView] = useState<'dag' | 'console'>('dag')
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed)

  const completedSteps = dagData?.nodes.filter((n: any) => n.status === 'completed').length || 0
  const totalSteps = dagData?.nodes.length || 0
  const progressPercent = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0

  return (
    <div className="space-y-4">
      {/* Task Progress Bar */}
      {showProgress && dagData && (
        <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-white font-semibold">Task Progress</h3>
            <span className="text-sm text-gray-400">
              {completedSteps} / {totalSteps} steps
            </span>
          </div>
          <div className="w-full bg-black/50 rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {dagData.nodes.map((node: any) => (
              <div
                key={node.id}
                className={`px-3 py-1 rounded-full text-xs font-medium ${node.status === 'completed'
                    ? 'bg-green-500/20 text-green-400'
                    : node.status === 'executing'
                      ? 'bg-blue-500/20 text-blue-400 animate-pulse'
                      : node.status === 'failed'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-gray-500/20 text-gray-400'
                  }`}
              >
                {node.name}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Workspace View */}
      <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg overflow-hidden h-full flex flex-col">
        {/* Header with Tabs and Collapse Button */}
        <div className="border-b border-white/10 p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-semibold">Workspace</h3>
            <div className="flex items-center space-x-2">
              {/* View Tabs */}
              <div className="flex items-center space-x-2 bg-black/30 rounded-lg p-1">
                <button
                  onClick={() => setWorkspaceView('dag')}
                  className={`flex items-center space-x-2 px-3 py-1.5 rounded-md transition-all text-sm ${workspaceView === 'dag'
                      ? 'bg-purple-500 text-white'
                      : 'text-gray-400 hover:text-white'
                    }`}
                >
                  <Network className="w-4 h-4" />
                  <span>DAG View</span>
                </button>
                <button
                  onClick={() => setWorkspaceView('console')}
                  className={`flex items-center space-x-2 px-3 py-1.5 rounded-md transition-all text-sm ${workspaceView === 'console'
                      ? 'bg-blue-500 text-white'
                      : 'text-gray-400 hover:text-white'
                    }`}
                >
                  <Code className="w-4 h-4" />
                  <span>Console</span>
                </button>
              </div>

              {/* Collapse Button */}
              {isCollapsible && (
                <button
                  onClick={() => setIsCollapsed(!isCollapsed)}
                  className="p-2 text-gray-400 hover:text-white transition-colors"
                  title={isCollapsed ? 'Expand' : 'Collapse'}
                >
                  {isCollapsed ? (
                    <ChevronDown className="w-5 h-5" />
                  ) : (
                    <ChevronUp className="w-5 h-5" />
                  )}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Workspace Content */}
        {!isCollapsed && (
          <div className="flex-1 min-h-0">
            {workspaceView === 'dag' ? (
              dagData ? (
                <DAGWorkspace
                  dagData={dagData}
                  runId={currentRunId}
                  costSummary={costSummary}
                  costTimeSeries={costTimeSeries}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500">
                  <div className="text-center">
                    <Network className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>Workflow DAG will appear here</p>
                  </div>
                </div>
              )
            ) : (
              <ConsoleOutput output={consoleOutput} isRunning={isRunning} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
