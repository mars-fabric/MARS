'use client'

import { useMemo } from 'react'

interface MarkdownRendererProps {
  content: string
}

/**
 * Lightweight Markdown renderer using regex transforms.
 * Renders into HTML with .mars-markdown class for styling via mars.css.
 * (No extra dependency required.)
 */
export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const html = useMemo(() => renderMarkdown(content), [content])

  return (
    <div
      className="mars-markdown px-4 py-3"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderMarkdown(md: string): string {
  let html = ''
  const lines = md.split('\n')
  let inCodeBlock = false
  let codeBlockContent = ''
  let codeBlockLang = ''
  let inList: 'ul' | 'ol' | null = null

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Code blocks
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        html += `<pre><code>${escapeHtml(codeBlockContent.trimEnd())}</code></pre>\n`
        codeBlockContent = ''
        inCodeBlock = false
      } else {
        if (inList) { html += inList === 'ul' ? '</ul>' : '</ol>'; inList = null }
        codeBlockLang = line.slice(3).trim()
        inCodeBlock = true
      }
      continue
    }

    if (inCodeBlock) {
      codeBlockContent += line + '\n'
      continue
    }

    // Close lists if needed
    const isListItem = line.match(/^(\s*[-*]|\s*\d+\.)\s/)
    if (!isListItem && inList) {
      html += inList === 'ul' ? '</ul>\n' : '</ol>\n'
      inList = null
    }

    // Blank line
    if (line.trim() === '') {
      if (inList) { html += inList === 'ul' ? '</ul>\n' : '</ol>\n'; inList = null }
      continue
    }

    // Headings
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      const level = headingMatch[1].length
      html += `<h${level}>${inlineMarkdown(headingMatch[2])}</h${level}>\n`
      continue
    }

    // Horizontal rules
    if (line.match(/^(-{3,}|_{3,}|\*{3,})$/)) {
      html += '<hr>\n'
      continue
    }

    // Blockquotes
    if (line.startsWith('> ')) {
      html += `<blockquote><p>${inlineMarkdown(line.slice(2))}</p></blockquote>\n`
      continue
    }

    // Unordered list items
    const ulMatch = line.match(/^\s*[-*]\s+(.+)$/)
    if (ulMatch) {
      if (inList !== 'ul') {
        if (inList) html += '</ol>\n'
        html += '<ul>\n'
        inList = 'ul'
      }
      html += `  <li>${inlineMarkdown(ulMatch[1])}</li>\n`
      continue
    }

    // Ordered list items
    const olMatch = line.match(/^\s*\d+\.\s+(.+)$/)
    if (olMatch) {
      if (inList !== 'ol') {
        if (inList) html += '</ul>\n'
        html += '<ol>\n'
        inList = 'ol'
      }
      html += `  <li>${inlineMarkdown(olMatch[1])}</li>\n`
      continue
    }

    // Paragraph
    html += `<p>${inlineMarkdown(line)}</p>\n`
  }

  // Close any open blocks
  if (inCodeBlock) {
    html += `<pre><code>${escapeHtml(codeBlockContent.trimEnd())}</code></pre>\n`
  }
  if (inList) {
    html += inList === 'ul' ? '</ul>\n' : '</ol>\n'
  }

  return html
}

function inlineMarkdown(text: string): string {
  let result = escapeHtml(text)
  // Bold
  result = result.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  result = result.replace(/__(.+?)__/g, '<strong>$1</strong>')
  // Italic
  result = result.replace(/\*(.+?)\*/g, '<em>$1</em>')
  result = result.replace(/_(.+?)_/g, '<em>$1</em>')
  // Inline code
  result = result.replace(/`(.+?)`/g, '<code>$1</code>')
  // Links [text](url)
  result = result.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
  return result
}
