'use client'

import React from 'react'
import { X } from 'lucide-react'

export interface SessionPillProps {
  sessionId: string
  name: string
  status: 'active' | 'paused' | 'queued' | 'completed' | 'failed'
  progress?: number
  active?: boolean
  onClick: (sessionId: string) => void
  onClose?: (sessionId: string) => void
}

const statusDotColor: Record<string, string> = {
  active: 'var(--mars-color-success)',
  paused: 'var(--mars-color-warning)',
  queued: 'var(--mars-color-info)',
  completed: 'var(--mars-color-primary)',
  failed: 'var(--mars-color-danger)',
}

export default function SessionPill({
  sessionId,
  name,
  status,
  progress,
  active = false,
  onClick,
  onClose,
}: SessionPillProps) {
  const dotColor = statusDotColor[status] || 'var(--mars-color-text-tertiary)'

  return (
    <div
      className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full text-xs font-medium cursor-pointer transition-all duration-mars-fast select-none"
      style={{
        backgroundColor: active
          ? 'var(--mars-color-primary-subtle)'
          : 'var(--mars-color-surface-overlay)',
        color: active
          ? 'var(--mars-color-primary-text)'
          : 'var(--mars-color-text-secondary)',
        border: active
          ? '1px solid var(--mars-color-primary)'
          : '1px solid transparent',
      }}
      onClick={() => onClick(sessionId)}
      onMouseEnter={(e) => {
        if (!active) {
          e.currentTarget.style.backgroundColor = 'var(--mars-color-bg-hover)'
          e.currentTarget.style.color = 'var(--mars-color-text)'
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          e.currentTarget.style.backgroundColor = 'var(--mars-color-surface-overlay)'
          e.currentTarget.style.color = 'var(--mars-color-text-secondary)'
        }
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick(sessionId)
        }
      }}
      aria-label={`Session: ${name} (${status})`}
    >
      {/* Status dot */}
      <span
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{ backgroundColor: dotColor }}
      />

      {/* Session name (truncated) */}
      <span className="max-w-[100px] truncate">{name}</span>

      {/* Progress ring (tiny) */}
      {progress != null && progress > 0 && progress < 100 && (
        <svg className="w-3.5 h-3.5 flex-shrink-0 -rotate-90" viewBox="0 0 16 16">
          <circle
            cx="8"
            cy="8"
            r="6"
            fill="none"
            strokeWidth="2"
            style={{ stroke: 'var(--mars-color-surface-overlay)' }}
          />
          <circle
            cx="8"
            cy="8"
            r="6"
            fill="none"
            strokeWidth="2"
            strokeDasharray={`${(progress / 100) * 37.7} 37.7`}
            strokeLinecap="round"
            style={{ stroke: dotColor }}
          />
        </svg>
      )}

      {/* Close button */}
      {onClose && (
        <button
          className="flex-shrink-0 p-0.5 rounded-full transition-colors duration-mars-fast"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
          onClick={(e) => {
            e.stopPropagation()
            onClose(sessionId)
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--mars-color-text)'
            e.currentTarget.style.backgroundColor = 'var(--mars-color-surface-overlay)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--mars-color-text-tertiary)'
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
          aria-label={`Close session ${name}`}
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </div>
  )
}
