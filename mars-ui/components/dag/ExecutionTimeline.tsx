import React, { useState } from 'react';
import { format } from 'date-fns';
import { Code, FileText, MessageSquare, AlertCircle, ChevronDown, ChevronRight, Wrench } from 'lucide-react';

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

interface ExecutionTimelineProps {
  events: ExecutionEvent[];
  onEventClick?: (event: ExecutionEvent) => void;
}

export default function ExecutionTimeline({ events, onEventClick }: ExecutionTimelineProps) {
  const [viewMode, setViewMode] = useState<'timeline' | 'table'>('timeline');
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set());
  
  const toggleEventExpansion = (eventId: string) => {
    setExpandedEvents(prev => {
      const newSet = new Set(prev);
      if (newSet.has(eventId)) {
        newSet.delete(eventId);
      } else {
        newSet.add(eventId);
      }
      return newSet;
    });
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
    const icons: Record<string, React.ReactNode> = {
      agent_call: <MessageSquare className="w-3 h-3" />,
      tool_call: <Wrench className="w-3 h-3" />,
      code_exec: <Code className="w-3 h-3" />,
      file_gen: <FileText className="w-3 h-3" />,
      error: <AlertCircle className="w-3 h-3" />,
    };
    return icons[eventType] || <div className="w-3 h-3 rounded-full" />;
  };
  
  const getEventTitle = (event: ExecutionEvent) => {
    if (event.event_type === 'code_exec') {
      const lang = event.meta?.language || event.inputs?.language || 'python';
      return `Code Execution (${lang})`;
    }
    if (event.event_type === 'tool_call') {
      const tool = event.meta?.tool_name || event.inputs?.tool || 'unknown';
      return `Tool Call: ${tool}`;
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
    // For code execution, show preview
    if (event.event_type === 'code_exec' && event.inputs?.code) {
      const codePreview = event.inputs.code.split('\n')[0].slice(0, 60);
      return `${codePreview}...`;
    }
    
    // For tool calls, show tool and args
    if (event.event_type === 'tool_call' && event.inputs?.tool) {
      const args = event.inputs.args ? event.inputs.args.slice(0, 40) : '';
      return `${event.inputs.tool}(${args}${args.length >= 40 ? '...' : ''})`;
    }
    
    // For file generation, show file path
    if (event.event_type === 'file_gen' && (event.outputs?.file_path || event.meta?.file_path)) {
      const filePath = event.outputs?.file_path || event.meta?.file_path;
      return filePath;
    }
    
    // For agent messages, show content
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
      <div className="mt-2 space-y-2">
        {/* Code Display */}
        {event.inputs?.code && (
          <div className="bg-gray-900 rounded p-3 overflow-auto max-h-64">
            <div className="text-xs text-gray-400 mb-2">Code:</div>
            <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap">
              {event.inputs.code}
            </pre>
          </div>
        )}
        
        {/* Inputs Display */}
        {event.inputs && !event.inputs.code && Object.keys(event.inputs).length > 0 && (
          <div className="bg-blue-50 rounded p-3 border border-blue-200">
            <div className="text-xs font-semibold text-blue-700 mb-2">📥 Inputs:</div>
            {event.inputs.message && (
              <div className="text-sm text-gray-700 whitespace-pre-wrap">{event.inputs.message}</div>
            )}
            {event.inputs.tool && (
              <div className="text-sm text-gray-700">
                <span className="font-medium">Tool:</span> {event.inputs.tool}
                {event.inputs.args && (
                  <div className="mt-1 text-xs bg-white rounded p-2 overflow-auto">
                    <pre>{event.inputs.args}</pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        
        {/* Outputs Display */}
        {event.outputs && Object.keys(event.outputs).length > 0 && (
          <div className="bg-green-50 rounded p-3 border border-green-200">
            <div className="text-xs font-semibold text-green-700 mb-2">📤 Outputs:</div>
            {event.outputs.full_content && (
              <div className="text-sm text-gray-700 whitespace-pre-wrap max-h-48 overflow-auto">
                {event.outputs.full_content}
              </div>
            )}
            {event.outputs.result && !event.outputs.full_content && (
              <div className="text-sm font-mono bg-white rounded p-2 overflow-auto max-h-48">
                {event.outputs.result}
              </div>
            )}
            {event.outputs.file_path && (
              <div className="text-sm text-gray-700">
                <span className="font-medium">File:</span> {event.outputs.file_path}
              </div>
            )}
          </div>
        )}
        
        {/* Metadata */}
        {event.meta && (
          <div className="bg-gray-50 rounded p-2 border border-gray-200">
            <div className="text-xs text-gray-500">
              {event.meta.language && <span className="mr-3">Language: {event.meta.language}</span>}
              {event.meta.tool_name && <span className="mr-3">Tool: {event.meta.tool_name}</span>}
              {event.meta.files_written && event.meta.files_written.length > 0 && (
                <span>Files: {event.meta.files_written.join(', ')}</span>
              )}
            </div>
          </div>
        )}
        
        {/* Error Message */}
        {event.error_message && (
          <div className="bg-red-50 rounded p-3 border border-red-200">
            <div className="text-xs font-semibold text-red-700 mb-1">❌ Error:</div>
            <div className="text-sm text-red-600">{event.error_message}</div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="execution-timeline p-4 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-lg font-semibold">Execution Events</h3>
          <p className="text-xs text-gray-500 mt-1">{events.length} events captured</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setViewMode('table')}
            className={`px-3 py-1 rounded text-sm flex items-center gap-1 ${viewMode === 'table' ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
          >
            📊 Table
          </button>
          <button
            onClick={() => setViewMode('timeline')}
            className={`px-3 py-1 rounded text-sm flex items-center gap-1 ${viewMode === 'timeline' ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
          >
            📈 Timeline
          </button>
        </div>
      </div>
      
      {viewMode === 'table' ? (
        <div className="flex-1 overflow-auto">
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 bg-gray-100 border-b-2 border-gray-300">
              <tr>
                <th className="text-left p-2 font-semibold">#</th>
                <th className="text-left p-2 font-semibold">Type</th>
                <th className="text-left p-2 font-semibold">Agent</th>
                <th className="text-left p-2 font-semibold">Description</th>
                <th className="text-left p-2 font-semibold">Time</th>
                <th className="text-left p-2 font-semibold">Duration</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event, index) => (
                <tr
                  key={event.id}
                  onClick={() => onEventClick?.(event)}
                  className="border-b hover:bg-blue-50 cursor-pointer"
                >
                  <td className="p-2 text-gray-500">{event.execution_order}</td>
                  <td className="p-2">
                    <span className="flex items-center gap-1">
                      <span className={`w-7 h-7 rounded-full ${getEventColor(event.event_type)} flex items-center justify-center text-white`}>
                        {getEventIcon(event.event_type)}
                      </span>
                      <span className="text-xs ml-1">{event.event_type}</span>
                    </span>
                  </td>
                  <td className="p-2">
                    <span className="text-blue-600 font-medium text-xs">{event.agent_name}</span>
                  </td>
                  <td className="p-2 max-w-md">
                    <div className="truncate text-gray-700">{getEventDescription(event)}</div>
                  </td>
                  <td className="p-2 text-xs text-gray-500">
                    {format(new Date(event.timestamp), 'HH:mm:ss')}
                  </td>
                  <td className="p-2 text-xs text-gray-500">
                    {event.duration_ms ? `${event.duration_ms}ms` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {events.length === 0 && (
            <div className="text-center text-gray-500 py-8">
              No execution events yet
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gray-300" />
            
            {/* Events */}
            <div className="space-y-2">
              {events.map((event, index) => {
                const isExpanded = expandedEvents.has(event.id);
                return (
                  <div
                    key={event.id}
                    className="relative flex items-start rounded hover:bg-gray-50 transition-colors"
                    style={{ marginLeft: `${event.depth * 20}px` }}
                  >
                    {/* Event dot */}
                    <div className={`absolute left-4 w-6 h-6 rounded-full ${getEventColor(event.event_type)} flex items-center justify-center text-white z-10 shadow-md`}>
                      {getEventIcon(event.event_type)}
                    </div>
                    
                    {/* Event content */}
                    <div className="ml-14 flex-1 pb-2">
                      <div 
                        className="cursor-pointer"
                        onClick={() => toggleEventExpansion(event.id)}
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex items-center gap-2">
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-gray-500" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-gray-500" />
                            )}
                            <div>
                              <span className="font-medium text-sm">{getEventTitle(event)}</span>
                              {event.agent_name && (
                                <span className="ml-2 text-xs text-blue-600 font-medium">
                                  @ {event.agent_name}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="text-xs text-gray-500">
                            {event.timestamp && format(new Date(event.timestamp), 'HH:mm:ss.SSS')}
                          </div>
                        </div>
                        
                        {!isExpanded && (
                          <div className="text-xs text-gray-600 mt-1 ml-6 truncate">
                            {getEventDescription(event)}
                          </div>
                        )}
                        
                        {event.duration_ms && (
                          <div className="text-xs text-gray-500 mt-1 ml-6">
                            ⏱ {event.duration_ms}ms
                          </div>
                        )}
                      </div>
                      
                      {renderEventDetails(event, isExpanded)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          
          {events.length === 0 && (
            <div className="text-center text-gray-500 py-8">
              <div className="text-4xl mb-2">📊</div>
              <div>No execution events yet</div>
              <div className="text-xs mt-1">Events will appear here as the workflow executes</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
