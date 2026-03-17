// components/tables/StepTable.tsx

'use client';

import { Eye, RotateCw, Play } from 'lucide-react';
import { DataTable } from './DataTable';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Column, StepRow, PaginationInfo } from '@/types/tables';

interface StepTableProps {
  steps: StepRow[];
  pagination?: PaginationInfo;
  isLoading?: boolean;
  onViewStep: (step: StepRow) => void;
  onRetryStep?: (step: StepRow) => void;
  onPlayFromStep?: (step: StepRow) => void;
}

export function StepTable({
  steps,
  pagination,
  isLoading,
  onViewStep,
  onRetryStep,
  onPlayFromStep,
}: StepTableProps) {
  const columns: Column<StepRow>[] = [
    {
      id: 'step_number',
      header: '#',
      accessor: 'step_number',
      sortable: true,
      width: 'w-16',
      align: 'center',
    },
    {
      id: 'description',
      header: 'Description',
      accessor: (row) => (
        <div className="max-w-sm truncate" title={row.description}>
          {row.description}
        </div>
      ),
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
      id: 'status',
      header: 'Status',
      accessor: (row) => <StatusBadge status={row.status} size="sm" />,
      sortable: true,
    },
    {
      id: 'cost',
      header: 'Cost',
      accessor: (row) => `$${row.cost.toFixed(4)}`,
      sortable: true,
      align: 'right',
    },
    {
      id: 'retry_count',
      header: 'Retries',
      accessor: (row) =>
        row.retry_count > 0 ? (
          <span className="text-orange-400">{row.retry_count}</span>
        ) : (
          <span className="text-gray-500">0</span>
        ),
      sortable: true,
      align: 'center',
    },
    {
      id: 'started_at',
      header: 'Started',
      accessor: (row) =>
        row.started_at
          ? new Date(row.started_at).toLocaleTimeString()
          : '-',
      sortable: true,
    },
  ];

  const actions = (row: StepRow) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        onClick={(e) => {
          e.stopPropagation();
          onViewStep(row);
        }}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="View step details"
      >
        <Eye className="w-4 h-4 text-gray-400" />
      </button>
      {onRetryStep && row.status === 'failed' && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRetryStep(row);
          }}
          className="p-2 hover:bg-orange-500/20 rounded transition-colors"
          title="Retry step"
        >
          <RotateCw className="w-4 h-4 text-orange-400" />
        </button>
      )}
      {onPlayFromStep && ['completed', 'failed'].includes(row.status) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPlayFromStep(row);
          }}
          className="p-2 hover:bg-blue-500/20 rounded transition-colors"
          title="Play from this step"
        >
          <Play className="w-4 h-4 text-blue-400" />
        </button>
      )}
    </div>
  );

  return (
    <DataTable
      columns={columns}
      data={steps}
      keyExtractor={(row) => row.id}
      pagination={pagination}
      isLoading={isLoading}
      onRowClick={onViewStep}
      emptyMessage="No steps found"
      searchPlaceholder="Search steps..."
      actions={actions}
    />
  );
}
