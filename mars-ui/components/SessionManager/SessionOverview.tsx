"use client";

import {
  Activity,
  Clock,
  PlayCircle,
  CheckCircle2,
  XCircle,
  PauseCircle,
  Cpu,
  FileText,
} from "lucide-react";
import { SessionDetail, SessionRun } from "@/types/sessions";

interface SessionOverviewProps {
  detail: SessionDetail;
  runs: SessionRun[];
}

const statusIcons: Record<string, typeof CheckCircle2> = {
  active: PlayCircle,
  completed: CheckCircle2,
  failed: XCircle,
  suspended: PauseCircle,
};

const statusColors: Record<string, string> = {
  active: "text-green-400",
  completed: "text-blue-400",
  failed: "text-red-400",
  suspended: "text-yellow-400",
  expired: "text-gray-400",
};

function formatDuration(start: string | null, end: string | null): string {
  if (!start) return "-";
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const diffMs = e - s;
  const secs = Math.floor(diffMs / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ${secs % 60}s`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

export function SessionOverview({ detail, runs }: SessionOverviewProps) {
  const StatusIcon = statusIcons[detail.status] || Activity;
  const statusColor = statusColors[detail.status] || "text-gray-400";

  const runsByStatus = runs.reduce<Record<string, number>>((acc, r) => {
    acc[r.status] = (acc[r.status] || 0) + 1;
    return acc;
  }, {});

  const latestRun = runs.length > 0 ? runs[0] : null;
  const taskDescription =
    latestRun?.task_description || detail.config?.task || null;

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4 bg-gray-900">
      {/* Status & Mode */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <StatusIcon className={`w-4 h-4 ${statusColor}`} />
            <span className="text-xs text-gray-400 uppercase tracking-wide">
              Status
            </span>
          </div>
          <p className={`text-sm font-medium ${statusColor}`}>
            {detail.status}
          </p>
          {detail.current_phase && (
            <p className="text-xs text-gray-500 mt-1">
              Phase: {detail.current_phase}
              {detail.current_step != null && ` / Step ${detail.current_step}`}
            </p>
          )}
        </div>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <Cpu className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-gray-400 uppercase tracking-wide">
              Mode
            </span>
          </div>
          <p className="text-sm font-medium text-white">{detail.mode}</p>
          {latestRun?.model && (
            <p className="text-xs text-gray-500 mt-1">
              Model: {latestRun.model}
            </p>
          )}
        </div>
      </div>

      {/* Timing */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
        <div className="flex items-center gap-2 mb-2">
          <Clock className="w-4 h-4 text-blue-400" />
          <span className="text-xs text-gray-400 uppercase tracking-wide">
            Timing
          </span>
        </div>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div>
            <p className="text-xs text-gray-500">Created</p>
            <p className="text-gray-300">
              {detail.created_at
                ? new Date(detail.created_at).toLocaleString()
                : "-"}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Updated</p>
            <p className="text-gray-300">
              {detail.updated_at
                ? new Date(detail.updated_at).toLocaleString()
                : "-"}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Duration</p>
            <p className="text-gray-300">
              {formatDuration(detail.created_at, detail.updated_at)}
            </p>
          </div>
        </div>
      </div>

      {/* Runs Summary */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
        <div className="flex items-center gap-2 mb-2">
          <PlayCircle className="w-4 h-4 text-green-400" />
          <span className="text-xs text-gray-400 uppercase tracking-wide">
            Runs ({runs.length})
          </span>
        </div>
        {runs.length === 0 ? (
          <p className="text-sm text-gray-500">No workflow runs recorded</p>
        ) : (
          <div className="space-y-2">
            <div className="flex gap-3 text-xs">
              {Object.entries(runsByStatus).map(([status, count]) => (
                <span key={status} className="text-gray-400">
                  <span
                    className={`font-medium ${
                      statusColors[status] || "text-gray-300"
                    }`}
                  >
                    {count}
                  </span>{" "}
                  {status}
                </span>
              ))}
            </div>
            {latestRun && (
              <div className="text-xs text-gray-500 border-t border-gray-700 pt-2 mt-2">
                Latest: {latestRun.id.substring(0, 20)}...{" "}
                ({latestRun.status}) &middot;{" "}
                {latestRun.started_at
                  ? new Date(latestRun.started_at).toLocaleString()
                  : ""}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Task Description */}
      {taskDescription && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="w-4 h-4 text-yellow-400" />
            <span className="text-xs text-gray-400 uppercase tracking-wide">
              Task
            </span>
          </div>
          <p className="text-sm text-gray-300 whitespace-pre-wrap">
            {taskDescription}
          </p>
        </div>
      )}

      {/* Conversation Stats */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
        <div className="flex items-center gap-2 mb-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="text-xs text-gray-400 uppercase tracking-wide">
            Data Captured
          </span>
        </div>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div>
            <p className="text-xs text-gray-500">Messages</p>
            <p className="text-gray-300">
              {detail.conversation_history?.length || 0}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Context Vars</p>
            <p className="text-gray-300">
              {Object.keys(detail.context_variables || {}).length}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Has Plan</p>
            <p className="text-gray-300">{detail.plan_data ? "Yes" : "No"}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
