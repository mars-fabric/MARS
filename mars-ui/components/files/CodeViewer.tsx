'use client'

import { useMemo } from 'react'
import { getLanguageFromFileName } from './fileIcons'

interface CodeViewerProps {
  content: string
  fileName: string
  language?: string
  maxLines?: number
}

/**
 * Code viewer with line numbers and MARS token styling.
 * Uses plain text rendering with line numbers (no heavy syntax highlighting dependency
 * to keep the bundle light). If react-syntax-highlighter is available in the project,
 * the FilePreview component can swap this out.
 */
export default function CodeViewer({ content, fileName, language, maxLines }: CodeViewerProps) {
  const lang = language || getLanguageFromFileName(fileName)

  const lines = useMemo(() => {
    const allLines = content.split('\n')
    return maxLines ? allLines.slice(0, maxLines) : allLines
  }, [content, maxLines])

  const lineNumberWidth = String(lines.length).length

  return (
    <div className="mars-file-viewer-body overflow-auto" style={{ backgroundColor: 'var(--mars-color-console-bg)' }}>
      <pre className="p-0 m-0" style={{ tabSize: 4 }}>
        <code className="block">
          {lines.map((line, idx) => (
            <div key={idx} className="flex hover:bg-[rgba(255,255,255,0.03)] px-3">
              <span
                className="select-none text-right pr-4 flex-shrink-0"
                style={{
                  color: 'var(--mars-color-text-tertiary)',
                  minWidth: `${lineNumberWidth + 2}ch`,
                  fontFamily: 'var(--mars-font-mono)',
                  fontSize: 'var(--mars-text-xs)',
                  lineHeight: '1.7',
                }}
              >
                {idx + 1}
              </span>
              <span
                style={{
                  color: 'var(--mars-color-console-text)',
                  fontFamily: 'var(--mars-font-mono)',
                  fontSize: 'var(--mars-text-xs)',
                  lineHeight: '1.7',
                  whiteSpace: 'pre',
                }}
              >
                {line}
              </span>
            </div>
          ))}
        </code>
      </pre>
      {maxLines && content.split('\n').length > maxLines && (
        <div className="p-2 text-center text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
          Showing first {maxLines} of {content.split('\n').length} lines
        </div>
      )}
    </div>
  )
}
