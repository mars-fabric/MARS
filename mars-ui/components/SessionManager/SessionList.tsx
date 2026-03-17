"use client";

import { useState, useEffect, useCallback } from "react";
import { Loader2, Play, Pause, Trash2, RefreshCw, Filter, Eye } from "lucide-react";

interface Session {
  session_id: string;
  name: string;
  mode: string;
  status: string;
  current_phase: string | null;
  current_step: number | null;
  created_at: string | null;
  updated_at: string | null;
}

interface SessionListProps {
  onResume: (sessionId: string, mode?: string) => void;
  onViewLogs?: (sessionId: string, mode?: string) => void;
  onSelect?: (sessionId: string, mode?: string) => void;
  selectedSessionId?: string | null;
  filter?: "active" | "suspended" | "completed" | null;
  modeFilter?: string | null;
  compact?: boolean;
}

const MODE_LABELS: Record<string, string> = {
  copilot: "Copilot",
  "planning-control": "Planning & Control",
  "hitl-interactive": "HITL Interactive",
  "one-shot": "One Shot",
  "idea-generation": "Idea Generation",
  ocr: "OCR",
  arxiv: "arXiv Filter",
  "enhance-input": "Enhance Input",
};

const MODE_COLORS: Record<string, string> = {
  copilot: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  "planning-control": "bg-blue-500/20 text-blue-400 border-blue-500/30",
  "hitl-interactive": "bg-orange-500/20 text-orange-400 border-orange-500/30",
  "one-shot": "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
  "idea-generation": "bg-pink-500/20 text-pink-400 border-pink-500/30",
  ocr: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  arxiv: "bg-indigo-500/20 text-indigo-400 border-indigo-500/30",
  "enhance-input": "bg-teal-500/20 text-teal-400 border-teal-500/30",
};

export function SessionList({ onResume, onViewLogs, onSelect, selectedSessionId, filter, modeFilter, compact = false }: SessionListProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMode, setSelectedMode] = useState<string | null>(modeFilter || null);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filter) params.set("status", filter);
      if (selectedMode) params.set("mode", selectedMode);
      params.set("limit", "50");

      const response = await fetch(`/api/sessions?${params}`);
      if (!response.ok) throw new Error("Failed to fetch sessions");

      const data = await response.json();
      setSessions(data.sessions);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [filter, selectedMode]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleSuspend = async (sessionId: string) => {
    try {
      const response = await fetch(`/api/sessions/${sessionId}/suspend`, {
        method: "POST",
      });
      if (response.ok) {
        fetchSessions();
      }
    } catch (e) {
      console.error("Failed to suspend session:", e);
    }
  };

  const handleDelete = async (sessionId: string) => {
    if (!confirm("Are you sure you want to delete this session?")) return;

    try {
      const response = await fetch(`/api/sessions/${sessionId}`, {
        method: "DELETE",
      });
      if (response.ok) {
        fetchSessions();
      }
    } catch (e) {
      console.error("Failed to delete session:", e);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "N/A";
    return new Date(dateStr).toLocaleString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-500/20 text-green-400 border-green-500/30";
      case "suspended":
        return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
      case "completed":
        return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      case "expired":
        return "bg-gray-500/20 text-gray-400 border-gray-500/30";
      default:
        return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    }
  };

  const getModeLabel = (mode: string) => MODE_LABELS[mode] || mode;
  const getModeColor = (mode: string) => MODE_COLORS[mode] || "bg-gray-500/20 text-gray-400 border-gray-500/30";

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-400 text-sm flex items-center gap-2">
        Error: {error}
        <button
          onClick={fetchSessions}
          className="p-1 text-gray-400 hover:text-white transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-semibold text-gray-300">Sessions</h3>
        <div className="flex items-center gap-2">
          {/* Mode filter dropdown */}
          <div className="relative">
            <select
              value={selectedMode || ""}
              onChange={(e) => setSelectedMode(e.target.value || null)}
              className="appearance-none pl-6 pr-2 py-0.5 text-xs bg-gray-700 border border-gray-600 rounded text-white cursor-pointer"
            >
              <option value="">All Modes</option>
              {Object.entries(MODE_LABELS).map(([id, label]) => (
                <option key={id} value={id}>{label}</option>
              ))}
            </select>
            <Filter className="absolute left-1.5 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400 pointer-events-none" />
          </div>
          <button
            onClick={fetchSessions}
            className="p-1 text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {sessions.length === 0 ? (
        <div className="p-4 text-center text-gray-500 text-sm">
          No sessions found
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map((session) => (
            <div
              key={session.session_id}
              onClick={() => onSelect?.(session.session_id, session.mode)}
              className={`bg-gray-800 border rounded-lg p-3 transition-colors ${
                selectedSessionId === session.session_id
                  ? "border-blue-500 bg-gray-800/80"
                  : "border-gray-700 hover:border-gray-600"
              } ${onSelect ? "cursor-pointer" : ""}`}
            >
              <div className="flex justify-between items-start mb-2">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-white truncate">
                    {session.name}
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className={`px-1.5 py-0 text-[10px] font-medium rounded border ${getModeColor(session.mode)}`}>
                      {getModeLabel(session.mode)}
                    </span>
                    {session.current_phase && (
                      <span className="text-xs text-gray-400">
                        {session.current_phase}
                        {session.current_step !== null && ` (Step ${session.current_step})`}
                      </span>
                    )}
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 text-[10px] font-medium rounded-full border ${getStatusColor(
                    session.status
                  )}`}
                >
                  {session.status}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <div className="text-[10px] text-gray-500">
                  {compact ? formatDate(session.updated_at).split(",")[0] : `Updated: ${formatDate(session.updated_at)}`}
                </div>
                <div className="flex gap-1.5" onClick={(e) => e.stopPropagation()}>
                  {onViewLogs && (
                    <button
                      onClick={() => onViewLogs(session.session_id, session.mode)}
                      className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-600/20 text-gray-300 hover:bg-gray-600/30 rounded transition-colors"
                    >
                      <Eye className="h-3 w-3" />
                      Logs
                    </button>
                  )}
                  {(session.status === "suspended" || session.status === "active") && (
                    <button
                      onClick={() => onResume(session.session_id, session.mode)}
                      className="flex items-center gap-1 px-2 py-1 text-xs bg-green-600/20 text-green-400 hover:bg-green-600/30 rounded transition-colors"
                    >
                      <Play className="h-3 w-3" />
                      Resume
                    </button>
                  )}
                  {session.status === "active" && (
                    <button
                      onClick={() => handleSuspend(session.session_id)}
                      className="flex items-center gap-1 px-2 py-1 text-xs bg-yellow-600/20 text-yellow-400 hover:bg-yellow-600/30 rounded transition-colors"
                    >
                      <Pause className="h-3 w-3" />
                      Suspend
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(session.session_id)}
                    className="p-1 text-gray-500 hover:text-red-400 rounded transition-colors"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
