'use client'

import { Modal } from '@/components/core'
import { WorkflowDashboard } from '@/components/workflow'
import { useWebSocketContext } from '@/contexts/WebSocketContext'

interface WorkflowModalProps {
  open: boolean
  onClose: () => void
  elapsedTime?: string
  onPause?: () => void
  onResume?: () => void
  onCancel?: () => void
  onPlayFromNode?: (nodeId: string) => void
  branches?: any[]
  currentBranchId?: string
  workflowHistory?: any[]
  onCreateBranch?: (...args: any[]) => void
  onSelectBranch?: (id: string) => void
  onViewBranch?: (id: string) => void
  onCompareBranches?: (a: string, b: string) => void
  onViewWorkflow?: (w: any) => void
  onResumeWorkflow?: (w: any) => void
  onBranchWorkflow?: (w: any) => void
}

export default function WorkflowModal({
  open,
  onClose,
  elapsedTime = '0:00',
  onPause,
  onResume,
  onCancel,
  onPlayFromNode,
  branches = [],
  currentBranchId,
  workflowHistory = [],
  onCreateBranch,
  onSelectBranch,
  onViewBranch,
  onCompareBranches,
  onViewWorkflow,
  onResumeWorkflow,
  onBranchWorkflow,
}: WorkflowModalProps) {
  const {
    workflowStatus,
    isRunning,
    dagData,
    costSummary,
    costTimeSeries,
    filesUpdatedCounter,
    sendMessage,
    currentRunId,
    connected,
    addConsoleOutput,
    setWorkflowStatus,
  } = useWebSocketContext()

  // If no handlers passed, use direct WebSocket message sends
  const handlePause = onPause || (() => {
    if (connected && currentRunId) {
      sendMessage({ type: 'pause', run_id: currentRunId })
      setWorkflowStatus('paused')
      addConsoleOutput('Pause request sent to workflow')
    }
  })

  const handleResume = onResume || (() => {
    if (connected && currentRunId) {
      sendMessage({ type: 'resume', run_id: currentRunId })
      setWorkflowStatus('executing')
      addConsoleOutput('Resume request sent to workflow')
    }
  })

  const handleCancel = onCancel || (() => {
    if (connected && currentRunId) {
      sendMessage({ type: 'cancel', run_id: currentRunId })
      addConsoleOutput('Cancel request sent to workflow')
    }
  })

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Workflow"
      size="xl"
    >
      <div className="h-[600px] overflow-hidden -mx-6 -my-4">
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
          onPause={handlePause}
          onResume={handleResume}
          onCancel={handleCancel}
          onPlayFromNode={onPlayFromNode || (() => {})}
          onCreateBranch={onCreateBranch || (() => {})}
          onSelectBranch={onSelectBranch || (() => {})}
          onViewBranch={onViewBranch || (() => {})}
          onCompareBranches={onCompareBranches || (() => {})}
          onViewWorkflow={onViewWorkflow || (() => {})}
          onResumeWorkflow={onResumeWorkflow || (() => {})}
          onBranchWorkflow={onBranchWorkflow || (() => {})}
        />
      </div>
    </Modal>
  )
}
