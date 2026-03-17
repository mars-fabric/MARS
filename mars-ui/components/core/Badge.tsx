'use client'

import React from 'react'

export interface BadgeProps {
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'
  size?: 'sm' | 'md'
  dot?: boolean
  children: React.ReactNode
}

const variantStyles: Record<string, { bg: string; text: string }> = {
  default: { bg: 'var(--mars-color-surface-overlay)', text: 'var(--mars-color-text-secondary)' },
  primary: { bg: 'var(--mars-color-primary-subtle)', text: 'var(--mars-color-primary-text)' },
  success: { bg: 'var(--mars-color-success-subtle)', text: 'var(--mars-color-success)' },
  warning: { bg: 'var(--mars-color-warning-subtle)', text: 'var(--mars-color-warning)' },
  danger: { bg: 'var(--mars-color-danger-subtle)', text: 'var(--mars-color-danger)' },
  info: { bg: 'var(--mars-color-info-subtle)', text: 'var(--mars-color-info)' },
}

export default function Badge({ variant = 'default', size = 'sm', dot = false, children }: BadgeProps) {
  const styles = variantStyles[variant]

  if (dot) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <span
          className="w-2 h-2 rounded-full"
          style={{ backgroundColor: styles.text }}
        />
        <span
          className={size === 'sm' ? 'text-xs' : 'text-sm'}
          style={{ color: styles.text }}
        >
          {children}
        </span>
      </span>
    )
  }

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full
        ${size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'}`}
      style={{
        backgroundColor: styles.bg,
        color: styles.text,
      }}
    >
      {children}
    </span>
  )
}
