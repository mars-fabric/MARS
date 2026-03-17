'use client'

import React, { forwardRef } from 'react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
  iconRight?: React.ReactNode
  fullWidth?: boolean
}

const variantStyles: Record<string, React.CSSProperties> = {
  primary: {
    backgroundColor: 'var(--mars-color-primary)',
    color: 'white',
    borderColor: 'transparent',
  },
  secondary: {
    backgroundColor: 'transparent',
    color: 'var(--mars-color-text)',
    borderColor: 'var(--mars-color-border-strong)',
  },
  ghost: {
    backgroundColor: 'transparent',
    color: 'var(--mars-color-text-secondary)',
    borderColor: 'transparent',
  },
  danger: {
    backgroundColor: 'var(--mars-color-danger)',
    color: 'white',
    borderColor: 'transparent',
  },
}

const sizeClasses: Record<string, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-4 text-sm gap-2',
  lg: 'h-10 px-5 text-sm gap-2',
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    loading = false,
    icon,
    iconRight,
    fullWidth = false,
    disabled,
    className = '',
    children,
    ...props
  },
  ref
) {
  const isDisabled = disabled || loading

  return (
    <button
      ref={ref}
      disabled={isDisabled}
      className={`
        inline-flex items-center justify-center font-medium
        rounded-mars-md border transition-colors duration-mars-fast
        ${sizeClasses[size]}
        ${fullWidth ? 'w-full' : ''}
        ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${className}
      `}
      style={{
        ...variantStyles[variant],
        ...(isDisabled ? {} : {}),
      }}
      onMouseEnter={(e) => {
        if (!isDisabled) {
          const target = e.currentTarget
          if (variant === 'primary') target.style.backgroundColor = 'var(--mars-color-primary-hover)'
          else if (variant === 'secondary') target.style.backgroundColor = 'var(--mars-color-bg-hover)'
          else if (variant === 'ghost') target.style.backgroundColor = 'var(--mars-color-bg-hover)'
          else if (variant === 'danger') target.style.backgroundColor = '#DC2626'
        }
        props.onMouseEnter?.(e)
      }}
      onMouseLeave={(e) => {
        if (!isDisabled) {
          e.currentTarget.style.backgroundColor = variantStyles[variant].backgroundColor as string
        }
        props.onMouseLeave?.(e)
      }}
      {...props}
    >
      {loading && (
        <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="opacity-25" />
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="opacity-75" />
        </svg>
      )}
      {!loading && icon}
      {children}
      {iconRight}
    </button>
  )
})

export default Button
