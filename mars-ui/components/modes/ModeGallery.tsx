'use client'

import { useState, useMemo } from 'react'
import { Search } from 'lucide-react'
import { MARS_MODES } from '@/lib/modes'
import ModeCard from './ModeCard'
import { EmptyState } from '@/components/core'

interface ModeGalleryProps {
  onLaunchMode: (modeId: string) => void
  onConfigureMode?: (modeId: string) => void
}

export default function ModeGallery({ onLaunchMode, onConfigureMode }: ModeGalleryProps) {
  const [searchQuery, setSearchQuery] = useState('')

  const visibleModes = useMemo(() => MARS_MODES.filter((m) => m.id !== 'copilot'), [])

  const filteredModes = useMemo(() => {
    if (!searchQuery.trim()) return visibleModes
    const q = searchQuery.toLowerCase()
    return visibleModes.filter(
      (m) =>
        m.displayName.toLowerCase().includes(q) ||
        m.description.toLowerCase().includes(q) ||
        m.tags.some((t) => t.toLowerCase().includes(q))
    )
  }, [searchQuery, visibleModes])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h2
          className="text-3xl font-bold mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Modes
        </h2>
        <p
          className="text-base mb-6"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Select an execution mode to start a new workflow
        </p>

        {/* Search */}
        <div className="relative max-w-md">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          />
          <input
            type="text"
            placeholder="Search modes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-mars-md border text-sm
              focus:outline-none focus:ring-2 focus:ring-[var(--mars-color-primary)]"
            style={{
              backgroundColor: 'var(--mars-color-surface-raised)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
          />
        </div>
      </div>

      {/* Grid */}
      {filteredModes.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredModes.map((mode) => (
            <ModeCard
              key={mode.id}
              mode={mode}
              onLaunch={onLaunchMode}
              onConfigure={onConfigureMode}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No modes found"
          description={`No modes match "${searchQuery}". Try a different search term.`}
          action={{
            label: 'Clear search',
            onClick: () => setSearchQuery(''),
          }}
        />
      )}
    </div>
  )
}
