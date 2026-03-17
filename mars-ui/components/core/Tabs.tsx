'use client'

import React, { useRef, useCallback } from 'react'

export interface TabItem {
  id: string
  label: string
  icon?: React.ReactNode
  badge?: number | string
  disabled?: boolean
}

export interface TabsProps {
  items: TabItem[]
  activeId: string
  onChange: (id: string) => void
  variant?: 'underline' | 'pills'
  size?: 'sm' | 'md'
}

export default function Tabs({ items, activeId, onChange, variant = 'underline', size = 'md' }: TabsProps) {
  const tabRefs = useRef<Map<string, HTMLButtonElement>>(new Map())

  const handleKeyDown = useCallback((e: React.KeyboardEvent, currentIndex: number) => {
    const enabledItems = items.filter(item => !item.disabled)
    const currentEnabledIndex = enabledItems.findIndex(item => item.id === items[currentIndex].id)

    let targetIndex = -1

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault()
      targetIndex = (currentEnabledIndex + 1) % enabledItems.length
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault()
      targetIndex = (currentEnabledIndex - 1 + enabledItems.length) % enabledItems.length
    } else if (e.key === 'Home') {
      e.preventDefault()
      targetIndex = 0
    } else if (e.key === 'End') {
      e.preventDefault()
      targetIndex = enabledItems.length - 1
    }

    if (targetIndex >= 0) {
      const targetItem = enabledItems[targetIndex]
      onChange(targetItem.id)
      tabRefs.current.get(targetItem.id)?.focus()
    }
  }, [items, onChange])

  const isUnderline = variant === 'underline'

  return (
    <div
      role="tablist"
      className={`flex ${isUnderline ? 'border-b' : 'gap-1 p-1 rounded-mars-md'}`}
      style={{
        borderColor: isUnderline ? 'var(--mars-color-border)' : undefined,
        backgroundColor: !isUnderline ? 'var(--mars-color-surface-overlay)' : undefined,
      }}
    >
      {items.map((item, index) => {
        const isActive = item.id === activeId
        return (
          <button
            key={item.id}
            ref={(el) => {
              if (el) tabRefs.current.set(item.id, el)
            }}
            role="tab"
            aria-selected={isActive}
            aria-disabled={item.disabled}
            tabIndex={isActive ? 0 : -1}
            disabled={item.disabled}
            onClick={() => !item.disabled && onChange(item.id)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={`
              inline-flex items-center gap-2 font-medium transition-colors duration-mars-fast
              ${size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm'}
              ${item.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
              ${isUnderline
                ? `border-b-2 -mb-px ${isActive
                    ? 'border-[var(--mars-color-primary)]'
                    : 'border-transparent hover:border-[var(--mars-color-border)]'
                  }`
                : `rounded-mars-sm ${isActive ? '' : 'hover:bg-[var(--mars-color-bg-hover)]'}`
              }
            `}
            style={{
              color: isActive
                ? 'var(--mars-color-primary)'
                : 'var(--mars-color-text-secondary)',
              backgroundColor: !isUnderline && isActive
                ? 'var(--mars-color-bg)'
                : undefined,
            }}
          >
            {item.icon}
            {item.label}
            {item.badge !== undefined && (
              <span
                className="min-w-[18px] h-[18px] flex items-center justify-center
                  rounded-full text-[10px] font-semibold px-1"
                style={{
                  backgroundColor: isActive
                    ? 'var(--mars-color-primary-subtle)'
                    : 'var(--mars-color-surface-overlay)',
                  color: isActive
                    ? 'var(--mars-color-primary)'
                    : 'var(--mars-color-text-tertiary)',
                }}
              >
                {item.badge}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
