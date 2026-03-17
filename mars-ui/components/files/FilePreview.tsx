'use client'

import { useState } from 'react'
import { Download, ExternalLink, File as FileIcon } from 'lucide-react'
import { getFileIconConfig, isImageFile, isCSVFile, isMarkdownFile, isTextFile } from './fileIcons'
import CodeViewer from './CodeViewer'
import CSVTableViewer from './CSVTableViewer'
import MarkdownRenderer from './MarkdownRenderer'

interface FilePreviewProps {
  fileName: string
  filePath?: string
  content?: string | null
  mimeType?: string
  contentType?: string
  encoding?: string
  sizeBytes?: number
  /** For base64-encoded images from the API */
  base64Content?: string
  /** Direct image URL (for /api/files/serve-image) */
  imageUrl?: string
  onDownload?: () => void
  onOpenExternal?: () => void
  loading?: boolean
  maxCodeLines?: number
}

function formatSize(bytes?: number): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FilePreview({
  fileName,
  filePath,
  content,
  mimeType,
  contentType,
  encoding,
  sizeBytes,
  base64Content,
  imageUrl,
  onDownload,
  onOpenExternal,
  loading = false,
  maxCodeLines,
}: FilePreviewProps) {
  const iconConfig = getFileIconConfig(fileName)
  const Icon = iconConfig.icon

  // Loading state
  if (loading) {
    return (
      <div className="mars-file-viewer">
        <div className="mars-file-viewer-header">
          <div className="flex items-center gap-2">
            <Icon className="w-4 h-4" style={{ color: iconConfig.color }} />
            <span>{fileName}</span>
          </div>
        </div>
        <div className="flex items-center justify-center py-16">
          <div
            className="w-8 h-8 border-2 rounded-full animate-spin"
            style={{ borderColor: 'var(--mars-color-border)', borderTopColor: 'var(--mars-color-primary)' }}
          />
        </div>
      </div>
    )
  }

  // Image preview — base64 or URL
  const isImg = isImageFile(fileName, mimeType)
  if (isImg) {
    const imgSrc = base64Content
      ? `data:${mimeType || 'image/png'};base64,${base64Content}`
      : imageUrl || ''

    return (
      <div className="mars-file-viewer">
        <FileViewerHeader
          fileName={fileName}
          sizeBytes={sizeBytes}
          iconConfig={iconConfig}
          onDownload={onDownload}
          onOpenExternal={onOpenExternal}
        />
        <div className="mars-file-viewer-body flex items-center justify-center p-4" style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}>
          {imgSrc ? (
            <img
              src={imgSrc}
              alt={fileName}
              className="max-w-full max-h-[60vh] object-contain rounded"
              style={{ cursor: onOpenExternal ? 'pointer' : 'default' }}
              onClick={onOpenExternal}
            />
          ) : (
            <NoPreview fileName={fileName} message="Image source not available" />
          )}
        </div>
      </div>
    )
  }

  // No content available — show placeholder
  if (!content) {
    return (
      <div className="mars-file-viewer">
        <FileViewerHeader
          fileName={fileName}
          sizeBytes={sizeBytes}
          iconConfig={iconConfig}
          onDownload={onDownload}
          onOpenExternal={onOpenExternal}
        />
        <NoPreview fileName={fileName} />
      </div>
    )
  }

  // CSV / TSV table view
  if (isCSVFile(fileName)) {
    return (
      <div className="mars-file-viewer">
        <FileViewerHeader
          fileName={fileName}
          sizeBytes={sizeBytes}
          iconConfig={iconConfig}
          onDownload={onDownload}
          onOpenExternal={onOpenExternal}
        />
        <CSVTableViewer content={content} />
      </div>
    )
  }

  // Markdown rendering
  if (isMarkdownFile(fileName)) {
    return (
      <div className="mars-file-viewer">
        <FileViewerHeader
          fileName={fileName}
          sizeBytes={sizeBytes}
          iconConfig={iconConfig}
          onDownload={onDownload}
          onOpenExternal={onOpenExternal}
        />
        <div className="mars-file-viewer-body">
          <MarkdownRenderer content={content} />
        </div>
      </div>
    )
  }

  // JSON pretty-print
  if (fileName.endsWith('.json')) {
    let prettyContent = content
    try {
      prettyContent = JSON.stringify(JSON.parse(content), null, 2)
    } catch {
      // Use as-is if not valid JSON
    }
    return (
      <div className="mars-file-viewer">
        <FileViewerHeader
          fileName={fileName}
          sizeBytes={sizeBytes}
          iconConfig={iconConfig}
          onDownload={onDownload}
          onOpenExternal={onOpenExternal}
        />
        <CodeViewer content={prettyContent} fileName={fileName} maxLines={maxCodeLines} />
      </div>
    )
  }

  // Code / text files
  if (isTextFile(fileName)) {
    return (
      <div className="mars-file-viewer">
        <FileViewerHeader
          fileName={fileName}
          sizeBytes={sizeBytes}
          iconConfig={iconConfig}
          onDownload={onDownload}
          onOpenExternal={onOpenExternal}
        />
        <CodeViewer content={content} fileName={fileName} maxLines={maxCodeLines} />
      </div>
    )
  }

  // Fallback: raw text
  return (
    <div className="mars-file-viewer">
      <FileViewerHeader
        fileName={fileName}
        sizeBytes={sizeBytes}
        iconConfig={iconConfig}
        onDownload={onDownload}
        onOpenExternal={onOpenExternal}
      />
      <div className="mars-file-viewer-body p-4">
        <pre
          className="text-xs overflow-auto whitespace-pre-wrap"
          style={{ color: 'var(--mars-color-text-secondary)', fontFamily: 'var(--mars-font-mono)' }}
        >
          {content}
        </pre>
      </div>
    </div>
  )
}

// -- Sub-components --

function FileViewerHeader({
  fileName,
  sizeBytes,
  iconConfig,
  onDownload,
  onOpenExternal,
}: {
  fileName: string
  sizeBytes?: number
  iconConfig: { icon: any; color: string }
  onDownload?: () => void
  onOpenExternal?: () => void
}) {
  const Icon = iconConfig.icon
  return (
    <div className="mars-file-viewer-header">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4" style={{ color: iconConfig.color }} />
        <span>{fileName}</span>
        {sizeBytes != null && sizeBytes > 0 && (
          <span style={{ color: 'var(--mars-color-text-tertiary)' }}>
            ({formatSize(sizeBytes)})
          </span>
        )}
      </div>
      <div className="flex items-center gap-1">
        {onDownload && (
          <button
            onClick={onDownload}
            className="p-1 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)] transition-colors"
            title="Download"
            aria-label={`Download ${fileName}`}
          >
            <Download className="w-3.5 h-3.5" />
          </button>
        )}
        {onOpenExternal && (
          <button
            onClick={onOpenExternal}
            className="p-1 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)] transition-colors"
            title="Open in new tab"
            aria-label={`Open ${fileName} in new tab`}
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}

function NoPreview({ fileName, message }: { fileName: string; message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12" style={{ color: 'var(--mars-color-text-tertiary)' }}>
      <FileIcon className="w-10 h-10 mb-3 opacity-40" />
      <p className="text-sm">{message || 'Preview not available'}</p>
      <p className="text-xs mt-1 opacity-60">Use download or view buttons above</p>
    </div>
  )
}
