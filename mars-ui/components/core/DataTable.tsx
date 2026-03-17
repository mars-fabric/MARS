'use client'

import React from 'react'
import Skeleton from './Skeleton'
import EmptyState from './EmptyState'
import { Inbox } from 'lucide-react'

export interface Column<T> {
  id: string
  header: string
  accessor: (row: T) => React.ReactNode
  sortable?: boolean
  width?: string
}

export interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  loading?: boolean
  emptyMessage?: string
  onRowClick?: (row: T) => void
  selectedId?: string
  getRowId?: (row: T) => string
  stickyHeader?: boolean
}

export default function DataTable<T>({
  columns,
  data,
  loading = false,
  emptyMessage = 'No data available',
  onRowClick,
  selectedId,
  getRowId,
  stickyHeader = false,
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className="w-full">
        <div
          className="grid gap-0 border rounded-mars-md overflow-hidden"
          style={{ borderColor: 'var(--mars-color-border)' }}
        >
          {/* Header skeleton */}
          <div
            className="grid gap-4 px-4 py-3"
            style={{
              gridTemplateColumns: columns.map(c => c.width || '1fr').join(' '),
              backgroundColor: 'var(--mars-color-surface-overlay)',
            }}
          >
            {columns.map(col => (
              <Skeleton key={col.id} variant="text" height={14} width="60%" />
            ))}
          </div>
          {/* Row skeletons */}
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="grid gap-4 px-4 py-3 border-t"
              style={{
                gridTemplateColumns: columns.map(c => c.width || '1fr').join(' '),
                borderColor: 'var(--mars-color-border)',
              }}
            >
              {columns.map(col => (
                <Skeleton key={col.id} variant="text" height={14} />
              ))}
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <EmptyState
        icon={<Inbox className="w-6 h-6" />}
        title={emptyMessage}
      />
    )
  }

  return (
    <div
      className="w-full border rounded-mars-md overflow-hidden"
      style={{ borderColor: 'var(--mars-color-border)' }}
    >
      <table className="w-full border-collapse">
        <thead>
          <tr
            style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
            className={stickyHeader ? 'sticky top-0' : ''}
          >
            {columns.map(col => (
              <th
                key={col.id}
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider"
                style={{
                  color: 'var(--mars-color-text-tertiary)',
                  width: col.width,
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => {
            const rowId = getRowId ? getRowId(row) : String(index)
            const isSelected = selectedId === rowId

            return (
              <tr
                key={rowId}
                onClick={() => onRowClick?.(row)}
                className={`
                  border-t transition-colors duration-mars-fast
                  ${onRowClick ? 'cursor-pointer' : ''}
                `}
                style={{
                  borderColor: 'var(--mars-color-border)',
                  backgroundColor: isSelected
                    ? 'var(--mars-color-primary-subtle)'
                    : undefined,
                }}
                onMouseEnter={(e) => {
                  if (!isSelected && onRowClick) {
                    e.currentTarget.style.backgroundColor = 'var(--mars-color-bg-hover)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.backgroundColor = ''
                  }
                }}
              >
                {columns.map(col => (
                  <td
                    key={col.id}
                    className="px-4 py-3 text-sm"
                    style={{ color: 'var(--mars-color-text)' }}
                  >
                    {col.accessor(row)}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
