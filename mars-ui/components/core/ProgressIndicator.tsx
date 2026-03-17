'use client'

import React from 'react'

export interface ProgressIndicatorProps {
  value: number
  variant?: 'bar' | 'ring'
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  color?: 'primary' | 'success' | 'warning' | 'danger'
}

const colorMap: Record<string, string> = {
  primary: 'var(--mars-color-primary)',
  success: 'var(--mars-color-success)',
  warning: 'var(--mars-color-warning)',
  danger: 'var(--mars-color-danger)',
}

const barSizes: Record<string, string> = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-3',
}

const ringSizes: Record<string, { size: number; stroke: number }> = {
  sm: { size: 32, stroke: 3 },
  md: { size: 48, stroke: 4 },
  lg: { size: 64, stroke: 5 },
}

export default function ProgressIndicator({
  value,
  variant = 'bar',
  size = 'md',
  showLabel = false,
  color = 'primary',
}: ProgressIndicatorProps) {
  const clampedValue = Math.max(0, Math.min(100, value))
  const progressColor = colorMap[color]

  if (variant === 'ring') {
    const { size: ringSize, stroke } = ringSizes[size]
    const radius = (ringSize - stroke) / 2
    const circumference = 2 * Math.PI * radius
    const offset = circumference - (clampedValue / 100) * circumference

    return (
      <div className="relative inline-flex items-center justify-center">
        <svg
          width={ringSize}
          height={ringSize}
          className="-rotate-90"
          aria-valuenow={clampedValue}
          aria-valuemin={0}
          aria-valuemax={100}
          role="progressbar"
        >
          <circle
            cx={ringSize / 2}
            cy={ringSize / 2}
            r={radius}
            fill="none"
            stroke="var(--mars-color-surface-overlay)"
            strokeWidth={stroke}
          />
          <circle
            cx={ringSize / 2}
            cy={ringSize / 2}
            r={radius}
            fill="none"
            stroke={progressColor}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-mars-slow"
          />
        </svg>
        {showLabel && (
          <span
            className="absolute text-xs font-medium"
            style={{ color: 'var(--mars-color-text)' }}
          >
            {Math.round(clampedValue)}%
          </span>
        )}
      </div>
    )
  }

  // Bar variant
  return (
    <div className="w-full">
      <div
        className={`w-full rounded-full overflow-hidden ${barSizes[size]}`}
        style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
        role="progressbar"
        aria-valuenow={clampedValue}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`${barSizes[size]} rounded-full transition-all duration-mars-slow`}
          style={{
            width: `${clampedValue}%`,
            backgroundColor: progressColor,
          }}
        />
      </div>
      {showLabel && (
        <span
          className="text-xs font-medium mt-1 block text-right"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          {Math.round(clampedValue)}%
        </span>
      )}
    </div>
  )
}
