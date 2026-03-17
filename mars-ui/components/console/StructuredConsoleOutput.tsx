'use client'

import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import { Terminal, ArrowDown } from 'lucide-react'
import LogEntryRenderer from './LogEntryRenderer'
import PhaseIndicatorBar from './PhaseIndicatorBar'
import type { StructuredLogEntry, LogLevel } from '@/types/console'
import { rawToStructured } from '@/types/console'

interface StructuredConsoleOutputProps {
  /** Raw string output lines (legacy format) */
  output: string[]
  isRunning: boolean
  onClear?: () => void
  /** Pre-structured entries (if available from WebSocketContext) */
  structuredEntries?: StructuredLogEntry[]
  filterLevel?: 'all' | LogLevel
  searchQuery?: string
}

export default function StructuredConsoleOutput({
  output,
  isRunning,
  onClear,
  structuredEntries,
  filterLevel = 'all',
  searchQuery = '',
}: StructuredConsoleOutputProps) {
  const consoleRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)

  // Convert raw strings to structured entries (memoized)
  const entries: StructuredLogEntry[] = useMemo(() => {
    if (structuredEntries && structuredEntries.length > 0) {
      return structuredEntries
    }
    return output.map(rawToStructured)
  }, [output, structuredEntries])

  // Apply filters
  const filteredEntries = useMemo(() => {
    let filtered = entries

    if (filterLevel !== 'all') {
      filtered = filtered.filter(e => {
        if (filterLevel === 'error') return e.level === 'error'
        if (filterLevel === 'warning') return e.level === 'warning'
        if (filterLevel === 'success') return e.level === 'success'
        if (filterLevel === 'info') return e.level === 'info' || e.level === 'system' || e.level === 'debug'
        return true
      })
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      filtered = filtered.filter(e =>
        e.message.toLowerCase().includes(q) ||
        e.rawText.toLowerCase().includes(q) ||
        (e.agent && e.agent.toLowerCase().includes(q))
      )
    }

    return filtered
  }, [entries, filterLevel, searchQuery])

  // Track last known phase for phase indicators
  const lastPhase = useMemo(() => {
    for (let i = filteredEntries.length - 1; i >= 0; i--) {
      if (filteredEntries[i].phase) return filteredEntries[i].phase
    }
    return undefined
  }, [filteredEntries])

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight
    }
  }, [filteredEntries.length, autoScroll])

  // Scroll detection
  useEffect(() => {
    const el = consoleRef.current
    if (!el) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = el
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 50
      setShowScrollButton(!isNearBottom && filteredEntries.length > 3)
      if (isNearBottom) setAutoScroll(true)
      else setAutoScroll(false)
    }

    el.addEventListener('scroll', handleScroll)
    return () => el.removeEventListener('scroll', handleScroll)
  }, [filteredEntries.length])

  const scrollToBottom = useCallback(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight
      setAutoScroll(true)
    }
  }, [])

  return (
    <div
      className="h-full flex flex-col overflow-hidden relative"
      style={{ backgroundColor: 'var(--mars-color-console-bg)' }}
    >
      {/* Console Content */}
      <div
        ref={consoleRef}
        className="flex-1 py-2 overflow-y-auto console-scrollbar"
        role="log"
        aria-label="Console output"
        aria-live="polite"
        style={{ minHeight: 0 }}
      >
        {filteredEntries.length === 0 ? (
          <div className="flex items-center justify-center h-full" style={{ color: 'var(--mars-color-text-tertiary)' }}>
            <div className="text-center">
              <Terminal className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Console output will appear here</p>
              <p className="text-xs mt-1 opacity-60">Submit a task to get started</p>
            </div>
          </div>
        ) : (
          <div role="list">
            {filteredEntries.map((entry, index) => {
              // Insert phase indicator when phase changes
              const prevEntry = index > 0 ? filteredEntries[index - 1] : null
              const showPhase = entry.phase && (!prevEntry || prevEntry.phase !== entry.phase)

              return (
                <div key={entry.id}>
                  {showPhase && entry.phase && (
                    <PhaseIndicatorBar
                      phase={entry.phase}
                      active={isRunning && index === filteredEntries.length - 1}
                    />
                  )}
                  <LogEntryRenderer entry={entry} index={index} />
                </div>
              )
            })}

            {/* Running indicator */}
            {isRunning && (
              <div className="flex items-center gap-2 px-3 py-1" style={{ color: 'var(--mars-color-success)' }}>
                <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--mars-color-success)' }} />
                <span className="text-xs font-mono typing-animation">Processing...</span>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* Scroll-to-bottom FAB */}
      {showScrollButton && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 right-4 p-2 rounded-full shadow-mars-lg transition-all duration-mars-fast"
          style={{
            backgroundColor: 'var(--mars-color-primary)',
            color: '#fff',
            zIndex: 10,
          }}
          aria-label="Scroll to bottom"
        >
          <ArrowDown className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}
