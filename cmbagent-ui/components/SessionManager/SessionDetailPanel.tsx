"use client";

import { useState } from "react";
import {
  ArrowLeft,
  LayoutDashboard,
  Terminal,
  Activity,
  DollarSign,
  FileText,
  Settings,
  GitBranch,
  Loader2,
  AlertCircle,
  RefreshCw,
  ChevronDown,
} from "lucide-react";
import { useSessionDetail } from "@/hooks/useSessionDetail";
import { SessionDetailTab } from "@/types/sessions";
import { SessionOverview } from "./SessionOverview";
import { SessionConsoleTab } from "./SessionConsoleTab";
import { SessionConfigTab } from "./SessionConfigTab";
import { SessionCostsTab } from "./SessionCostsTab";
import { SessionDAGTab } from "./SessionDAGTab";
import { SessionPlanTab } from "./SessionPlanTab";
import { SessionResultsTab } from "./SessionResultsTab";
import { DAGHistoryView, DAGFilesView } from "@/components/dag";

interface SessionDetailPanelProps {
  sessionId: string;
  onClose: () => void;
  onResume?: (sessionId: string, mode?: string) => void;
}

const baseTabs: { id: SessionDetailTab; label: string; icon: typeof Activity; needsRun?: boolean }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "console", label: "Console", icon: Terminal, needsRun: true },
  { id: "plan", label: "Plan", icon: FileText, needsRun: true },
  { id: "dag", label: "DAG", icon: GitBranch, needsRun: true },
  { id: "events", label: "Events", icon: Activity, needsRun: true },
  { id: "costs", label: "Costs", icon: DollarSign, needsRun: true },
  { id: "files", label: "Files", icon: FileText, needsRun: true },
  { id: "config", label: "Config", icon: Settings },
];

const modeColors: Record<string, string> = {
  copilot: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  "planning-control": "bg-blue-500/20 text-blue-400 border-blue-500/30",
  "one-shot": "bg-green-500/20 text-green-400 border-green-500/30",
  "hitl-interactive": "bg-orange-500/20 text-orange-400 border-orange-500/30",
  "idea-generation": "bg-pink-500/20 text-pink-400 border-pink-500/30",
};

const statusColors: Record<string, string> = {
  active: "bg-green-500/20 text-green-400 border-green-500/30",
  completed: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  failed: "bg-red-500/20 text-red-400 border-red-500/30",
  suspended: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  expired: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

export function SessionDetailPanel({
  sessionId,
  onClose,
  onResume,
}: SessionDetailPanelProps) {
  const {
    detail,
    runs,
    selectedRunId,
    setSelectedRunId,
    loading,
    error,
    refetch,
  } = useSessionDetail(sessionId);
  const [activeTab, setActiveTab] = useState<SessionDetailTab>("overview");
  const [runDropdownOpen, setRunDropdownOpen] = useState(false);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900 text-gray-400">
        <Loader2 className="h-8 w-8 animate-spin mr-3" />
        <span>Loading session...</span>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-400" />
          <p className="text-sm text-red-400 mb-3">{error || "Session not found"}</p>
          <button
            onClick={refetch}
            className="px-3 py-1.5 text-xs bg-gray-800 text-gray-300 rounded hover:bg-gray-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const modeClass = modeColors[detail.mode] || "bg-gray-500/20 text-gray-400 border-gray-500/30";
  const statusClass = statusColors[detail.status] || statusColors.expired;
  const selectedRun = runs.find((r) => r.id === selectedRunId);
  const showResultsTab = detail.status === "completed" || selectedRun?.status === "completed";
  const tabs = showResultsTab
    ? [
      baseTabs[0],
      { id: "console" as SessionDetailTab, label: "Console", icon: Terminal, needsRun: true },
      { id: "plan" as SessionDetailTab, label: "Plan", icon: FileText, needsRun: true },
      { id: "results" as SessionDetailTab, label: "Results", icon: FileText, needsRun: true },
      ...baseTabs.filter((t) => !["overview", "console", "plan"].includes(t.id)),
    ]
    : baseTabs;

  const noRunMessage = (
    <div className="flex items-center justify-center h-full text-gray-400">
      <div className="text-center">
        <Activity className="w-10 h-10 mx-auto mb-3 text-gray-500" />
        <p className="text-sm">No run data available</p>
        <p className="text-xs text-gray-500 mt-1">
          This session has no associated workflow runs.
        </p>
      </div>
    </div>
  );

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-gray-700 px-3 py-2.5">
        <div className="flex items-center gap-2">
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-white transition-colors rounded"
            title="Back to session list"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <h2 className="text-sm font-medium text-white truncate flex-1">
            {detail.name}
          </h2>
          <span className={`text-xs px-2 py-0.5 rounded-full border ${statusClass}`}>
            {detail.status}
          </span>
          {onResume && (detail.status === "active" || detail.status === "suspended") && (
            <button
              onClick={() => onResume(sessionId, detail.mode)}
              className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-500 transition-colors"
            >
              Resume
            </button>
          )}
          <button
            onClick={refetch}
            className="p-1 text-gray-400 hover:text-white transition-colors rounded"
            title="Refresh"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="flex items-center gap-2 mt-1 ml-7">
          <span className={`text-xs px-1.5 py-0.5 rounded border ${modeClass}`}>
            {detail.mode}
          </span>
          {detail.current_phase && (
            <span className="text-xs text-gray-500">
              Phase: {detail.current_phase}
            </span>
          )}
          {detail.updated_at && (
            <span className="text-xs text-gray-500 ml-auto">
              {new Date(detail.updated_at).toLocaleString()}
            </span>
          )}
        </div>
      </div>

      {/* Run Selector (only if multiple runs) */}
      {runs.length > 1 && (
        <div className="flex-shrink-0 border-b border-gray-700 px-3 py-1.5">
          <div className="relative">
            <button
              onClick={() => setRunDropdownOpen(!runDropdownOpen)}
              className="flex items-center gap-2 text-xs text-gray-300 bg-gray-800 rounded px-2 py-1.5 w-full hover:bg-gray-750 transition-colors"
            >
              <span className="text-gray-500">Run:</span>
              <span className="truncate flex-1 text-left">
                {selectedRun
                  ? `${selectedRun.id.substring(0, 24)}... (${selectedRun.status})`
                  : "Select a run"}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
            </button>

            {runDropdownOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded shadow-lg z-10 max-h-48 overflow-y-auto">
                {runs.map((run) => (
                  <button
                    key={run.id}
                    onClick={() => {
                      setSelectedRunId(run.id);
                      setRunDropdownOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-700 transition-colors ${run.id === selectedRunId ? "bg-gray-700" : ""
                      }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300 truncate">
                        {run.id.substring(0, 30)}...
                      </span>
                      <span
                        className={`ml-2 px-1.5 py-0.5 rounded text-xs ${statusColors[run.status] || statusColors.expired
                          }`}
                      >
                        {run.status}
                      </span>
                    </div>
                    {run.started_at && (
                      <p className="text-gray-500 mt-0.5">
                        {new Date(run.started_at).toLocaleString()}
                      </p>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab Bar */}
      <div className="flex-shrink-0 flex border-b border-gray-700 overflow-x-auto">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors ${activeTab === tab.id
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-gray-200"
                }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeTab === "overview" && (
          <SessionOverview detail={detail} runs={runs} />
        )}

        {activeTab === "results" &&
          (selectedRunId ? (
            <SessionResultsTab runId={selectedRunId} />
          ) : (
            noRunMessage
          ))}

        {activeTab === "dag" &&
          (selectedRunId ? (
            <SessionDAGTab runId={selectedRunId} />
          ) : (
            noRunMessage
          ))}

        {activeTab === "console" &&
          (selectedRunId ? (
            <SessionConsoleTab runId={selectedRunId} />
          ) : (
            noRunMessage
          ))}

        {activeTab === "plan" &&
          (selectedRunId ? (
            <SessionPlanTab runId={selectedRunId} />
          ) : (
            noRunMessage
          ))}

        {activeTab === "events" &&
          (selectedRunId ? (
            <DAGHistoryView runId={selectedRunId} />
          ) : (
            noRunMessage
          ))}

        {activeTab === "costs" &&
          (selectedRunId ? (
            <SessionCostsTab runId={selectedRunId} />
          ) : (
            noRunMessage
          ))}

        {activeTab === "files" &&
          (selectedRunId ? (
            <DAGFilesView runId={selectedRunId} refreshTrigger={0} />
          ) : (
            noRunMessage
          ))}

        {activeTab === "config" && (
          <SessionConfigTab
            config={detail.config || {}}
            context={detail.context_variables || {}}
            plan={detail.plan_data}
          />
        )}
      </div>
    </div>
  );
}
