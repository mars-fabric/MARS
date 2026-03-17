'use client'

import React, { useState, useCallback, useRef } from 'react'
import { Upload, X, FileIcon, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import type { UploadedFile } from '@/types/deepresearch'

interface FileUploadZoneProps {
  files: UploadedFile[]
  onUpload: (file: File) => void
  disabled?: boolean
}

export default function FileUploadZone({ files, onUpload, disabled }: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    if (!disabled) setIsDragging(true)
  }, [disabled])

  const handleDragLeave = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (disabled) return
    const droppedFiles = Array.from(e.dataTransfer.files)
    droppedFiles.forEach(onUpload)
  }, [disabled, onUpload])

  const handleClick = useCallback(() => {
    if (!disabled) inputRef.current?.click()
  }, [disabled])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || [])
    selected.forEach(onUpload)
    if (inputRef.current) inputRef.current.value = ''
  }, [onUpload])

  const statusIcon = (status: UploadedFile['status']) => {
    switch (status) {
      case 'uploading': return <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: 'var(--mars-color-primary)' }} />
      case 'done': return <CheckCircle className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-success)' }} />
      case 'error': return <AlertCircle className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-danger)' }} />
      default: return <FileIcon className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-tertiary)' }} />
    }
  }

  return (
    <div>
      {/* Drop zone */}
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className="cursor-pointer rounded-mars-md border-2 border-dashed p-6 text-center transition-colors"
        style={{
          borderColor: isDragging ? 'var(--mars-color-primary)' : 'var(--mars-color-border)',
          backgroundColor: isDragging ? 'var(--mars-color-primary-subtle)' : 'transparent',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        <Upload
          className="w-8 h-8 mx-auto mb-2"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        />
        <p
          className="text-sm font-medium"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Drop files here or click to browse
        </p>
        <p
          className="text-xs mt-1"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          CSV, JSON, FITS, HDF5, TXT, MD, and more (max 10MB)
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleChange}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="mt-3 space-y-1">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              className="flex items-center gap-2 px-3 py-2 rounded-mars-sm text-xs"
              style={{
                backgroundColor: 'var(--mars-color-surface-overlay)',
                color: 'var(--mars-color-text-secondary)',
              }}
            >
              {statusIcon(f.status)}
              <span className="flex-1 truncate">{f.name}</span>
              <span style={{ color: 'var(--mars-color-text-tertiary)' }}>
                {(f.size / 1024).toFixed(1)} KB
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
