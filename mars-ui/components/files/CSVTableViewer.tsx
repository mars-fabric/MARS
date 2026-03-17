'use client'

import { useMemo } from 'react'

interface CSVTableViewerProps {
  content: string
  delimiter?: string
  maxRows?: number
}

export default function CSVTableViewer({ content, delimiter, maxRows = 500 }: CSVTableViewerProps) {
  const { headers, rows } = useMemo(() => {
    const lines = content.split('\n').filter(l => l.trim())
    if (lines.length === 0) return { headers: [], rows: [] }

    // Auto-detect delimiter
    const sep = delimiter || (lines[0].includes('\t') ? '\t' : ',')

    const parseLine = (line: string): string[] => {
      const result: string[] = []
      let current = ''
      let inQuotes = false

      for (let i = 0; i < line.length; i++) {
        const char = line[i]
        if (char === '"') {
          inQuotes = !inQuotes
        } else if (char === sep && !inQuotes) {
          result.push(current.trim())
          current = ''
        } else {
          current += char
        }
      }
      result.push(current.trim())
      return result
    }

    const headerRow = parseLine(lines[0])
    const dataRows = lines.slice(1, maxRows + 1).map(parseLine)

    return { headers: headerRow, rows: dataRows }
  }, [content, delimiter, maxRows])

  if (headers.length === 0) {
    return (
      <div className="p-4 text-center" style={{ color: 'var(--mars-color-text-tertiary)' }}>
        No data to display
      </div>
    )
  }

  return (
    <div className="mars-file-viewer-body">
      <table className="mars-csv-table">
        <thead>
          <tr>
            <th style={{ width: '3ch' }}>#</th>
            {headers.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIdx) => (
            <tr key={rowIdx}>
              <td style={{ color: 'var(--mars-color-text-tertiary)' }}>{rowIdx + 1}</td>
              {row.map((cell, cellIdx) => (
                <td key={cellIdx}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length >= maxRows && (
        <div className="p-2 text-center text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
          Showing first {maxRows} rows
        </div>
      )}
    </div>
  )
}
