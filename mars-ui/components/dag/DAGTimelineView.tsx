// components/dag/DAGTimelineView.tsx
'use client';

import { useState, useEffect, useMemo } from 'react';
import { Clock, CheckCircle2, XCircle, Circle, AlertCircle } from 'lucide-react';
import { getApiUrl } from '@/lib/config';

interface DAGTimelineViewProps {
  runId: string;
}

interface TimelineEvent {
  id: string;
  timestamp: string;
  event_type: string;
  agent_name?: string;
  node_id?: string;
  description?: string;
  status?: string;
  duration_ms?: number;
}

export function DAGTimelineView({ runId }: DAGTimelineViewProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTimeline();
  }, [runId]);

  const fetchTimeline = async () => {
    if (!runId) return;
    
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(getApiUrl(`/api/runs/${runId}/history`));
      if (!response.ok) {
        throw new Error(`Failed to fetch timeline: ${response.statusText}`);
      }
      const data = await response.json();
      setEvents(data.events || []);
    } catch (err) {
      console.error('Error fetching timeline:', err);
      setError(err instanceof Error ? err.message : 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  };

  // Group events by time periods
  const groupedEvents = useMemo(() => {
    if (events.length === 0) return [];

    const sorted = [...events].sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    const startTime = new Date(sorted[0].timestamp).getTime();
    const groups: { time: string; relativeTime: string; events: TimelineEvent[] }[] = [];
    
    sorted.forEach(event => {
      const eventTime = new Date(event.timestamp);
      const elapsed = eventTime.getTime() - startTime;
      const seconds = Math.floor(elapsed / 1000);
      const minutes = Math.floor(seconds / 60);
      
      const relativeTime = minutes > 0 
        ? `${minutes}m ${seconds % 60}s`
        : `${seconds}s`;

      const timeLabel = eventTime.toLocaleTimeString();
      
      // Find or create group
      let group = groups.find(g => g.time === timeLabel);
      if (!group) {
        group = { time: timeLabel, relativeTime: `+${relativeTime}`, events: [] };
        groups.push(group);
      }
      group.events.push(event);
    });

    return groups;
  }, [events]);

  const getEventIcon = (event: TimelineEvent) => {
    if (event.status === 'completed' || event.event_type === 'node_completed') {
      return <CheckCircle2 className="w-5 h-5 text-green-400" />;
    }
    if (event.status === 'failed' || event.event_type === 'node_failed') {
      return <XCircle className="w-5 h-5 text-red-400" />;
    }
    if (event.status === 'running' || event.event_type === 'node_started') {
      return <Circle className="w-5 h-5 text-blue-400 animate-pulse" />;
    }
    return <Circle className="w-4 h-4 text-gray-500" />;
  };

  const getEventColor = (event: TimelineEvent) => {
    if (event.status === 'completed' || event.event_type === 'node_completed') {
      return 'border-green-500/50 bg-green-500/5';
    }
    if (event.status === 'failed' || event.event_type === 'node_failed') {
      return 'border-red-500/50 bg-red-500/5';
    }
    if (event.status === 'running' || event.event_type === 'node_started') {
      return 'border-blue-500/50 bg-blue-500/5';
    }
    return 'border-gray-700 bg-gray-800/50';
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-gray-400">Loading timeline...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-red-400">
          <AlertCircle className="w-8 h-8 mx-auto mb-2" />
          {error}
        </div>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-gray-400">No timeline data available</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
          <Clock className="w-6 h-6" />
          Execution Timeline
        </h2>

        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gray-700" />

          {/* Timeline events */}
          <div className="space-y-6">
            {groupedEvents.map((group, groupIdx) => (
              <div key={groupIdx} className="relative">
                {/* Time marker */}
                <div className="flex items-center gap-4 mb-4">
                  <div className="flex items-center gap-2 bg-gray-800 px-3 py-1 rounded-full border border-gray-700">
                    <Clock className="w-4 h-4 text-blue-400" />
                    <span className="text-sm text-gray-300">{group.time}</span>
                    <span className="text-xs text-gray-500">{group.relativeTime}</span>
                  </div>
                </div>

                {/* Events in this time group */}
                <div className="space-y-3 ml-16">
                  {group.events.map((event, eventIdx) => (
                    <div
                      key={event.id}
                      className={`relative flex items-start gap-3 p-4 rounded-lg border ${getEventColor(event)}`}
                    >
                      {/* Event icon */}
                      <div className="flex-shrink-0 mt-0.5">
                        {getEventIcon(event)}
                      </div>

                      {/* Event content */}
                      <div className="flex-grow min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-white text-sm">
                            {event.event_type.replace(/_/g, ' ').toUpperCase()}
                          </span>
                          {event.agent_name && (
                            <span className="text-xs px-2 py-0.5 bg-gray-700 text-gray-300 rounded">
                              {event.agent_name}
                            </span>
                          )}
                          {event.node_id && (
                            <span className="text-xs px-2 py-0.5 bg-gray-700 text-gray-300 rounded">
                              {event.node_id}
                            </span>
                          )}
                        </div>

                        {event.description && (
                          <p className="text-sm text-gray-400 mt-1">
                            {event.description}
                          </p>
                        )}

                        {event.duration_ms && event.duration_ms > 0 && (
                          <div className="text-xs text-gray-500 mt-2">
                            Duration: {(event.duration_ms / 1000).toFixed(2)}s
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
