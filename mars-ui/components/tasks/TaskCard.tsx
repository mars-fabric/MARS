'use client'

import React from 'react'
import { MoreVertical, Play, Copy, Archive } from 'lucide-react'
import { Badge, Dropdown, IconButton } from '@/components/core'

export interface TaskCardProps {
  id: string
  name: string
  description: string
  mode: string
  status: 'draft' | 'active' | 'archived'
  lastRun?: string
  icon: React.ReactNode
  color: string
  onOpen: (id: string) => void
  onDuplicate?: (id: string) => void
  onArchive?: (id: string) => void
}

const statusVariant: Record<string, 'default' | 'success' | 'warning'> = {
  draft: 'default',
  active: 'success',
  archived: 'default',
}

function formatLastRun(iso: string): string {
  const date = new Date(iso)
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

export default function TaskCard({
  id,
  name,
  description,
  mode,
  status,
  lastRun,
  icon,
  color,
  onOpen,
  onDuplicate,
  onArchive,
}: TaskCardProps) {
  const dropdownItems = [
    { id: 'open', label: 'Open', icon: <Play className="w-4 h-4" /> },
    { id: 'duplicate', label: 'Duplicate', icon: <Copy className="w-4 h-4" />, disabled: !onDuplicate },
    { id: 'divider-1', label: '', divider: true },
    { id: 'archive', label: status === 'archived' ? 'Unarchive' : 'Archive', icon: <Archive className="w-4 h-4" />, disabled: !onArchive },
  ]

  const handleAction = (actionId: string) => {
    switch (actionId) {
      case 'open':
        onOpen(id)
        break
      case 'duplicate':
        onDuplicate?.(id)
        break
      case 'archive':
        onArchive?.(id)
        break
    }
  }

  return (
    <div
      className="group relative border rounded-mars-lg p-5 transition-all duration-mars-normal cursor-pointer"
      style={{
        backgroundColor: 'var(--mars-color-surface-raised)',
        borderColor: 'var(--mars-color-border)',
      }}
      onClick={() => onOpen(id)}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'var(--mars-color-border-strong)'
        e.currentTarget.style.boxShadow = 'var(--mars-shadow-md)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--mars-color-border)'
        e.currentTarget.style.boxShadow = 'none'
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen(id)
        }
      }}
    >
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div
          className={`w-10 h-10 rounded-mars-md bg-gradient-to-br ${color} flex items-center justify-center flex-shrink-0`}
        >
          <span className="text-white">{icon}</span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3
              className="text-sm font-semibold truncate"
              style={{ color: 'var(--mars-color-text)' }}
            >
              {name}
            </h3>
            <Badge variant={statusVariant[status]} size="sm">
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Badge>
          </div>
          <p
            className="text-xs truncate mb-2"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            {description}
          </p>
          <div className="flex items-center gap-3">
            <Badge variant="info" size="sm">{mode}</Badge>
            {lastRun && (
              <span
                className="text-xs"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
              >
                Last run: {formatLastRun(lastRun)}
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div
          className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-mars-fast"
          onClick={(e) => e.stopPropagation()}
        >
          <Dropdown
            trigger={
              <IconButton
                variant="ghost"
                size="sm"
                label="Task actions"
                icon={<MoreVertical className="w-4 h-4" />}
              />
            }
            items={dropdownItems}
            onSelect={handleAction}
            align="right"
          />
        </div>
      </div>
    </div>
  )
}
