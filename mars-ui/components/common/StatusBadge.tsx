// components/common/StatusBadge.tsx

'use client';

import {
  Clock,
  Play,
  CheckCircle,
  XCircle,
  Pause,
  HelpCircle,
  Loader2,
} from 'lucide-react';

type WorkflowStatus =
  | 'draft'
  | 'planning'
  | 'executing'
  | 'paused'
  | 'waiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled';

interface StatusBadgeProps {
  status: WorkflowStatus | string;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  showLabel?: boolean;
  pulse?: boolean;
}

const statusConfig: Record<
  WorkflowStatus,
  {
    label: string;
    icon: React.ReactNode;
    bgColor: string;
    textColor: string;
    borderColor: string;
  }
> = {
  draft: {
    label: 'Draft',
    icon: <Clock className="w-full h-full" />,
    bgColor: 'bg-gray-500/20',
    textColor: 'text-gray-400',
    borderColor: 'border-gray-500/30',
  },
  planning: {
    label: 'Planning',
    icon: <Loader2 className="w-full h-full animate-spin" />,
    bgColor: 'bg-blue-500/20',
    textColor: 'text-blue-400',
    borderColor: 'border-blue-500/30',
  },
  executing: {
    label: 'Executing',
    icon: <Play className="w-full h-full" />,
    bgColor: 'bg-blue-500/20',
    textColor: 'text-blue-400',
    borderColor: 'border-blue-500/30',
  },
  paused: {
    label: 'Paused',
    icon: <Pause className="w-full h-full" />,
    bgColor: 'bg-yellow-500/20',
    textColor: 'text-yellow-400',
    borderColor: 'border-yellow-500/30',
  },
  waiting_approval: {
    label: 'Waiting Approval',
    icon: <HelpCircle className="w-full h-full animate-pulse" />,
    bgColor: 'bg-purple-500/20',
    textColor: 'text-purple-400',
    borderColor: 'border-purple-500/30',
  },
  completed: {
    label: 'Completed',
    icon: <CheckCircle className="w-full h-full" />,
    bgColor: 'bg-green-500/20',
    textColor: 'text-green-400',
    borderColor: 'border-green-500/30',
  },
  failed: {
    label: 'Failed',
    icon: <XCircle className="w-full h-full" />,
    bgColor: 'bg-red-500/20',
    textColor: 'text-red-400',
    borderColor: 'border-red-500/30',
  },
  cancelled: {
    label: 'Cancelled',
    icon: <XCircle className="w-full h-full" />,
    bgColor: 'bg-gray-500/20',
    textColor: 'text-gray-400',
    borderColor: 'border-gray-500/30',
  },
};

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1 text-sm',
  lg: 'px-4 py-1.5 text-base',
};

const iconSizes = {
  sm: 'w-3 h-3',
  md: 'w-4 h-4',
  lg: 'w-5 h-5',
};

export function StatusBadge({
  status,
  size = 'md',
  showIcon = true,
  showLabel = true,
  pulse = false,
}: StatusBadgeProps) {
  const config = statusConfig[status as WorkflowStatus] || statusConfig.draft;
  const isActive = status === 'executing' || status === 'planning';

  return (
    <div
      className={`
        inline-flex items-center space-x-1.5 rounded-full border font-medium
        ${config.bgColor} ${config.textColor} ${config.borderColor}
        ${sizeClasses[size]}
        ${pulse || isActive ? 'animate-pulse' : ''}
      `}
    >
      {showIcon && (
        <div className={iconSizes[size]}>
          {config.icon}
        </div>
      )}
      {showLabel && <span>{config.label}</span>}
    </div>
  );
}
