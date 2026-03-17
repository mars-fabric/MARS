// components/dag/DAGStatsPanel.tsx
'use client';

import { useMemo } from 'react';
import { 
  TrendingUp, 
  Clock, 
  Activity, 
  CheckCircle2, 
  XCircle, 
  Loader2,
  Circle,
  BarChart3,
  Timer
} from 'lucide-react';

interface DAGStatsPanelProps {
  stats: {
    total: number;
    completed: number;
    running: number;
    failed: number;
    pending: number;
    progress: number;
    duration: number | null;
    startTime: number | null;
    endTime: number | null;
  };
  nodes: any[];
  selectedNodeId: string | null;
}

export function DAGStatsPanel({ stats, nodes, selectedNodeId }: DAGStatsPanelProps) {
  // Agent-wise breakdown
  const agentStats = useMemo(() => {
    const agentMap = new Map<string, { completed: number; failed: number; total: number; running: number }>();
    
    nodes.forEach(node => {
      // Skip nodes without agent names
      if (!node.agent || node.agent === 'unknown' || node.agent.trim() === '') {
        return;
      }
      
      const agent = node.agent;
      if (!agentMap.has(agent)) {
        agentMap.set(agent, { completed: 0, failed: 0, total: 0, running: 0 });
      }
      const agentData = agentMap.get(agent)!;
      agentData.total++;
      if (node.status === 'completed') agentData.completed++;
      if (node.status === 'failed') agentData.failed++;
      if (node.status === 'running') agentData.running++;
    });
    
    return Array.from(agentMap.entries())
      .map(([agent, data]) => ({
        agent,
        ...data,
        successRate: data.total > 0 ? (data.completed / data.total) * 100 : 0
      }))
      .sort((a, b) => b.total - a.total);
  }, [nodes]);

  // Average execution time per node
  const avgExecutionTime = useMemo(() => {
    const completedNodes = nodes.filter(n => n.started_at && n.completed_at);
    if (completedNodes.length === 0) return null;
    
    const totalTime = completedNodes.reduce((sum, node) => {
      const start = new Date(node.started_at).getTime();
      const end = new Date(node.completed_at).getTime();
      return sum + (end - start);
    }, 0);
    
    return totalTime / completedNodes.length;
  }, [nodes]);

  // Retry information
  const retryStats = useMemo(() => {
    const retriedNodes = nodes.filter(n => n.retry_info?.retry_count > 0);
    const totalRetries = retriedNodes.reduce((sum, n) => sum + (n.retry_info?.retry_count || 0), 0);
    
    return {
      retriedNodes: retriedNodes.length,
      totalRetries,
      avgRetriesPerNode: retriedNodes.length > 0 ? totalRetries / retriedNodes.length : 0
    };
  }, [nodes]);

  const formatDuration = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  };

  const selectedNode = selectedNodeId ? nodes.find(n => n.id === selectedNodeId) : null;

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* Overall Progress */}
      <div className="bg-gray-800/80 rounded-lg p-4 border border-gray-700">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-blue-400" />
          Overall Progress
        </h3>
        
        {/* Progress Bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1 text-xs text-gray-400">
            <span>Completion</span>
            <span className="font-mono text-white">{stats.progress.toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all duration-500"
              style={{ width: `${stats.progress}%` }}
            />
          </div>
        </div>

        {/* Status Breakdown */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-2 p-2 bg-gray-900/50 rounded">
            <CheckCircle2 className="w-4 h-4 text-green-500" />
            <div>
              <div className="text-gray-400">Completed</div>
              <div className="font-semibold text-white">{stats.completed}</div>
            </div>
          </div>
          
          <div className="flex items-center gap-2 p-2 bg-gray-900/50 rounded">
            <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
            <div>
              <div className="text-gray-400">Running</div>
              <div className="font-semibold text-white">{stats.running}</div>
            </div>
          </div>
          
          <div className="flex items-center gap-2 p-2 bg-gray-900/50 rounded">
            <XCircle className="w-4 h-4 text-red-500" />
            <div>
              <div className="text-gray-400">Failed</div>
              <div className="font-semibold text-white">{stats.failed}</div>
            </div>
          </div>
          
          <div className="flex items-center gap-2 p-2 bg-gray-900/50 rounded">
            <Circle className="w-4 h-4 text-gray-500" />
            <div>
              <div className="text-gray-400">Pending</div>
              <div className="font-semibold text-white">{stats.pending}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Timing Information */}
      {stats.duration && (
        <div className="bg-gray-800/80 rounded-lg p-4 border border-gray-700">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4 text-purple-400" />
            Timing
          </h3>
          
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Total Duration</span>
              <span className="font-mono text-white">{formatDuration(stats.duration)}</span>
            </div>
            
            {avgExecutionTime && (
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Avg per Node</span>
                <span className="font-mono text-white">{formatDuration(avgExecutionTime)}</span>
              </div>
            )}
            
            {stats.startTime && (
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Started</span>
                <span className="font-mono text-white">
                  {new Date(stats.startTime).toLocaleTimeString()}
                </span>
              </div>
            )}
            
            {stats.endTime && (
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Ended</span>
                <span className="font-mono text-white">
                  {new Date(stats.endTime).toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Agent Breakdown */}
      {agentStats.length > 0 && (
        <div className="bg-gray-800/80 rounded-lg p-4 border border-gray-700">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-orange-400" />
            Agent Breakdown
          </h3>
          
          <div className="space-y-2">
            {agentStats.map(({ agent, completed, failed, total, successRate }) => (
              <div key={agent} className="text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-gray-300 truncate" title={agent}>{agent}</span>
                  <span className="text-gray-400">{completed}/{total}</span>
                </div>
                <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all ${
                      failed > 0 ? 'bg-red-500' : 'bg-green-500'
                    }`}
                    style={{ width: `${successRate}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Retry Statistics */}
      {retryStats.retriedNodes > 0 && (
        <div className="bg-gray-800/80 rounded-lg p-4 border border-gray-700">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <Timer className="w-4 h-4 text-yellow-400" />
            Retries
          </h3>
          
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Nodes with Retries</span>
              <span className="font-mono text-white">{retryStats.retriedNodes}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Total Retries</span>
              <span className="font-mono text-white">{retryStats.totalRetries}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Avg per Node</span>
              <span className="font-mono text-white">{retryStats.avgRetriesPerNode.toFixed(1)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Selected Node Details */}
      {selectedNode && (
        <div className="bg-blue-900/20 rounded-lg p-4 border border-blue-700">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-blue-400" />
            Selected Node
          </h3>
          
          <div className="space-y-2 text-xs">
            <div>
              <span className="text-gray-400">ID:</span>
              <div className="font-mono text-white mt-0.5 break-all">{selectedNode.id}</div>
            </div>
            
            <div>
              <span className="text-gray-400">Label:</span>
              <div className="text-white mt-0.5">{selectedNode.label}</div>
            </div>
            
            <div>
              <span className="text-gray-400">Agent:</span>
              <div className="text-white mt-0.5">{selectedNode.agent || 'N/A'}</div>
            </div>
            
            <div>
              <span className="text-gray-400">Status:</span>
              <div className="mt-0.5">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  selectedNode.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                  selectedNode.status === 'running' ? 'bg-blue-500/20 text-blue-400' :
                  selectedNode.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                  'bg-gray-500/20 text-gray-400'
                }`}>
                  {selectedNode.status}
                </span>
              </div>
            </div>
            
            {selectedNode.started_at && selectedNode.completed_at && (
              <div>
                <span className="text-gray-400">Duration:</span>
                <div className="font-mono text-white mt-0.5">
                  {formatDuration(
                    new Date(selectedNode.completed_at).getTime() - 
                    new Date(selectedNode.started_at).getTime()
                  )}
                </div>
              </div>
            )}
            
            {selectedNode.error && (
              <div>
                <span className="text-gray-400">Error:</span>
                <div className="text-red-400 mt-0.5 break-words">{selectedNode.error}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
