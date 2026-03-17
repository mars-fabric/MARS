'use client'

import React from 'react'
import { Play, Eye, Pause, X, Clock } from 'lucide-react'
import { Badge, IconButton } from '@/components/core'
import { getModeDisplayName } from '@/lib/modes'

export interface SessionCardProps {
  session: {
    session_id: string
    name: string
    mode: string
    status: string
    current_phase?: string | null
    current_step?: number | null
    created_at?: string | null
    updated_at?: string | null
    progress?: number
  }
  selected?: boolean
  onSelect: (id: string) => void
  onResume?: (id: string, mode?: string) => void
  onViewLogs?: (id: string, mode?: string) => void
  onPause?: (id: string) => void
  onCancel?: (id: string) => void
  compact?: boolean
}

const statusConfig: Record<string, { color: string; variant: 'default' | 'success' | 'warning' | 'danger' | 'info' }> = {
  active: { color: 'var(--mars-color-success)', variant: 'success' },
  queued: { color: 'var(--mars-color-info)', variant: 'info' },
  suspended: { color: 'var(--mars-color-warning)', variant: 'warning' },
  paused: { color: 'var(--mars-color-warning)', variant: 'warning' },
  completed: { color: 'var(--mars-color-primary)', variant: 'info' },
  failed: { color: 'var(--mars-color-danger)', variant: 'danger' },
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: 'Active',
    queued: 'Queued',
    suspended: 'Paused',
    paused: 'Paused',
    completed: 'Completed',
    failed: 'Failed',
  }
  return labels[status] || status
}

function formatDuration(start: string | null | undefined, end?: string | null): string {
  if (!start) return ''
  const startDate = parseSessionDate(start)
  const endDate = end ? parseSessionDate(end) : new Date()
  const diffMs = endDate.getTime() - startDate.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return '<1m'
  if (diffMins < 60) return `${diffMins}m`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ${diffMins % 60}m`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ${diffHours % 24}h`
}

function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = parseSessionDate(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function parseSessionDate(iso: string): Date {
  // Treat timestamps without timezone suffix as UTC to avoid local-time skew.
  const hasTimezone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso)
  return new Date(hasTimezone ? iso : `${iso}Z`)
}

export default function SessionCard({
  session,
  selected = false,
  onSelect,
  onResume,
  onViewLogs,
  onPause,
  onCancel,
  compact = false,
}: SessionCardProps) {
  const config = statusConfig[session.status] || statusConfig.completed
  const isResumable = ['suspended', 'paused', 'active'].includes(session.status)
  const isPausable = session.status === 'active'
  const isCancellable = ['active', 'queued'].includes(session.status)

  return (
    <div
      className="group relative border rounded-mars-lg p-4 transition-all duration-mars-normal cursor-pointer"
      style={{
        backgroundColor: selected
          ? 'var(--mars-color-primary-subtle)'
          : 'var(--mars-color-surface-raised)',
        borderColor: selected
          ? 'var(--mars-color-primary)'
          : 'var(--mars-color-border)',
        borderLeftWidth: '3px',
        borderLeftColor: config.color,
      }}
      onClick={() => onSelect(session.session_id)}
      onMouseEnter={(e) => {
        if (!selected) {
          e.currentTarget.style.borderColor = 'var(--mars-color-border-strong)'
          e.currentTarget.style.boxShadow = 'var(--mars-shadow-md)'
        }
      }}
      onMouseLeave={(e) => {
        if (!selected) {
          e.currentTarget.style.borderColor = 'var(--mars-color-border)'
          e.currentTarget.style.boxShadow = 'none'
        }
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect(session.session_id)
        }
      }}
    >
      <div className="flex items-start gap-3">
        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Name + Status */}
          <div className="flex items-center gap-2 mb-1">
            <h3
              className="text-sm font-semibold truncate"
              style={{ color: 'var(--mars-color-text)' }}
            >
              {session.name}
            </h3>
            <Badge variant={config.variant} size="sm">
              {getStatusLabel(session.status)}
            </Badge>
          </div>

          {/* Mode + Phase */}
          <div className="flex items-center gap-2 mb-2">
            <Badge variant="info" size="sm">
              {getModeDisplayName(session.mode)}
            </Badge>
            {session.current_phase && (
              <span
                className="text-xs"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
              >
                {session.current_phase}
                {session.current_step != null && ` (Step ${session.current_step})`}
              </span>
            )}
          </div>

          {/* Progress bar */}
          {session.progress != null && session.progress > 0 && session.progress < 100 && (
            <div className="mb-2">
              <div
                className="h-1.5 rounded-full overflow-hidden"
                style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
              >
                <div
                  className="h-full rounded-full transition-all duration-mars-normal"
                  style={{
                    width: `${session.progress}%`,
                    backgroundColor: config.color,
                  }}
                />
              </div>
            </div>
          )}

          {/* Timestamps */}
          {!compact && (
            <div className="flex items-center gap-3">
              {session.created_at && (
                <span
                  className="flex items-center gap-1 text-xs"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                >
                  <Clock className="w-3 h-3" />
                  {formatDuration(session.created_at, session.status === 'active' ? undefined : session.updated_at)}
                </span>
              )}
              {session.updated_at && (
                <span
                  className="text-xs"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                >
                  Updated {formatTimestamp(session.updated_at)}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div
          className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-mars-fast"
          onClick={(e) => e.stopPropagation()}
        >
          {onViewLogs && (
            <IconButton
              variant="ghost"
              size="sm"
              label="View logs"
              icon={<Eye className="w-4 h-4" />}
              onClick={() => onViewLogs(session.session_id, session.mode)}
            />
          )}
          {isResumable && onResume && (
            <IconButton
              variant="ghost"
              size="sm"
              label="Resume"
              icon={<Play className="w-4 h-4" style={{ color: 'var(--mars-color-success)' }} />}
              onClick={() => onResume(session.session_id, session.mode)}
            />
          )}
          {isPausable && onPause && (
            <IconButton
              variant="ghost"
              size="sm"
              label="Pause"
              icon={<Pause className="w-4 h-4" style={{ color: 'var(--mars-color-warning)' }} />}
              onClick={() => onPause(session.session_id)}
            />
          )}
          {isCancellable && onCancel && (
            <IconButton
              variant="ghost"
              size="sm"
              label="Cancel"
              icon={<X className="w-4 h-4" />}
              onClick={() => onCancel(session.session_id)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
