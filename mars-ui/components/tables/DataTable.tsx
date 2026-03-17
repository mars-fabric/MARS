// components/tables/DataTable.tsx

'use client';

import { useState } from 'react';
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  Search,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import { Column, TableState, PaginationInfo } from '@/types/tables';

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  pagination?: PaginationInfo;
  isLoading?: boolean;
  onStateChange?: (state: TableState) => void;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  searchPlaceholder?: string;
  actions?: (row: T) => React.ReactNode;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  pagination,
  isLoading = false,
  onStateChange,
  onRowClick,
  emptyMessage = 'No data available',
  searchPlaceholder = 'Search...',
  actions,
}: DataTableProps<T>) {
  const [tableState, setTableState] = useState<TableState>({
    page: 1,
    pageSize: 10,
    sortColumn: null,
    sortDirection: 'asc',
    searchQuery: '',
    filters: {},
  });

  const updateState = (updates: Partial<TableState>) => {
    const newState = { ...tableState, ...updates };
    setTableState(newState);
    onStateChange?.(newState);
  };

  const handleSort = (columnId: string) => {
    if (tableState.sortColumn === columnId) {
      updateState({
        sortDirection: tableState.sortDirection === 'asc' ? 'desc' : 'asc',
      });
    } else {
      updateState({
        sortColumn: columnId,
        sortDirection: 'asc',
      });
    }
  };

  const getSortIcon = (columnId: string) => {
    if (tableState.sortColumn !== columnId) {
      return <ChevronsUpDown className="w-4 h-4 text-gray-500" />;
    }
    return tableState.sortDirection === 'asc' ? (
      <ChevronUp className="w-4 h-4 text-blue-400" />
    ) : (
      <ChevronDown className="w-4 h-4 text-blue-400" />
    );
  };

  const getCellValue = (row: T, column: Column<T>) => {
    if (typeof column.accessor === 'function') {
      return column.accessor(row);
    }
    return row[column.accessor] as React.ReactNode;
  };

  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-700 overflow-hidden">
      {/* Search Bar */}
      <div className="px-4 py-3 border-b border-gray-700">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={tableState.searchQuery}
            onChange={(e) => updateState({ searchQuery: e.target.value, page: 1 })}
            placeholder={searchPlaceholder}
            className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-800/50">
              {columns.map((column) => (
                <th
                  key={column.id}
                  className={`px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider ${
                    column.width || ''
                  }`}
                  style={{ textAlign: column.align || 'left' }}
                >
                  {column.sortable !== false ? (
                    <button
                      onClick={() => handleSort(column.id)}
                      className="flex items-center space-x-1 hover:text-white transition-colors"
                    >
                      <span>{column.header}</span>
                      {getSortIcon(column.id)}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              ))}
              {actions && (
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {isLoading ? (
              <tr>
                <td
                  colSpan={columns.length + (actions ? 1 : 0)}
                  className="px-4 py-12 text-center"
                >
                  <Loader2 className="w-8 h-8 text-blue-400 animate-spin mx-auto" />
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (actions ? 1 : 0)}
                  className="px-4 py-12 text-center text-gray-400"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row) => (
                <tr
                  key={keyExtractor(row)}
                  onClick={() => onRowClick?.(row)}
                  className={`hover:bg-gray-800/50 transition-colors ${
                    onRowClick ? 'cursor-pointer' : ''
                  }`}
                >
                  {columns.map((column) => (
                    <td
                      key={column.id}
                      className="px-4 py-3 text-sm text-gray-300"
                      style={{ textAlign: column.align || 'left' }}
                    >
                      {getCellValue(row, column)}
                    </td>
                  ))}
                  {actions && (
                    <td className="px-4 py-3 text-right">
                      {actions(row)}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pagination && (
        <div className="px-4 py-3 border-t border-gray-700 flex items-center justify-between">
          <div className="text-sm text-gray-400">
            Showing {((pagination.page - 1) * pagination.pageSize) + 1} to{' '}
            {Math.min(pagination.page * pagination.pageSize, pagination.totalItems)} of{' '}
            {pagination.totalItems} results
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => updateState({ page: tableState.page - 1 })}
              disabled={pagination.page <= 1}
              className="p-2 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
            >
              <ChevronLeft className="w-4 h-4 text-gray-400" />
            </button>
            <span className="text-sm text-gray-300">
              Page {pagination.page} of {pagination.totalPages}
            </span>
            <button
              onClick={() => updateState({ page: tableState.page + 1 })}
              disabled={pagination.page >= pagination.totalPages}
              className="p-2 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
            >
              <ChevronRight className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
