// components/dag/DAGFilesView.tsx
'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  FileText,
  Search,
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  AlertCircle,
  X
} from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { FilePreview, getFileIconConfig } from '@/components/files';

interface DAGFilesViewProps {
  runId: string;
  refreshTrigger?: number;
}

interface FileNode {
  id: string;
  file_path: string;
  file_name: string;
  file_type: string;
  size_bytes: number;
  node_id: string;
  agent_name?: string;
  created_at: string;
  file_content?: string;
  content_type?: string;
  encoding?: string;
  mime_type?: string;
}

export function DAGFilesView({ runId, refreshTrigger }: DAGFilesViewProps) {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [fileTypeFilter, setFileTypeFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'list' | 'tree'>('list');
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchFiles();
  }, [runId, refreshTrigger]);

  const fetchFiles = async () => {
    if (!runId) return;

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(getApiUrl(`/api/runs/${runId}/files`));
      if (!response.ok) {
        throw new Error(`Failed to fetch files: ${response.statusText}`);
      }
      const data = await response.json();
      setFiles(data.files || []);
    } catch (err) {
      console.error('Error fetching files:', err);
      setError(err instanceof Error ? err.message : 'Failed to load files');
    } finally {
      setLoading(false);
    }
  };

  const filteredFiles = useMemo(() => {
    return files.filter(file => {
      const matchesSearch = searchQuery === '' ||
        file.file_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        file.file_path.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesType = fileTypeFilter === 'all' ||
        (fileTypeFilter === 'code' && file.file_name.match(/\.(py|js|ts|tsx|jsx|json|yaml|yml)$/)) ||
        (fileTypeFilter === 'data' && file.file_name.match(/\.(csv|txt|md|json)$/)) ||
        (fileTypeFilter === 'images' && file.file_name.match(/\.(png|jpg|jpeg|gif|svg)$/)) ||
        (fileTypeFilter === 'logs' && file.file_name.match(/\.(log|txt)$/));

      return matchesSearch && matchesType;
    });
  }, [files, searchQuery, fileTypeFilter]);

  const fileTree = useMemo(() => {
    const tree: any = {};

    filteredFiles.forEach(file => {
      const parts = file.file_path.split('/');
      let current = tree;

      parts.forEach((part, index) => {
        if (index === parts.length - 1) {
          if (!current._files) current._files = [];
          current._files.push(file);
        } else {
          if (!current[part]) current[part] = {};
          current = current[part];
        }
      });
    });

    return tree;
  }, [filteredFiles]);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleFileClick = async (file: FileNode) => {
    setSelectedFile(file);

    if (!file.file_content) {
      setLoadingContent(true);
      try {
        const response = await fetch(getApiUrl(`/api/files/content?file_path=${encodeURIComponent(file.file_path)}`));
        if (response.ok) {
          const data = await response.json();
          if (data.content) {
            setSelectedFile({
              ...file,
              file_content: data.content,
              content_type: data.content_type,
              encoding: data.encoding,
              mime_type: data.mime_type
            });
          } else if (data.content_type === 'binary') {
            setSelectedFile({ ...file, file_content: `[Binary file - ${formatFileSize(data.size || file.size_bytes)}]\n\nThis file cannot be displayed as text.` });
          }
        } else {
          setSelectedFile({ ...file, file_content: `Error: ${response.status} ${response.statusText}` });
        }
      } catch (error) {
        setSelectedFile({ ...file, file_content: 'Error loading file content' });
      } finally {
        setLoadingContent(false);
      }
    }
  };

  const handleDownload = (file: FileNode) => {
    const blob = new Blob([file.file_content || ''], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = file.file_name;
    link.click();
    URL.revokeObjectURL(url);
  };

  const toggleDirectory = (path: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const renderFileIcon = (fileName: string, isDir = false) => {
    const config = getFileIconConfig(fileName, isDir);
    const IconComponent = config.icon;
    return <IconComponent className="w-4 h-4" style={{ color: config.color }} />;
  };

  const renderTree = (tree: any, path: string = '') => {
    const entries = Object.entries(tree).filter(([key]) => key !== '_files');
    const treeFiles = tree._files || [];

    return (
      <>
        {entries.map(([dirName, subtree]) => {
          const fullPath = path ? `${path}/${dirName}` : dirName;
          const isExpanded = expandedDirs.has(fullPath);

          return (
            <div key={fullPath}>
              <button
                onClick={() => toggleDirectory(fullPath)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded transition-colors
                  hover:bg-[var(--mars-color-bg-hover)]"
                aria-expanded={isExpanded}
              >
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4" style={{ color: 'var(--mars-color-text-tertiary)' }} />
                ) : (
                  <ChevronRight className="w-4 h-4" style={{ color: 'var(--mars-color-text-tertiary)' }} />
                )}
                {isExpanded ? (
                  <FolderOpen className="w-4 h-4" style={{ color: '#3B82F6' }} />
                ) : (
                  <Folder className="w-4 h-4" style={{ color: '#3B82F6' }} />
                )}
                <span style={{ color: 'var(--mars-color-text)' }}>{dirName}</span>
              </button>

              {isExpanded && (
                <div className="ml-6">
                  {renderTree(subtree, fullPath)}
                </div>
              )}
            </div>
          );
        })}

        {treeFiles.map((file: FileNode) => (
          <button
            key={file.id}
            onClick={() => handleFileClick(file)}
            className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded transition-colors ${
              selectedFile?.id === file.id
                ? 'bg-[var(--mars-color-primary-subtle)] border-l-2'
                : 'hover:bg-[var(--mars-color-bg-hover)]'
            }`}
            style={selectedFile?.id === file.id ? { borderLeftColor: 'var(--mars-color-primary)' } : undefined}
          >
            <div className="w-4" />
            {renderFileIcon(file.file_name)}
            <span className="truncate flex-1 text-left" style={{ color: 'var(--mars-color-text)' }}>{file.file_name}</span>
            <span className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>{formatFileSize(file.size_bytes)}</span>
          </button>
        ))}
      </>
    );
  };

  const fileTypes = [
    { value: 'all', label: 'All Files' },
    { value: 'code', label: 'Code' },
    { value: 'data', label: 'Data' },
    { value: 'images', label: 'Images' },
    { value: 'logs', label: 'Logs' },
  ];

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center" style={{ backgroundColor: 'var(--mars-color-surface)' }}>
        <div className="text-center">
          <div
            className="w-10 h-10 border-2 rounded-full animate-spin mx-auto mb-4"
            style={{ borderColor: 'var(--mars-color-border)', borderTopColor: 'var(--mars-color-primary)' }}
          />
          <p style={{ color: 'var(--mars-color-text-tertiary)' }}>Loading files...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center" style={{ backgroundColor: 'var(--mars-color-surface)' }}>
        <div className="text-center" style={{ color: 'var(--mars-color-danger)' }}>
          <AlertCircle className="w-10 h-10 mx-auto mb-3" />
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex" style={{ backgroundColor: 'var(--mars-color-surface)' }}>
      {/* Files List/Tree */}
      <div className="flex-1 overflow-auto border-r" style={{ borderColor: 'var(--mars-color-border)' }}>
        <div className="p-4">
          <div className="flex items-center gap-2 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--mars-color-text-tertiary)' }} />
              <input
                type="search"
                placeholder="Search files..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-3 py-2 text-sm rounded-mars-md border outline-none"
                style={{
                  backgroundColor: 'var(--mars-color-surface-raised)',
                  borderColor: 'var(--mars-color-border)',
                  color: 'var(--mars-color-text)',
                }}
                aria-label="Search files"
              />
            </div>

            <select
              value={fileTypeFilter}
              onChange={(e) => setFileTypeFilter(e.target.value)}
              className="px-3 py-2 text-sm rounded-mars-md border"
              style={{
                backgroundColor: 'var(--mars-color-surface-raised)',
                borderColor: 'var(--mars-color-border)',
                color: 'var(--mars-color-text)',
              }}
              aria-label="Filter by file type"
            >
              {fileTypes.map(type => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>

            <div
              className="flex gap-1 p-1 rounded-mars-md"
              style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
              role="radiogroup"
              aria-label="View mode"
            >
              <button
                onClick={() => setViewMode('list')}
                role="radio"
                aria-checked={viewMode === 'list'}
                className={`px-2 py-1 text-xs rounded-mars-sm transition-colors ${
                  viewMode === 'list'
                    ? 'bg-[var(--mars-color-primary)] text-white'
                    : 'text-[var(--mars-color-text-secondary)]'
                }`}
              >
                List
              </button>
              <button
                onClick={() => setViewMode('tree')}
                role="radio"
                aria-checked={viewMode === 'tree'}
                className={`px-2 py-1 text-xs rounded-mars-sm transition-colors ${
                  viewMode === 'tree'
                    ? 'bg-[var(--mars-color-primary)] text-white'
                    : 'text-[var(--mars-color-text-secondary)]'
                }`}
              >
                Tree
              </button>
            </div>
          </div>

          {filteredFiles.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-10 h-10 mx-auto mb-3 opacity-40" style={{ color: 'var(--mars-color-text-tertiary)' }} />
              <p style={{ color: 'var(--mars-color-text-tertiary)' }}>No files generated yet</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {viewMode === 'tree' ? (
                renderTree(fileTree)
              ) : (
                filteredFiles.map(file => (
                  <button
                    key={file.id}
                    onClick={() => handleFileClick(file)}
                    className={`w-full flex items-center gap-3 p-3 rounded-mars-md transition-colors border ${
                      selectedFile?.id === file.id
                        ? 'bg-[var(--mars-color-primary-subtle)] border-[var(--mars-color-primary)]'
                        : 'hover:bg-[var(--mars-color-bg-hover)] border-[var(--mars-color-border)]'
                    }`}
                  >
                    {renderFileIcon(file.file_name)}
                    <div className="flex-1 min-w-0 text-left">
                      <p className="text-sm font-medium truncate" style={{ color: 'var(--mars-color-text)' }}>
                        {file.file_name}
                      </p>
                      <p className="text-xs truncate" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                        {file.file_path}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                        {formatFileSize(file.size_bytes)}
                      </p>
                      {file.agent_name && (
                        <p className="text-xs" style={{ color: 'var(--mars-color-text-disabled)' }}>
                          {file.agent_name}
                        </p>
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* File Preview — now uses unified FilePreview component */}
      {selectedFile && (
        <div className="w-2/3 overflow-auto" style={{ backgroundColor: 'var(--mars-color-surface-raised)' }}>
          <div
            className="sticky top-0 p-4 border-b flex items-center justify-between"
            style={{
              backgroundColor: 'var(--mars-color-surface-raised)',
              borderColor: 'var(--mars-color-border)',
              zIndex: 10,
            }}
          >
            <div className="flex items-center gap-3 min-w-0">
              {renderFileIcon(selectedFile.file_name)}
              <div className="min-w-0">
                <h4 className="text-base font-semibold truncate" style={{ color: 'var(--mars-color-text)' }}>{selectedFile.file_name}</h4>
                <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                  <span>{formatFileSize(selectedFile.size_bytes)}</span>
                  <span>Node: {selectedFile.node_id}</span>
                  {selectedFile.agent_name && <span>Agent: {selectedFile.agent_name}</span>}
                  <span>{new Date(selectedFile.created_at).toLocaleString()}</span>
                </div>
              </div>
            </div>
            <button
              onClick={() => setSelectedFile(null)}
              className="p-2 rounded-mars-md hover:bg-[var(--mars-color-bg-hover)] transition-colors"
              style={{ color: 'var(--mars-color-text-tertiary)' }}
              aria-label="Close preview"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-4">
            <FilePreview
              fileName={selectedFile.file_name}
              filePath={selectedFile.file_path}
              content={selectedFile.file_content}
              mimeType={selectedFile.mime_type}
              contentType={selectedFile.content_type}
              encoding={selectedFile.encoding}
              sizeBytes={selectedFile.size_bytes}
              base64Content={selectedFile.content_type === 'image' && selectedFile.encoding === 'base64' ? selectedFile.file_content || undefined : undefined}
              loading={loadingContent}
              onDownload={selectedFile.file_content ? () => handleDownload(selectedFile) : undefined}
            />
          </div>
        </div>
      )}
    </div>
  );
}
