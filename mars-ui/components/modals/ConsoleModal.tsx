'use client'

import { useState, useCallback } from 'react'
import { Modal } from '@/components/core'
import { StructuredConsoleOutput } from '@/components/console'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { Search, Download, Trash2, Copy } from 'lucide-react'
import type { LogLevel } from '@/types/console'

interface ConsoleModalProps {
  open: boolean
  onClose: () => void
}

type FilterLevel = 'all' | LogLevel

export default function ConsoleModal({ open, onClose }: ConsoleModalProps) {
  const { consoleOutput, isRunning, clearConsole } = useWebSocketContext()
  const [filterLevel, setFilterLevel] = useState<FilterLevel>('all')
  const [searchQuery, setSearchQuery] = useState('')

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
    <Modal
      open={open}
      onClose={onClose}
      title="Console"
      size="lg"
    >
      {/* Filter Bar */}
      <div
        className="flex items-center gap-2 p-3 border-b -mx-6 -mt-4 px-6"
        style={{ borderColor: 'var(--mars-color-border)' }}
        role="toolbar"
        aria-label="Console filters"
      >
        {/* Level Filter */}
        <div
          className="flex items-center gap-1 rounded-mars-md p-0.5"
          style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
          role="radiogroup"
          aria-label="Log level filter"
        >
          {(['all', 'info', 'warning', 'error'] as FilterLevel[]).map((level) => (
            <button
              key={level}
              onClick={() => setFilterLevel(level)}
              role="radio"
              aria-checked={filterLevel === level}
              className={`px-2 py-1 text-xs rounded-mars-sm capitalize transition-colors ${
                filterLevel === level
                  ? 'bg-[var(--mars-color-primary)] text-white'
                  : 'text-[var(--mars-color-text-secondary)] hover:text-[var(--mars-color-text)]'
              }`}
            >
              {level}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="flex-1 relative">
          <Search
            className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
            aria-hidden="true"
          />
          <input
            type="search"
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-mars-sm border outline-none"
            style={{
              backgroundColor: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
            aria-label="Search console logs"
          />
        </div>

        {/* Actions */}
        <button
          onClick={handleCopyAll}
          title="Copy all"
          className="p-1.5 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)] transition-colors"
          aria-label="Copy all logs to clipboard"
        >
          <Copy className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-secondary)' }} />
        </button>
        <button
          onClick={handleDownload}
          title="Download logs"
          className="p-1.5 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)] transition-colors"
          aria-label="Download logs as text file"
        >
          <Download className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-secondary)' }} />
        </button>
        <button
          onClick={clearConsole}
          title="Clear console"
          className="p-1.5 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)] transition-colors"
          aria-label="Clear console output"
        >
          <Trash2 className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-secondary)' }} />
        </button>
      </div>

      {/* Console Content — structured log viewer */}
      <div
        className="min-h-[400px] max-h-[500px] overflow-hidden rounded-mars-md -mx-6 mt-3"
        style={{ backgroundColor: 'var(--mars-color-console-bg)' }}
      >
        <StructuredConsoleOutput
          output={consoleOutput}
          isRunning={isRunning}
          onClear={clearConsole}
          filterLevel={filterLevel}
          searchQuery={searchQuery}
        />
      </div>

      {/* Status Bar */}
      <div
        className="flex items-center justify-between py-1.5 text-xs border-t -mx-6 -mb-4 px-6"
        style={{
          borderColor: 'var(--mars-color-border)',
          color: 'var(--mars-color-text-tertiary)',
        }}
        role="status"
      >
        <span>
          {consoleOutput.length} lines{' '}
          {filterLevel !== 'all' ? `(${filterLevel} filter)` : ''}
        </span>
        {isRunning && (
          <span className="flex items-center gap-1">
            <span
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ backgroundColor: 'var(--mars-color-success)' }}
            />
            Live
          </span>
        )}
      </div>
    </Modal>
  )
}
