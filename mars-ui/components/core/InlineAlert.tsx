'use client'

import React, { useState } from 'react'
import { X, CheckCircle, AlertTriangle, AlertCircle, Info } from 'lucide-react'

export interface InlineAlertProps {
  type: 'info' | 'success' | 'warning' | 'error'
  title?: string
  children: React.ReactNode
  closable?: boolean
  onClose?: () => void
  action?: { label: string; onClick: () => void }
}

const typeConfig: Record<string, { icon: React.ReactNode; color: string; bg: string; border: string }> = {
  info: {
    icon: <Info className="w-4 h-4" />,
    color: 'var(--mars-color-info)',
    bg: 'var(--mars-color-info-subtle)',
    border: 'var(--mars-color-info)',
  },
  success: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'var(--mars-color-success)',
    bg: 'var(--mars-color-success-subtle)',
    border: 'var(--mars-color-success)',
  },
  warning: {
    icon: <AlertTriangle className="w-4 h-4" />,
    color: 'var(--mars-color-warning)',
    bg: 'var(--mars-color-warning-subtle)',
    border: 'var(--mars-color-warning)',
  },
  error: {
    icon: <AlertCircle className="w-4 h-4" />,
    color: 'var(--mars-color-danger)',
    bg: 'var(--mars-color-danger-subtle)',
    border: 'var(--mars-color-danger)',
  },
}

export default function InlineAlert({ type, title, children, closable, onClose, action }: InlineAlertProps) {
  const [visible, setVisible] = useState(true)
  const config = typeConfig[type]

  if (!visible) return null

  const handleClose = () => {
    setVisible(false)
    onClose?.()
  }

  return (
    <div
      className="flex items-start gap-3 p-3 rounded-mars-md"
      style={{
        backgroundColor: config.bg,
        borderLeft: `3px solid ${config.border}`,
      }}
      role="alert"
    >
      <span style={{ color: config.color }} className="flex-shrink-0 mt-0.5">
        {config.icon}
      </span>

      <div className="flex-1 min-w-0">
        {title && (
          <p className="text-sm font-medium mb-0.5" style={{ color: 'var(--mars-color-text)' }}>
            {title}
          </p>
        )}
        <div className="text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
          {children}
        </div>
        {action && (
          <button
            onClick={action.onClick}
            className="mt-2 text-xs font-medium transition-colors duration-mars-fast"
            style={{ color: config.color }}
          >
            {action.label}
          </button>
        )}
      </div>

      {closable && (
        <button
          onClick={handleClose}
          className="flex-shrink-0 p-0.5 rounded transition-colors duration-mars-fast
            hover:bg-[var(--mars-color-bg-hover)]"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
          aria-label="Dismiss alert"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}
