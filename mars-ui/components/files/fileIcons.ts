// components/files/fileIcons.ts — Consistent Lucide file-type icon mapping
import {
  FileText,
  Code,
  Image,
  Database,
  File,
  FileJson,
  FileSpreadsheet,
  FileType,
  Folder,
  FolderOpen,
  MessageSquare,
  BarChart3,
  Clock,
  type LucideIcon,
} from 'lucide-react'

export interface FileIconMapping {
  icon: LucideIcon
  color: string
}

const extensionMap: Record<string, FileIconMapping> = {
  // Code files
  py: { icon: Code, color: '#3B82F6' },
  js: { icon: Code, color: '#F59E0B' },
  ts: { icon: Code, color: '#3B82F6' },
  tsx: { icon: Code, color: '#3B82F6' },
  jsx: { icon: Code, color: '#F59E0B' },
  html: { icon: Code, color: '#EF4444' },
  css: { icon: Code, color: '#8B5CF6' },
  scss: { icon: Code, color: '#EC4899' },
  // Data files
  json: { icon: FileJson, color: '#F59E0B' },
  yaml: { icon: FileText, color: '#22C55E' },
  yml: { icon: FileText, color: '#22C55E' },
  xml: { icon: FileText, color: '#EF4444' },
  csv: { icon: FileSpreadsheet, color: '#22C55E' },
  tsv: { icon: FileSpreadsheet, color: '#22C55E' },
  // Document files
  md: { icon: FileType, color: '#6B7280' },
  txt: { icon: FileText, color: '#6B7280' },
  pdf: { icon: FileText, color: '#EF4444' },
  doc: { icon: FileText, color: '#3B82F6' },
  docx: { icon: FileText, color: '#3B82F6' },
  // Image files
  png: { icon: Image, color: '#8B5CF6' },
  jpg: { icon: Image, color: '#8B5CF6' },
  jpeg: { icon: Image, color: '#8B5CF6' },
  gif: { icon: Image, color: '#8B5CF6' },
  svg: { icon: Image, color: '#F59E0B' },
  webp: { icon: Image, color: '#8B5CF6' },
  bmp: { icon: Image, color: '#8B5CF6' },
  tiff: { icon: Image, color: '#8B5CF6' },
  tif: { icon: Image, color: '#8B5CF6' },
  // Database files
  db: { icon: Database, color: '#F97316' },
  sql: { icon: Database, color: '#F97316' },
  sqlite: { icon: Database, color: '#F97316' },
  // Log files
  log: { icon: FileText, color: '#6B7280' },
}

const directoryMap: Record<string, FileIconMapping> = {
  chats: { icon: MessageSquare, color: '#3B82F6' },
  codebase: { icon: Code, color: '#22C55E' },
  cost: { icon: BarChart3, color: '#F59E0B' },
  data: { icon: Folder, color: '#8B5CF6' },
  time: { icon: Clock, color: '#F97316' },
}

/**
 * Get the icon and color for a file by its name/extension.
 */
export function getFileIconConfig(fileName: string, isDirectory = false): FileIconMapping {
  if (isDirectory) {
    return directoryMap[fileName] || { icon: Folder, color: '#3B82F6' }
  }

  const ext = fileName.split('.').pop()?.toLowerCase() || ''
  return extensionMap[ext] || { icon: File, color: '#6B7280' }
}

/**
 * Get the icon for an expanded directory.
 */
export function getOpenDirectoryIcon(): FileIconMapping {
  return { icon: FolderOpen, color: '#3B82F6' }
}

/**
 * Detect if a file is viewable as text.
 */
export function isTextFile(fileName: string): boolean {
  const ext = fileName.split('.').pop()?.toLowerCase() || ''
  const textExtensions = [
    'py', 'js', 'ts', 'tsx', 'jsx', 'html', 'css', 'scss',
    'json', 'yaml', 'yml', 'xml', 'md', 'txt', 'log', 'csv', 'tsv',
    'sql', 'sh', 'bash', 'env', 'toml', 'ini', 'cfg', 'conf',
    'gitignore', 'dockerfile', 'makefile',
  ]
  return textExtensions.includes(ext) || !ext
}

/**
 * Detect if a file is an image.
 */
export function isImageFile(fileName: string, mimeType?: string): boolean {
  if (mimeType?.startsWith('image/')) return true
  const ext = fileName.split('.').pop()?.toLowerCase() || ''
  return ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'tiff', 'tif'].includes(ext)
}

/**
 * Detect if a file is a CSV/TSV.
 */
export function isCSVFile(fileName: string): boolean {
  const ext = fileName.split('.').pop()?.toLowerCase() || ''
  return ['csv', 'tsv'].includes(ext)
}

/**
 * Detect if a file is Markdown.
 */
export function isMarkdownFile(fileName: string): boolean {
  const ext = fileName.split('.').pop()?.toLowerCase() || ''
  return ext === 'md'
}

/**
 * Get syntax highlighting language for a file extension.
 */
export function getLanguageFromFileName(fileName: string): string {
  const ext = fileName.split('.').pop()?.toLowerCase() || ''
  const langMap: Record<string, string> = {
    py: 'python',
    js: 'javascript',
    ts: 'typescript',
    tsx: 'tsx',
    jsx: 'jsx',
    html: 'html',
    css: 'css',
    scss: 'scss',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    xml: 'xml',
    sql: 'sql',
    sh: 'bash',
    bash: 'bash',
    md: 'markdown',
  }
  return langMap[ext] || 'text'
}
