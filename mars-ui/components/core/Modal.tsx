'use client'

import React, { useEffect, useRef, useCallback } from 'react'
import { X } from 'lucide-react'

export interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  children: React.ReactNode
  footer?: React.ReactNode
  closeOnEscape?: boolean
  closeOnBackdrop?: boolean
}

const sizeWidths: Record<string, string> = {
  sm: '480px',
  md: '640px',
  lg: '960px',
  xl: '1200px',
}

export default function Modal({
  open,
  onClose,
  title,
  size = 'md',
  children,
  footer,
  closeOnEscape = true,
  closeOnBackdrop = true,
}: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  // Focus trap
  const trapFocus = useCallback((e: KeyboardEvent) => {
    if (e.key !== 'Tab' || !modalRef.current) return

    const focusable = modalRef.current.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    if (focusable.length === 0) return

    const first = focusable[0]
    const last = focusable[focusable.length - 1]

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }, [])

  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement as HTMLElement
      // Focus the modal after render
      requestAnimationFrame(() => {
        modalRef.current?.focus()
      })

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && closeOnEscape) {
          onClose()
        }
        trapFocus(e)
      }

      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'

      return () => {
        document.removeEventListener('keydown', handleKeyDown)
        document.body.style.overflow = ''
        previousFocusRef.current?.focus()
      }
    }
  }, [open, closeOnEscape, onClose, trapFocus])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ zIndex: 'var(--mars-z-modal-backdrop)' }}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 animate-[mars-fade-in_var(--mars-duration-fast)_var(--mars-ease-standard)]"
        onClick={closeOnBackdrop ? onClose : undefined}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        className="relative w-full rounded-mars-lg shadow-mars-xl flex flex-col
          animate-[mars-scale-in_var(--mars-duration-normal)_var(--mars-ease-standard)]
          outline-none"
        style={{
          maxWidth: sizeWidths[size],
          maxHeight: '90vh',
          backgroundColor: 'var(--mars-color-surface-raised)',
          border: '1px solid var(--mars-color-border)',
          zIndex: 'var(--mars-z-modal)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0"
          style={{ borderColor: 'var(--mars-color-border)' }}
        >
          <h2
            id="modal-title"
            className="text-lg font-semibold"
            style={{ color: 'var(--mars-color-text)' }}
          >
            {title}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-mars-md transition-colors duration-mars-fast
              hover:bg-[var(--mars-color-bg-hover)]"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
            aria-label="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 min-h-0">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div
            className="flex items-center justify-end gap-3 px-6 py-4 border-t flex-shrink-0"
            style={{ borderColor: 'var(--mars-color-border)' }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
