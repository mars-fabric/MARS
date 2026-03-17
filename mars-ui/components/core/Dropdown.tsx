'use client'

import React, { useState, useRef, useEffect } from 'react'

export interface DropdownItem {
  id: string
  label: string
  icon?: React.ReactNode
  disabled?: boolean
  danger?: boolean
  divider?: boolean
}

export interface DropdownProps {
  trigger: React.ReactNode
  items: DropdownItem[]
  onSelect: (id: string) => void
  align?: 'left' | 'right'
}

export default function Dropdown({ trigger, items, onSelect, align = 'left' }: DropdownProps) {
  const [open, setOpen] = useState(false)
  const [focusedIndex, setFocusedIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selectableItems = items.filter(item => !item.divider && !item.disabled)

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault()
        setOpen(true)
        setFocusedIndex(0)
      }
      return
    }

    switch (e.key) {
      case 'Escape':
        e.preventDefault()
        setOpen(false)
        setFocusedIndex(-1)
        break
      case 'ArrowDown':
        e.preventDefault()
        setFocusedIndex(prev => (prev + 1) % selectableItems.length)
        break
      case 'ArrowUp':
        e.preventDefault()
        setFocusedIndex(prev => (prev - 1 + selectableItems.length) % selectableItems.length)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        if (focusedIndex >= 0 && focusedIndex < selectableItems.length) {
          onSelect(selectableItems[focusedIndex].id)
          setOpen(false)
          setFocusedIndex(-1)
        }
        break
    }
  }

  return (
    <div ref={containerRef} className="relative inline-flex" onKeyDown={handleKeyDown}>
      <div
        onClick={() => {
          setOpen(prev => !prev)
          if (!open) setFocusedIndex(-1)
        }}
        role="button"
        tabIndex={0}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {trigger}
      </div>

      {open && (
        <div
          ref={menuRef}
          role="listbox"
          className="absolute top-full mt-1 min-w-[180px] py-1 rounded-mars-md shadow-mars-lg
            animate-[mars-scale-in_var(--mars-duration-fast)_var(--mars-ease-standard)]"
          style={{
            backgroundColor: 'var(--mars-color-surface-raised)',
            border: '1px solid var(--mars-color-border)',
            zIndex: 'var(--mars-z-dropdown)',
            [align === 'right' ? 'right' : 'left']: 0,
          }}
        >
          {items.map((item, index) => {
            if (item.divider) {
              return (
                <div
                  key={`divider-${index}`}
                  className="my-1 border-t"
                  style={{ borderColor: 'var(--mars-color-border)' }}
                />
              )
            }

            const selectableIndex = selectableItems.indexOf(item)
            const isFocused = selectableIndex === focusedIndex

            return (
              <button
                key={item.id}
                role="option"
                aria-selected={isFocused}
                disabled={item.disabled}
                onClick={() => {
                  if (!item.disabled) {
                    onSelect(item.id)
                    setOpen(false)
                  }
                }}
                className={`
                  w-full flex items-center gap-2 px-3 py-2 text-sm text-left
                  transition-colors duration-mars-fast
                  ${item.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
                `}
                style={{
                  color: item.danger
                    ? 'var(--mars-color-danger)'
                    : 'var(--mars-color-text)',
                  backgroundColor: isFocused
                    ? 'var(--mars-color-bg-hover)'
                    : undefined,
                }}
                onMouseEnter={() => setFocusedIndex(selectableIndex)}
              >
                {item.icon && <span className="w-4 h-4 flex-shrink-0">{item.icon}</span>}
                {item.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
