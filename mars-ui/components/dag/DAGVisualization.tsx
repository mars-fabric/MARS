// components/dag/DAGVisualization.tsx

'use client';

import { useCallback, useMemo, useState, useEffect } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  MiniMap,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  ConnectionMode,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import DAGNodeComponent from './DAGNode';
import { DAGControls } from './DAGControls';
import { NodeActionDialog } from './NodeActionDialog';
import { DAGNodeData, statusColors } from '@/types/dag';

const nodeTypes = {
  dagNode: DAGNodeComponent,
};

interface DAGVisualizationProps {
  dagData: { nodes: any[]; edges: any[] } | null;
  onNodeSelect?: (nodeId: string | null) => void;
  onPlayFromNode?: (nodeId: string) => void;
  showMinimap?: boolean;
  isFullscreen?: boolean;
  runId?: string;
}

// Layout calculation
function calculateLayout(
  rawNodes: any[],
  rawEdges: any[],
  direction: 'TB' | 'LR' = 'TB'
): { nodes: Node<DAGNodeData>[]; edges: Edge[] } {
  if (!rawNodes.length) return { nodes: [], edges: [] };

  // Build adjacency map
  const adjacency: Map<string, string[]> = new Map();
  const inDegree: Map<string, number> = new Map();

  rawNodes.forEach((n) => {
    adjacency.set(n.id, []);
    inDegree.set(n.id, 0);
  });

  rawEdges.forEach((e) => {
    adjacency.get(e.source)?.push(e.target);
    inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1);
  });

  // Topological sort to get levels
  const levels: string[][] = [];
  const visited = new Set<string>();
  const queue = rawNodes.filter((n) => inDegree.get(n.id) === 0).map((n) => n.id);

  while (queue.length > 0) {
    const currentLevel: string[] = [];
    const nextQueue: string[] = [];

    for (const nodeId of queue) {
      if (visited.has(nodeId)) continue;
      visited.add(nodeId);
      currentLevel.push(nodeId);

      for (const child of adjacency.get(nodeId) || []) {
        inDegree.set(child, (inDegree.get(child) || 0) - 1);
        if (inDegree.get(child) === 0) {
          nextQueue.push(child);
        }
      }
    }

    if (currentLevel.length > 0) {
      levels.push(currentLevel);
    }
    queue.length = 0;
    queue.push(...nextQueue);
  }

  // Calculate positions
  const nodeSpacing = 250;
  const levelSpacing = 150;
  const nodes: Node<DAGNodeData>[] = [];

  levels.forEach((level, levelIndex) => {
    const levelWidth = level.length * nodeSpacing;
    const startOffset = -levelWidth / 2 + nodeSpacing / 2;

    level.forEach((nodeId, nodeIndex) => {
      const rawNode = rawNodes.find((n) => n.id === nodeId);
      if (!rawNode) return;

      const x = direction === 'LR'
        ? levelIndex * levelSpacing
        : startOffset + nodeIndex * nodeSpacing;
      const y = direction === 'LR'
        ? startOffset + nodeIndex * nodeSpacing
        : levelIndex * levelSpacing;

      nodes.push({
        id: nodeId,
        type: 'dagNode',
        position: { x, y },
        data: {
          id: rawNode.id || nodeId,
          label: rawNode.label || rawNode.name || rawNode.id || nodeId,
          type: rawNode.type || 'agent',
          status: rawNode.status || 'pending',
          agent: rawNode.agent,
          goal: rawNode.goal,  // Step goal/objective
          summary: rawNode.summary,  // Human-readable summary
          stepNumber: rawNode.step_number ?? rawNode.stepNumber,
          description: rawNode.description,  // Full description with instructions
          insights: rawNode.insights,  // Detailed bullet points as text
          task: rawNode.task,
          bulletPoints: rawNode.bullet_points ?? rawNode.bulletPoints,  // Raw bullet points array
          startedAt: rawNode.started_at ?? rawNode.startedAt,
          completedAt: rawNode.completed_at ?? rawNode.completedAt,
          error: rawNode.error,
          retryInfo: rawNode.retry_info ?? rawNode.retryInfo,
          runId: rawNode.run_id ?? rawNode.runId,  // Include run_id for API calls
          generated_plan: rawNode.generated_plan,  // For planning nodes - the generated plan data
        },
      });
    });
  });

  // Create edges with styling
  const edges: Edge[] = rawEdges.map((e) => ({
    id: `${e.source}-${e.target}`,
    source: e.source,
    target: e.target,
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#4B5563', strokeWidth: 2 },
  }));

  return { nodes, edges };
}

// Inner component that uses ReactFlow hooks
function DAGVisualizationInner({
  dagData,
  onNodeSelect,
  onPlayFromNode,
  showMinimap = true,
  isFullscreen = false,
  runId,
}: DAGVisualizationProps) {
  const [layout, setLayout] = useState<'horizontal' | 'vertical'>('vertical');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Calculate layout
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(() => {
    if (!dagData) return { nodes: [], edges: [] };
    return calculateLayout(
      dagData.nodes,
      dagData.edges,
      layout === 'horizontal' ? 'LR' : 'TB'
    );
  }, [dagData, layout]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);

  // Update nodes when layout changes
  useEffect(() => {
    setNodes(layoutNodes);
    setEdges(layoutEdges);
  }, [layoutNodes, layoutEdges, setNodes, setEdges]);

  // Update node statuses and data when dagData changes
  useEffect(() => {
    if (!dagData || !dagData.nodes) return;

    setNodes((nds) =>
      nds.map((node) => {
        const rawNode = dagData.nodes.find((n) => n.id === node.id);
        if (rawNode) {
          return {
            ...node,
            data: {
              ...node.data,
              status: rawNode.status || node.data.status,
              error: rawNode.error ?? node.data.error,
              startedAt: rawNode.started_at ?? rawNode.startedAt ?? node.data.startedAt,
              completedAt: rawNode.completed_at ?? rawNode.completedAt ?? node.data.completedAt,
              retryInfo: rawNode.retry_info ?? rawNode.retryInfo ?? node.data.retryInfo,
              // Update goal, summary, description if they've been populated
              goal: rawNode.goal ?? node.data.goal,
              summary: rawNode.summary ?? node.data.summary,
              description: rawNode.description ?? node.data.description,
              insights: rawNode.insights ?? node.data.insights,
              bulletPoints: rawNode.bullet_points ?? rawNode.bulletPoints ?? node.data.bulletPoints,
              // Update generated_plan for planning nodes
              generated_plan: rawNode.generated_plan ?? node.data.generated_plan,
            },
          };
        }
        return node;
      })
    );
  }, [dagData, setNodes]);

  // Handle node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id);
      onNodeSelect?.(node.id);
    },
    [onNodeSelect]
  );

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  // Get selected node data
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    const node = nodes.find((n) => n.id === selectedNodeId);
    return node?.data || null;
  }, [selectedNodeId, nodes]);

  // MiniMap node color
  const minimapNodeColor = useCallback((node: Node<DAGNodeData>) => {
    return statusColors[node.data.status] || '#6B7280';
  }, []);

  return (
    <div className="relative w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        attributionPosition="bottom-right"
        className="bg-gray-900"
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#374151"
        />
        {showMinimap && (
          <MiniMap
            nodeColor={minimapNodeColor}
            maskColor="rgba(0, 0, 0, 0.8)"
            className="!bg-gray-800 !border-gray-700"
          />
        )}
      </ReactFlow>

      <DAGControls layout={layout} onLayoutChange={setLayout} />

      <NodeActionDialog
        node={selectedNode}
        runId={runId}
        onClose={() => {
          setSelectedNodeId(null);
          onNodeSelect?.(null);
        }}
        onPlayFromNode={onPlayFromNode}
      />
    </div>
  );
}

// Main component wrapped with ReactFlowProvider
export function DAGVisualization(props: DAGVisualizationProps) {
  // Show placeholder if no data
  if (!props.dagData || props.dagData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center max-w-md p-6">
          <div className="mb-4 text-gray-500">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
            </svg>
          </div>
          <p className="text-lg mb-2 text-white">No DAG Data Available</p>
          <p className="text-sm mb-4">
            DAG visualization will appear once you <span className="text-blue-400 font-medium">run a task</span>.
          </p>
          <p className="text-xs text-gray-500">
            Start a task execution to see the workflow graph visualization with real-time status updates.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ReactFlowProvider>
      <DAGVisualizationInner {...props} />
    </ReactFlowProvider>
  );
}
