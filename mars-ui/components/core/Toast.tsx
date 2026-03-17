'use client'

import React, { useEffect, useState } from 'react'
import { X, CheckCircle, AlertTriangle, AlertCircle, Info } from 'lucide-react'

export interface ToastProps {
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message?: string
  duration?: number
  onClose: () => void
  action?: { label: string; onClick: () => void }
}

const typeConfig: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
  info: {
    icon: <Info className="w-5 h-5" />,
    color: 'var(--mars-color-info)',
    bg: 'var(--mars-color-info-subtle)',
  },
  success: {
    icon: <CheckCircle className="w-5 h-5" />,
    color: 'var(--mars-color-success)',
    bg: 'var(--mars-color-success-subtle)',
  },
  warning: {
    icon: <AlertTriangle className="w-5 h-5" />,
    color: 'var(--mars-color-warning)',
    bg: 'var(--mars-color-warning-subtle)',
  },
  error: {
    icon: <AlertCircle className="w-5 h-5" />,
    color: 'var(--mars-color-danger)',
    bg: 'var(--mars-color-danger-subtle)',
  },
}

export default function Toast({ type, title, message, duration = 5000, onClose, action }: ToastProps) {
  const [exiting, setExiting] = useState(false)
  const config = typeConfig[type]

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        setExiting(true)
        setTimeout(onClose, 200)
      }, duration)
      return () => clearTimeout(timer)
    }
  }, [duration, onClose])

  return (
    <div
      className={`
        flex items-start gap-3 p-4 rounded-mars-lg shadow-mars-lg min-w-[320px] max-w-[480px]
        transition-all duration-mars-normal
        ${exiting ? 'opacity-0 translate-x-4' : 'animate-[mars-slide-up_var(--mars-duration-normal)_var(--mars-ease-standard)]'}
      `}
      style={{
        backgroundColor: 'var(--mars-color-surface-raised)',
        border: '1px solid var(--mars-color-border)',
      }}
      role="alert"
    >
      <span style={{ color: config.color }} className="flex-shrink-0 mt-0.5">
        {config.icon}
      </span>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
          {title}
        </p>
        {message && (
          <p className="mt-1 text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>
            {message}
          </p>
        )}
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

      <button
        onClick={() => {
          setExiting(true)
          setTimeout(onClose, 200)
        }}
        className="flex-shrink-0 p-1 rounded-mars-sm transition-colors duration-mars-fast
          hover:bg-[var(--mars-color-bg-hover)]"
        style={{ color: 'var(--mars-color-text-tertiary)' }}
        aria-label="Dismiss notification"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
