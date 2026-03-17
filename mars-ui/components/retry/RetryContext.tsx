// components/retry/RetryContext.tsx

'use client';

import { useState } from 'react';
import { Code, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';

interface RetryContextProps {
  errorMessage: string;
  traceback?: string;
  previousAttempts?: {
    attempt: number;
    error: string;
    timestamp: string;
  }[];
}

export function RetryContext({ errorMessage, traceback, previousAttempts }: RetryContextProps) {
  const [showTraceback, setShowTraceback] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyTraceback = () => {
    if (traceback) {
      navigator.clipboard.writeText(traceback);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-3">
      {/* Error Message */}
      <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
        <p className="text-sm text-red-300">{errorMessage}</p>
      </div>

      {/* Traceback */}
      {traceback && (
        <div className="border border-gray-700 rounded-lg overflow-hidden">
          <button
            onClick={() => setShowTraceback(!showTraceback)}
            className="w-full flex items-center justify-between px-4 py-2 bg-gray-800 hover:bg-gray-700 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <Code className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-300">Traceback</span>
            </div>
            <div className="flex items-center space-x-2">
              {showTraceback && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    copyTraceback();
                  }}
                  className="p-1 hover:bg-gray-600 rounded"
                >
                  {copied ? (
                    <Check className="w-4 h-4 text-green-400" />
                  ) : (
                    <Copy className="w-4 h-4 text-gray-400" />
                  )}
                </button>
              )}
              {showTraceback ? (
                <ChevronDown className="w-4 h-4 text-gray-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-400" />
              )}
            </div>
          </button>
          {showTraceback && (
            <pre className="p-4 bg-gray-900 text-xs text-gray-400 overflow-x-auto max-h-64 overflow-y-auto">
              {traceback}
            </pre>
          )}
        </div>
      )}

      {/* Previous Attempts */}
      {previousAttempts && previousAttempts.length > 0 && (
        <div>
          <h4 className="text-xs text-gray-400 mb-2">Previous Attempts</h4>
          <div className="space-y-2">
            {previousAttempts.map((attempt) => (
              <div
                key={attempt.attempt}
                className="p-2 bg-gray-800/50 rounded text-xs"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-gray-400">Attempt {attempt.attempt}</span>
                  <span className="text-gray-500">
                    {new Date(attempt.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-red-400 truncate">{attempt.error}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
