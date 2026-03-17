// components/retry/RetryHistory.tsx

'use client';

import { CheckCircle, XCircle, Clock } from 'lucide-react';
import { RetryHistoryItem } from '@/types/retry';

interface RetryHistoryProps {
  history: RetryHistoryItem[];
}

export function RetryHistory({ history }: RetryHistoryProps) {
  if (history.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <h4 className="text-xs text-gray-400 mb-2">Retry History</h4>
      <div className="space-y-1">
        {history.map((item, index) => (
          <div
            key={index}
            className={`flex items-center justify-between p-2 rounded text-xs ${
              item.succeeded ? 'bg-green-500/10' : 'bg-red-500/10'
            }`}
          >
            <div className="flex items-center space-x-2">
              {item.succeeded ? (
                <CheckCircle className="w-3 h-3 text-green-400" />
              ) : (
                <XCircle className="w-3 h-3 text-red-400" />
              )}
              <span className="text-gray-300">
                Attempt {item.attempt_number}
              </span>
            </div>
            <div className="flex items-center space-x-2 text-gray-400">
              <Clock className="w-3 h-3" />
              <span>{new Date(item.timestamp).toLocaleTimeString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
