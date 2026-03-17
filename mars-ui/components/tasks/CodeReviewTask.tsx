'use client'

import { ArrowLeft, Construction } from 'lucide-react'

interface CodeReviewTaskProps {
  onBack: () => void
}

export default function CodeReviewTask({ onBack }: CodeReviewTaskProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
      <header className="bg-black/20 backdrop-blur-sm border-b border-white/10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center space-x-4">
            <button
              onClick={onBack}
              className="p-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-white">AI Code Review</h1>
              <p className="text-sm text-gray-300">AI-powered code review assistant</p>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-12">
        <div className="max-w-2xl mx-auto text-center">
          <Construction className="w-24 h-24 text-orange-400 mx-auto mb-6 opacity-50" />
          <h2 className="text-3xl font-bold text-white mb-4">Coming Soon</h2>
          <p className="text-gray-400 text-lg mb-8">
            This task will provide AI-powered code review suggestions, security analysis, 
            and best practice recommendations for your pull requests.
          </p>
          <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6 text-left">
            <h3 className="text-white font-semibold mb-4">Planned Features:</h3>
            <ul className="space-y-2 text-gray-400">
              <li>• Security vulnerability detection</li>
              <li>• Code quality analysis</li>
              <li>• Performance optimization suggestions</li>
              <li>• Best practices and design patterns</li>
              <li>• Integration with GitHub/GitLab PRs</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
