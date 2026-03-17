'use client'

import { ReactNode } from 'react'
import { WebSocketProvider } from '@/contexts/WebSocketContext'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { ToastProvider } from '@/components/core/ToastContainer'

interface ProvidersProps {
  children: ReactNode
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <WebSocketProvider>
        <ToastProvider>
          {children}
        </ToastProvider>
      </WebSocketProvider>
    </ThemeProvider>
  )
}
