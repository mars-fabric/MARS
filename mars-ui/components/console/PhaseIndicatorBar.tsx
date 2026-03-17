'use client'

import type { PhaseType } from '@/types/console'

interface PhaseIndicatorBarProps {
  phase: PhaseType
  active?: boolean
}

const phaseLabels: Record<PhaseType, string> = {
  planning: 'Planning',
  analyzing: 'Analyzing',
  executing: 'Executing',
  reviewing: 'Reviewing',
  completing: 'Completing',
}

export default function PhaseIndicatorBar({ phase, active = false }: PhaseIndicatorBarProps) {
  return (
    <div
      className={`mars-phase-indicator ${active ? 'mars-phase-active' : ''}`}
      role="status"
      aria-label={`Phase: ${phaseLabels[phase]}`}
    >
      <span className="mars-phase-dot" />
      <span>{phaseLabels[phase]}</span>
    </div>
  )
}
