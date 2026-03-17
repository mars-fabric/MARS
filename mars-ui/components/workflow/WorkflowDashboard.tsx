// components/workflow/WorkflowDashboard.tsx

'use client';

import { useState, useMemo } from 'react';
import { WorkflowStateBar } from './WorkflowStateBar';
import { DAGWorkspace } from '@/components/dag';
import { CreateBranchDialog } from '@/components/branching';
import { Branch, ResumableNode } from '@/types/branching';
import { WorkflowRow } from '@/types/tables';
import { CostSummary, CostTimeSeries } from '@/types/cost';

interface WorkflowDashboardProps {
  status: string;
  dagData: { run_id?: string; nodes: any[]; edges: any[] } | null;
  totalCost?: number;
  elapsedTime?: string;
  branches?: Branch[];
  currentBranchId?: string;
  workflowHistory?: WorkflowRow[];
  costSummary?: CostSummary;
  costTimeSeries?: CostTimeSeries[];
  filesUpdatedCounter?: number;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  onPlayFromNode?: (nodeId: string) => void;
  onCreateBranch?: (nodeId: string, name: string, hypothesis?: string, newInstructions?: string, executeImmediately?: boolean) => void;
  onSelectBranch?: (branchId: string) => void;
  onViewBranch?: (branchId: string) => void;
  onCompareBranches?: (branchIdA: string, branchIdB: string) => void;
  onViewWorkflow?: (workflow: WorkflowRow) => void;
  onResumeWorkflow?: (workflow: WorkflowRow) => void;
  onBranchWorkflow?: (workflow: WorkflowRow) => void;
}

export function WorkflowDashboard({
  status,
  dagData,
  totalCost = 0,
  elapsedTime = '0:00',
  branches = [],
  currentBranchId,
  workflowHistory = [],
  costSummary,
  costTimeSeries = [],
  filesUpdatedCounter,
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
}: WorkflowDashboardProps) {
  const [showCreateBranchDialog, setShowCreateBranchDialog] = useState(false);

  // Calculate progress from DAG data
  const { progress, totalSteps, completedSteps, resumableNodes } = useMemo(() => {
    if (!dagData || dagData.nodes.length === 0) {
      return { progress: 0, totalSteps: 0, completedSteps: 0, resumableNodes: [] };
    }

    const total = dagData.nodes.length;
    const completed = dagData.nodes.filter(
      (n) => n.status === 'completed'
    ).length;
    const failed = dagData.nodes.filter((n) => n.status === 'failed').length;
    const prog = total > 0 ? ((completed + failed) / total) * 100 : 0;

    // Extract resumable nodes for branch creation
    const resumable: ResumableNode[] = dagData.nodes
      .filter((n) => n.status === 'completed' || n.status === 'failed')
      .map((n, index) => ({
        node_id: n.id,
        order_index: n.step_number || index,
        node_type: n.type || 'agent',
        agent: n.agent,
        status: n.status,
        has_checkpoint: true,  // Assume checkpoint exists for completed nodes
        can_resume: true,
      }));

    return {
      progress: prog,
      totalSteps: total,
      completedSteps: completed,
      resumableNodes: resumable,
    };
  }, [dagData]);

  const handleCreateBranch = (
    nodeId: string,
    name: string,
    hypothesis?: string,
    newInstructions?: string,
    executeImmediately?: boolean
  ) => {
    onCreateBranch?.(nodeId, name, hypothesis, newInstructions, executeImmediately);
    setShowCreateBranchDialog(false);
  };

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* State Bar */}
      <WorkflowStateBar
        status={status}
        progress={progress}
        totalSteps={totalSteps}
        completedSteps={completedSteps}
        totalCost={totalCost}
        elapsedTime={elapsedTime}
        onPause={onPause}
        onResume={onResume}
        onCancel={onCancel}
      />

      {/* Main Content - DAGWorkspace with all tabs inside */}
      <div className="flex-grow min-h-0 overflow-hidden">
        <div className="h-full bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
          <DAGWorkspace
            dagData={dagData}
            onPlayFromNode={onPlayFromNode}
            runId={dagData?.run_id}
            costSummary={costSummary}
            costTimeSeries={costTimeSeries}
            filesUpdatedCounter={filesUpdatedCounter}
          />
        </div>
      </div>

      {/* Create Branch Dialog */}
      {showCreateBranchDialog && (
        <CreateBranchDialog
          resumableNodes={resumableNodes}
          onCreateBranch={handleCreateBranch}
          onClose={() => setShowCreateBranchDialog(false)}
        />
      )}
    </div>
  );
}
