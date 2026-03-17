'use client'

import { useEffect, useRef, useState, ReactNode } from 'react'
import {
  Terminal,
  Copy,
  Trash2,
  ArrowDown,
  XCircle,
  AlertTriangle,
  CheckCircle,
  Info,
  Wrench,
  FileText,
  Code,
  Target,
  BarChart3,
  FolderOpen,
  Plug,
  StopCircle,
  Pause,
  Play,
  GitBranch,
  Eye,
  Search as SearchIcon,
} from 'lucide-react'

interface ConsoleOutputProps {
  output: string[]
  isRunning: boolean
  onClear?: () => void
}

// Icon config for different log line types
interface LineConfig {
  icon: ReactNode
  className: string
}

function getLineConfig(line: string): LineConfig {
  const lower = line.toLowerCase()

  if (lower.includes('error') || lower.includes('failed') || lower.includes('exception')) {
    return {
      icon: <XCircle className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: 'var(--mars-color-danger)' }} />,
      className: 'text-console-error',
    }
  }
  if (lower.includes('warning') || lower.includes('warn')) {
    return {
      icon: <AlertTriangle className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: 'var(--mars-color-warning)' }} />,
      className: 'text-console-warning',
    }
  }
  if (lower.includes('success') || lower.includes('completed') || line.includes('\u2713')) {
    return {
      icon: <CheckCircle className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: 'var(--mars-color-success)' }} />,
      className: 'text-console-success',
    }
  }
  if (lower.includes('info')) {
    return {
      icon: <Info className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: 'var(--mars-color-info)' }} />,
      className: 'text-console-info',
    }
  }
  if (line.startsWith('>>>') || line.startsWith('$')) {
    return {
      icon: <Wrench className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#60A5FA' }} />,
      className: 'text-blue-400',
    }
  }
  if (lower.includes('code explanation:')) {
    return {
      icon: <FileText className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#FBBF24' }} />,
      className: 'text-yellow-400 font-semibold',
    }
  }
  if (lower.includes('python code:')) {
    return {
      icon: <Code className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#34D399' }} />,
      className: 'text-green-400 font-semibold',
    }
  }
  if (lower.includes('final result:')) {
    return {
      icon: <Target className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#A78BFA' }} />,
      className: 'text-purple-400 font-bold',
    }
  }
  if (lower.includes('dag created') || lower.includes('dag updated')) {
    return {
      icon: <BarChart3 className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#60A5FA' }} />,
      className: 'text-console-info',
    }
  }
  if (lower.includes('file(s) tracked')) {
    return {
      icon: <FolderOpen className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#60A5FA' }} />,
      className: 'text-console-info',
    }
  }
  if (lower.includes('websocket connected') || lower.includes('websocket disconnected') || lower.includes('websocket reconnected')) {
    return {
      icon: <Plug className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#60A5FA' }} />,
      className: 'text-console-info',
    }
  }
  if (lower.includes('stopped by user')) {
    return {
      icon: <StopCircle className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: 'var(--mars-color-danger)' }} />,
      className: 'text-console-error',
    }
  }
  if (lower.includes('workflow paused') || lower.includes('pause request')) {
    return {
      icon: <Pause className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: 'var(--mars-color-warning)' }} />,
      className: 'text-console-warning',
    }
  }
  if (lower.includes('workflow resumed') || lower.includes('resume request')) {
    return {
      icon: <Play className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: 'var(--mars-color-success)' }} />,
      className: 'text-console-success',
    }
  }
  if (lower.includes('workflow started')) {
    return {
      icon: <Play className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: 'var(--mars-color-success)' }} />,
      className: 'text-console-success',
    }
  }
  if (lower.includes('branch') || lower.includes('switched to branch')) {
    return {
      icon: <GitBranch className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#A78BFA' }} />,
      className: 'text-purple-400',
    }
  }
  if (lower.includes('viewing')) {
    return {
      icon: <Eye className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#60A5FA' }} />,
      className: 'text-blue-400',
    }
  }
  if (lower.includes('comparing')) {
    return {
      icon: <SearchIcon className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: '#60A5FA' }} />,
      className: 'text-blue-400',
    }
  }
  if (lower.includes('approval')) {
    return {
      icon: <Pause className="w-3.5 h-3.5 inline-block mr-1.5 flex-shrink-0" style={{ color: 'var(--mars-color-warning)' }} />,
      className: 'text-console-warning',
    }
  }

  // Default: no prefix icon
  return {
    icon: null,
    className: 'text-console-text',
  }
}

// Strip emoji prefixes from text that the backend sends
function stripEmojiPrefix(line: string): string {
  // Remove leading emoji characters and variation selectors followed by optional space
  // Matches common emoji ranges used in console output
  return line.replace(/^[\u2139\u231B\u23F8\u23F9\u25B6\u26A0\u2705\u274C\u2B06\uD83C-\uDBFF][\uDC00-\uDFFF]?\uFE0F?\s*/g, '')
}

export default function ConsoleOutput({ output, isRunning, onClear }: ConsoleOutputProps) {
  const consoleRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const [showScrollButton, setShowScrollButton] = useState(false)

  // Auto-scroll to bottom when new output is added
  useEffect(() => {
    const scrollToBottom = () => {
      if (consoleRef.current) {
        consoleRef.current.scrollTop = consoleRef.current.scrollHeight
      }
    }

    const timeoutId = setTimeout(scrollToBottom, 50)
    return () => clearTimeout(timeoutId)
  }, [output])

  // Also scroll when running state changes
  useEffect(() => {
    if (isRunning && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight
    }
  }, [isRunning])

  // Handle scroll detection for showing scroll-to-bottom button
  useEffect(() => {
    const handleScroll = () => {
      if (consoleRef.current) {
        const { scrollTop, scrollHeight, clientHeight } = consoleRef.current
        const isNearBottom = scrollHeight - scrollTop - clientHeight < 50
        setShowScrollButton(!isNearBottom && output.length > 3)
      }
    }

    const consoleElement = consoleRef.current
    if (consoleElement) {
      consoleElement.addEventListener('scroll', handleScroll)
      return () => consoleElement.removeEventListener('scroll', handleScroll)
    }
  }, [output.length])

  const scrollToBottom = () => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight
    }
  }

  const copyToClipboard = () => {
    const text = output.join('\n')
    navigator.clipboard.writeText(text)
  }

  const clearConsole = () => {
    if (onClear) {
      onClear()
    }
  }

  const formatOutput = (line: string, index: number) => {
    const cleanedLine = stripEmojiPrefix(line)
    const config = getLineConfig(cleanedLine)

    return (
      <div key={index} className={`${config.className} font-mono text-xs leading-tight flex items-start`}>
        <span className="text-gray-500 select-none mr-2 flex-shrink-0">
          {String(index + 1).padStart(3, '0')}
        </span>
        {config.icon && <span className="select-none flex-shrink-0 mt-px">{config.icon}</span>}
        <span className="whitespace-pre-wrap break-all">{cleanedLine}</span>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-console-bg rounded-xl border border-white/20 overflow-hidden relative">
      {/* Console Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-black/40 border-b border-white/10">
        <div className="flex items-center space-x-2">
          <Terminal className="w-5 h-5 text-green-400" />
          {isRunning && (
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-green-400 text-xs">Running</span>
            </div>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={scrollToBottom}
            className="p-1.5 text-gray-400 hover:text-white transition-colors"
            title="Scroll to bottom"
          >
            <ArrowDown className="w-4 h-4" />
          </button>
          <button
            onClick={copyToClipboard}
            className="p-1.5 text-gray-400 hover:text-white transition-colors"
            title="Copy to clipboard"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            onClick={clearConsole}
            className="p-1.5 text-gray-400 hover:text-white transition-colors"
            title="Clear console"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Console Content */}
      <div
        ref={consoleRef}
        className="flex-1 px-3 py-2 overflow-y-auto console-scrollbar"
        style={{ minHeight: 0 }}
      >
        {output.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <Terminal className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>Console output will appear here...</p>
              <p className="text-sm mt-2">Submit a task to get started</p>
            </div>
          </div>
        ) : (
          <div className="space-y-1">
            {output.map((line, index) => formatOutput(line, index))}
            {isRunning && (
              <div className="flex items-center space-x-2 text-green-400 font-mono text-xs">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <span className="typing-animation">Processing...</span>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* Floating Scroll to Bottom Button */}
      {showScrollButton && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-20 right-6 p-3 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg transition-all duration-200 z-10"
          title="Scroll to bottom"
        >
          <ArrowDown className="w-5 h-5" />
        </button>
      )}

      {/* Console Footer */}
      <div className="px-3 py-1.5 bg-black/40 border-t border-white/10">
        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>{output.length} lines</span>
          <span>MARS Console v1.0</span>
        </div>
      </div>
    </div>
  )
}
