'use client'

import React from 'react'

export interface SkeletonProps {
  variant?: 'text' | 'rectangular' | 'circular'
  width?: string | number
  height?: string | number
  lines?: number
}

export default function Skeleton({ variant = 'text', width, height, lines = 1 }: SkeletonProps) {
  const baseClass = 'animate-pulse rounded'

  if (variant === 'circular') {
    const size = width || height || 40
    return (
      <div
        className={baseClass}
        style={{
          width: typeof size === 'number' ? `${size}px` : size,
          height: typeof size === 'number' ? `${size}px` : size,
          borderRadius: '50%',
          backgroundColor: 'var(--mars-color-surface-overlay)',
        }}
      />
    )
  }

  if (variant === 'rectangular') {
    return (
      <div
        className={`${baseClass} rounded-mars-md`}
        style={{
          width: width ? (typeof width === 'number' ? `${width}px` : width) : '100%',
          height: height ? (typeof height === 'number' ? `${height}px` : height) : '80px',
          backgroundColor: 'var(--mars-color-surface-overlay)',
        }}
      />
    )
  }

  // Text variant
  return (
    <div className="space-y-2" style={{ width: width ? (typeof width === 'number' ? `${width}px` : width) : '100%' }}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={`${baseClass} rounded-mars-sm`}
          style={{
            height: height ? (typeof height === 'number' ? `${height}px` : height) : '14px',
            backgroundColor: 'var(--mars-color-surface-overlay)',
            width: i === lines - 1 && lines > 1 ? '75%' : '100%',
          }}
        />
      ))}
    </div>
  )
}
