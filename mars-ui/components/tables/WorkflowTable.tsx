// components/tables/WorkflowTable.tsx

'use client';

import { Eye, Play, Trash2, GitBranch } from 'lucide-react';
import { DataTable } from './DataTable';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Column, WorkflowRow, PaginationInfo } from '@/types/tables';

interface WorkflowTableProps {
  workflows: WorkflowRow[];
  pagination?: PaginationInfo;
  isLoading?: boolean;
  onViewWorkflow: (workflow: WorkflowRow) => void;
  onResumeWorkflow?: (workflow: WorkflowRow) => void;
  onBranchWorkflow?: (workflow: WorkflowRow) => void;
  onDeleteWorkflow?: (workflow: WorkflowRow) => void;
}

export function WorkflowTable({
  workflows,
  pagination,
  isLoading,
  onViewWorkflow,
  onResumeWorkflow,
  onBranchWorkflow,
  onDeleteWorkflow,
}: WorkflowTableProps) {
  const columns: Column<WorkflowRow>[] = [
    {
      id: 'task_description',
      header: 'Task',
      accessor: (row) => (
        <div className="max-w-xs truncate" title={row.task_description}>
          {row.task_description}
        </div>
      ),
      sortable: true,
    },
    {
      id: 'status',
      header: 'Status',
      accessor: (row) => <StatusBadge status={row.status} size="sm" />,
      sortable: true,
    },
    {
      id: 'agent',
      header: 'Agent',
      accessor: (row) => (
        <span className="px-2 py-0.5 bg-gray-700 rounded text-xs">
          {row.agent}
        </span>
      ),
      sortable: true,
    },
    {
      id: 'model',
      header: 'Model',
      accessor: (row) => (
        <span className="text-xs text-gray-400">{row.model}</span>
      ),
      sortable: true,
    },
    {
      id: 'step_count',
      header: 'Steps',
      accessor: 'step_count',
      sortable: true,
      align: 'center',
    },
    {
      id: 'total_cost',
      header: 'Cost',
      accessor: (row) => `$${row.total_cost.toFixed(4)}`,
      sortable: true,
      align: 'right',
    },
    {
      id: 'started_at',
      header: 'Started',
      accessor: (row) =>
        row.started_at
          ? new Date(row.started_at).toLocaleString()
          : '-',
      sortable: true,
    },
  ];

  const actions = (row: WorkflowRow) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        onClick={(e) => {
          e.stopPropagation();
          onViewWorkflow(row);
        }}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="View workflow"
      >
        <Eye className="w-4 h-4 text-gray-400" />
      </button>
      {onResumeWorkflow && ['paused', 'failed'].includes(row.status) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onResumeWorkflow(row);
          }}
          className="p-2 hover:bg-green-500/20 rounded transition-colors"
          title="Resume workflow"
        >
          <Play className="w-4 h-4 text-green-400" />
        </button>
      )}
      {onBranchWorkflow && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onBranchWorkflow(row);
          }}
          className="p-2 hover:bg-purple-500/20 rounded transition-colors"
          title="Create branch"
        >
          <GitBranch className="w-4 h-4 text-purple-400" />
        </button>
      )}
      {onDeleteWorkflow && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDeleteWorkflow(row);
          }}
          className="p-2 hover:bg-red-500/20 rounded transition-colors"
          title="Delete workflow"
        >
          <Trash2 className="w-4 h-4 text-red-400" />
        </button>
      )}
    </div>
  );

  return (
    <DataTable
      columns={columns}
      data={workflows}
      keyExtractor={(row) => row.id}
      pagination={pagination}
      isLoading={isLoading}
      onRowClick={onViewWorkflow}
      emptyMessage="No workflows found"
      searchPlaceholder="Search workflows..."
      actions={actions}
    />
  );
}
