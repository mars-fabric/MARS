// components/dag/DAGNodeDetails.tsx

'use client';

import { X, Clock, Bot, FileText, AlertTriangle, RotateCw, Code, Download } from 'lucide-react';
import { DAGNodeData, statusColors } from '@/types/dag';
import { useEffect, useState } from 'react';

interface DAGNodeDetailsProps {
  node: DAGNodeData | null;
  onClose: () => void;
  onPlayFromNode?: (nodeId: string) => void;
}

interface NodeFile {
  id: string;
  file_path: string;
  file_type: string;
  size_bytes: number;
  created_at: string;
}

interface NodeEvent {
  id: string;
  event_type: string;
  agent_name?: string;
  timestamp: string;
  duration_ms?: number;
  inputs?: any;
  outputs?: any;
}

export function DAGNodeDetails({ node, onClose, onPlayFromNode }: DAGNodeDetailsProps) {
  const [files, setFiles] = useState<NodeFile[]>([]);
  const [events, setEvents] = useState<NodeEvent[]>([]);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    if (node) {
      fetchNodeDetails();
    }
  }, [node]);
  
  const fetchNodeDetails = async () => {
    if (!node) return;
    
    setLoading(true);
    try {
      // Fetch files
      // CRITICAL: Always pass run_id to avoid getting events from wrong workflow runs
      const runId = node.runId || node.run_id;
      
      const filesRes = await fetch(`/api/nodes/${node.id}/files?run_id=${runId}`);
      if (filesRes.ok) {
        const filesData = await filesRes.json();
        setFiles(filesData.files || []);
      }
      
      // Fetch events with run_id filter
      const eventsRes = await fetch(`/api/nodes/${node.id}/events?run_id=${runId}&include_internal=false`);
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
  
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };
  
  const getFileIcon = (fileType: string) => {
    switch (fileType) {
      case 'code': return <Code className="w-4 h-4 text-green-500" />;
      case 'data': return <FileText className="w-4 h-4 text-blue-500" />;
      case 'plot': return <FileText className="w-4 h-4 text-purple-500" />;
      default: return <FileText className="w-4 h-4 text-gray-500" />;
    }
  };

  if (!node) return null;

  const statusColor = statusColors[node.status];

  return (
    <div className="absolute top-4 right-4 z-10 w-96 bg-gray-800/95 backdrop-blur rounded-lg border border-gray-700 shadow-xl max-h-[90vh] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <h3 className="text-sm font-medium text-white">Node Details</h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-700 rounded transition-colors"
        >
          <X className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      {/* Content - Scrollable */}
      <div className="p-4 space-y-4 overflow-y-auto flex-1">
        {/* Status Badge */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 uppercase">Status</span>
          <div
            className="flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium"
            style={{
              backgroundColor: `${statusColor}20`,
              color: statusColor,
            }}
          >
            <span>{node.status}</span>
          </div>
        </div>

        {/* Label */}
        <div>
          <span className="text-xs text-gray-400 uppercase block mb-1">Task</span>
          <span className="text-sm text-white">{node.label}</span>
        </div>

        {/* Type */}
        <div>
          <span className="text-xs text-gray-400 uppercase block mb-1">Type</span>
          <span className="text-sm text-white capitalize">{node.type}</span>
        </div>

        {/* Agent */}
        {node.agent && (
          <div className="flex items-center space-x-2">
            <Bot className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-white">{node.agent}</span>
          </div>
        )}

        {/* Timing */}
        {(node.startedAt || node.completedAt) && (
          <div className="space-y-1">
            {node.startedAt && (
              <div className="flex items-center space-x-2 text-xs">
                <Clock className="w-3 h-3 text-gray-400" />
                <span className="text-gray-400">Started:</span>
                <span className="text-white">
                  {new Date(node.startedAt).toLocaleTimeString()}
                </span>
              </div>
            )}
            {node.completedAt && (
              <div className="flex items-center space-x-2 text-xs">
                <Clock className="w-3 h-3 text-gray-400" />
                <span className="text-gray-400">Completed:</span>
                <span className="text-white">
                  {new Date(node.completedAt).toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Files Section */}
        {files.length > 0 && (
          <div className="border-t border-gray-700 pt-4">
            <h4 className="text-xs text-gray-400 uppercase mb-2 flex items-center">
              <FileText className="w-3 h-3 mr-1" />
              Files Generated ({files.length})
            </h4>
            <div className="space-y-2">
              {files.map((file) => (
                <div 
                  key={file.id} 
                  className="bg-gray-700/50 rounded p-2 text-xs hover:bg-gray-700/70 transition-colors"
                >
                  <div className="flex items-center space-x-2 mb-1">
                    {getFileIcon(file.file_type)}
                    <span className="text-white flex-1 truncate font-mono" title={file.file_path}>
                      {file.file_path.split('/').pop()}
                    </span>
                  </div>
                  <div className="flex justify-between text-gray-400">
                    <span className="capitalize">{file.file_type}</span>
                    <span>{formatFileSize(file.size_bytes)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Events Summary */}
        {events.length > 0 && (
          <div className="border-t border-gray-700 pt-4">
            <h4 className="text-xs text-gray-400 uppercase mb-2">
              Execution Events ({events.length})
            </h4>
            <div className="space-y-1">
              {events.slice(0, 5).map((event) => (
                <div key={event.id} className="text-xs text-gray-300 flex justify-between">
                  <span className="truncate flex-1">
                    {event.event_type} {event.agent_name && `@ ${event.agent_name}`}
                  </span>
                  <span className="text-gray-500 ml-2">
                    {event.duration_ms ? `${event.duration_ms}ms` : '-'}
                  </span>
                </div>
              ))}
              {events.length > 5 && (
                <div className="text-xs text-gray-500 italic">
                  +{events.length - 5} more events
                </div>
              )}
            </div>
          </div>
        )}

        {/* Retry Info */}
        {node.retryInfo && (
          <div className="flex items-center space-x-2 text-orange-400">
            <RotateCw className="w-4 h-4" />
            <span className="text-sm">
              Retry attempt {node.retryInfo.attemptNumber} of {node.retryInfo.maxAttempts}
            </span>
          </div>
        )}

        {/* Error */}
        {node.error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <div className="flex items-center space-x-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <span className="text-xs text-red-400 uppercase">Error</span>
            </div>
            <p className="text-sm text-red-300">{node.error}</p>
          </div>
        )}

        {/* Description */}
        {node.description && (
          <div className="p-3 bg-gray-700/50 rounded-lg">
            <div className="flex items-center space-x-2 mb-2">
              <FileText className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-400 uppercase">Description</span>
            </div>
            <p className="text-sm text-gray-300">{node.description}</p>
          </div>
        )}
      </div>

      {/* Actions */}
      {onPlayFromNode && node.status !== 'running' && (
        <div className="px-4 py-3 border-t border-gray-700">
          <button
            onClick={() => onPlayFromNode(node.id)}
            className="w-full px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Play from this node
          </button>
        </div>
      )}
    </div>
  );
}
