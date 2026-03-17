'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, CheckCircle, XCircle, Edit3, RefreshCw, MessageSquare, ChevronDown, ChevronUp } from 'lucide-react'
import { ApprovalRequestedData } from '@/types/websocket-events'

interface ApprovalChatPanelProps {
  approval: ApprovalRequestedData | null
  onResolve: (resolution: string, feedback?: string, modifications?: string) => void
  isExpanded?: boolean
  onToggleExpand?: () => void
}

const OPTION_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string; description: string }> = {
  approve: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'bg-green-600 hover:bg-green-700 border-green-500',
    label: 'Approve',
    description: 'Accept and proceed with execution'
  },
  approved: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'bg-green-600 hover:bg-green-700 border-green-500',
    label: 'Approve',
    description: 'Accept and proceed with execution'
  },
  continue: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'bg-green-600 hover:bg-green-700 border-green-500',
    label: 'Continue',
    description: 'Continue to next step'
  },
  // Tool approval options
  allow: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'bg-green-600 hover:bg-green-700 border-green-500',
    label: 'Allow Once',
    description: 'Allow this operation once'
  },
  allow_session: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'bg-emerald-600 hover:bg-emerald-700 border-emerald-500',
    label: 'Allow for Session',
    description: 'Auto-approve this tool type for the rest of this session'
  },
  deny: {
    icon: <XCircle className="w-4 h-4" />,
    color: 'bg-red-600 hover:bg-red-700 border-red-500',
    label: 'Deny',
    description: 'Block this operation'
  },
  edit: {
    icon: <Edit3 className="w-4 h-4" />,
    color: 'bg-blue-600 hover:bg-blue-700 border-blue-500',
    label: 'Edit',
    description: 'Modify the operation'
  },
  submit: {
    icon: <Send className="w-4 h-4" />,
    color: 'bg-blue-600 hover:bg-blue-700 border-blue-500',
    label: 'Submit',
    description: 'Submit your input'
  },
  exit: {
    icon: <XCircle className="w-4 h-4" />,
    color: 'bg-gray-600 hover:bg-gray-700 border-gray-500',
    label: 'Exit',
    description: 'End the session'
  },
  reject: {
    icon: <XCircle className="w-4 h-4" />,
    color: 'bg-red-600 hover:bg-red-700 border-red-500',
    label: 'Reject',
    description: 'Cancel the workflow'
  },
  rejected: {
    icon: <XCircle className="w-4 h-4" />,
    color: 'bg-red-600 hover:bg-red-700 border-red-500',
    label: 'Reject',
    description: 'Cancel the workflow'
  },
  abort: {
    icon: <XCircle className="w-4 h-4" />,
    color: 'bg-red-600 hover:bg-red-700 border-red-500',
    label: 'Abort',
    description: 'Stop the workflow'
  },
  revise: {
    icon: <RefreshCw className="w-4 h-4" />,
    color: 'bg-yellow-600 hover:bg-yellow-700 border-yellow-500',
    label: 'Revise',
    description: 'Provide feedback for revision'
  },
  redo: {
    icon: <RefreshCw className="w-4 h-4" />,
    color: 'bg-yellow-600 hover:bg-yellow-700 border-yellow-500',
    label: 'Redo',
    description: 'Repeat this step'
  },
  modify: {
    icon: <Edit3 className="w-4 h-4" />,
    color: 'bg-blue-600 hover:bg-blue-700 border-blue-500',
    label: 'Modify',
    description: 'Edit the plan directly'
  },
  modified: {
    icon: <Edit3 className="w-4 h-4" />,
    color: 'bg-blue-600 hover:bg-blue-700 border-blue-500',
    label: 'Modify',
    description: 'Edit the plan directly'
  },
  skip: {
    icon: <RefreshCw className="w-4 h-4" />,
    color: 'bg-gray-600 hover:bg-gray-700 border-gray-500',
    label: 'Skip',
    description: 'Skip this step'
  },
  // Proposal options
  option_1: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'bg-blue-600 hover:bg-blue-700 border-blue-500',
    label: 'Option 1',
    description: 'Quick & Direct approach'
  },
  option_2: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'bg-purple-600 hover:bg-purple-700 border-purple-500',
    label: 'Option 2',
    description: 'Planned & Thorough approach'
  },
  option_3: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'bg-cyan-600 hover:bg-cyan-700 border-cyan-500',
    label: 'Option 3',
    description: 'Research First approach'
  },
  custom: {
    icon: <Edit3 className="w-4 h-4" />,
    color: 'bg-amber-600 hover:bg-amber-700 border-amber-500',
    label: 'Custom',
    description: 'Describe your own approach'
  }
}

export function ApprovalChatPanel({ approval, onResolve, isExpanded = true, onToggleExpand }: ApprovalChatPanelProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [feedback, setFeedback] = useState('')
  const [modifications, setModifications] = useState('')
  const [showContext, setShowContext] = useState(false)
  const feedbackRef = useRef<HTMLTextAreaElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // Reset state when approval changes
  useEffect(() => {
    setSelectedOption(null)
    setFeedback('')
    setModifications('')
    setShowContext(false)
  }, [approval?.approval_id])

  // Auto-focus feedback when option is selected
  useEffect(() => {
    if (selectedOption && feedbackRef.current) {
      feedbackRef.current.focus()
    }
  }, [selectedOption])

  // Scroll panel into view when approval appears
  useEffect(() => {
    if (approval && panelRef.current) {
      panelRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }, [approval])

  if (!approval) return null

  const options = approval.options || ['approve', 'reject', 'modify']

  const handleSubmit = () => {
    if (!selectedOption) return
    onResolve(selectedOption, feedback || undefined, modifications || undefined)
    setSelectedOption(null)
    setFeedback('')
    setModifications('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && selectedOption) {
      handleSubmit()
    }
  }

  const getCheckpointTitle = (type?: string) => {
    switch (type) {
      case 'after_planning':
        return '📋 Plan Review Required'
      case 'before_step':
        return '⏳ Step Approval Required'
      case 'after_step':
        return '✅ Step Review Required'
      case 'on_error':
        return '⚠️ Error Recovery'
      case 'manual_pause':
        return '⏸️ Manual Pause'
      case 'ag2_dynamic':
        return '🤖 Agent Requesting Input'
      case 'tool_approval':
        return '🔧 Tool Approval Required'
      case 'clarification':
        return '❓ Quick Question'
      case 'proposal':
        return '💡 Choose an Approach'
      case 'chat_input':
      case 'next_task':
        return '💬 Your Turn'
      case 'copilot_turn':
        return '💬 Your Turn'
      case 'copilot_proposal':
        return '🤖 Copilot Proposal'
      case 'copilot_result':
        return '📊 Results Ready'
      default:
        return '🔔 Approval Required'
    }
  }

  // Check if this is a chat input type (requires primary text input)
  const isChatInput = approval.checkpoint_type === 'chat_input' ||
                      approval.checkpoint_type === 'next_task' ||
                      approval.checkpoint_type === 'clarification' ||
                      approval.checkpoint_type === 'copilot_turn' ||
                      approval.context?.requires_text_input === true

  const formatContext = (context: Record<string, any>) => {
    if (!context) return null

    // Handle tool approval context specially
    if (context.tool_category) {
      const categoryLabels: Record<string, { icon: string; label: string; color: string }> = {
        bash: { icon: '💻', label: 'Shell Command', color: 'bg-orange-500/20 text-orange-300 border-orange-500/50' },
        code_exec: { icon: '🐍', label: 'Code Execution', color: 'bg-blue-500/20 text-blue-300 border-blue-500/50' },
        file_write: { icon: '📝', label: 'File Write', color: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/50' },
        install: { icon: '📦', label: 'Package Install', color: 'bg-purple-500/20 text-purple-300 border-purple-500/50' },
        web: { icon: '🌐', label: 'Web Request', color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50' },
      }
      const catInfo = categoryLabels[context.tool_category] || { 
        icon: '🔧', 
        label: context.tool_category, 
        color: 'bg-gray-500/20 text-gray-300 border-gray-500/50' 
      }
      
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${catInfo.color}`}>
              <span>{catInfo.icon}</span>
              {catInfo.label}
            </span>
            {context.agent_name && context.agent_name !== 'unknown' && (
              <span className="text-xs text-gray-500">from {context.agent_name}</span>
            )}
          </div>
          {context.prompt && (
            <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50">
              <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono overflow-auto max-h-48">
                {context.prompt}
              </pre>
            </div>
          )}
          {context.can_auto_allow && (
            <div className="text-xs text-gray-500 italic">
              💡 Tip: Click "Allow for Session" to auto-approve future {catInfo.label.toLowerCase()} operations
            </div>
          )}
        </div>
      )
    }

    // Handle proposals display
    if (context.proposals && Array.isArray(context.proposals)) {
      return (
        <div className="space-y-3">
          <div className="text-sm font-medium text-gray-300">💡 Suggested Approaches:</div>
          <div className="space-y-3">
            {context.proposals.map((proposal: any, idx: number) => {
              const title = proposal.title || `Option ${idx + 1}`
              const description = proposal.description || ''
              const pros = proposal.pros || []
              const cons = proposal.cons || []

              return (
                <div key={idx} className="bg-gray-800/30 rounded-lg p-3 border border-gray-700/50">
                  <div className="flex items-start gap-2">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600/30 text-blue-300 text-xs flex items-center justify-center font-medium">
                      {idx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-200">{title}</div>
                      {description && (
                        <div className="text-sm text-gray-400 mt-1">{description}</div>
                      )}
                      {pros.length > 0 && (
                        <div className="mt-2 text-xs text-green-400">
                          ✅ {pros.join(' • ')}
                        </div>
                      )}
                      {cons.length > 0 && (
                        <div className="mt-1 text-xs text-yellow-400">
                          ⚠️ {cons.join(' • ')}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
          <div className="text-xs text-gray-500 italic">
            Select an option above or describe your own approach
          </div>
        </div>
      )
    }

    // Handle clarification questions
    if (context.questions && Array.isArray(context.questions)) {
      return (
        <div className="space-y-3">
          <div className="text-sm font-medium text-gray-300">❓ Questions:</div>
          <ol className="space-y-2">
            {context.questions.map((question: string, idx: number) => (
              <li key={idx} className="bg-gray-800/30 rounded-lg p-2 border border-gray-700/50 text-sm text-gray-300">
                {idx + 1}. {question}
              </li>
            ))}
          </ol>
        </div>
      )
    }
    
    // Handle plan display specially
    if (context.plan && Array.isArray(context.plan)) {
      return (
        <div className="space-y-3">
          <div className="text-sm font-medium text-gray-300">📋 Plan Steps:</div>
          <ol className="space-y-2">
            {context.plan.map((step: any, idx: number) => {
              // Extract step info - handle different field names
              const subTask = typeof step === 'string' 
                ? step 
                : step.sub_task || step.description || step.name || step.task || JSON.stringify(step)
              const agent = step.sub_task_agent || step.agent || ''
              const bulletPoints = step.bullet_points || step.instructions || []
              
              return (
                <li key={idx} className="bg-gray-800/30 rounded-lg p-3 border border-gray-700/50">
                  <div className="flex items-start gap-2">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600/30 text-blue-300 text-xs flex items-center justify-center font-medium">
                      {idx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-gray-200">{subTask}</div>
                      {agent && (
                        <div className="text-xs text-gray-500 mt-1">Agent: {agent}</div>
                      )}
                      {bulletPoints.length > 0 && (
                        <ul className="mt-2 space-y-1">
                          {bulletPoints.slice(0, 3).map((bp: string, bpIdx: number) => (
                            <li key={bpIdx} className="text-xs text-gray-400 flex items-start gap-1">
                              <span className="text-gray-600">•</span>
                              <span>{bp}</span>
                            </li>
                          ))}
                          {bulletPoints.length > 3 && (
                            <li className="text-xs text-gray-500 italic">
                              ...and {bulletPoints.length - 3} more instructions
                            </li>
                          )}
                        </ul>
                      )}
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>
        </div>
      )
    }

    // Generic context display
    return (
      <pre className="text-xs text-gray-400 overflow-auto max-h-40 whitespace-pre-wrap">
        {JSON.stringify(context, null, 2)}
      </pre>
    )
  }

  return (
    <div 
      ref={panelRef}
      className="border-t border-blue-500/30 bg-gradient-to-b from-blue-900/20 to-gray-900/50 flex flex-col max-h-[60vh]"
    >
      {/* Header */}
      <div 
        className="flex items-center justify-between px-4 py-2 bg-blue-600/20 cursor-pointer hover:bg-blue-600/30 transition-colors flex-shrink-0"
        onClick={onToggleExpand}
      >
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-blue-300">
            {getCheckpointTitle(approval.checkpoint_type)}
          </span>
          <span className="px-2 py-0.5 text-xs bg-blue-500/30 text-blue-200 rounded-full animate-pulse">
            Waiting for response
          </span>
        </div>
        {onToggleExpand && (
          isExpanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronUp className="w-4 h-4 text-gray-400" />
        )}
      </div>

      {isExpanded && (
        <div className="flex flex-col flex-1 min-h-0">
          {/* Scrollable content area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
            {/* Message from agent */}
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-white">AI</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
                  <p className="text-sm text-gray-200 whitespace-pre-wrap">
                    {approval.description || approval.message || approval.action || 'Please review and approve to continue.'}
                  </p>
                </div>
                
                {/* Show plan prominently if present */}
                {approval.context?.plan && Array.isArray(approval.context.plan) && approval.context.plan.length > 0 && (
                  <div className="mt-3">
                    {formatContext(approval.context)}
                  </div>
                )}
                
                {/* Context toggle for non-plan data */}
                {approval.context && Object.keys(approval.context).filter(k => k !== 'plan').length > 0 && (
                  <div className="mt-2">
                    <button
                      onClick={() => setShowContext(!showContext)}
                      className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    >
                      {showContext ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      {showContext ? 'Hide' : 'View'} additional details
                    </button>
                    {showContext && (
                      <div className="mt-2 bg-gray-800/30 rounded-md p-3 border border-gray-700/50">
                        <pre className="text-xs text-gray-400 overflow-auto max-h-40 whitespace-pre-wrap">
                          {JSON.stringify(
                            Object.fromEntries(Object.entries(approval.context).filter(([k]) => k !== 'plan')),
                            null,
                            2
                          )}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Fixed bottom section - Options and feedback */}
          <div className="flex-shrink-0 border-t border-gray-700/50 bg-gray-900/80 p-4 space-y-3">
            {/* Chat Input Mode - show text input first */}
            {isChatInput ? (
              <div className="space-y-3">
                <div className="flex gap-2">
                  <div className="flex-1">
                    <textarea
                      ref={feedbackRef}
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      placeholder={approval.context?.input_placeholder || "Enter your next task or message..."}
                      className="w-full px-3 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                      rows={3}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && feedback.trim()) {
                          onResolve('submit', feedback)
                          setFeedback('')
                        }
                      }}
                      autoFocus
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Press ⌘/Ctrl + Enter to submit
                    </p>
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => {
                      onResolve('exit')
                    }}
                    className="px-4 py-2 rounded-lg font-medium text-sm bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
                  >
                    Exit Session
                  </button>
                  <button
                    onClick={() => {
                      if (feedback.trim()) {
                        onResolve('submit', feedback)
                        setFeedback('')
                      }
                    }}
                    disabled={!feedback.trim()}
                    className={`
                      px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 transition-colors
                      ${feedback.trim()
                        ? 'bg-blue-600 hover:bg-blue-700 text-white'
                        : 'bg-gray-700 text-gray-500 cursor-not-allowed'}
                    `}
                  >
                    <Send className="w-4 h-4" />
                    Send
                  </button>
                </div>
              </div>
            ) : (
              /* Standard approval mode with options */
              <>
                {/* Options */}
                <div className="flex flex-wrap gap-2">
                  {options.map((option) => {
                    const config = OPTION_CONFIG[option.toLowerCase()] || {
                      icon: <CheckCircle className="w-4 h-4" />,
                      color: 'bg-gray-600 hover:bg-gray-700 border-gray-500',
                      label: option,
                      description: option
                    }
                    const isSelected = selectedOption === option

                    return (
                      <button
                        key={option}
                        onClick={() => setSelectedOption(isSelected ? null : option)}
                        className={`
                          flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium
                          transition-all duration-200
                          ${isSelected
                            ? `${config.color} text-white ring-2 ring-offset-2 ring-offset-gray-900 ring-white/30`
                            : 'bg-gray-800/50 border-gray-600 text-gray-300 hover:bg-gray-700/50 hover:border-gray-500'
                          }
                        `}
                        title={config.description}
                      >
                        {config.icon}
                        {config.label}
                      </button>
                    )
                  })}
                </div>

                {/* Feedback input - shown when option is selected */}
                {selectedOption && (
                  <div className="space-y-3 animate-in slide-in-from-top-2 duration-200">
                    {/* Show modifications input for modify option */}
                    {selectedOption.toLowerCase() === 'modify' && (
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">
                          Modifications (JSON or plain text):
                        </label>
                        <textarea
                          value={modifications}
                          onChange={(e) => setModifications(e.target.value)}
                          placeholder='{"step_1": "Modified step description..."}'
                          className="w-full px-3 py-2 bg-gray-800/50 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none font-mono"
                          rows={3}
                          onKeyDown={handleKeyDown}
                        />
                      </div>
                    )}

                    {/* Feedback input */}
                    <div className="flex gap-2">
                      <div className="flex-1">
                        <textarea
                          ref={feedbackRef}
                          value={feedback}
                          onChange={(e) => setFeedback(e.target.value)}
                          placeholder={
                            selectedOption.toLowerCase() === 'revise'
                              ? "Describe what changes you'd like..."
                              : "Optional: Add feedback or instructions..."
                          }
                          className="w-full px-3 py-2 bg-gray-800/50 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                          rows={2}
                          onKeyDown={handleKeyDown}
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Press ⌘/Ctrl + Enter to submit
                        </p>
                      </div>
                      <button
                        onClick={handleSubmit}
                        className={`
                          self-end px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2
                          transition-all duration-200
                          ${OPTION_CONFIG[selectedOption.toLowerCase()]?.color || 'bg-blue-600 hover:bg-blue-700'}
                          text-white
                        `}
                      >
                        <Send className="w-4 h-4" />
                        Submit
                      </button>
                    </div>
                  </div>
                )}

                {/* Quick actions hint */}
                {!selectedOption && (
                  <p className="text-xs text-gray-500 text-center">
                    Select an option above to continue the workflow
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
