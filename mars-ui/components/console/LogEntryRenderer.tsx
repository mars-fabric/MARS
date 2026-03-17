'use client'

import React, { useState } from 'react'
import {
  XCircle,
  AlertTriangle,
  CheckCircle,
  Info,
  Wrench,
  Code,
  Target,
  BarChart3,
  FolderOpen,
  Plug,
  StopCircle,
  Pause,
  Play,
  GitBranch,
  MessageSquare,
  Brain,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import type { StructuredLogEntry, LogLevel, LogSource } from '@/types/console'

interface LogEntryRendererProps {
  entry: StructuredLogEntry
  index: number
  showTimestamp?: boolean
}

function getIcon(entry: StructuredLogEntry): React.ReactNode {
  const iconClass = 'w-3.5 h-3.5'

  // By source first (most specific)
  switch (entry.source) {
    case 'agent_thinking':
      return <Brain className={iconClass} style={{ color: '#A78BFA' }} />
    case 'agent_tool_call':
    case 'tool_call':
      return <Wrench className={iconClass} style={{ color: '#60A5FA' }} />
    case 'code_execution':
      return <Code className={iconClass} style={{ color: '#34D399' }} />
    case 'dag':
      return <BarChart3 className={iconClass} style={{ color: '#60A5FA' }} />
    case 'files':
      return <FolderOpen className={iconClass} style={{ color: '#60A5FA' }} />
    case 'connection':
      return <Plug className={iconClass} style={{ color: '#60A5FA' }} />
    case 'approval':
      return <Pause className={iconClass} style={{ color: 'var(--mars-color-warning)' }} />
    case 'result':
      return <Target className={iconClass} style={{ color: '#A78BFA' }} />
    case 'cost':
      return <BarChart3 className={iconClass} style={{ color: '#FBBF24' }} />
    default:
      break
  }

  // By level
  switch (entry.level) {
    case 'error':
      return <XCircle className={iconClass} style={{ color: 'var(--mars-color-danger)' }} />
    case 'warning':
      return <AlertTriangle className={iconClass} style={{ color: 'var(--mars-color-warning)' }} />
    case 'success':
      return <CheckCircle className={iconClass} style={{ color: 'var(--mars-color-success)' }} />
    case 'system':
      return <Info className={iconClass} style={{ color: 'var(--mars-color-info)' }} />
    default:
      break
  }

  // Agent messages
  if (entry.agent) {
    return <MessageSquare className={iconClass} style={{ color: '#60A5FA' }} />
  }

  // Check text content for specific patterns
  const lower = entry.message.toLowerCase()
  if (lower.includes('workflow started')) return <Play className={iconClass} style={{ color: 'var(--mars-color-success)' }} />
  if (lower.includes('workflow paused')) return <Pause className={iconClass} style={{ color: 'var(--mars-color-warning)' }} />
  if (lower.includes('workflow resumed')) return <Play className={iconClass} style={{ color: 'var(--mars-color-success)' }} />
  if (lower.includes('stopped by user')) return <StopCircle className={iconClass} style={{ color: 'var(--mars-color-danger)' }} />
  if (lower.includes('branch')) return <GitBranch className={iconClass} style={{ color: '#A78BFA' }} />

  return null
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

export default function LogEntryRenderer({ entry, index, showTimestamp = true }: LogEntryRendererProps) {
  const [codeExpanded, setCodeExpanded] = useState(false)
  const icon = getIcon(entry)

  return (
    <div
      className="mars-log-entry"
      data-level={entry.level}
      role="listitem"
    >
      {/* Line number */}
      <span className="mars-log-timestamp">
        {String(index + 1).padStart(3, '0')}
      </span>

      {/* Timestamp */}
      {showTimestamp && entry.timestamp && (
        <span className="mars-log-timestamp">
          {formatTimestamp(entry.timestamp)}
        </span>
      )}

      {/* Icon */}
      {icon && (
        <span className="mars-log-icon" aria-hidden="true">
          {icon}
        </span>
      )}

      {/* Agent badge */}
      {entry.agent && (
        <span className="mars-log-agent-badge">
          {entry.agent}
        </span>
      )}

      {/* Message + optional code block */}
      <div className="mars-log-message">
        <span>{entry.message}</span>

        {/* Collapsible code block */}
        {entry.code && (
          <div>
            <button
              onClick={() => setCodeExpanded(!codeExpanded)}
              className="inline-flex items-center gap-1 mt-1 text-[var(--mars-color-text-tertiary)] hover:text-[var(--mars-color-text-secondary)] transition-colors"
              aria-expanded={codeExpanded}
            >
              {codeExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              <span className="text-[10px] uppercase tracking-wider">
                {entry.codeLanguage || 'code'} {codeExpanded ? '(collapse)' : '(expand)'}
              </span>
            </button>
            {codeExpanded && (
              <div className="mars-log-code-block">
                <pre><code>{entry.code}</code></pre>
              </div>
            )}
          </div>
        )}

        {/* Collapsible result */}
        {entry.codeResult && (
          <div>
            <button
              onClick={() => setCodeExpanded(!codeExpanded)}
              className="inline-flex items-center gap-1 mt-1 text-[var(--mars-color-text-tertiary)] hover:text-[var(--mars-color-text-secondary)] transition-colors"
              aria-expanded={codeExpanded}
            >
              {codeExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              <span className="text-[10px] uppercase tracking-wider">
                result {codeExpanded ? '(collapse)' : '(expand)'}
              </span>
            </button>
            {codeExpanded && (
              <div className="mars-log-code-block">
                <pre><code>{entry.codeResult}</code></pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
