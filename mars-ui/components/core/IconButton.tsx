'use client'

import React, { forwardRef } from 'react'

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  label: string
  icon: React.ReactNode
  active?: boolean
  badge?: number | string
}

const sizeClasses: Record<string, string> = {
  sm: 'w-8 h-8',
  md: 'w-9 h-9',
  lg: 'w-10 h-10',
}

const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  {
    variant = 'default',
    size = 'md',
    label,
    icon,
    active = false,
    badge,
    disabled,
    className = '',
    ...props
  },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled}
      aria-label={label}
      className={`
        relative inline-flex items-center justify-center
        rounded-mars-md transition-colors duration-mars-fast
        ${sizeClasses[size]}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${className}
      `}
      style={{
        color: active
          ? 'var(--mars-color-primary)'
          : variant === 'danger'
            ? 'var(--mars-color-danger)'
            : 'var(--mars-color-text-secondary)',
        backgroundColor: active ? 'var(--mars-color-primary-subtle)' : 'transparent',
      }}
      onMouseEnter={(e) => {
        if (!disabled && !active) {
          e.currentTarget.style.backgroundColor = 'var(--mars-color-bg-hover)'
          e.currentTarget.style.color = variant === 'danger'
            ? 'var(--mars-color-danger)'
            : 'var(--mars-color-text)'
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled && !active) {
          e.currentTarget.style.backgroundColor = 'transparent'
          e.currentTarget.style.color = variant === 'danger'
            ? 'var(--mars-color-danger)'
            : 'var(--mars-color-text-secondary)'
        }
      }}
      {...props}
    >
      {icon}
      {badge !== undefined && (
        <span
          className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center
            rounded-full text-[10px] font-semibold px-1"
          style={{
            backgroundColor: 'var(--mars-color-danger)',
            color: 'white',
          }}
        >
          {badge}
        </span>
      )}
    </button>
  )
})

export default IconButton
