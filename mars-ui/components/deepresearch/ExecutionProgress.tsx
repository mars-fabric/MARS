'use client'

import React, { useRef, useEffect } from 'react'
import { Loader2 } from 'lucide-react'

interface ExecutionProgressProps {
  consoleOutput: string[]
  isExecuting: boolean
  stageName: string
}

export default function ExecutionProgress({ consoleOutput, isExecuting, stageName }: ExecutionProgressProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [consoleOutput])

  return (
    <div className="space-y-4">
      {/* Status indicator */}
      <div className="flex items-center gap-3">
        {isExecuting ? (
          <>
            <Loader2
              className="w-5 h-5 animate-spin"
              style={{ color: 'var(--mars-color-primary)' }}
            />
            <span
              className="text-sm font-medium"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Running {stageName}...
            </span>
          </>
        ) : (
          <span
            className="text-sm font-medium"
            style={{ color: 'var(--mars-color-success)' }}
          >
            {stageName} complete
          </span>
        )}
      </div>

      {/* Console output */}
      <div
        ref={scrollRef}
        className="rounded-mars-md border p-4 font-mono text-xs overflow-y-auto"
        style={{
          backgroundColor: 'var(--mars-color-surface)',
          borderColor: 'var(--mars-color-border)',
          color: 'var(--mars-color-text-secondary)',
          maxHeight: '400px',
          minHeight: '200px',
        }}
      >
        {consoleOutput.length === 0 ? (
          <p style={{ color: 'var(--mars-color-text-tertiary)' }}>
            Waiting for output...
          </p>
        ) : (
          consoleOutput.map((line, i) => (
            <div key={i} className="py-0.5">
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
