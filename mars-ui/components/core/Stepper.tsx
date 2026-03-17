'use client'

import React from 'react'
import { Check, X, Minus } from 'lucide-react'

export interface StepperStep {
  id: string
  label: string
  status: 'pending' | 'active' | 'completed' | 'failed' | 'skipped'
  description?: string
}

export interface StepperProps {
  steps: StepperStep[]
  orientation?: 'horizontal' | 'vertical'
  size?: 'sm' | 'md'
}

const statusConfig: Record<string, { bg: string; border: string; icon?: React.ReactNode }> = {
  pending: {
    bg: 'var(--mars-color-surface-overlay)',
    border: 'var(--mars-color-border)',
  },
  active: {
    bg: 'var(--mars-color-primary-subtle)',
    border: 'var(--mars-color-primary)',
  },
  completed: {
    bg: 'var(--mars-color-success-subtle)',
    border: 'var(--mars-color-success)',
    icon: <Check className="w-3.5 h-3.5" />,
  },
  failed: {
    bg: 'var(--mars-color-danger-subtle)',
    border: 'var(--mars-color-danger)',
    icon: <X className="w-3.5 h-3.5" />,
  },
  skipped: {
    bg: 'var(--mars-color-surface-overlay)',
    border: 'var(--mars-color-border)',
    icon: <Minus className="w-3.5 h-3.5" />,
  },
}

export default function Stepper({ steps, orientation = 'horizontal', size = 'md' }: StepperProps) {
  const isVertical = orientation === 'vertical'
  const dotSize = size === 'sm' ? 'w-6 h-6' : 'w-8 h-8'

  return (
    <div
      className={`flex ${isVertical ? 'flex-col' : 'items-center'}`}
      role="list"
    >
      {steps.map((step, index) => {
        const config = statusConfig[step.status]
        const isLast = index === steps.length - 1

        return (
          <div
            key={step.id}
            className={`flex ${isVertical ? 'flex-row' : 'flex-col items-center'} ${!isLast ? 'flex-1' : ''}`}
            role="listitem"
          >
            <div className={`flex ${isVertical ? 'flex-col items-center' : 'items-center w-full'}`}>
              {/* Step Dot */}
              <div
                className={`${dotSize} flex-shrink-0 rounded-full flex items-center justify-center
                  text-xs font-medium transition-colors duration-mars-normal`}
                style={{
                  backgroundColor: config.bg,
                  border: `2px solid ${config.border}`,
                  color: step.status === 'active'
                    ? 'var(--mars-color-primary)'
                    : step.status === 'completed'
                      ? 'var(--mars-color-success)'
                      : step.status === 'failed'
                        ? 'var(--mars-color-danger)'
                        : 'var(--mars-color-text-tertiary)',
                }}
              >
                {config.icon || (step.status === 'active' ? (
                  <span className="w-2 h-2 rounded-full bg-current" />
                ) : (
                  index + 1
                ))}
              </div>

              {/* Connector Line */}
              {!isLast && (
                <div
                  className={`${isVertical ? 'w-0.5 min-h-[24px] mx-auto my-1' : 'flex-1 h-0.5 mx-2'}`}
                  style={{
                    backgroundColor: step.status === 'completed'
                      ? 'var(--mars-color-success)'
                      : 'var(--mars-color-border)',
                  }}
                />
              )}
            </div>

            {/* Label */}
            <div className={`${isVertical ? 'ml-3 pb-6' : 'mt-2 text-center'}`}>
              <p
                className={`${size === 'sm' ? 'text-xs' : 'text-sm'} font-medium`}
                style={{
                  color: step.status === 'active'
                    ? 'var(--mars-color-text)'
                    : 'var(--mars-color-text-secondary)',
                }}
              >
                {step.label}
              </p>
              {step.description && (
                <p
                  className="text-xs mt-0.5"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                >
                  {step.description}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
