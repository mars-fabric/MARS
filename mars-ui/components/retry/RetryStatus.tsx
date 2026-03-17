// components/retry/RetryStatus.tsx

'use client';

import { useState, useEffect } from 'react';
import {
  RotateCw,
  AlertTriangle,
  Clock,
  Lightbulb,
  TrendingUp,
  Timer,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { RetryInfo, ErrorCategory } from '@/types/retry';

interface RetryStatusProps {
  retryInfo: RetryInfo;
  onManualRetry?: () => void;
  onProvideContext?: (context: string) => void;
}

const categoryColors: Record<ErrorCategory, string> = {
  NETWORK: 'text-yellow-400 bg-yellow-500/20',
  RATE_LIMIT: 'text-orange-400 bg-orange-500/20',
  API_ERROR: 'text-red-400 bg-red-500/20',
  VALIDATION: 'text-purple-400 bg-purple-500/20',
  TIMEOUT: 'text-yellow-400 bg-yellow-500/20',
  RESOURCE: 'text-blue-400 bg-blue-500/20',
  UNKNOWN: 'text-gray-400 bg-gray-500/20',
};

const categoryDescriptions: Record<ErrorCategory, string> = {
  NETWORK: 'Network connectivity issue',
  RATE_LIMIT: 'API rate limit exceeded',
  API_ERROR: 'External API returned error',
  VALIDATION: 'Input validation failed',
  TIMEOUT: 'Operation timed out',
  RESOURCE: 'Resource not found or unavailable',
  UNKNOWN: 'Unexpected error occurred',
};

export function RetryStatus({
  retryInfo,
  onManualRetry,
  onProvideContext,
}: RetryStatusProps) {
  const [backoffRemaining, setBackoffRemaining] = useState(retryInfo.backoff_seconds || 0);
  const [userContext, setUserContext] = useState('');

  // Countdown timer for backoff
  useEffect(() => {
    if (backoffRemaining <= 0) return;

    const interval = setInterval(() => {
      setBackoffRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, [backoffRemaining]);

  // Update backoff when new retry info received
  useEffect(() => {
    setBackoffRemaining(retryInfo.backoff_seconds || 0);
  }, [retryInfo.backoff_seconds]);

  const progressPercentage = (retryInfo.attempt_number / retryInfo.max_attempts) * 100;

  return (
    <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-orange-500/20 border-b border-orange-500/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <RotateCw className="w-5 h-5 text-orange-400 animate-spin" />
            <div>
              <h3 className="text-sm font-medium text-orange-300">
                Retry in Progress
              </h3>
              <p className="text-xs text-orange-400/70">
                Step #{retryInfo.step_number}
              </p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-lg font-bold text-orange-300">
              {retryInfo.attempt_number}
            </span>
            <span className="text-sm text-orange-400/70">
              / {retryInfo.max_attempts}
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-3 h-1.5 bg-orange-900/50 rounded-full overflow-hidden">
          <div
            className="h-full bg-orange-500 rounded-full transition-all duration-500"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Error Category */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Error Category</span>
          <span className={`px-2 py-1 rounded text-xs font-medium ${categoryColors[retryInfo.error_category]}`}>
            {retryInfo.error_category}
          </span>
        </div>

        {/* Error Message */}
        <div>
          <div className="flex items-center space-x-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span className="text-xs text-gray-400">Error Message</span>
          </div>
          <p className="text-sm text-red-300 bg-red-500/10 p-3 rounded-lg">
            {retryInfo.error_message}
          </p>
        </div>

        {/* Success Probability */}
        {retryInfo.success_probability !== undefined && (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-400">Success Probability</span>
            </div>
            <span className={`text-sm font-medium ${
              retryInfo.success_probability > 0.7 ? 'text-green-400' :
              retryInfo.success_probability > 0.4 ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {Math.round(retryInfo.success_probability * 100)}%
            </span>
          </div>
        )}

        {/* Strategy */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Retry Strategy</span>
          <span className="text-sm text-gray-300 capitalize">
            {retryInfo.strategy.replace('_', ' ')}
          </span>
        </div>

        {/* Backoff Timer */}
        {backoffRemaining > 0 && (
          <div className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
            <div className="flex items-center space-x-2">
              <Timer className="w-4 h-4 text-blue-400" />
              <span className="text-sm text-gray-300">Next attempt in</span>
            </div>
            <span className="text-lg font-mono text-blue-400">
              {backoffRemaining}s
            </span>
          </div>
        )}

        {/* Suggestions */}
        {retryInfo.suggestions.length > 0 && (
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <Lightbulb className="w-4 h-4 text-yellow-400" />
              <span className="text-xs text-gray-400">Suggestions</span>
            </div>
            <ul className="space-y-1">
              {retryInfo.suggestions.map((suggestion, index) => (
                <li
                  key={index}
                  className="text-sm text-gray-300 pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-yellow-400"
                >
                  {suggestion}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* User Context Input */}
        {onProvideContext && (
          <div>
            <label className="block text-xs text-gray-400 mb-2">
              Provide Additional Context (Optional)
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={userContext}
                onChange={(e) => setUserContext(e.target.value)}
                placeholder="e.g., 'Try using a different API key'"
                className="flex-grow px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-orange-500"
              />
              <button
                onClick={() => {
                  if (userContext.trim()) {
                    onProvideContext(userContext.trim());
                    setUserContext('');
                  }
                }}
                disabled={!userContext.trim()}
                className="px-4 py-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 rounded-lg transition-colors disabled:opacity-50"
              >
                Send
              </button>
            </div>
          </div>
        )}

        {/* Manual Retry Button */}
        {onManualRetry && backoffRemaining === 0 && (
          <button
            onClick={onManualRetry}
            className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-orange-500 hover:bg-orange-600 text-white font-medium rounded-lg transition-colors"
          >
            <RotateCw className="w-4 h-4" />
            <span>Retry Now</span>
          </button>
        )}
      </div>
    </div>
  );
}
