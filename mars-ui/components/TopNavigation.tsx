'use client'

import { usePathname, useRouter } from 'next/navigation'
import { Brain, ListTodo } from 'lucide-react'

export default function TopNavigation() {
  const pathname = usePathname()
  const router = useRouter()

  const isResearchMode = pathname === '/'
  const isTasksMode = pathname === '/tasks'

  return (
    <div className="bg-black/20 backdrop-blur-sm border-b border-white/10">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div className="py-4">
            <h1 className="text-2xl font-bold text-white">
              MARS
            </h1>
          </div>

          {/* Mode Switcher */}
          <div className="flex items-center space-x-2 bg-black/30 rounded-lg p-1">
            <button
              onClick={() => router.push('/')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-md transition-all ${
                isResearchMode
                  ? 'bg-blue-500 text-white shadow-lg'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Brain className="w-4 h-4" />
              <span className="font-medium">Research</span>
            </button>
            <button
              onClick={() => router.push('/tasks')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-md transition-all ${
                isTasksMode
                  ? 'bg-purple-500 text-white shadow-lg'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <ListTodo className="w-4 h-4" />
              <span className="font-medium">Tasks</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
