'use client'

import React, { useState, useRef, useEffect, useId } from 'react'

export interface TooltipProps {
  content: string | React.ReactNode
  children: React.ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

const positionStyles: Record<string, React.CSSProperties> = {
  top: { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: '8px' },
  bottom: { top: '100%', left: '50%', transform: 'translateX(-50%)', marginTop: '8px' },
  left: { right: '100%', top: '50%', transform: 'translateY(-50%)', marginRight: '8px' },
  right: { left: '100%', top: '50%', transform: 'translateY(-50%)', marginLeft: '8px' },
}

export default function Tooltip({ content, children, position = 'top', delay = 300 }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const tooltipId = useId()

  const show = () => {
    timeoutRef.current = setTimeout(() => setVisible(true), delay)
  }

  const hide = () => {
    clearTimeout(timeoutRef.current)
    setVisible(false)
  }

  useEffect(() => {
    return () => clearTimeout(timeoutRef.current)
  }, [])

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      <span aria-describedby={visible ? tooltipId : undefined}>
        {children}
      </span>

      {visible && (
        <span
          id={tooltipId}
          role="tooltip"
          className="absolute whitespace-nowrap px-2.5 py-1.5 text-xs font-medium
            rounded-mars-md shadow-mars-md pointer-events-none
            animate-[mars-fade-in_var(--mars-duration-fast)_var(--mars-ease-standard)]"
          style={{
            ...positionStyles[position],
            backgroundColor: 'var(--mars-color-surface-overlay)',
            color: 'var(--mars-color-text)',
            border: '1px solid var(--mars-color-border)',
            zIndex: 'var(--mars-z-tooltip)',
          }}
        >
          {content}
        </span>
      )}
    </span>
  )
}
