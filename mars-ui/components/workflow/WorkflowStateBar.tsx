// components/workflow/WorkflowStateBar.tsx

'use client';

import { DollarSign, Layers, Timer } from 'lucide-react';
import { StatusBadge } from '@/components/common/StatusBadge';
import { ProgressBar } from '@/components/common/ProgressBar';
import { WorkflowControls } from './WorkflowControls';

interface WorkflowStateBarProps {
  status: string;
  progress: number;
  totalSteps: number;
  completedSteps: number;
  totalCost?: number;
  elapsedTime?: string;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
}

export function WorkflowStateBar({
  status,
  progress,
  totalSteps,
  completedSteps,
  totalCost = 0,
  elapsedTime = '0:00',
  onPause,
  onResume,
  onCancel,
}: WorkflowStateBarProps) {
  return (
    <div className="bg-gray-800/50 backdrop-blur border border-gray-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        {/* Status and Controls */}
        <div className="flex items-center space-x-4">
          <StatusBadge status={status} size="lg" />
          <WorkflowControls
            status={status}
            onPause={onPause}
            onResume={onResume}
            onCancel={onCancel}
          />
        </div>

        {/* Quick Stats */}
        <div className="flex items-center space-x-6">
          {/* Steps */}
          <div className="flex items-center space-x-2 text-gray-400">
            <Layers className="w-4 h-4" />
            <span className="text-sm">
              <span className="text-white font-medium">{completedSteps}</span>
              <span className="mx-1">/</span>
              <span>{totalSteps}</span>
              <span className="ml-1">steps</span>
            </span>
          </div>

          {/* Time */}
          <div className="flex items-center space-x-2 text-gray-400">
            <Timer className="w-4 h-4" />
            <span className="text-sm text-white font-medium">{elapsedTime}</span>
          </div>

          {/* Cost */}
          <div className="flex items-center space-x-2 text-gray-400">
            <DollarSign className="w-4 h-4" />
            <span className="text-sm text-white font-medium">
              ${totalCost.toFixed(4)}
            </span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <ProgressBar
        progress={progress}
        label="Overall Progress"
        animated={status === 'executing'}
        color={status === 'failed' ? 'red' : status === 'completed' ? 'green' : 'blue'}
      />
    </div>
  );
}
