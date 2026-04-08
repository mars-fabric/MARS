'use client'

import React, { useState, useCallback, useRef, useEffect } from 'react'

interface ResizableSplitPaneProps {
          left: React.ReactNode
          right: React.ReactNode
          /** Initial width of the right pane in pixels (default 320) */
          defaultRightWidth?: number
          /** Minimum width of the right pane in pixels (default 200) */
          minRightWidth?: number
          /** Maximum width of the right pane in pixels (default 600) */
          maxRightWidth?: number
          /** Minimum width of the left pane in pixels (default 300) */
          minLeftWidth?: number
          /** Additional className for the container */
          className?: string
          /** Additional style for the container */
          style?: React.CSSProperties
}

export default function ResizableSplitPane({
          left,
          right,
          defaultRightWidth = 320,
          minRightWidth = 200,
          maxRightWidth = 600,
          minLeftWidth = 300,
          className = '',
          style,
}: ResizableSplitPaneProps) {
          const [rightWidth, setRightWidth] = useState(defaultRightWidth)
          const [isDragging, setIsDragging] = useState(false)
          const containerRef = useRef<HTMLDivElement>(null)
          const startXRef = useRef(0)
          const startWidthRef = useRef(0)

          const handleMouseDown = useCallback((e: React.MouseEvent) => {
                    e.preventDefault()
                    setIsDragging(true)
                    startXRef.current = e.clientX
                    startWidthRef.current = rightWidth
          }, [rightWidth])

          useEffect(() => {
                    if (!isDragging) return

                    const handleMouseMove = (e: MouseEvent) => {
                              const containerWidth = containerRef.current?.offsetWidth ?? 0
                              const delta = startXRef.current - e.clientX
                              let newWidth = startWidthRef.current + delta

                              // Effective max: the smaller of maxRightWidth or what leaves minLeftWidth for the left pane
                              const effectiveMax = Math.min(maxRightWidth, containerWidth - minLeftWidth - 8)

                              // Clamp to min/effective-max right width
                              newWidth = Math.max(minRightWidth, Math.min(effectiveMax, newWidth))

                              setRightWidth(newWidth)
                    }

                    const handleMouseUp = () => {
                              setIsDragging(false)
                    }

                    document.addEventListener('mousemove', handleMouseMove)
                    document.addEventListener('mouseup', handleMouseUp)
                    return () => {
                              document.removeEventListener('mousemove', handleMouseMove)
                              document.removeEventListener('mouseup', handleMouseUp)
                    }
          }, [isDragging, minRightWidth, maxRightWidth, minLeftWidth])

          return (
                    <div
                              ref={containerRef}
                              className={`flex ${className}`}
                              style={{ ...style, userSelect: isDragging ? 'none' : undefined }}
                    >
                              {/* Left pane */}
                              <div className="flex-1 min-w-0 flex flex-col" style={{ minHeight: 0 }}>
                                        {left}
                              </div>

                              {/* Draggable divider */}
                              <div
                                        onMouseDown={handleMouseDown}
                                        className="flex-shrink-0 flex items-center justify-center group"
                                        style={{
                                                  width: '8px',
                                                  cursor: 'col-resize',
                                        }}
                              >
                                        <div
                                                  className="rounded-full transition-colors"
                                                  style={{
                                                            width: '3px',
                                                            height: '40px',
                                                            backgroundColor: isDragging
                                                                      ? 'var(--mars-color-primary)'
                                                                      : 'var(--mars-color-border)',
                                                  }}
                                        />
                              </div>

                              {/* Right pane */}
                              <div
                                        className="flex-shrink-0 flex flex-col"
                                        style={{ width: `${rightWidth}px`, minHeight: 0 }}
                              >
                                        {right}
                              </div>
                    </div>
          )
}
