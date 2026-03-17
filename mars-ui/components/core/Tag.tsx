'use client'

import React from 'react'
import { X } from 'lucide-react'

export interface TagProps {
  label: string
  color?: string
  onRemove?: () => void
  icon?: React.ReactNode
}

export default function Tag({ label, color, onRemove, icon }: TagProps) {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-mars-md
        transition-colors duration-mars-fast"
      style={{
        backgroundColor: color ? `${color}20` : 'var(--mars-color-surface-overlay)',
        color: color || 'var(--mars-color-text-secondary)',
        border: `1px solid ${color ? `${color}40` : 'var(--mars-color-border)'}`,
      }}
    >
      {icon && <span className="w-3.5 h-3.5">{icon}</span>}
      {label}
      {onRemove && (
        <button
          onClick={onRemove}
          className="ml-0.5 p-0.5 rounded-full hover:opacity-70 transition-opacity"
          aria-label={`Remove ${label}`}
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </span>
  )
}
