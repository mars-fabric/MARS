// types/mars-ui.ts

export type NavItem = {
  id: string
  label: string
  icon: string  // Lucide icon name
  href: string
  badge?: number | string
}

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl'

export type ModalState = {
  consoleOpen: boolean
  workflowOpen: boolean
}

export type SessionPillData = {
  sessionId: string
  name: string
  status: 'active' | 'paused' | 'queued' | 'completed' | 'failed'
  progress?: number  // 0-100
  mode?: string
}

export type ToastType = 'info' | 'success' | 'warning' | 'error'

export type ToastData = {
  id: string
  type: ToastType
  title: string
  message?: string
  duration?: number  // ms, default 5000
  action?: {
    label: string
    onClick: () => void
  }
}
