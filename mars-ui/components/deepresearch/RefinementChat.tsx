'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react'
import { Send, Check, Loader2 } from 'lucide-react'
import { Button } from '@/components/core'
import type { useDeepresearchTask } from '@/hooks/useDeepresearchTask'
import type { RefinementMessage } from '@/types/deepresearch'

interface RefinementChatProps {
  messages: RefinementMessage[]
  onSend: (message: string) => Promise<string | null>
  onApply: (content: string) => void
  isLoading?: boolean
}

export default function RefinementChat({ messages, onSend, onApply, isLoading }: RefinementChatProps) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = useCallback(async () => {
    if (!input.trim() || sending) return
    const msg = input.trim()
    setInput('')
    setSending(true)
    await onSend(msg)
    setSending(false)
  }, [input, sending, onSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="px-4 py-3 border-b flex-shrink-0"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <p
          className="text-sm font-medium"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Refinement Chat
        </p>
        <p
          className="text-xs"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          Ask the AI to modify or improve the content
        </p>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-3"
        style={{ minHeight: 0 }}
      >
        {messages.length === 0 && (
          <p
            className="text-xs text-center py-8"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            Ask the AI to refine the content. For example:
            &quot;Make the methodology section more specific&quot;
            or &quot;Focus on weak lensing approaches&quot;
          </p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className="max-w-[85%] rounded-mars-md px-3 py-2 text-xs"
              style={{
                backgroundColor: msg.role === 'user'
                  ? 'var(--mars-color-primary-subtle)'
                  : 'var(--mars-color-surface-overlay)',
                color: 'var(--mars-color-text)',
              }}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.role === 'assistant' && (
                <button
                  onClick={() => onApply(msg.content)}
                  className="mt-2 flex items-center gap-1 text-xs font-medium"
                  style={{ color: 'var(--mars-color-primary)' }}
                >
                  <Check className="w-3 h-3" />
                  Apply to editor
                </button>
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div
              className="rounded-mars-md px-3 py-2"
              style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
            >
              <Loader2
                className="w-4 h-4 animate-spin"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div
        className="px-4 py-3 border-t flex-shrink-0"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe how to refine..."
            rows={2}
            className="flex-1 rounded-mars-md border p-2 text-xs resize-none outline-none"
            style={{
              backgroundColor: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
            disabled={sending || isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sending}
            className="p-2 rounded-mars-md transition-colors"
            style={{
              backgroundColor: input.trim() ? 'var(--mars-color-primary)' : 'var(--mars-color-surface-overlay)',
              color: input.trim() ? 'white' : 'var(--mars-color-text-tertiary)',
              opacity: sending ? 0.5 : 1,
            }}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
