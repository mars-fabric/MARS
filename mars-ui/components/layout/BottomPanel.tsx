'use client'

import { useState, useCallback, useRef } from 'react'
import { Terminal, GitBranch, ChevronDown, ChevronUp, Maximize2, Minimize2, Trash2, Copy, Download } from 'lucide-react'
import ConsoleOutput from '@/components/ConsoleOutput'
import { ApprovalChatPanel } from '@/components/ApprovalChatPanel'
import { WorkflowDashboard } from '@/components/workflow'

interface BottomPanelProps {
  consoleOutput: string[]
  isRunning: boolean
  onClearConsole: () => void
  pendingApproval: any | null
  onApprovalResolve: (resolution: string, feedback?: string, modifications?: string) => void
  // Workflow props
  workflowStatus: string | null
  dagData: any | null
  elapsedTime: string
  costSummary: any
  costTimeSeries: any[]
  filesUpdatedCounter: number
  branches: any[]
  currentBranchId?: string
  workflowHistory: any[]
  onPause: () => void
  onResume: () => void
  onCancel: () => void
  onPlayFromNode: (nodeId: string) => void
  onCreateBranch: (...args: any[]) => void
  onSelectBranch: (id: string) => void
  onViewBranch: (id: string) => void
  onCompareBranches: (a: string, b: string) => void
  onViewWorkflow: (w: any) => void
  onResumeWorkflow: (w: any) => void
  onBranchWorkflow: (w: any) => void
}

type PanelState = 'collapsed' | 'normal' | 'expanded'

export default function BottomPanel({
  consoleOutput,
  isRunning,
  onClearConsole,
  pendingApproval,
  onApprovalResolve,
  workflowStatus,
  dagData,
  elapsedTime,
  costSummary,
  costTimeSeries,
  filesUpdatedCounter,
  branches,
  currentBranchId,
  workflowHistory,
  onPause,
  onResume,
  onCancel,
  onPlayFromNode,
  onCreateBranch,
  onSelectBranch,
  onViewBranch,
  onCompareBranches,
  onViewWorkflow,
  onResumeWorkflow,
  onBranchWorkflow,
}: BottomPanelProps) {
  const [activeTab, setActiveTab] = useState<'console' | 'workflow'>('console')
  const [panelState, setPanelState] = useState<PanelState>('normal')
  const [height, setHeight] = useState(280)
  const resizeRef = useRef<{ startY: number; startHeight: number } | null>(null)
  const prevRunningRef = useRef(isRunning)

  // Auto-expand when task starts
  if (isRunning && !prevRunningRef.current && panelState === 'collapsed') {
    setPanelState('normal')
  }
  prevRunningRef.current = isRunning

  const panelHeight = panelState === 'collapsed' ? 34 : panelState === 'expanded' ? '60vh' : height

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    resizeRef.current = { startY: e.clientY, startHeight: height }
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizeRef.current) return
      const delta = resizeRef.current.startY - e.clientY
      const newHeight = Math.max(120, Math.min(window.innerHeight * 0.8, resizeRef.current.startHeight + delta))
      setHeight(newHeight)
      setPanelState('normal')
    }
    const handleMouseUp = () => {
      resizeRef.current = null
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [height])

  const togglePanel = () => {
    setPanelState(prev => prev === 'collapsed' ? 'normal' : 'collapsed')
  }

  const toggleExpand = () => {
    setPanelState(prev => prev === 'expanded' ? 'normal' : 'expanded')
  }

  const handleCopyAll = useCallback(() => {
    navigator.clipboard.writeText(consoleOutput.join('\n'))
  }, [consoleOutput])

  const handleDownload = useCallback(() => {
    const blob = new Blob([consoleOutput.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mars-console-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }, [consoleOutput])

  return (
    <div
      className="flex flex-col border-t flex-shrink-0"
      style={{
        height: typeof panelHeight === 'number' ? `${panelHeight}px` : panelHeight,
        borderColor: 'var(--mars-color-border)',
        backgroundColor: 'var(--mars-color-surface-raised)',
        transition: panelState === 'collapsed' || panelState === 'expanded'
          ? 'height 200ms ease' : 'none',
      }}
    >
      {/* Resize handle */}
      {panelState !== 'collapsed' && (
        <div
          className="h-[3px] cursor-row-resize flex-shrink-0 group"
          style={{ backgroundColor: 'var(--mars-color-border)' }}
          onMouseDown={handleMouseDown}
        >
          <div className="h-full w-full group-hover:bg-[var(--mars-color-primary)] transition-colors" />
        </div>
      )}

      {/* Header bar */}
      <div
        className="flex items-center justify-between px-3 flex-shrink-0"
        style={{
          height: '30px',
          borderBottom: panelState !== 'collapsed' ? '1px solid var(--mars-color-border)' : 'none',
        }}
      >
        {/* Tabs */}
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => { setActiveTab('console'); if (panelState === 'collapsed') setPanelState('normal') }}
            className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
              activeTab === 'console' && panelState !== 'collapsed'
                ? 'text-[var(--mars-color-primary)] bg-[var(--mars-color-primary-subtle)]'
                : 'text-[var(--mars-color-text-secondary)] hover:text-[var(--mars-color-text)]'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            Console
            {isRunning && (
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: 'var(--mars-color-success)' }} />
            )}
            {consoleOutput.length > 0 && (
              <span
                className="text-[10px] px-1 rounded-full"
                style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
              >
                {consoleOutput.length}
              </span>
            )}
          </button>

          <button
            onClick={() => { setActiveTab('workflow'); if (panelState === 'collapsed') setPanelState('normal') }}
            className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
              activeTab === 'workflow' && panelState !== 'collapsed'
                ? 'text-[var(--mars-color-primary)] bg-[var(--mars-color-primary-subtle)]'
                : 'text-[var(--mars-color-text-secondary)] hover:text-[var(--mars-color-text)]'
            }`}
          >
            <GitBranch className="w-3.5 h-3.5" />
            Workflow
            {dagData && dagData.nodes && dagData.nodes.length > 0 && (
              <span
                className="text-[10px] px-1 rounded-full"
                style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
              >
                {dagData.nodes.length}
              </span>
            )}
          </button>

          {/* Pending approval badge */}
          {pendingApproval && (
            <span
              className="text-[10px] px-1.5 py-0.5 rounded-full animate-pulse ml-1"
              style={{ backgroundColor: 'var(--mars-color-warning)', color: '#000' }}
            >
              Approval needed
            </span>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-0.5">
          {activeTab === 'console' && panelState !== 'collapsed' && (
            <>
              <button
                onClick={handleCopyAll}
                className="p-1 rounded-sm transition-colors"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--mars-color-bg-hover)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent' }}
                title="Copy all"
              >
                <Copy className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleDownload}
                className="p-1 rounded-sm transition-colors"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--mars-color-bg-hover)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent' }}
                title="Download logs"
              >
                <Download className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={onClearConsole}
                className="p-1 rounded-sm transition-colors"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--mars-color-bg-hover)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent' }}
                title="Clear console"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </>
          )}

          <div className="w-px h-4 mx-1" style={{ backgroundColor: 'var(--mars-color-border)' }} />

          <button
            onClick={toggleExpand}
            className="p-1 rounded-sm transition-colors"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--mars-color-bg-hover)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent' }}
            title={panelState === 'expanded' ? 'Restore' : 'Maximize'}
          >
            {panelState === 'expanded'
              ? <Minimize2 className="w-3.5 h-3.5" />
              : <Maximize2 className="w-3.5 h-3.5" />
            }
          </button>
          <button
            onClick={togglePanel}
            className="p-1 rounded-sm transition-colors"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--mars-color-bg-hover)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent' }}
            title={panelState === 'collapsed' ? 'Expand panel' : 'Collapse panel'}
          >
            {panelState === 'collapsed'
              ? <ChevronUp className="w-3.5 h-3.5" />
              : <ChevronDown className="w-3.5 h-3.5" />
            }
          </button>
        </div>
      </div>

      {/* Content */}
      {panelState !== 'collapsed' && (
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
          {activeTab === 'console' && (
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
              <div className="flex-1 min-h-0 overflow-auto">
                <ConsoleOutput
                  output={consoleOutput}
                  isRunning={isRunning}
                  onClear={onClearConsole}
                />
              </div>
              {/* Approval panel at bottom when pending */}
              {pendingApproval && (
                <div className="flex-shrink-0">
                  <ApprovalChatPanel
                    approval={pendingApproval}
                    onResolve={onApprovalResolve}
                  />
                </div>
              )}
            </div>
          )}
          {activeTab === 'workflow' && (
            <div className="flex-1 min-h-0 overflow-auto">
              <WorkflowDashboard
                status={workflowStatus || (isRunning ? 'executing' : 'draft')}
                dagData={dagData}
                elapsedTime={elapsedTime}
                branches={branches}
                currentBranchId={currentBranchId}
                workflowHistory={workflowHistory}
                costSummary={costSummary}
                costTimeSeries={costTimeSeries}
                filesUpdatedCounter={filesUpdatedCounter}
                onPause={onPause}
                onResume={onResume}
                onCancel={onCancel}
                onPlayFromNode={onPlayFromNode}
                onCreateBranch={onCreateBranch}
                onSelectBranch={onSelectBranch}
                onViewBranch={onViewBranch}
                onCompareBranches={onCompareBranches}
                onViewWorkflow={onViewWorkflow}
                onResumeWorkflow={onResumeWorkflow}
                onBranchWorkflow={onBranchWorkflow}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
