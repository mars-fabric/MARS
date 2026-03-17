// components/workflow/WorkflowTimeline.tsx

'use client';

import { CheckCircle, XCircle, Clock, Play, Pause, RotateCw } from 'lucide-react';

interface TimelineStep {
  id: string;
  stepNumber: number;
  description: string;
  status: string;
  startedAt?: string;
  completedAt?: string;
  duration?: string;
  agent?: string;
  error?: string;
}

interface WorkflowTimelineProps {
  steps: TimelineStep[];
  currentStepId?: string;
}

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-gray-400" />,
  running: <Play className="w-4 h-4 text-blue-400 animate-pulse" />,
  completed: <CheckCircle className="w-4 h-4 text-green-400" />,
  failed: <XCircle className="w-4 h-4 text-red-400" />,
  paused: <Pause className="w-4 h-4 text-yellow-400" />,
  retrying: <RotateCw className="w-4 h-4 text-orange-400 animate-spin" />,
};

const statusColors: Record<string, string> = {
  pending: 'border-gray-600',
  running: 'border-blue-500 bg-blue-500/10',
  completed: 'border-green-500',
  failed: 'border-red-500 bg-red-500/10',
  paused: 'border-yellow-500',
  retrying: 'border-orange-500 bg-orange-500/10',
};

export function WorkflowTimeline({ steps, currentStepId }: WorkflowTimelineProps) {
  if (steps.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400">
        <p>No steps yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {steps.map((step, index) => (
        <div
          key={step.id}
          className={`
            relative flex items-start p-3 rounded-lg border-l-4 transition-all
            ${statusColors[step.status] || statusColors.pending}
            ${step.id === currentStepId ? 'ring-2 ring-blue-400/50' : ''}
          `}
        >
          {/* Connection Line */}
          {index < steps.length - 1 && (
            <div className="absolute left-5 top-10 bottom-0 w-px bg-gray-700 -ml-px" />
          )}

          {/* Status Icon */}
          <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-gray-800 border border-gray-700 mr-3">
            {statusIcons[step.status] || statusIcons.pending}
          </div>

          {/* Content */}
          <div className="flex-grow min-w-0">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-400">Step {step.stepNumber}</span>
                {step.agent && (
                  <span className="text-xs px-2 py-0.5 bg-gray-700 rounded text-gray-300">
                    {step.agent}
                  </span>
                )}
              </div>
              {step.duration && (
                <span className="text-xs text-gray-400">{step.duration}</span>
              )}
            </div>

            <p className="text-sm text-white truncate" title={step.description}>
              {step.description}
            </p>

            {step.error && (
              <p className="text-xs text-red-400 mt-1 truncate" title={step.error}>
                {step.error}
              </p>
            )}

            {/* Time Info */}
            {(step.startedAt || step.completedAt) && (
              <div className="flex items-center space-x-4 mt-1 text-xs text-gray-500">
                {step.startedAt && (
                  <span>Started: {new Date(step.startedAt).toLocaleTimeString()}</span>
                )}
                {step.completedAt && (
                  <span>Ended: {new Date(step.completedAt).toLocaleTimeString()}</span>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
