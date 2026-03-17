// components/dag/DAGNode.tsx

'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps, Node } from '@xyflow/react';
import {
  ClipboardList,
  Settings2,
  Bot,
  UserCheck,
  GitBranch,
  CheckCircle,
  Play,
  Pause,
  AlertCircle,
  RotateCw,
  Clock,
} from 'lucide-react';
import { DAGNodeData, NodeStatus, NodeType, statusColors } from '@/types/dag';

const nodeIcons: Record<NodeType, React.ReactNode> = {
  planning: <ClipboardList className="w-4 h-4" />,
  control: <Settings2 className="w-4 h-4" />,
  agent: <Bot className="w-4 h-4" />,
  approval: <UserCheck className="w-4 h-4" />,
  parallel: <GitBranch className="w-4 h-4" />,
  terminator: <CheckCircle className="w-4 h-4" />,
};

const statusIcons: Record<NodeStatus, React.ReactNode> = {
  pending: <Clock className="w-3 h-3" />,
  running: <Play className="w-3 h-3 animate-pulse" />,
  completed: <CheckCircle className="w-3 h-3" />,
  failed: <AlertCircle className="w-3 h-3" />,
  paused: <Pause className="w-3 h-3" />,
  waiting_approval: <UserCheck className="w-3 h-3 animate-pulse" />,
  retrying: <RotateCw className="w-3 h-3 animate-spin" />,
  skipped: <Clock className="w-3 h-3 opacity-50" />,
};

// Define the node type with the correct structure
type DAGNodeType = Node<DAGNodeData, 'dagNode'>;

// Use NodeProps with the full node type
type DAGNodeComponentProps = NodeProps<DAGNodeType>;

function DAGNodeComponent({ data, selected }: DAGNodeComponentProps) {
  const statusColor = statusColors[data.status];
  const isActive = data.status === 'running' || data.status === 'retrying';

  return (
    <div
      className={`
        relative px-4 py-3 rounded-lg border-2 bg-gray-900/90 backdrop-blur
        transition-all duration-200 min-w-[220px] max-w-[320px]
        ${selected ? 'ring-2 ring-blue-400 ring-offset-2 ring-offset-gray-900' : ''}
        ${isActive ? 'shadow-lg shadow-blue-500/20' : ''}
      `}
      style={{ borderColor: statusColor }}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-gray-600 !border-2 !border-gray-400"
      />

      {/* Node Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <div
            className="p-1.5 rounded"
            style={{ backgroundColor: `${statusColor}20` }}
          >
            {nodeIcons[data.type] || nodeIcons['agent']}
          </div>
          <span className="text-xs text-gray-400 uppercase">
            {data.stepNumber !== undefined && data.stepNumber > 0 ? 'STEP' : (data.type || 'agent')}
          </span>
        </div>
        <div
          className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs"
          style={{
            backgroundColor: `${statusColor}20`,
            color: statusColor,
          }}
        >
          {statusIcons[data.status]}
          <span>{data.status}</span>
        </div>
      </div>

      {/* Node Label */}
      <div className="text-sm font-medium text-white break-words line-clamp-3" title={data.label || data.id}>
        {data.stepNumber !== undefined && data.stepNumber !== null && data.stepNumber > 0 ? (
          <>
            {/* Check if label already includes step number */}
            {data.label && data.label.toLowerCase().startsWith('step') ? (
              data.label
            ) : (
              <>
                <span className="text-gray-400">Step {data.stepNumber}: </span>
                {data.goal || data.label || data.id || 'Unnamed Node'}
              </>
            )}
          </>
        ) : (
          data.label || data.id || 'Unnamed Node'
        )}
      </div>

      {/* Node Description/Goal */}
      {(data.goal || data.insights || data.description) && (
        <div className="mt-2 text-xs text-gray-400 break-words line-clamp-2" 
             title={data.goal || data.insights || data.description}>
          {data.goal || data.insights || data.description}
        </div>
      )}

      {/* Agent Info - Only show for planning/control nodes, not regular steps */}
      {data.agent && (data.type === 'planning' || data.type === 'control' || data.type === 'terminator') && (
        <div className="mt-1 text-xs text-gray-400 flex items-center space-x-1">
          <Bot className="w-3 h-3" />
          <span>{data.agent}</span>
        </div>
      )}

      {/* Retry Info */}
      {data.retryInfo && (
        <div className="mt-1 text-xs text-orange-400 flex items-center space-x-1">
          <RotateCw className="w-3 h-3" />
          <span>
            Attempt {data.retryInfo.attemptNumber}/{data.retryInfo.maxAttempts}
          </span>
        </div>
      )}

      {/* Error Preview */}
      {data.error && (
        <div className="mt-2 text-xs text-red-400 truncate" title={data.error}>
          {data.error}
        </div>
      )}

      {/* Running Animation */}
      {isActive && (
        <div
          className="absolute inset-0 rounded-lg border-2 animate-pulse pointer-events-none"
          style={{ borderColor: statusColor, opacity: 0.3 }}
        />
      )}

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-gray-600 !border-2 !border-gray-400"
      />
    </div>
  );
}

export default memo(DAGNodeComponent);
