// components/tables/SessionTable.tsx

'use client';

import { Eye, Trash2 } from 'lucide-react';
import { DataTable } from './DataTable';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Column, SessionRow, PaginationInfo } from '@/types/tables';

interface SessionTableProps {
  sessions: SessionRow[];
  pagination?: PaginationInfo;
  isLoading?: boolean;
  onViewSession: (session: SessionRow) => void;
  onDeleteSession?: (session: SessionRow) => void;
}

export function SessionTable({
  sessions,
  pagination,
  isLoading,
  onViewSession,
  onDeleteSession,
}: SessionTableProps) {
  const columns: Column<SessionRow>[] = [
    {
      id: 'name',
      header: 'Session Name',
      accessor: 'name',
      sortable: true,
    },
    {
      id: 'status',
      header: 'Status',
      accessor: (row) => <StatusBadge status={row.status} size="sm" />,
      sortable: true,
    },
    {
      id: 'workflow_count',
      header: 'Workflows',
      accessor: 'workflow_count',
      sortable: true,
      align: 'center',
    },
    {
      id: 'total_cost',
      header: 'Total Cost',
      accessor: (row) => `$${row.total_cost.toFixed(4)}`,
      sortable: true,
      align: 'right',
    },
    {
      id: 'created_at',
      header: 'Created',
      accessor: (row) => new Date(row.created_at).toLocaleDateString(),
      sortable: true,
    },
    {
      id: 'last_active_at',
      header: 'Last Active',
      accessor: (row) =>
        row.last_active_at
          ? new Date(row.last_active_at).toLocaleString()
          : 'Never',
      sortable: true,
    },
  ];

  const actions = (row: SessionRow) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        onClick={(e) => {
          e.stopPropagation();
          onViewSession(row);
        }}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="View session"
      >
        <Eye className="w-4 h-4 text-gray-400" />
      </button>
      {onDeleteSession && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDeleteSession(row);
          }}
          className="p-2 hover:bg-red-500/20 rounded transition-colors"
          title="Delete session"
        >
          <Trash2 className="w-4 h-4 text-red-400" />
        </button>
      )}
    </div>
  );

  return (
    <DataTable
      columns={columns}
      data={sessions}
      keyExtractor={(row) => row.id}
      pagination={pagination}
      isLoading={isLoading}
      onRowClick={onViewSession}
      emptyMessage="No sessions found"
      searchPlaceholder="Search sessions..."
      actions={actions}
    />
  );
}
