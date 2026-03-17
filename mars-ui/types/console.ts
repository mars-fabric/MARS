// types/console.ts — Structured log entry types for the MARS console

export type LogLevel = 'info' | 'success' | 'warning' | 'error' | 'debug' | 'system'

export type LogSource =
  | 'agent_message'
  | 'agent_thinking'
  | 'agent_tool_call'
  | 'code_execution'
  | 'tool_call'
  | 'workflow'
  | 'dag'
  | 'approval'
  | 'cost'
  | 'files'
  | 'connection'
  | 'status'
  | 'output'
  | 'error'
  | 'result'
  | 'phase'

export type PhaseType =
  | 'planning'
  | 'analyzing'
  | 'executing'
  | 'reviewing'
  | 'completing'

export interface StructuredLogEntry {
  id: string
  timestamp: string
  level: LogLevel
  source: LogSource
  agent?: string
  message: string
  rawText: string          // The original text for search/filter/copy
  code?: string            // Code block content (for code_execution)
  codeLanguage?: string    // Language for syntax highlighting
  codeResult?: string      // Result of code/tool execution
  toolName?: string        // Tool name for tool_call entries
  phase?: PhaseType        // Phase indicator
  collapsible?: boolean    // Whether code/result blocks can collapse
}

let _entryCounter = 0

export function createLogEntry(
  partial: Omit<StructuredLogEntry, 'id' | 'timestamp'> & { timestamp?: string }
): StructuredLogEntry {
  _entryCounter++
  return {
    id: `log-${_entryCounter}-${Date.now()}`,
    timestamp: partial.timestamp || new Date().toISOString(),
    ...partial,
  }
}

/**
 * Derive a LogLevel from raw console text (heuristic).
 */
export function inferLevel(text: string): LogLevel {
  const lower = text.toLowerCase()
  if (lower.includes('error') || lower.includes('failed') || lower.includes('exception')) return 'error'
  if (lower.includes('warning') || lower.includes('warn')) return 'warning'
  if (lower.includes('success') || lower.includes('completed') || lower.includes('✅') || lower.includes('\u2713')) return 'success'
  if (lower.includes('websocket') || lower.includes('connected') || lower.includes('disconnected')) return 'system'
  return 'info'
}

/**
 * Derive a LogSource from raw console text (heuristic).
 */
export function inferSource(text: string): LogSource {
  const lower = text.toLowerCase()
  if (lower.includes('workflow')) return 'workflow'
  if (lower.includes('dag')) return 'dag'
  if (lower.includes('approval')) return 'approval'
  if (lower.includes('websocket') || lower.includes('connected') || lower.includes('disconnected')) return 'connection'
  if (lower.includes('file(s) tracked')) return 'files'
  return 'output'
}

/**
 * Detect phase transitions from raw output.
 */
export function inferPhase(text: string): PhaseType | undefined {
  const lower = text.toLowerCase()
  if (lower.includes('planning') || lower.includes('creating plan')) return 'planning'
  if (lower.includes('analyzing') || lower.includes('analysis')) return 'analyzing'
  if (lower.includes('executing') || lower.includes('running')) return 'executing'
  if (lower.includes('reviewing') || lower.includes('review')) return 'reviewing'
  if (lower.includes('completing') || lower.includes('finalizing')) return 'completing'
  return undefined
}

/**
 * Extract agent name from bracketed text like "[AgentName] message".
 */
export function extractAgent(text: string): { agent?: string; message: string } {
  const match = text.match(/^\[([^\]]+)\]\s*(.*)$/)
  if (match) {
    return { agent: match[1], message: match[2] }
  }
  return { message: text }
}

/**
 * Strip leading emoji characters from text.
 */
export function stripEmoji(text: string): string {
  // Remove common leading emoji characters used in MARS console messages
  // Using surrogate pairs to avoid the ES2015 'u' flag requirement
  return text.replace(/^(?:[\u2139\u231B\u23F8\u23F9\u25B6\u26A0\u2705\u274C\u2B06]|[\uD83C-\uDBFF][\uDC00-\uDFFF]|\uFE0F|\u200D|\u20E3)+\s*/g, '')
}

/**
 * Convert a raw console string into a StructuredLogEntry.
 * Used to bridge legacy string-based console output with the new structured system.
 */
export function rawToStructured(rawText: string): StructuredLogEntry {
  const cleaned = stripEmoji(rawText)
  const level = inferLevel(cleaned)
  const source = inferSource(cleaned)
  const phase = inferPhase(cleaned)
  const { agent, message } = extractAgent(cleaned)

  return createLogEntry({
    level,
    source: phase ? 'phase' : source,
    agent,
    message,
    rawText,
    phase,
  })
}
