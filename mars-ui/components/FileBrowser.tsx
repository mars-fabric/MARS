'use client'

import { useState, useEffect } from 'react'
import {
  Folder,
  ArrowLeft,
  RotateCcw,
  Download,
  Eye
} from 'lucide-react'
import { FilePreview, getFileIconConfig, isImageFile } from '@/components/files'

interface FileItem {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  modified?: number
  mime_type?: string
}

interface DirectoryListing {
  path: string
  items: FileItem[]
  parent?: string
}

interface FileBrowserProps {
  workDir: string
  onFileSelect?: (file: FileItem) => void
}

export default function FileBrowser({ workDir, onFileSelect }: FileBrowserProps) {
  const [currentPath, setCurrentPath] = useState(workDir)
  const [listing, setListing] = useState<DirectoryListing | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null)
  const [fileContent, setFileContent] = useState<string | null>(null)

  const loadDirectory = async (path: string) => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/files/list?path=${encodeURIComponent(path)}`)
      if (!response.ok) {
        throw new Error(`Failed to load directory: ${response.statusText}`)
      }

      const data: DirectoryListing = await response.json()
      setListing(data)
      setCurrentPath(data.path)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load directory')
    } finally {
      setLoading(false)
    }
  }

  const loadFileContent = async (file: FileItem) => {
    if (file.type !== 'file') return

    const isImage = isImageFile(file.name, file.mime_type)

    if (isImage) {
      setSelectedFile(file)
      setFileContent(null)

      if (onFileSelect) {
        onFileSelect(file)
      }
      return
    }

    try {
      const response = await fetch(`/api/files/content?path=${encodeURIComponent(file.path)}`)
      if (!response.ok) {
        throw new Error(`Failed to load file: ${response.statusText}`)
      }

      const data = await response.json()
      setFileContent(data.content)
      setSelectedFile(file)

      if (onFileSelect) {
        onFileSelect(file)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load file')
    }
  }

  useEffect(() => {
    loadDirectory(currentPath)
  }, [currentPath])

  const renderFileIcon = (item: FileItem) => {
    const config = getFileIconConfig(item.name, item.type === 'directory')
    const IconComponent = config.icon
    return <IconComponent className="w-4 h-4" style={{ color: config.color }} />
  }

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return ''
    const units = ['B', 'KB', 'MB', 'GB']
    let size = bytes
    let unitIndex = 0
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`
  }

  const formatDate = (timestamp?: number) => {
    if (!timestamp) return ''
    return new Date(timestamp * 1000).toLocaleString()
  }

  const navigateUp = () => {
    if (listing?.parent) {
      setCurrentPath(listing.parent)
    }
  }

  const navigateToDirectory = (item: FileItem) => {
    if (item.type === 'directory') {
      setCurrentPath(item.path)
    }
  }

  const handleDownload = () => {
    if (!selectedFile) return

    const isImage = isImageFile(selectedFile.name, selectedFile.mime_type)
    if (isImage) {
      const link = document.createElement('a')
      link.href = `/api/files/serve-image?path=${encodeURIComponent(selectedFile.path)}`
      link.download = selectedFile.name
      link.click()
    } else {
      const blob = new Blob([fileContent || ''], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = selectedFile.name
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  return (
    <div
      className="h-full flex flex-col rounded-mars-lg border overflow-hidden"
      style={{
        backgroundColor: 'var(--mars-color-surface)',
        borderColor: 'var(--mars-color-border)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 border-b"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <div className="flex items-center space-x-2">
          <Folder className="w-5 h-5" style={{ color: '#3B82F6' }} />
          <h3
            className="font-medium"
            style={{ color: 'var(--mars-color-text)' }}
          >
            File Browser
          </h3>
        </div>

        <button
          onClick={() => loadDirectory(currentPath)}
          disabled={loading}
          className="p-2 rounded-mars-md hover:bg-[var(--mars-color-bg-hover)] transition-colors disabled:opacity-50"
          style={{ color: 'var(--mars-color-text-secondary)' }}
          title="Refresh"
          aria-label="Refresh directory listing"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Navigation */}
      <div
        className="flex items-center p-3 border-b"
        style={{
          backgroundColor: 'var(--mars-color-surface-overlay)',
          borderColor: 'var(--mars-color-border)',
        }}
      >
        <button
          onClick={navigateUp}
          disabled={!listing?.parent || loading}
          className="p-1 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed mr-2"
          style={{ color: 'var(--mars-color-text-secondary)' }}
          title="Go up"
          aria-label="Navigate to parent directory"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        <span
          className="text-sm font-mono truncate"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          {currentPath}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div
              className="w-8 h-8 border-2 rounded-full animate-spin"
              style={{ borderColor: 'var(--mars-color-border)', borderTopColor: 'var(--mars-color-primary)' }}
            />
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full" style={{ color: 'var(--mars-color-danger)' }}>
            <p>{error}</p>
          </div>
        ) : (
          <div className="h-full overflow-y-auto">
            {listing?.items.length === 0 ? (
              <div className="flex items-center justify-center h-full" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                <p>Directory is empty</p>
              </div>
            ) : (
              <div className="p-2" role="listbox" aria-label="Files and directories">
                {listing?.items.map((item, index) => (
                  <div
                    key={index}
                    role="option"
                    aria-selected={selectedFile?.path === item.path}
                    className={`flex items-center p-2 rounded-mars-md cursor-pointer transition-colors ${
                      selectedFile?.path === item.path
                        ? 'bg-[var(--mars-color-primary-subtle)]'
                        : 'hover:bg-[var(--mars-color-bg-hover)]'
                    }`}
                    onClick={() => {
                      if (item.type === 'directory') {
                        navigateToDirectory(item)
                      } else {
                        loadFileContent(item)
                      }
                    }}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        if (item.type === 'directory') {
                          navigateToDirectory(item)
                        } else {
                          loadFileContent(item)
                        }
                      }
                    }}
                  >
                    <div className="flex items-center flex-1 min-w-0">
                      {renderFileIcon(item)}
                      <span
                        className="ml-2 text-sm truncate"
                        style={{ color: 'var(--mars-color-text)' }}
                      >
                        {item.name}
                      </span>
                    </div>

                    <div className="flex items-center space-x-4 text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                      {item.type === 'file' && (
                        <span>{formatFileSize(item.size)}</span>
                      )}
                      <span>{formatDate(item.modified)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* File Content Preview — using FilePreview component */}
      {selectedFile && (
        <div
          className="border-t p-4"
          style={{ borderColor: 'var(--mars-color-border)' }}
        >
          <div className="flex items-center justify-between mb-3">
            <div>
              <h4 className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>{selectedFile.name}</h4>
              <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                {selectedFile.mime_type} {selectedFile.size ? `\u2022 ${formatFileSize(selectedFile.size)}` : ''}
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={handleDownload}
                className="p-1 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)] transition-colors"
                style={{ color: 'var(--mars-color-text-secondary)' }}
                title="Download"
                aria-label={`Download ${selectedFile.name}`}
              >
                <Download className="w-3 h-3" />
              </button>
              {isImageFile(selectedFile.name, selectedFile.mime_type) && (
                <button
                  onClick={() => {
                    window.open(`/api/files/serve-image?path=${encodeURIComponent(selectedFile.path)}`, '_blank')
                  }}
                  className="p-1 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)] transition-colors"
                  style={{ color: 'var(--mars-color-text-secondary)' }}
                  title="View in new tab"
                  aria-label={`Open ${selectedFile.name} in new tab`}
                >
                  <Eye className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>

          <div className="max-h-64 overflow-hidden">
            <FilePreview
              fileName={selectedFile.name}
              filePath={selectedFile.path}
              content={fileContent}
              mimeType={selectedFile.mime_type}
              sizeBytes={selectedFile.size}
              imageUrl={isImageFile(selectedFile.name, selectedFile.mime_type)
                ? `/api/files/serve-image?path=${encodeURIComponent(selectedFile.path)}`
                : undefined
              }
              onOpenExternal={isImageFile(selectedFile.name, selectedFile.mime_type)
                ? () => window.open(`/api/files/serve-image?path=${encodeURIComponent(selectedFile.path)}`, '_blank')
                : undefined
              }
              maxCodeLines={30}
            />
          </div>
        </div>
      )}
    </div>
  )
}
