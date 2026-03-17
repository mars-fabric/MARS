'use client'

import { Github } from 'lucide-react'
import { ConnectionStatus } from '@/components/common/ConnectionStatus'
import { useWebSocketContext } from '@/contexts/WebSocketContext'

export default function Header() {
  const { connected, reconnectAttempt, lastError, reconnect } = useWebSocketContext()

  return (
    <header className="bg-black/20 backdrop-blur-sm border-b border-white/10">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div>
              <h1 className="text-2xl font-bold text-white">MARS</h1>
              <p className="text-sm text-gray-300">Autonomous Research Platform</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <ConnectionStatus
              connected={connected}
              reconnectAttempt={reconnectAttempt}
              lastError={lastError}
              onReconnect={reconnect}
            />

            <a
              href="https://github.com/CMBAgents/cmbagent"
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 text-gray-400 hover:text-white transition-colors"
            >
              <Github className="w-5 h-5" />
            </a>
          </div>
        </div>
      </div>
    </header>
  )
}
