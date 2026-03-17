// components/dag/DAGHistoryView.tsx
'use client';

import { useState, useEffect } from 'react';
import { 
  Clock, 
  GitBranch, 
  User, 
  FileText, 
  AlertCircle,
  ChevronRight,
  Activity,
  Zap,
  CheckCircle2,
  XCircle,
  Filter,
  X
} from 'lucide-react';
import { getApiUrl } from '@/lib/config';

interface DAGHistoryViewProps {
  runId: string;
}

interface HistoryEvent {
  id: string;
  timestamp: string;
  event_type: string;
  event_subtype?: string;
  node_id?: string;
  agent_name?: string;
  description?: string;
  meta?: any;
  inputs?: any;
  outputs?: any;
  error_message?: string;
  status?: string;
  duration_ms?: number;
}

export function DAGHistoryView({ runId }: DAGHistoryViewProps) {
  const [events, setEvents] = useState<HistoryEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<HistoryEvent | null>(null);
  const [filterType, setFilterType] = useState<string>('all');

  useEffect(() => {
    fetchHistory();
  }, [runId, filterType]);

  const fetchHistory = async () => {
    if (!runId) return;
    
    setLoading(true);
    setError(null);
    try {
      const url = filterType === 'all' 
        ? getApiUrl(`/api/runs/${runId}/history`)
        : getApiUrl(`/api/runs/${runId}/history?event_type=${filterType}`);
      
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch history: ${response.statusText}`);
      }
      const data = await response.json();
      setEvents(data.events || []);
    } catch (err) {
      console.error('Error fetching history:', err);
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setLoading(false);
    }
  };

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'agent_call':
      case 'agent_message': return <User className="w-4 h-4" />;
      case 'code_exec':
      case 'code_execution': return <FileText className="w-4 h-4" />;
      case 'tool_call': return <Zap className="w-4 h-4" />;
      case 'handoff': return <GitBranch className="w-4 h-4" />;
      case 'file_gen': return <FileText className="w-4 h-4" />;
      default: return <Activity className="w-4 h-4" />;
    }
  };

  const getEventColor = (type: string, status?: string) => {
    if (status === 'failed') return 'text-red-400 bg-red-500/10';
    if (status === 'completed') return 'text-green-400 bg-green-500/10';
    
    switch (type) {
      case 'agent_call':
      case 'agent_message': return 'text-blue-400 bg-blue-500/10';
      case 'code_exec':
      case 'code_execution': return 'text-purple-400 bg-purple-500/10';
      case 'tool_call': return 'text-yellow-400 bg-yellow-500/10';
      case 'handoff': return 'text-cyan-400 bg-cyan-500/10';
      case 'file_gen': return 'text-green-400 bg-green-500/10';
      default: return 'text-gray-400 bg-gray-500/10';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit'
    });
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const eventTypes = [
    { value: 'all', label: 'All Events' },
    { value: 'agent_call', label: 'Agent Calls' },
    { value: 'code_exec', label: 'Code Execution' },
    { value: 'tool_call', label: 'Tool Calls' },
    { value: 'handoff', label: 'Handoffs' },
    { value: 'file_gen', label: 'File Generation' },
  ];

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">Loading execution history...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <div className="text-center text-red-400">
          <AlertCircle className="w-12 h-12 mx-auto mb-4" />
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex bg-gray-900">
      {/* Events List */}
      <div className="flex-1 overflow-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-white">
              Execution History
              <span className="ml-2 text-sm text-gray-400">({events.length} events)</span>
            </h3>
            
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="px-3 py-1.5 text-sm bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {eventTypes.map(type => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
            </div>
          </div>

          {events.length === 0 ? (
            <div className="text-center py-12">
              <Activity className="w-12 h-12 text-gray-600 mx-auto mb-3" />
              <p className="text-gray-400">No history events yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {events.map((event) => (
                <button
                  key={event.id}
                  onClick={() => setSelectedEvent(event)}
                  className={`w-full text-left p-4 rounded-lg transition-colors border ${
                    selectedEvent?.id === event.id
                      ? 'bg-blue-900/30 border-blue-700'
                      : 'hover:bg-gray-800/50 border-gray-700 hover:border-gray-600'
                  }`}
                >
                  <div className="flex items-start gap-3 relative">
                    <div className={`flex-shrink-0 p-2 rounded ${getEventColor(event.event_type, event.status)}`}>
                      {getEventIcon(event.event_type)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white">
                            {event.event_type.replace(/_/g, ' ').toUpperCase()}
                          </span>
                          {event.event_subtype && (
                            <span className="text-xs text-gray-400">({event.event_subtype})</span>
                          )}
                          {event.status && (
                            <span className={`flex items-center gap-1 text-xs ${
                              event.status === 'completed' ? 'text-green-400' :
                              event.status === 'failed' ? 'text-red-400' :
                              'text-blue-400'
                            }`}>
                              {event.status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                              {event.status === 'failed' && <XCircle className="w-3 h-3" />}
                              {event.status}
                            </span>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-3 text-xs text-gray-400">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatTime(event.timestamp)}
                          </span>
                          {event.duration_ms && <span>{formatDuration(event.duration_ms)}</span>}
                        </div>
                      </div>

                      {event.agent_name && (
                        <div className="text-sm text-gray-400 mb-1">
                          Agent: <span className="text-white font-mono">{event.agent_name}</span>
                        </div>
                      )}

                      {event.node_id && (
                        <div className="text-xs text-gray-500">
                          Node: <span className="font-mono">{event.node_id}</span>
                        </div>
                      )}

                      {event.error_message && (
                        <div className="mt-2 text-sm text-red-400 flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                          <span className="break-words line-clamp-2">{event.error_message}</span>
                        </div>
                      )}
                    </div>

                    <ChevronRight className="w-4 h-4 text-gray-600 flex-shrink-0 mt-1" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Event Details Panel */}
      {selectedEvent && (
        <div className="w-96 border-l border-gray-700 bg-gray-800/50 overflow-auto">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded ${getEventColor(selectedEvent.event_type, selectedEvent.status)}`}>
                  {getEventIcon(selectedEvent.event_type)}
                </div>
                <h4 className="text-lg font-semibold text-white">Event Details</h4>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <div className="text-xs text-gray-500 uppercase mb-1">Type</div>
                <div className="text-white font-semibold">
                  {selectedEvent.event_type.replace(/_/g, ' ')}
                </div>
              </div>

              <div>
                <div className="text-xs text-gray-500 uppercase mb-1">Timestamp</div>
                <div className="text-white font-mono text-sm">
                  {new Date(selectedEvent.timestamp).toLocaleString()}
                </div>
              </div>

              {selectedEvent.duration_ms && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Duration</div>
                  <div className="text-white">{formatDuration(selectedEvent.duration_ms)}</div>
                </div>
              )}

              {selectedEvent.agent_name && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Agent</div>
                  <div className="text-white font-mono">{selectedEvent.agent_name}</div>
                </div>
              )}

              {selectedEvent.node_id && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Node ID</div>
                  <div className="text-white font-mono text-sm">{selectedEvent.node_id}</div>
                </div>
              )}

              {selectedEvent.status && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Status</div>
                  <div className={`inline-flex items-center gap-1 px-2 py-1 rounded text-sm ${
                    selectedEvent.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                    selectedEvent.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                    'bg-blue-500/20 text-blue-400'
                  }`}>
                    {selectedEvent.status === 'completed' && <CheckCircle2 className="w-4 h-4" />}
                    {selectedEvent.status === 'failed' && <XCircle className="w-4 h-4" />}
                    {selectedEvent.status}
                  </div>
                </div>
              )}

              {selectedEvent.error_message && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Error</div>
                  <div className="p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm whitespace-pre-wrap">
                    {selectedEvent.error_message}
                  </div>
                </div>
              )}

              {selectedEvent.inputs && Object.keys(selectedEvent.inputs).length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Inputs</div>
                  <pre className="p-3 bg-gray-900 rounded text-xs text-gray-300 overflow-x-auto max-h-40 overflow-y-auto">
                    {JSON.stringify(selectedEvent.inputs, null, 2)}
                  </pre>
                </div>
              )}

              {selectedEvent.outputs && Object.keys(selectedEvent.outputs).length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Outputs</div>
                  <pre className="p-3 bg-gray-900 rounded text-xs text-gray-300 overflow-x-auto max-h-40 overflow-y-auto">
                    {JSON.stringify(selectedEvent.outputs, null, 2)}
                  </pre>
                </div>
              )}

              {selectedEvent.meta && Object.keys(selectedEvent.meta).length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Metadata</div>
                  <pre className="p-3 bg-gray-900 rounded text-xs text-gray-300 overflow-x-auto max-h-60 overflow-y-auto">
                    {JSON.stringify(selectedEvent.meta, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
