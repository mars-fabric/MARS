// components/dag/NodeActionDialog.tsx
'use client';

import { useState, useEffect, useMemo } from 'react';
import { format } from 'date-fns';
import {
  X,
  Clock,
  Bot,
  FileText,
  AlertTriangle,
  RotateCw,
  Code,
  Download,
  Play,
  Zap,
  Activity,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Wrench,
  GitBranch,
  CheckCircle,
  Settings2,
  ClipboardList,
  UserCheck,
  Layers,
  Sparkles,
  TrendingUp,
  Database,
  Eye,
  Info,
} from 'lucide-react';
import { DAGNodeData, statusColors, NodeType } from '@/types/dag';

interface NodeActionDialogProps {
  node: DAGNodeData | null;
  runId?: string;
  onClose: () => void;
  onPlayFromNode?: (nodeId: string) => void;
  onCreateBranch?: (nodeId: string) => void;
}

interface NodeFile {
  id: string;
  file_path: string;
  file_type: string;
  size_bytes: number;
  created_at: string;
}

interface ExecutionEvent {
  id: string;
  event_type: string;
  event_subtype?: string;
  agent_name?: string;
  timestamp: string;
  duration_ms?: number;
  execution_order: number;
  depth: number;
  status: string;
  inputs?: any;
  outputs?: any;
  error_message?: string;
  meta?: any;
}

type TabType = 'overview' | 'events' | 'files' | 'metrics';

const nodeTypeIcons: Record<NodeType, any> = {
  planning: ClipboardList,
  control: Settings2,
  agent: Bot,
  approval: UserCheck,
  parallel: GitBranch,
  terminator: CheckCircle,
};

export function NodeActionDialog({ node, runId, onClose, onPlayFromNode, onCreateBranch }: NodeActionDialogProps) {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [files, setFiles] = useState<NodeFile[]>([]);
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [playConfirm, setPlayConfirm] = useState(false);
  const [branchConfirm, setBranchConfirm] = useState(false);

  useEffect(() => {
    if (node) {
      fetchNodeDetails();
    }
  }, [node]);

  const fetchNodeDetails = async () => {
    if (!node) return;

    setLoading(true);
    try {
      // Get runId from node or prop
      const effectiveRunId = node.runId || node.run_id || runId;
      
      // Build query params with run_id if available
      const params = new URLSearchParams();
      if (effectiveRunId) {
        params.set('run_id', effectiveRunId);
      }
      params.set('include_internal', 'false');
      
      const queryString = params.toString();
      
      // Fetch files
      const filesRes = await fetch(`http://localhost:8000/api/nodes/${node.id}/files?${queryString}`);
      if (filesRes.ok) {
        const filesData = await filesRes.json();
        setFiles(filesData.files || []);
      }

      // Fetch events with run_id filter
      const eventsRes = await fetch(`http://localhost:8000/api/nodes/${node.id}/events?${queryString}`);
      if (eventsRes.ok) {
        const eventsData = await eventsRes.json();
        setEvents(eventsData.events || []);
      }
    } catch (error) {
      console.error('Error fetching node details:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleEventExpansion = (eventId: string) => {
    setExpandedEvents((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(eventId)) {
        newSet.delete(eventId);
      } else {
        newSet.add(eventId);
      }
      return newSet;
    });
  };

  // Computed metrics
  const metrics = useMemo(() => {
    if (!node) return null;

    const duration = node.startedAt && node.completedAt
      ? new Date(node.completedAt).getTime() - new Date(node.startedAt).getTime()
      : null;

    const totalEventDuration = events.reduce((sum, e) => sum + (e.duration_ms || 0), 0);
    const avgEventDuration = events.length > 0 ? totalEventDuration / events.length : 0;

    const eventsByType = events.reduce((acc, e) => {
      acc[e.event_type] = (acc[e.event_type] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return {
      duration,
      totalEvents: events.length,
      totalEventDuration,
      avgEventDuration,
      eventsByType,
      filesGenerated: files.length,
      totalFileSize: files.reduce((sum, f) => sum + f.size_bytes, 0),
    };
  }, [node, events, files]);

  if (!node) return null;

  const statusColor = statusColors[node.status];
  const NodeIcon = nodeTypeIcons[node.type] || Bot;

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const getFileIcon = (fileType: string) => {
    switch (fileType) {
      case 'code':
        return <Code className="w-4 h-4 text-green-500" />;
      case 'data':
        return <Database className="w-4 h-4 text-blue-500" />;
      case 'plot':
        return <Activity className="w-4 h-4 text-purple-500" />;
      default:
        return <FileText className="w-4 h-4 text-gray-500" />;
    }
  };

  const getEventColor = (eventType: string) => {
    const colors: Record<string, string> = {
      agent_call: 'bg-blue-500',
      tool_call: 'bg-purple-500',
      code_exec: 'bg-green-500',
      file_gen: 'bg-yellow-500',
      handoff: 'bg-orange-500',
      error: 'bg-red-500',
    };
    return colors[eventType] || 'bg-gray-500';
  };

  const getEventIcon = (eventType: string) => {
    const icons: Record<string, any> = {
      agent_call: MessageSquare,
      tool_call: Wrench,
      code_exec: Code,
      file_gen: FileText,
      error: AlertTriangle,
    };
    const Icon = icons[eventType] || Activity;
    return <Icon className="w-3 h-3" />;
  };

  const getEventTitle = (event: ExecutionEvent) => {
    if (event.event_type === 'code_exec') {
      const lang = event.meta?.language || event.inputs?.language || 'python';
      return `Code Execution (${lang})`;
    }
    if (event.event_type === 'tool_call') {
      const tool = event.meta?.tool_name || event.inputs?.tool || 'unknown';
      return `Tool: ${tool}`;
    }
    if (event.event_type === 'file_gen') {
      return 'File Generated';
    }
    if (event.event_type === 'agent_call') {
      return event.event_subtype === 'message' ? 'Agent Message' : 'Agent Action';
    }
    return event.event_type.replace('_', ' ').toUpperCase();
  };

  const getEventDescription = (event: ExecutionEvent) => {
    if (event.event_type === 'code_exec' && event.inputs?.code) {
      const codePreview = event.inputs.code.split('\n')[0].slice(0, 60);
      return `${codePreview}...`;
    }
    if (event.event_type === 'tool_call' && event.inputs?.tool) {
      const args = event.inputs.args ? event.inputs.args.slice(0, 40) : '';
      return `${event.inputs.tool}(${args}${args.length >= 40 ? '...' : ''})`;
    }
    if (event.event_type === 'file_gen' && (event.outputs?.file_path || event.meta?.file_path)) {
      const filePath = event.outputs?.file_path || event.meta?.file_path;
      return filePath;
    }
    if (event.outputs?.full_content && event.outputs.full_content !== 'None') {
      return event.outputs.full_content.slice(0, 100);
    }
    if (event.inputs?.message && event.inputs.message !== 'None' && event.inputs.message !== '') {
      return event.inputs.message.slice(0, 100);
    }
    return event.event_subtype || 'Processing...';
  };

  const renderEventDetails = (event: ExecutionEvent, isExpanded: boolean) => {
    if (!isExpanded) return null;

    return (
      <div className="mt-3 ml-9 space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
        {/* Code Display */}
        {event.inputs?.code && (
          <div className="bg-gray-900 rounded-lg p-3 overflow-auto max-h-64 border border-gray-700">
            <div className="text-xs text-gray-400 mb-2 flex items-center gap-2">
              <Code className="w-3 h-3" />
              Code:
            </div>
            <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap">
              {event.inputs.code}
            </pre>
          </div>
        )}

        {/* Inputs Display */}
        {event.inputs && !event.inputs.code && Object.keys(event.inputs).length > 0 && (
          <div className="bg-blue-500/10 rounded-lg p-3 border border-blue-500/30">
            <div className="text-xs font-semibold text-blue-400 mb-2 flex items-center gap-1">
              <Download className="w-3 h-3 rotate-180" /> Inputs:
            </div>
            {event.inputs.message && (
              <div className="text-sm text-gray-300 whitespace-pre-wrap">{event.inputs.message}</div>
            )}
            {event.inputs.tool && (
              <div className="text-sm text-gray-300">
                <span className="font-medium">Tool:</span> {event.inputs.tool}
                {event.inputs.args && (
                  <div className="mt-1 text-xs bg-gray-800/50 rounded p-2 overflow-auto">
                    <pre className="text-gray-400">{event.inputs.args}</pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Outputs Display */}
        {event.outputs && Object.keys(event.outputs).length > 0 && (
          <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/30">
            <div className="text-xs font-semibold text-green-400 mb-2 flex items-center gap-1">
              <Download className="w-3 h-3" /> Outputs:
            </div>
            {event.outputs.full_content && (
              <div className="text-sm text-gray-300 whitespace-pre-wrap max-h-48 overflow-auto">
                {event.outputs.full_content}
              </div>
            )}
            {event.outputs.result && !event.outputs.full_content && (
              <div className="text-sm font-mono bg-gray-800/50 rounded p-2 overflow-auto max-h-48 text-gray-300">
                {event.outputs.result}
              </div>
            )}
            {event.outputs.file_path && (
              <div className="text-sm text-gray-300">
                <span className="font-medium">File:</span> {event.outputs.file_path}
              </div>
            )}
          </div>
        )}

        {/* Metadata */}
        {event.meta && Object.keys(event.meta).length > 0 && (
          <div className="bg-gray-700/30 rounded-lg p-2 border border-gray-600">
            <div className="text-xs text-gray-400 flex flex-wrap gap-3">
              {event.meta.language && (
                <span className="flex items-center gap-1">
                  <Code className="w-3 h-3" />
                  Language: {event.meta.language}
                </span>
              )}
              {event.meta.tool_name && (
                <span className="flex items-center gap-1">
                  <Wrench className="w-3 h-3" />
                  Tool: {event.meta.tool_name}
                </span>
              )}
              {event.meta.files_written && event.meta.files_written.length > 0 && (
                <span className="flex items-center gap-1">
                  <FileText className="w-3 h-3" />
                  Files: {event.meta.files_written.join(', ')}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Error Message */}
        {event.error_message && (
          <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/30">
            <div className="text-xs font-semibold text-red-400 mb-1 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              Error:
            </div>
            <div className="text-sm text-red-300">{event.error_message}</div>
          </div>
        )}
      </div>
    );
  };

  const renderOverviewTab = () => (
    <div className="space-y-4">
      {/* Status Card */}
      <div className="relative overflow-hidden rounded-xl border border-gray-700 bg-gradient-to-br from-gray-800 to-gray-900 p-6">
        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-full blur-3xl" />
        <div className="relative">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div
                className="p-3 rounded-lg"
                style={{
                  backgroundColor: `${statusColor}20`,
                }}
              >
                <NodeIcon className="w-6 h-6" style={{ color: statusColor }} />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">{node.label}</h3>
                <p className="text-sm text-gray-400 capitalize">{node.type}</p>
              </div>
            </div>
            <div
              className="px-4 py-2 rounded-full text-sm font-semibold"
              style={{
                backgroundColor: `${statusColor}20`,
                color: statusColor,
                border: `1px solid ${statusColor}40`,
              }}
            >
              {node.status}
            </div>
          </div>

          {node.agent && (
            <div className="flex items-center gap-2 text-gray-300 bg-gray-800/50 rounded-lg p-3">
              <Bot className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium">Agent:</span>
              <span className="text-sm">{node.agent}</span>
            </div>
          )}
        </div>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-2 gap-3">
        {metrics?.duration && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-2 text-gray-400 mb-2">
              <Clock className="w-4 h-4" />
              <span className="text-xs uppercase">Duration</span>
            </div>
            <div className="text-2xl font-bold text-white">{formatDuration(metrics.duration)}</div>
          </div>
        )}
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 mb-2">
            <Activity className="w-4 h-4" />
            <span className="text-xs uppercase">Events</span>
          </div>
          <div className="text-2xl font-bold text-white">{events.length}</div>
        </div>
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 mb-2">
            <FileText className="w-4 h-4" />
            <span className="text-xs uppercase">Files</span>
          </div>
          <div className="text-2xl font-bold text-white">{files.length}</div>
        </div>
        {metrics?.avgEventDuration && metrics.avgEventDuration > 0 && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-2 text-gray-400 mb-2">
              <TrendingUp className="w-4 h-4" />
              <span className="text-xs uppercase">Avg Time</span>
            </div>
            <div className="text-2xl font-bold text-white">{metrics.avgEventDuration.toFixed(0)}ms</div>
          </div>
        )}
      </div>

      {/* Timing Details */}
      {(node.startedAt || node.completedAt) && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 space-y-2">
          <div className="text-xs text-gray-400 uppercase mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Timeline
          </div>
          {node.startedAt && (
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-400">Started</span>
              <span className="text-white font-mono">
                {new Date(node.startedAt).toLocaleTimeString()}
              </span>
            </div>
          )}
          {node.completedAt && (
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-400">Completed</span>
              <span className="text-white font-mono">
                {new Date(node.completedAt).toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Retry Info */}
      {node.retryInfo && (
        <div className="flex items-center gap-3 p-4 bg-orange-500/10 border border-orange-500/30 rounded-lg">
          <RotateCw className="w-5 h-5 text-orange-400" />
          <div>
            <div className="text-sm font-medium text-orange-400">Retry in Progress</div>
            <div className="text-xs text-orange-300">
              Attempt {node.retryInfo.attemptNumber} of {node.retryInfo.maxAttempts}
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {node.error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <span className="text-sm font-semibold text-red-400">Error Occurred</span>
          </div>
          <p className="text-sm text-red-300">{node.error}</p>
        </div>
      )}

      {/* Goal - Primary objective of this step */}
      {node.goal && (
        <div className="p-4 bg-gradient-to-br from-emerald-900/20 to-teal-900/20 border border-emerald-500/30 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-emerald-400" />
            <span className="text-xs text-emerald-400 uppercase font-semibold">Goal</span>
          </div>
          <p className="text-sm text-gray-200 font-medium">{node.goal}</p>
        </div>
      )}

      {/* Summary - What was accomplished */}
      {node.summary && (
        <div className="p-4 bg-gradient-to-br from-purple-900/20 to-indigo-900/20 border border-purple-500/30 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-purple-400 uppercase font-semibold">Summary</span>
          </div>
          <p className="text-sm text-gray-300">{node.summary}</p>
        </div>
      )}

      {/* Bullet Points / Instructions */}
      {node.bulletPoints && node.bulletPoints.length > 0 && (
        <div className="p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
          <div className="flex items-center gap-2 mb-3">
            <ClipboardList className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-gray-400 uppercase">Instructions</span>
          </div>
          <ul className="space-y-2">
            {node.bulletPoints.map((point: string, idx: number) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-gray-300">
                <span className="text-blue-400 mt-1">•</span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Description - Full description if different from goal */}
      {node.description && node.description !== node.goal && (
        <div className="p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Info className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-gray-400 uppercase">Description</span>
          </div>
          <p className="text-sm text-gray-300 whitespace-pre-line">{node.description}</p>
        </div>
      )}

      {/* Generated Plan (for planning nodes) */}
      {node.type === 'planning' && node.generated_plan && (
        <div className="p-4 bg-gradient-to-br from-blue-900/20 to-purple-900/20 border border-blue-500/30 rounded-lg">
          <div className="flex items-center gap-2 mb-3">
            <ClipboardList className="w-5 h-5 text-blue-400" />
            <span className="text-sm font-semibold text-blue-400 uppercase">Generated Plan</span>
          </div>
          <div className="space-y-3">
            {node.generated_plan.step_count && (
              <div className="text-sm text-gray-300">
                <span className="font-medium text-blue-300">Total Steps:</span>{' '}
                {node.generated_plan.step_count}
              </div>
            )}
            {node.generated_plan.breakdown && (
              <div className="text-sm text-gray-300">
                <span className="font-medium text-blue-300">Breakdown:</span>{' '}
                {node.generated_plan.breakdown}
              </div>
            )}
            {node.generated_plan.sub_tasks && (
              <div className="mt-3 space-y-2">
                <div className="text-xs text-blue-300 uppercase font-semibold">Sub-Tasks:</div>
                {node.generated_plan.sub_tasks.map((task, idx) => (
                  <div
                    key={idx}
                    className="bg-gray-800/50 border border-gray-700 rounded-lg p-3"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <div className="text-xs font-mono text-blue-400 bg-blue-500/20 px-2 py-0.5 rounded">
                        #{idx + 1}
                      </div>
                      {task.sub_task_agent && (
                        <div className="flex items-center gap-1 text-xs text-gray-400">
                          <Bot className="w-3 h-3" />
                          <span>{task.sub_task_agent}</span>
                        </div>
                      )}
                    </div>
                    {/* sub_task is the main field */}
                    <div className="text-sm text-gray-300 mt-2 font-medium">
                      {task.sub_task || 'No description'}
                    </div>
                    {/* Show bullet points if available */}
                    {task.bullet_points && task.bullet_points.length > 0 && (
                      <ul className="mt-2 space-y-1 ml-2">
                        {task.bullet_points.map((point: string, pointIdx: number) => (
                          <li key={pointIdx} className="flex items-start gap-2 text-xs text-gray-400">
                            <span className="text-blue-400 mt-0.5">•</span>
                            <span>{point}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}
            {node.generated_plan.steps && (
              <div className="mt-3 space-y-2">
                <div className="text-xs text-blue-300 uppercase font-semibold">Steps:</div>
                {node.generated_plan.steps.map((step, idx) => (
                  <div
                    key={idx}
                    className="bg-gray-800/50 border border-gray-700 rounded-lg p-3"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <div className="text-xs font-mono text-blue-400 bg-blue-500/20 px-2 py-0.5 rounded">
                        #{step.step_number || idx + 1}
                      </div>
                    </div>
                    <div className="text-sm text-gray-300 mt-2">
                      {step.description || step.title || 'No description'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );

  const renderEventsTab = () => (
    <div className="space-y-3">
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
        </div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-gray-400">
          <Activity className="w-12 h-12 mb-3 opacity-50" />
          <p className="text-sm">No execution events recorded</p>
          <p className="text-xs text-gray-500 mt-1">Events will appear as the node executes</p>
        </div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-gradient-to-b from-gray-700 via-gray-600 to-gray-700" />

          {/* Events */}
          {events.map((event, index) => {
            const isExpanded = expandedEvents.has(event.id);
            return (
              <div
                key={event.id}
                className="relative mb-2"
                style={{ marginLeft: `${event.depth * 16}px` }}
              >
                {/* Event dot */}
                <div
                  className={`absolute left-2.5 w-5 h-5 rounded-full ${getEventColor(
                    event.event_type
                  )} flex items-center justify-center text-white z-10 shadow-lg ring-2 ring-gray-900`}
                >
                  {getEventIcon(event.event_type)}
                </div>

                {/* Event content */}
                <div className="ml-11">
                  <div
                    className="cursor-pointer p-3 rounded-lg hover:bg-gray-800/50 transition-all border border-transparent hover:border-gray-700"
                    onClick={() => toggleEventExpansion(event.id)}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex items-center gap-2 flex-1">
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        )}
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-sm text-white">
                              {getEventTitle(event)}
                            </span>
                            {event.agent_name && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                {event.agent_name}
                              </span>
                            )}
                            {event.duration_ms && (
                              <span className="text-xs text-gray-500 flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {event.duration_ms}ms
                              </span>
                            )}
                          </div>
                          {!isExpanded && (
                            <div className="text-xs text-gray-400 mt-1 truncate">
                              {getEventDescription(event)}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="text-xs text-gray-500 font-mono ml-2 flex-shrink-0">
                        {event.timestamp && format(new Date(event.timestamp), 'HH:mm:ss.SSS')}
                      </div>
                    </div>
                  </div>

                  {renderEventDetails(event, isExpanded)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  const renderFilesTab = () => (
    <div className="space-y-3">
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
        </div>
      ) : files.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-gray-400">
          <FileText className="w-12 h-12 mb-3 opacity-50" />
          <p className="text-sm">No files generated yet</p>
          <p className="text-xs text-gray-500 mt-1">Files will appear here when created</p>
        </div>
      ) : (
        <>
          {/* File Stats */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3">
              <div className="text-xs text-gray-400 uppercase mb-1">Total Files</div>
              <div className="text-2xl font-bold text-white">{files.length}</div>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3">
              <div className="text-xs text-gray-400 uppercase mb-1">Total Size</div>
              <div className="text-2xl font-bold text-white">
                {formatFileSize(metrics?.totalFileSize || 0)}
              </div>
            </div>
          </div>

          {/* File List */}
          <div className="space-y-2">
            {files.map((file) => (
              <div
                key={file.id}
                className="group bg-gray-800/50 hover:bg-gray-800 border border-gray-700 hover:border-gray-600 rounded-lg p-4 transition-all cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">{getFileIcon(file.file_type)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className="text-sm font-mono text-white truncate"
                        title={file.file_path}
                      >
                        {file.file_path.split('/').pop()}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 capitalize flex-shrink-0">
                        {file.file_type}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-gray-400">
                      <span>{formatFileSize(file.size_bytes)}</span>
                      <span>•</span>
                      <span>{format(new Date(file.created_at), 'MMM d, HH:mm')}</span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1 font-mono truncate">
                      {file.file_path}
                    </div>
                  </div>
                  <button className="opacity-0 group-hover:opacity-100 transition-opacity p-2 hover:bg-gray-700 rounded">
                    <Eye className="w-4 h-4 text-gray-400" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );

  const renderMetricsTab = () => (
    <div className="space-y-4">
      {/* Performance Metrics */}
      <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/30 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="w-5 h-5 text-purple-400" />
          <h3 className="text-sm font-semibold text-purple-300 uppercase">Performance</h3>
        </div>

        <div className="space-y-3">
          {metrics?.duration && (
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-400">Total Duration</span>
                <span className="text-white font-mono">{formatDuration(metrics.duration)}</span>
              </div>
              <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                  style={{ width: '100%' }}
                />
              </div>
            </div>
          )}

          {metrics && metrics.totalEventDuration > 0 && (
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-400">Event Processing Time</span>
                <span className="text-white font-mono">
                  {formatDuration(metrics.totalEventDuration)}
                </span>
              </div>
              <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-green-500 to-emerald-500"
                  style={{
                    width: metrics.duration
                      ? `${(metrics.totalEventDuration / metrics.duration) * 100}%`
                      : '100%',
                  }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Event Type Breakdown */}
      {metrics && Object.keys(metrics.eventsByType).length > 0 && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <Layers className="w-5 h-5 text-blue-400" />
            <h3 className="text-sm font-semibold text-blue-300 uppercase">Event Breakdown</h3>
          </div>

          <div className="space-y-2">
            {Object.entries(metrics.eventsByType)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <div key={type} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-3 h-3 rounded-full ${getEventColor(type)}`}
                    />
                    <span className="text-sm text-gray-300 capitalize">
                      {type.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 w-24 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${getEventColor(type)}`}
                        style={{ width: `${(count / metrics.totalEvents) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm text-white font-mono w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
          <div className="text-xs text-gray-400 uppercase mb-2">Total Events</div>
          <div className="text-3xl font-bold text-white">{metrics?.totalEvents || 0}</div>
        </div>
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
          <div className="text-xs text-gray-400 uppercase mb-2">Avg Event Time</div>
          <div className="text-3xl font-bold text-white">
            {metrics?.avgEventDuration ? `${metrics.avgEventDuration.toFixed(0)}ms` : '-'}
          </div>
        </div>
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
          <div className="text-xs text-gray-400 uppercase mb-2">Files Created</div>
          <div className="text-3xl font-bold text-white">{metrics?.filesGenerated || 0}</div>
        </div>
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
          <div className="text-xs text-gray-400 uppercase mb-2">Data Size</div>
          <div className="text-3xl font-bold text-white">
            {formatFileSize(metrics?.totalFileSize || 0)}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-gray-900 rounded-2xl shadow-2xl border border-gray-700 flex flex-col animate-in slide-in-from-bottom-4 duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700 bg-gradient-to-r from-gray-800 to-gray-900">
          <div className="flex items-center gap-3">
            <div
              className="p-2 rounded-lg"
              style={{
                backgroundColor: `${statusColor}20`,
              }}
            >
              <NodeIcon className="w-5 h-5" style={{ color: statusColor }} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Node Execution Details</h2>
              <p className="text-xs text-gray-400">{node.id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-6 pt-4 border-b border-gray-700/50">
          {[
            { id: 'overview' as TabType, label: 'Overview', icon: Eye },
            { id: 'events' as TabType, label: 'Events', icon: Activity, count: events.length },
            { id: 'files' as TabType, label: 'Files', icon: FileText, count: files.length },
            { id: 'metrics' as TabType, label: 'Metrics', icon: TrendingUp },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? 'bg-gray-800 text-white border-t-2 border-blue-500'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className="px-1.5 py-0.5 text-xs rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'overview' && renderOverviewTab()}
          {activeTab === 'events' && renderEventsTab()}
          {activeTab === 'files' && renderFilesTab()}
          {activeTab === 'metrics' && renderMetricsTab()}
        </div>

        {/* Actions Footer */}
        {(onPlayFromNode || onCreateBranch) && node.status !== 'running' && (
          <div className="px-6 py-4 border-t border-gray-700 bg-gray-800/50 space-y-3">
            {/* Play from Node Button */}
            {onPlayFromNode && !playConfirm && !branchConfirm && (
              <button
                onClick={() => setPlayConfirm(true)}
                className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 text-white text-sm font-semibold rounded-lg transition-all shadow-lg hover:shadow-xl transform hover:scale-[1.02]"
              >
                <Play className="w-4 h-4" />
                Play Workflow from This Node
                <Zap className="w-4 h-4" />
              </button>
            )}

            {/* Create Branch Button */}
            {onCreateBranch && !playConfirm && !branchConfirm && (node.status === 'completed' || node.status === 'failed') && (
              <button
                onClick={() => setBranchConfirm(true)}
                className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-700 hover:to-purple-600 text-white text-sm font-semibold rounded-lg transition-all shadow-lg hover:shadow-xl transform hover:scale-[1.02]"
              >
                <GitBranch className="w-4 h-4" />
                Create Branch from This Node
              </button>
            )}

            {/* Play Confirmation */}
            {playConfirm && (
              <div className="space-y-3 animate-in slide-in-from-bottom-2 duration-200">
                <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="text-sm font-medium text-yellow-300">Confirm Action</div>
                      <div className="text-xs text-yellow-200/80 mt-1">
                        This will restart the workflow execution from node "{node.label}". All
                        subsequent nodes will be re-executed.
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPlayConfirm(false)}
                    className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      onPlayFromNode!(node.id);
                      onClose();
                    }}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-r from-green-600 to-green-500 hover:from-green-700 hover:to-green-600 text-white text-sm font-semibold rounded-lg transition-all shadow-lg"
                  >
                    <Zap className="w-4 h-4" />
                    Confirm & Execute
                  </button>
                </div>
              </div>
            )}

            {/* Branch Confirmation */}
            {branchConfirm && (
              <div className="space-y-3 animate-in slide-in-from-bottom-2 duration-200">
                <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                  <div className="flex items-start gap-2">
                    <GitBranch className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="text-sm font-medium text-purple-300">Create Branch</div>
                      <div className="text-xs text-purple-200/80 mt-1">
                        This will open the branch creation dialog. You can provide new instructions
                        for the planner while keeping all work completed up to this point.
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setBranchConfirm(false)}
                    className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      onCreateBranch!(node.id);
                      onClose();
                    }}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-700 hover:to-purple-600 text-white text-sm font-semibold rounded-lg transition-all shadow-lg"
                  >
                    <GitBranch className="w-4 h-4" />
                    Open Branch Dialog
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
