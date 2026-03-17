'use client'

import { Sun, Moon, Menu } from 'lucide-react'
import { ConnectionStatus } from '@/components/common/ConnectionStatus'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { useTheme } from '@/contexts/ThemeContext'

interface TopBarProps {
  onToggleMobileNav?: () => void
}

export default function TopBar({ onToggleMobileNav }: TopBarProps) {
  const { connected, reconnectAttempt, lastError, reconnect } = useWebSocketContext()
  const { theme, toggleTheme } = useTheme()

  return (
    <header
      className="flex flex-col flex-shrink-0 border-b"
      style={{
        backgroundColor: 'var(--mars-color-surface-raised)',
        borderColor: 'var(--mars-color-border)',
      }}
      role="banner"
    >
      {/* Top row: Logo + Actions */}
      <div
        className="flex items-center justify-between px-4"
        style={{ height: '44px' }}
      >
        {/* Left: Logo + Mobile menu */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {onToggleMobileNav && (
            <button
              onClick={onToggleMobileNav}
              className="p-2 rounded-mars-md transition-colors duration-mars-fast
                hover:bg-[var(--mars-color-bg-hover)] sm:hidden"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              aria-label="Toggle navigation menu"
            >
              <Menu className="w-5 h-5" />
            </button>
          )}
          <h1
            className="text-base font-bold"
            style={{ color: 'var(--mars-color-text)', fontFamily: 'var(--mars-font-sans)' }}
          >
            MARS
          </h1>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
          <button
            onClick={toggleTheme}
            className="p-2 rounded-mars-md transition-colors duration-mars-fast
              hover:bg-[var(--mars-color-bg-hover)]"
            style={{ color: 'var(--mars-color-text-secondary)' }}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            title={`${theme === 'dark' ? 'Light' : 'Dark'} mode`}
          >
            {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>

          <ConnectionStatus
            connected={connected}
            reconnectAttempt={reconnectAttempt}
            lastError={lastError}
            onReconnect={reconnect}
          />
        </div>
      </div>
    </header>
  )
}
