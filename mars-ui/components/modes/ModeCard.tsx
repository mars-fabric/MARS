'use client'

import { ModeConfig } from '@/lib/modes'
import * as LucideIcons from 'lucide-react'

interface ModeCardProps {
  mode: ModeConfig
  onLaunch: (modeId: string) => void
  onConfigure?: (modeId: string) => void
}

export default function ModeCard({ mode, onLaunch, onConfigure }: ModeCardProps) {
  const Icon = (LucideIcons as any)[mode.icon] || LucideIcons.Box

  return (
    <div
      className="group relative overflow-hidden rounded-mars-lg border transition-all duration-mars-normal
        hover:shadow-mars-lg hover:scale-[1.02] hover:border-[var(--mars-color-border-strong)]
        cursor-pointer"
      style={{
        backgroundColor: 'var(--mars-color-surface-raised)',
        borderColor: 'var(--mars-color-border)',
      }}
      onClick={() => onLaunch(mode.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onLaunch(mode.id)
        }
      }}
      aria-label={`Launch ${mode.displayName}`}
    >
      {/* Gradient overlay on hover */}
      <div
        className={`absolute inset-0 bg-gradient-to-br ${mode.color} opacity-0 group-hover:opacity-5 transition-opacity duration-mars-normal`}
      />

      <div className="relative p-6">
        {/* Icon */}
        <div
          className={`w-12 h-12 rounded-mars-md bg-gradient-to-br ${mode.color} flex items-center justify-center mb-4
            group-hover:scale-110 transition-transform duration-mars-normal`}
        >
          <Icon className="w-6 h-6 text-white" />
        </div>

        {/* Title */}
        <h3
          className="text-lg font-semibold mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          {mode.displayName}
        </h3>

        {/* Description */}
        <p
          className="text-sm mb-4 line-clamp-2"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          {mode.description}
        </p>

        {/* Tags */}
        <div className="flex flex-wrap gap-2 mb-4">
          {mode.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 text-xs rounded-mars-sm"
              style={{
                backgroundColor: 'var(--mars-color-primary-subtle)',
                color: 'var(--mars-color-primary-text)',
              }}
            >
              {tag}
            </span>
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <button
            className="text-sm font-medium px-4 py-2 rounded-mars-md transition-colors duration-mars-fast
              hover:opacity-90"
            style={{
              backgroundColor: 'var(--mars-color-primary)',
              color: 'white',
            }}
            onClick={(e) => {
              e.stopPropagation()
              onLaunch(mode.id)
            }}
          >
            Launch
          </button>
          {onConfigure && (
            <button
              className="text-sm px-3 py-2 rounded-mars-md transition-colors duration-mars-fast
                hover:bg-[var(--mars-color-bg-hover)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              onClick={(e) => {
                e.stopPropagation()
                onConfigure(mode.id)
              }}
            >
              Configure
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
