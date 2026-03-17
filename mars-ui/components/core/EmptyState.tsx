'use client'

import React from 'react'
import Button from './Button'

export interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: {
    label: string
    onClick: () => void
  }
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      {icon && (
        <div
          className="w-12 h-12 flex items-center justify-center rounded-full mb-4"
          style={{
            backgroundColor: 'var(--mars-color-surface-overlay)',
            color: 'var(--mars-color-text-tertiary)',
          }}
        >
          {icon}
        </div>
      )}
      <h3
        className="text-base font-semibold mb-1"
        style={{ color: 'var(--mars-color-text)' }}
      >
        {title}
      </h3>
      {description && (
        <p
          className="text-sm max-w-sm mb-4"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          {description}
        </p>
      )}
      {action && (
        <Button variant="primary" size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  )
}
