'use client'

import { useState, useEffect, ReactNode } from 'react'
import TopBar from './TopBar'
import SideNav from './SideNav'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const [sideNavCollapsed, setSideNavCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  // Auto-collapse SideNav on small screens
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 639px)')
    const handleChange = (e: MediaQueryListEvent | MediaQueryList) => {
      if (e.matches) {
        setSideNavCollapsed(true)
        setMobileNavOpen(false)
      }
    }
    handleChange(mq)
    mq.addEventListener('change', handleChange)
    return () => mq.removeEventListener('change', handleChange)
  }, [])

  // Close mobile nav on Escape
  useEffect(() => {
    if (!mobileNavOpen) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileNavOpen(false)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [mobileNavOpen])

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ backgroundColor: 'var(--mars-color-bg)' }}>
      {/* Skip-to-content link (a11y) */}
      <a href="#mars-main-content" className="mars-skip-link">
        Skip to main content
      </a>

      {/* Top Bar with Chrome-style session tabs */}
      <TopBar
        onToggleMobileNav={() => setMobileNavOpen(prev => !prev)}
      />

      {/* Body: SideNav + Content */}
      <div className="flex-1 flex min-h-0">
        {/* Mobile overlay backdrop */}
        {mobileNavOpen && (
          <div
            className="fixed inset-0 bg-black/50 lg:hidden"
            style={{ zIndex: 'var(--mars-z-nav)' }}
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* SideNav */}
        <div
          className={`
            ${mobileNavOpen ? 'fixed inset-y-0 left-0 z-[350]' : 'hidden sm:block'}
          `}
          style={mobileNavOpen ? { top: 'var(--mars-topbar-height)' } : undefined}
        >
          <SideNav
            collapsed={sideNavCollapsed && !mobileNavOpen}
            onToggle={() => {
              if (mobileNavOpen) {
                setMobileNavOpen(false)
              } else {
                setSideNavCollapsed(prev => !prev)
              }
            }}
          />
        </div>

        {/* Content Area */}
        <main
          id="mars-main-content"
          role="main"
          className="flex-1 min-h-0 overflow-auto"
          style={{ backgroundColor: 'var(--mars-color-bg)' }}
        >
          {children}
        </main>
      </div>

      {/* Live region for screen reader announcements */}
      <div aria-live="polite" aria-atomic="true" className="mars-live-region" id="mars-live-announcements" />
    </div>
  )
}
