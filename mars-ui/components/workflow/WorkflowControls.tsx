// components/workflow/WorkflowControls.tsx

'use client';

import { useState } from 'react';
import { Play, Pause, Square, RotateCw, AlertTriangle } from 'lucide-react';

interface WorkflowControlsProps {
  status: string;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
  disabled?: boolean;
}

export function WorkflowControls({
  status,
  onPause,
  onResume,
  onCancel,
  onRetry,
  disabled = false,
}: WorkflowControlsProps) {
  const [confirmCancel, setConfirmCancel] = useState(false);

  const canPause = status === 'executing' || status === 'planning';
  const canResume = status === 'paused';
  const canCancel = ['executing', 'planning', 'paused', 'waiting_approval'].includes(status);
  const canRetry = status === 'failed';

  const handleCancel = () => {
    if (confirmCancel) {
      onCancel?.();
      setConfirmCancel(false);
    } else {
      setConfirmCancel(true);
      // Auto-reset after 3 seconds
      setTimeout(() => setConfirmCancel(false), 3000);
    }
  };

  return (
    <div className="flex items-center space-x-2">
      {/* Pause Button */}
      {canPause && (
        <div className="relative group">
          <button
            onClick={onPause}
            disabled={disabled}
            className="flex items-center space-x-2 px-4 py-2 bg-yellow-500/20 hover:bg-yellow-500/30
                       text-yellow-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Pause className="w-4 h-4" />
            <span>Pause</span>
          </button>
          {/* Tooltip */}
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 
                          bg-gray-900 text-gray-200 text-xs rounded-lg opacity-0 group-hover:opacity-100
                          transition-opacity duration-200 pointer-events-none whitespace-nowrap z-50
                          border border-gray-700 shadow-lg">
            Pauses at step boundaries (after current LLM call completes)
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1
                            border-4 border-transparent border-t-gray-900"></div>
          </div>
        </div>
      )}

      {/* Resume Button */}
      {canResume && (
        <button
          onClick={onResume}
          disabled={disabled}
          className="flex items-center space-x-2 px-4 py-2 bg-green-500/20 hover:bg-green-500/30
                     text-green-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play className="w-4 h-4" />
          <span>Resume</span>
        </button>
      )}

      {/* Cancel Button */}
      {canCancel && (
        <button
          onClick={handleCancel}
          disabled={disabled}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors
                      disabled:opacity-50 disabled:cursor-not-allowed
                      ${confirmCancel
                        ? 'bg-red-500 hover:bg-red-600 text-white'
                        : 'bg-red-500/20 hover:bg-red-500/30 text-red-400'
                      }`}
        >
          {confirmCancel ? (
            <>
              <AlertTriangle className="w-4 h-4" />
              <span>Confirm Cancel?</span>
            </>
          ) : (
            <>
              <Square className="w-4 h-4" />
              <span>Cancel</span>
            </>
          )}
        </button>
      )}

      {/* Retry Button */}
      {canRetry && (
        <button
          onClick={onRetry}
          disabled={disabled}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30
                     text-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RotateCw className="w-4 h-4" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}
