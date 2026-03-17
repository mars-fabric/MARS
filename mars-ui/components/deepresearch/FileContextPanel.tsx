'use client'

import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Brain, Send, Edit3, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/core'

interface FileContextPanelProps {
  fileContextOutput: string[]
  fileContextStatus: 'idle' | 'running' | 'done' | 'error'
  fileContext: string
  onRefine: (message: string, content: string) => Promise<string | null>
  onSave: (content: string) => Promise<void>
  onContextChange: (ctx: string) => void
}

export default function FileContextPanel({
  fileContextOutput,
  fileContextStatus,
  fileContext,
  onRefine,
  onSave,
  onContextChange,
}: FileContextPanelProps) {
  const [refineInput, setRefineInput] = useState('')
  const [isRefining, setIsRefining] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editDraft, setEditDraft] = useState(fileContext)
  const consoleEndRef = useRef<HTMLDivElement>(null)

  // Keep edit draft in sync when context arrives
  useEffect(() => {
    if (!isEditing) setEditDraft(fileContext)
  }, [fileContext, isEditing])

  // Auto-scroll console
  useEffect(() => {
    consoleEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [fileContextOutput])

  const handleRefine = useCallback(async () => {
    if (!refineInput.trim() || isRefining) return
    const msg = refineInput.trim()
    setRefineInput('')
    setIsRefining(true)
    await onRefine(msg, fileContext)
    setIsRefining(false)
  }, [refineInput, isRefining, fileContext, onRefine])

  const handleSaveEdit = useCallback(async () => {
    setIsSaving(true)
    await onSave(editDraft)
    onContextChange(editDraft)
    setIsEditing(false)
    setIsSaving(false)
  }, [editDraft, onSave, onContextChange])

  if (fileContextStatus === 'idle') return null

  return (
    <div
      className="rounded-mars-md border overflow-hidden"
      style={{
        borderColor: 'var(--mars-color-border)',
        backgroundColor: 'var(--mars-color-surface)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <Brain className="w-4 h-4" style={{ color: 'var(--mars-color-accent)' }} />
        <span className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
          Data Understanding
        </span>
        <div className="ml-auto flex items-center gap-2">
          {fileContextStatus === 'running' && (
            <span className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              Analyzing...
            </span>
          )}
          {fileContextStatus === 'running' && (
            <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: 'var(--mars-color-accent)' }} />
          )}
          {fileContextStatus === 'done' && (
            <CheckCircle className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-success)' }} />
          )}
          {fileContextStatus === 'error' && (
            <AlertCircle className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-danger)' }} />
          )}
        </div>
      </div>

      {/* Streaming console while running */}
      {fileContextStatus === 'running' && (
        <div
          className="p-3 font-mono text-xs max-h-48 overflow-y-auto space-y-0.5"
          style={{
            backgroundColor: 'var(--mars-color-surface-overlay, #0d1117)',
            color: 'var(--mars-color-text-secondary)',
          }}
        >
          {fileContextOutput.map((line, i) => (
            <div key={i} className="leading-relaxed">{line}</div>
          ))}
          {fileContextOutput.length === 0 && (
            <div style={{ color: 'var(--mars-color-text-tertiary)' }}>Initializing...</div>
          )}
          <div ref={consoleEndRef} />
        </div>
      )}

      {/* Error state */}
      {fileContextStatus === 'error' && (
        <div className="px-4 py-3">
          <p className="text-sm" style={{ color: 'var(--mars-color-danger)' }}>
            Analysis failed. Make sure files were uploaded successfully and try again.
          </p>
          {fileContextOutput.length > 0 && (
            <p className="text-xs mt-1 font-mono" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              {fileContextOutput[fileContextOutput.length - 1]}
            </p>
          )}
        </div>
      )}

      {/* Done: show editable context + refine chat */}
      {fileContextStatus === 'done' && (
        <div className="p-4 space-y-4">
          {/* Context display / edit */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span
                className="text-xs font-medium"
                style={{ color: 'var(--mars-color-text-secondary)' }}
              >
                Generated Research Data Context
              </span>
              <div className="flex items-center gap-2">
                {isEditing ? (
                  <>
                    <button
                      onClick={() => { setIsEditing(false); setEditDraft(fileContext) }}
                      className="text-xs px-2 py-1 rounded transition-colors"
                      style={{ color: 'var(--mars-color-text-tertiary)' }}
                    >
                      Cancel
                    </button>
                    <Button
                      onClick={handleSaveEdit}
                      disabled={isSaving}
                      size="sm"
                      variant="primary"
                    >
                      {isSaving ? 'Saving...' : 'Save'}
                    </Button>
                  </>
                ) : (
                  <button
                    onClick={() => { setIsEditing(true); setEditDraft(fileContext) }}
                    title="Edit context"
                    className="p-1 rounded transition-colors"
                    style={{ color: 'var(--mars-color-text-tertiary)' }}
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>

            {isEditing ? (
              <textarea
                value={editDraft}
                onChange={e => setEditDraft(e.target.value)}
                rows={12}
                className="w-full rounded-mars-sm border p-3 text-xs font-mono resize-y outline-none"
                style={{
                  backgroundColor: 'var(--mars-color-surface-overlay)',
                  borderColor: 'var(--mars-color-border)',
                  color: 'var(--mars-color-text)',
                }}
              />
            ) : (
              <div
                className="text-xs p-3 rounded-mars-sm max-h-64 overflow-y-auto whitespace-pre-wrap font-mono"
                style={{
                  backgroundColor: 'var(--mars-color-surface-overlay)',
                  color: 'var(--mars-color-text-secondary)',
                  borderColor: 'var(--mars-color-border)',
                  border: '1px solid var(--mars-color-border)',
                }}
              >
                {fileContext || 'No context generated.'}
              </div>
            )}
          </div>

          {/* Refine chat */}
          {!isEditing && (
            <div className="space-y-1">
              <span
                className="text-xs"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
              >
                Refine the context with a follow-up instruction:
              </span>
              <div className="flex gap-2">
                <input
                  value={refineInput}
                  onChange={e => setRefineInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleRefine()
                    }
                  }}
                  placeholder="e.g. 'Focus on the key variables', 'Add more detail about the data format', 'Summarise the scientific context'"
                  disabled={isRefining}
                  className="flex-1 rounded-mars-sm border px-3 py-2 text-sm outline-none transition-colors"
                  style={{
                    backgroundColor: 'var(--mars-color-surface)',
                    borderColor: 'var(--mars-color-border)',
                    color: 'var(--mars-color-text)',
                  }}
                />
                <Button
                  onClick={handleRefine}
                  disabled={!refineInput.trim() || isRefining}
                  size="sm"
                  variant="secondary"
                >
                  {isRefining ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Send className="w-3.5 h-3.5" />
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
