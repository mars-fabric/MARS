// components/dag/DAGWorkspace.tsx
'use client';

import { useState, useCallback, useEffect } from 'react';
import { 
  Maximize2, 
  Minimize2, 
  X, 
  Grid3x3, 
  Clock, 
  History, 
  FileText,
  ZoomIn,
  ZoomOut,
  Home,
  Download,
  Share2,
  Filter,
  Search,
  ChevronLeft,
  ChevronRight,
  Layers
} from 'lucide-react';
import { DAGVisualization } from './DAGVisualization';
import ExecutionTimeline from './ExecutionTimeline';
import { DAGStatsPanel } from './DAGStatsPanel';
import { DAGHistoryView } from './DAGHistoryView';
import { DAGTimelineView } from './DAGTimelineView';
import { DAGFilesView } from './DAGFilesView';
import { CostDashboard } from '@/components/metrics';
import { CostSummary, CostTimeSeries } from '@/types/cost';
import { useCostData } from '@/hooks/useCostData';

interface DAGWorkspaceProps {
  dagData: { run_id?: string; nodes: any[]; edges: any[] } | null;
  onNodeSelect?: (nodeId: string | null) => void;
  onPlayFromNode?: (nodeId: string) => void;
  runId?: string;
  costSummary?: CostSummary;
  costTimeSeries?: CostTimeSeries[];
  filesUpdatedCounter?: number;
}

type TabType = 'graph' | 'timeline' | 'history' | 'files' | 'cost';

export function DAGWorkspace({ dagData, onNodeSelect, onPlayFromNode, runId, costSummary, costTimeSeries = [], filesUpdatedCounter }: DAGWorkspaceProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('graph');
  
  // Fetch cost data from database API as fallback
  const { costSummary: dbCostSummary, loading: costLoading } = useCostData(runId || null);
  
  // Use WebSocket cost data if available, otherwise fall back to database
  const effectiveCostSummary = costSummary || dbCostSummary;
  const [showStats, setShowStats] = useState(true);
  const [showMinimap, setShowMinimap] = useState(true);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Calculate workflow statistics
  const stats = useCallback(() => {
    if (!dagData?.nodes) return null;
    
    const total = dagData.nodes.length;
    const completed = dagData.nodes.filter(n => n.status === 'completed').length;
    const running = dagData.nodes.filter(n => n.status === 'running').length;
    const failed = dagData.nodes.filter(n => n.status === 'failed').length;
    const pending = dagData.nodes.filter(n => n.status === 'pending').length;
    
    // Calculate execution time
    const startTimes = dagData.nodes
      .filter(n => n.started_at)
      .map(n => new Date(n.started_at).getTime());
    const endTimes = dagData.nodes
      .filter(n => n.completed_at)
      .map(n => new Date(n.completed_at).getTime());
    
    const startTime = startTimes.length ? Math.min(...startTimes) : null;
    const endTime = endTimes.length ? Math.max(...endTimes) : null;
    const duration = startTime && endTime ? endTime - startTime : null;
    
    return {
      total,
      completed,
      running,
      failed,
      pending,
      progress: total > 0 ? (completed / total) * 100 : 0,
      duration,
      startTime,
      endTime
    };
  }, [dagData]);

  const workflowStats = stats();

  // Filter nodes based on search and status filter
  const filteredDagData = useCallback(() => {
    if (!dagData) return null;
    
    let filteredNodes = dagData.nodes;
    
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filteredNodes = filteredNodes.filter(node =>
        node.label?.toLowerCase().includes(query) ||
        node.id?.toLowerCase().includes(query) ||
        node.agent?.toLowerCase().includes(query) ||
        node.description?.toLowerCase().includes(query)
      );
    }
    
    if (statusFilter.length > 0) {
      filteredNodes = filteredNodes.filter(node =>
        statusFilter.includes(node.status)
      );
    }
    
    return {
      nodes: filteredNodes,
      edges: dagData.edges.filter(edge =>
        filteredNodes.some(n => n.id === edge.source) &&
        filteredNodes.some(n => n.id === edge.target)
      )
    };
  }, [dagData, searchQuery, statusFilter]);

  const handleToggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const handleNodeSelect = (nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    onNodeSelect?.(nodeId);
  };

  const handleExport = () => {
    if (!dagData) return;
    const dataStr = JSON.stringify(dagData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `dag-workflow-${runId || 'export'}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const tabs = [
    { id: 'graph' as TabType, label: 'DAG View', icon: Grid3x3 },
    { id: 'timeline' as TabType, label: 'Timeline', icon: Clock },
    { id: 'history' as TabType, label: 'History', icon: History },
    { id: 'files' as TabType, label: 'Files', icon: FileText },
    { id: 'cost' as TabType, label: 'Cost', icon: Layers },
  ];

  const statuses = [
    { value: 'pending', label: 'Pending', color: 'bg-gray-500' },
    { value: 'running', label: 'Running', color: 'bg-blue-500' },
    { value: 'completed', label: 'Completed', color: 'bg-green-500' },
    { value: 'failed', label: 'Failed', color: 'bg-red-500' },
  ];

  const toggleStatusFilter = (status: string) => {
    setStatusFilter(prev =>
      prev.includes(status)
        ? prev.filter(s => s !== status)
        : [...prev, status]
    );
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case 'f':
            e.preventDefault();
            document.getElementById('dag-search')?.focus();
            break;
          case 'e':
            e.preventDefault();
            handleExport();
            break;
        }
      }
      
      if (e.key === 'Escape') {
        if (isFullscreen) {
          setIsFullscreen(false);
        } else if (selectedNodeId) {
          setSelectedNodeId(null);
        }
      }
      
      if (e.key === 'f' && (e.ctrlKey || e.metaKey) && e.shiftKey) {
        e.preventDefault();
        setIsFullscreen(!isFullscreen);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen, selectedNodeId]);

  const containerClass = isFullscreen
    ? 'fixed inset-0 z-50 bg-gray-900'
    : 'relative w-full h-full bg-gray-900';

  return (
    <div className={containerClass}>
      {/* Header Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-400" />
            Workflow Execution Workspace
          </h2>
          
          {runId && (
            <span className="text-xs text-gray-400 font-mono px-2 py-1 bg-gray-700/50 rounded">
              {runId.slice(0, 8)}...
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              id="dag-search"
              type="text"
              placeholder="Search nodes... (Ctrl+F)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
            />
          </div>

          {/* Filter */}
          <div className="relative group">
            <button className="p-2 hover:bg-gray-700 rounded transition-colors">
              <Filter className={`w-4 h-4 ${statusFilter.length > 0 ? 'text-blue-400' : 'text-gray-400'}`} />
            </button>
            
            <div className="absolute right-0 top-full mt-1 w-48 bg-gray-800 border border-gray-700 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
              <div className="p-2 border-b border-gray-700">
                <p className="text-xs font-medium text-gray-400 uppercase">Filter by Status</p>
              </div>
              <div className="p-2 space-y-1">
                {statuses.map(status => (
                  <button
                    key={status.value}
                    onClick={() => toggleStatusFilter(status.value)}
                    className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-left hover:bg-gray-700 rounded transition-colors"
                  >
                    <div className={`w-3 h-3 rounded-full ${status.color} ${statusFilter.includes(status.value) ? 'ring-2 ring-white ring-offset-2 ring-offset-gray-800' : ''}`} />
                    <span className="text-gray-300">{status.label}</span>
                  </button>
                ))}
              </div>
              {statusFilter.length > 0 && (
                <div className="p-2 border-t border-gray-700">
                  <button
                    onClick={() => setStatusFilter([])}
                    className="w-full px-2 py-1 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
                  >
                    Clear Filters
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Export */}
          <button
            onClick={handleExport}
            title="Export DAG (Ctrl+E)"
            className="p-2 hover:bg-gray-700 rounded transition-colors"
          >
            <Download className="w-4 h-4 text-gray-400" />
          </button>

          {/* Share */}
          <button
            onClick={() => {
              if (runId) {
                navigator.clipboard.writeText(`${window.location.origin}?run=${runId}`);
                // TODO: Add toast notification
              }
            }}
            title="Copy shareable link"
            className="p-2 hover:bg-gray-700 rounded transition-colors"
          >
            <Share2 className="w-4 h-4 text-gray-400" />
          </button>

          {/* Fullscreen Toggle */}
          <button
            onClick={handleToggleFullscreen}
            title={isFullscreen ? 'Exit fullscreen (Ctrl+Shift+F)' : 'Enter fullscreen (Ctrl+Shift+F)'}
            className="p-2 hover:bg-gray-700 rounded transition-colors"
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4 text-gray-400" />
            ) : (
              <Maximize2 className="w-4 h-4 text-gray-400" />
            )}
          </button>

          {isFullscreen && (
            <button
              onClick={handleToggleFullscreen}
              className="p-2 hover:bg-gray-700 rounded transition-colors"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-4 py-2 bg-gray-800/50 border-b border-gray-700/50">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t transition-colors ${
                activeTab === tab.id
                  ? 'bg-gray-900 text-white border-t-2 border-blue-500'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}

        <div className="ml-auto flex items-center gap-2">
          {activeTab === 'graph' && (
            <>
              <button
                onClick={() => setShowMinimap(!showMinimap)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  showMinimap ? 'bg-blue-500/20 text-blue-400' : 'text-gray-400 hover:bg-gray-700'
                }`}
              >
                Minimap
              </button>
              <button
                onClick={() => setShowStats(!showStats)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  showStats ? 'bg-blue-500/20 text-blue-400' : 'text-gray-400 hover:bg-gray-700'
                }`}
              >
                Stats
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden" style={{ height: isFullscreen ? 'calc(100vh - 120px)' : 'calc(100% - 120px)' }}>
        {/* Sidebar Stats Panel (Collapsible) */}
        {showStats && activeTab === 'graph' && (
          <div className={`relative bg-gray-800/50 border-r border-gray-700 transition-all duration-300 ${
            sidebarCollapsed ? 'w-12' : 'w-80'
          }`}>
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="absolute -right-3 top-4 z-10 p-1 bg-gray-700 border border-gray-600 rounded-full hover:bg-gray-600 transition-colors"
            >
              {sidebarCollapsed ? (
                <ChevronRight className="w-3 h-3 text-gray-400" />
              ) : (
                <ChevronLeft className="w-3 h-3 text-gray-400" />
              )}
            </button>

            {!sidebarCollapsed && workflowStats && (
              <DAGStatsPanel 
                stats={workflowStats}
                nodes={dagData?.nodes || []}
                selectedNodeId={selectedNodeId}
              />
            )}

            {sidebarCollapsed && (
              <div className="flex flex-col items-center gap-4 py-4">
                <div className="text-xs text-gray-400 rotate-90 whitespace-nowrap">
                  Stats
                </div>
              </div>
            )}
          </div>
        )}

        {/* Main Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'graph' && (
            <DAGVisualization
              dagData={filteredDagData()}
              onNodeSelect={handleNodeSelect}
              onPlayFromNode={onPlayFromNode}
              showMinimap={showMinimap}
              isFullscreen={isFullscreen}
              runId={runId}
            />
          )}

          {activeTab === 'timeline' && runId && (
            <div className="h-full overflow-hidden bg-gray-900">
              <DAGTimelineView runId={runId} />
            </div>
          )}

          {activeTab === 'history' && runId && (
            <div className="h-full overflow-hidden bg-gray-900">
              <DAGHistoryView runId={runId} />
            </div>
          )}

          {activeTab === 'files' && runId && (
            <div className="h-full overflow-hidden bg-gray-900">
              <DAGFilesView runId={runId} refreshTrigger={filesUpdatedCounter} />
            </div>
          )}

          {activeTab === 'cost' && (
            <div className="h-full overflow-hidden bg-gray-900">
              {effectiveCostSummary ? (
                <CostDashboard 
                  summary={effectiveCostSummary}
                  timeSeries={costTimeSeries}
                />
              ) : costLoading ? (
                <div className="h-full flex items-center justify-center">
                  <p className="text-gray-400">Loading cost data from database...</p>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center">
                  <p className="text-gray-400">No cost data available yet</p>
                </div>
              )}
            </div>
          )}
          
          {activeTab === 'timeline' && !runId && (
            <div className="h-full flex items-center justify-center bg-gray-900">
              <p className="text-gray-400">No run ID available for timeline view (runId: {String(runId)})</p>
            </div>
          )}

          {activeTab === 'history' && !runId && (
            <div className="h-full flex items-center justify-center bg-gray-900">
              <p className="text-gray-400">No run ID available for history view (runId: {String(runId)})</p>
            </div>
          )}

          {activeTab === 'files' && !runId && (
            <div className="h-full flex items-center justify-center bg-gray-900">
              <p className="text-gray-400">No run ID available for files view (runId: {String(runId)})</p>
            </div>
          )}
        </div>
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-t border-gray-700 text-xs text-gray-400">
        <div className="flex items-center gap-4">
          {workflowStats && (
            <>
              <span>
                <strong className="text-white">{workflowStats.total}</strong> nodes
              </span>
              <span className="text-gray-600">|</span>
              <span className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <strong className="text-white">{workflowStats.completed}</strong> completed
              </span>
              <span className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-blue-500" />
                <strong className="text-white">{workflowStats.running}</strong> running
              </span>
              {workflowStats.failed > 0 && (
                <span className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full bg-red-500" />
                  <strong className="text-white">{workflowStats.failed}</strong> failed
                </span>
              )}
              {workflowStats.pending > 0 && (
                <span className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full bg-gray-500" />
                  <strong className="text-white">{workflowStats.pending}</strong> pending
                </span>
              )}
            </>
          )}
        </div>

        <div className="flex items-center gap-4">
          {workflowStats?.duration && (
            <span>
              Duration: <strong className="text-white">{(workflowStats.duration / 1000).toFixed(1)}s</strong>
            </span>
          )}
          {selectedNodeId && (
            <span>
              Selected: <strong className="text-white font-mono">{selectedNodeId}</strong>
            </span>
          )}
          {searchQuery && (
            <span>
              Filtered: <strong className="text-white">{filteredDagData()?.nodes.length || 0}</strong> / {dagData?.nodes.length || 0} nodes
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
