'use client'

import { useState, useRef, useEffect, useMemo } from 'react'
import { Send, Bot, User, Loader2, StopCircle, Settings, ChevronDown, ChevronUp, Terminal, Code, Copy, Check, FolderOpen } from 'lucide-react'
import { ApprovalRequestedData } from '@/types/websocket-events'
import { CredentialsKeyIcon } from './CredentialsKeyIcon'
import { CredentialsModal } from './CredentialsModal'
import { useCredentials } from '../hooks/useCredentials'
import { SessionList } from './SessionManager/SessionList'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  status?: 'pending' | 'complete' | 'error'
}

interface CopilotViewProps {
  consoleOutput: string[]
  isRunning: boolean
  onSendMessage: (message: string) => void
  onStop: () => void
  onClearSession?: () => void  // Optional: clear session and start fresh
  onResumeSession?: (sessionId: string) => void  // Resume a saved session
  pendingApproval: ApprovalRequestedData | null
  onApprovalResolve: (resolution: string, feedback?: string, modifications?: string) => void
  messages?: Message[]
  config?: {
    enablePlanning: boolean
    approvalMode: string
    autoApproveSimple: boolean
    maxPlanSteps: number
    model: string
    researcherModel: string
    plannerModel: string
    toolApproval?: string
    intelligentRouting?: string
  }
  onConfigChange?: (config: any) => void
}

// Code block component with syntax highlighting and copy button
function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative my-2 rounded-lg overflow-hidden bg-gray-900 border border-gray-700">
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 border-b border-gray-700">
        <span className="text-xs text-gray-400 font-mono">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="p-1 text-gray-400 hover:text-white transition-colors"
          title="Copy code"
        >
          {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
        </button>
      </div>
      <pre className="p-3 overflow-x-auto text-sm">
        <code className="text-gray-300 font-mono whitespace-pre">{code}</code>
      </pre>
    </div>
  )
}

// Parse message content for code blocks and format
function FormattedMessage({ content }: { content: string }) {
  const parts = useMemo(() => {
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g
    const segments: Array<{ type: 'text' | 'code'; content: string; language?: string }> = []
    let lastIndex = 0
    let match

    while ((match = codeBlockRegex.exec(content)) !== null) {
      // Add text before code block
      if (match.index > lastIndex) {
        segments.push({ type: 'text', content: content.slice(lastIndex, match.index) })
      }
      // Add code block
      segments.push({ type: 'code', content: match[2], language: match[1] })
      lastIndex = match.index + match[0].length
    }

    // Add remaining text
    if (lastIndex < content.length) {
      segments.push({ type: 'text', content: content.slice(lastIndex) })
    }

    return segments.length > 0 ? segments : [{ type: 'text' as const, content }]
  }, [content])

  return (
    <div className="space-y-1">
      {parts.map((part, idx) =>
        part.type === 'code' ? (
          <CodeBlock key={idx} code={part.content} language={part.language} />
        ) : (
          <p key={idx} className="text-sm whitespace-pre-wrap">{part.content}</p>
        )
      )}
    </div>
  )
}

// Log line formatter with colors and icons
function LogLine({ line, index }: { line: string; index: number }) {
  const getLogStyle = (text: string) => {
    const lowerText = text.toLowerCase()
    if (lowerText.includes('error') || lowerText.includes('failed') || lowerText.includes('exception')) {
      return { color: 'text-red-400', icon: '❌', bg: 'bg-red-500/10' }
    }
    if (lowerText.includes('success') || lowerText.includes('completed') || lowerText.includes('done') || lowerText.includes('✅')) {
      return { color: 'text-green-400', icon: '✅', bg: 'bg-green-500/10' }
    }
    if (lowerText.includes('warning') || lowerText.includes('⚠')) {
      return { color: 'text-yellow-400', icon: '⚠️', bg: 'bg-yellow-500/10' }
    }
    if (lowerText.includes('running') || lowerText.includes('processing') || lowerText.includes('executing')) {
      return { color: 'text-blue-400', icon: '🔄', bg: 'bg-blue-500/10' }
    }
    if (text.startsWith('>') || text.startsWith('$')) {
      return { color: 'text-cyan-400', icon: '>', bg: 'bg-cyan-500/5' }
    }
    if (text.includes('📊') || text.includes('DAG') || text.includes('workflow')) {
      return { color: 'text-purple-400', icon: '📊', bg: '' }
    }
    if (text.includes('🚀') || text.includes('started')) {
      return { color: 'text-blue-300', icon: '🚀', bg: '' }
    }
    return { color: 'text-gray-400', icon: '', bg: '' }
  }

  const style = getLogStyle(line)

  return (
    <div className={`py-0.5 px-1 rounded ${style.bg} ${style.color} text-xs font-mono truncate`}>
      {line}
    </div>
  )
}

export function CopilotView({
  consoleOutput,
  isRunning,
  onSendMessage,
  onStop,  onClearSession,  onResumeSession,  pendingApproval,
  onApprovalResolve,
  messages = [],
  config,
  onConfigChange,
}: CopilotViewProps) {
  const [inputValue, setInputValue] = useState('')
  const [showLogs, setShowLogs] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [showSessions, setShowSessions] = useState(false)
  const [showCredentialsModal, setShowCredentialsModal] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const logsRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Use credentials hook
  const {
    refreshKey,
    handleStatusChange,
    refreshCredentials,
  } = useCredentials()

  // Auto-scroll logs
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight
    }
  }, [consoleOutput])

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input when not running and no pending approval
  useEffect(() => {
    if (!isRunning && !pendingApproval && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isRunning, pendingApproval])

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault()
    if (inputValue.trim() && !isRunning) {
      onSendMessage(inputValue.trim())
      setInputValue('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleSubmit()
    }
  }

  // Handle approval for chat input type
  const handleApprovalSubmit = () => {
    if (pendingApproval && inputValue.trim()) {
      onApprovalResolve('submit', inputValue.trim())
      setInputValue('')
    }
  }

  const handleApprovalExit = () => {
    if (pendingApproval) {
      onApprovalResolve('exit')
    }
  }

  const isChatInput = pendingApproval?.checkpoint_type === 'chat_input' ||
                      pendingApproval?.checkpoint_type === 'next_task' ||
                      pendingApproval?.context?.requires_text_input === true

  const handleResumeSession = async (sessionId: string) => {
    if (onResumeSession) {
      onResumeSession(sessionId)
      setShowSessions(false)
    }
  }

  // Filter recent logs (last 50 for performance)
  const recentLogs = consoleOutput.slice(-50)

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header - Compact */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-700 bg-gray-800/50 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-purple-400" />
          <span className="font-medium text-sm text-white">Copilot</span>
          {isRunning && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 text-xs bg-green-500/20 text-green-400 rounded-full">
              <Loader2 className="w-3 h-3 animate-spin" />
              Running
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className={`p-1 rounded transition-colors ${showLogs ? 'text-purple-400 bg-purple-500/20' : 'text-gray-400 hover:text-white'}`}
            title={showLogs ? 'Hide logs' : 'Show logs'}
          >
            <Terminal className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowSessions(!showSessions)}
            className={`p-1 rounded transition-colors ${showSessions ? 'text-purple-400 bg-purple-500/20' : 'text-gray-400 hover:text-white'}`}
            title="Saved Sessions"
          >
            <FolderOpen className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-1 rounded transition-colors ${showSettings ? 'text-purple-400 bg-purple-500/20' : 'text-gray-400 hover:text-white'}`}
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
          <CredentialsKeyIcon
            refreshKey={refreshKey}
            onOpenCredentialsModal={() => setShowCredentialsModal(true)}
            onStatusChange={handleStatusChange}
          />
          {isRunning && (
            <button
              onClick={onStop}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-red-600 hover:bg-red-700 text-white rounded transition-colors"
            >
              <StopCircle className="w-3 h-3" />
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Settings Panel - Compact */}
      {showSettings && config && onConfigChange && (
        <div className="px-3 py-2 border-b border-gray-700 bg-gray-800/30 flex-shrink-0">
          <div className="grid grid-cols-6 gap-2 text-xs">
            <div>
              <label className="block text-gray-400 mb-0.5">Planning</label>
              <select
                value={config.enablePlanning ? 'true' : 'false'}
                onChange={(e) => onConfigChange({ ...config, enablePlanning: e.target.value === 'true' })}
                className="w-full px-1.5 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs"
              >
                <option value="true">On</option>
                <option value="false">Off</option>
              </select>
            </div>
            <div>
              <label className="block text-gray-400 mb-0.5">Approval</label>
              <select
                value={config.approvalMode}
                onChange={(e) => onConfigChange({ ...config, approvalMode: e.target.value })}
                className="w-full px-1.5 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs"
              >
                <option value="after_step">After</option>
                <option value="before_step">Before</option>
                <option value="both">Both</option>
                <option value="none">None</option>
              </select>
            </div>
            <div>
              <label className="block text-gray-400 mb-0.5">Max Steps</label>
              <input
                type="number"
                value={config.maxPlanSteps}
                onChange={(e) => onConfigChange({ ...config, maxPlanSteps: parseInt(e.target.value) })}
                className="w-full px-1.5 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs"
                min="1"
                max="10"
              />
            </div>
            <div>
              <label className="block text-gray-400 mb-0.5">Auto-approve</label>
              <select
                value={config.autoApproveSimple ? 'true' : 'false'}
                onChange={(e) => onConfigChange({ ...config, autoApproveSimple: e.target.value === 'true' })}
                className="w-full px-1.5 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs"
              >
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </div>
            <div>
              <label className="block text-gray-400 mb-0.5">Tool Approval</label>
              <select
                value={config.toolApproval || 'none'}
                onChange={(e) => onConfigChange({ ...config, toolApproval: e.target.value })}
                className="w-full px-1.5 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs"
              >
                <option value="none">None</option>
                <option value="prompt">Prompt</option>
                <option value="auto_allow_all">Auto Allow</option>
              </select>
            </div>
            <div>
              <label className="block text-gray-400 mb-0.5">Intelligence</label>
              <select
                value={config.intelligentRouting || 'balanced'}
                onChange={(e) => onConfigChange({ ...config, intelligentRouting: e.target.value })}
                className="w-full px-1.5 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs"
              >
                <option value="aggressive">Cautious</option>
                <option value="balanced">Balanced</option>
                <option value="minimal">Direct</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Sessions Panel */}
      {showSessions && (
        <div className="flex-shrink-0 border-b border-gray-700 p-3 bg-gray-800/30" style={{ maxHeight: '300px', overflowY: 'auto' }}>
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-sm font-bold text-white">Saved Sessions</h2>
            <button
              onClick={() => setShowSessions(false)}
              className="text-xs text-gray-400 hover:text-white transition-colors"
            >
              Close
            </button>
          </div>
          <SessionList
            onResume={handleResumeSession}
            modeFilter="copilot"
          />
        </div>
      )}

      {/* Logs Panel - Compact and collapsible, max 20% height */}
      {showLogs && recentLogs.length > 0 && (
        <div className="flex-shrink-0 border-b border-gray-700" style={{ maxHeight: '120px' }}>
          <div
            ref={logsRef}
            className="h-full overflow-y-auto p-2 bg-black/40"
          >
            {recentLogs.map((line, index) => (
              <LogLine key={index} line={line} index={index} />
            ))}
          </div>
        </div>
      )}

      {/* Chat Messages Area - Takes most space */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
        {messages.length === 0 && !pendingApproval && !isRunning ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot className="w-12 h-12 text-purple-400/50 mb-3" />
            <h3 className="text-base font-medium text-gray-300 mb-1">Copilot Ready</h3>
            <p className="text-xs text-gray-500 max-w-sm mb-4">
              Describe what you'd like to accomplish. I can write code, analyze data, and help with research.
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-md">
              {[
                'Analyze a dataset',
                'Write a Python script',
                'Create visualizations',
                'Research a topic',
                'Debug my code',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInputValue(suggestion)}
                  className="px-2.5 py-1 text-xs bg-purple-600/20 text-purple-300 rounded-full hover:bg-purple-600/30 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-2 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
                    message.role === 'user'
                      ? 'bg-blue-600'
                      : message.role === 'system'
                      ? 'bg-gray-600'
                      : 'bg-purple-600'
                  }`}
                >
                  {message.role === 'user' ? (
                    <User className="w-3.5 h-3.5 text-white" />
                  ) : (
                    <Bot className="w-3.5 h-3.5 text-white" />
                  )}
                </div>
                <div
                  className={`flex-1 max-w-[85%] ${
                    message.role === 'user' ? 'text-right' : ''
                  }`}
                >
                  <div
                    className={`inline-block px-3 py-2 rounded-lg text-left ${
                      message.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : message.role === 'system'
                        ? 'bg-gray-700 text-gray-300'
                        : 'bg-gray-800 text-gray-200 border border-gray-700'
                    }`}
                  >
                    <FormattedMessage content={message.content} />
                  </div>
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    {message.timestamp.toLocaleTimeString()}
                    {message.status === 'pending' && (
                      <Loader2 className="w-3 h-3 inline ml-1 animate-spin" />
                    )}
                  </p>
                </div>
              </div>
            ))}

            {/* Pending Approval Message */}
            {pendingApproval && !isChatInput && (
              <div className="flex gap-2">
                <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 bg-yellow-600">
                  <Bot className="w-3.5 h-3.5 text-white" />
                </div>
                <div className="flex-1">
                  <div className="bg-yellow-900/30 border border-yellow-600/50 rounded-lg p-3">
                    <p className="text-sm text-yellow-200 mb-2">
                      {pendingApproval.description || pendingApproval.message || 'Approval required'}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {(pendingApproval.options || ['approve', 'reject']).map((option) => (
                        <button
                          key={option}
                          onClick={() => onApprovalResolve(option)}
                          className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                            option === 'approve' || option === 'approved' || option === 'continue'
                              ? 'bg-green-600 hover:bg-green-700 text-white'
                              : option === 'reject' || option === 'rejected' || option === 'abort'
                              ? 'bg-red-600 hover:bg-red-700 text-white'
                              : 'bg-gray-600 hover:bg-gray-700 text-white'
                          }`}
                        >
                          {option.charAt(0).toUpperCase() + option.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Running indicator */}
            {isRunning && !pendingApproval && (
              <div className="flex gap-2">
                <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 bg-purple-600">
                  <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
                </div>
                <div className="flex-1">
                  <div className="bg-purple-900/20 border border-purple-600/30 rounded-lg px-3 py-2">
                    <p className="text-sm text-purple-300 flex items-center gap-2">
                      <span className="inline-block w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" />
                      Processing your request...
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area - Fixed at bottom */}
      <div className="flex-shrink-0 border-t border-gray-700 bg-gray-800/50 p-3">
        {isChatInput ? (
          /* Chat input mode for pending approval */
          <div className="space-y-2">
            <div className="text-xs text-gray-400">
              {pendingApproval?.message || pendingApproval?.description || 'Enter your next task:'}
            </div>
            <div className="flex gap-2">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && inputValue.trim()) {
                    handleApprovalSubmit()
                  }
                }}
                placeholder={pendingApproval?.context?.input_placeholder || "Enter your next task..."}
                className="flex-1 px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                rows={2}
                autoFocus
              />
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-gray-500">⌘/Ctrl+Enter to submit</span>
              <div className="flex gap-2">
                <button
                  onClick={handleApprovalExit}
                  className="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors"
                >
                  Exit
                </button>
                <button
                  onClick={handleApprovalSubmit}
                  disabled={!inputValue.trim()}
                  className={`px-3 py-1.5 text-xs rounded-lg font-medium flex items-center gap-1.5 transition-colors ${
                    inputValue.trim()
                      ? 'bg-purple-600 hover:bg-purple-700 text-white'
                      : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                  }`}
                >
                  <Send className="w-3.5 h-3.5" />
                  Send
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* Normal input mode */
          <form onSubmit={handleSubmit} className="flex gap-2">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isRunning ? "Waiting for response..." : "What would you like to do?"}
              className="flex-1 px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
              rows={2}
              disabled={isRunning || !!pendingApproval}
            />
            <button
              type="submit"
              disabled={!inputValue.trim() || isRunning || !!pendingApproval}
              className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors ${
                inputValue.trim() && !isRunning && !pendingApproval
                  ? 'bg-purple-600 hover:bg-purple-700 text-white'
                  : 'bg-gray-700 text-gray-500 cursor-not-allowed'
              }`}
            >
              {isRunning ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </form>
        )}
      </div>

      {/* Credentials Modal */}
      <CredentialsModal
        isOpen={showCredentialsModal}
        onClose={() => setShowCredentialsModal(false)}
        onCredentialsUpdated={() => {
          refreshCredentials()
        }}
      />
    </div>
  )
}
