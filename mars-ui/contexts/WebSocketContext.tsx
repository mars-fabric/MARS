// contexts/WebSocketContext.tsx

'use client';

import React, { createContext, useContext, useState, useCallback, useRef, useEffect, useMemo, ReactNode } from 'react';
import { useEventHandler } from '@/hooks/useEventHandler';
import { WebSocketEvent, DAGCreatedData, DAGNodeStatusChangedData, ApprovalRequestedData, DAGNodeData, DAGEdgeData, CostUpdateData, FilesUpdatedData, AgentMessageData } from '@/types/websocket-events';
import { getWsUrl, getApiUrl } from '@/lib/config';
import { CostSummary, CostTimeSeries, ModelCost, AgentCost, StepCost } from '@/types/cost';

interface WebSocketContextValue {
  // Connection state
  connected: boolean;
  reconnectAttempt: number;
  lastError: string | null;
  isConnecting: boolean;

  // Actions
  connect: (taskId: string, task: string, config: any) => Promise<void>;
  sendMessage: (message: any) => void;
  disconnect: () => void;
  reconnect: () => void;

  // Current run
  currentRunId: string | null;
  setCurrentRunId: (runId: string | null) => void;

  // Copilot session (for conversation continuation)
  copilotSessionId: string | null;
  setCopilotSessionId: (sessionId: string | null) => void;

  // Workflow state
  workflowStatus: string | null;
  setWorkflowStatus: (status: string | null) => void;

  // DAG state
  dagData: { run_id?: string; nodes: DAGNodeData[]; edges: DAGEdgeData[] } | null;
  updateDAGNode: (nodeId: string, status: string) => void;

  // Approval state
  pendingApproval: ApprovalRequestedData | null;
  clearApproval: () => void;

  // Console output
  consoleOutput: string[];
  addConsoleOutput: (output: string) => void;
  clearConsole: () => void;

  // Results
  results: any | null;
  setResults: (results: any) => void;

  // Running state
  isRunning: boolean;
  setIsRunning: (running: boolean) => void;

  // Cost tracking
  costSummary: CostSummary;
  costTimeSeries: CostTimeSeries[];

  // Files update trigger (increment to trigger refresh in DAGFilesView)
  filesUpdatedCounter: number;

  // Agent messages for copilot chat
  agentMessages: AgentMessageData[];
  clearAgentMessages: () => void;

  // Session management (Stage 11)
  resumeSession: (sessionId: string, additionalContext?: string) => Promise<void>;
  loadSessionHistory: (sessionId: string) => Promise<any>;

  // State restoration (for tab switching)
  setConsoleOutputDirect: (output: string[]) => void;
  setDagDataDirect: (data: { run_id?: string; nodes: DAGNodeData[]; edges: DAGEdgeData[] } | null) => void;
  setCostSummaryDirect: (summary: CostSummary) => void;
  setCostTimeSeriesDirect: (series: CostTimeSeries[]) => void;
}

const WebSocketContext = createContext<WebSocketContextValue | undefined>(undefined);

interface WebSocketProviderProps {
  children: ReactNode;
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  // Connection state
  const [connected, setConnected] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  // Local state
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [copilotSessionId, setCopilotSessionId] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<string | null>(null);
  const [dagData, setDAGData] = useState<{ run_id?: string; nodes: DAGNodeData[]; edges: DAGEdgeData[] } | null>(null);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequestedData | null>(null);
  const [consoleOutput, setConsoleOutput] = useState<string[]>([]);
  const [results, setResults] = useState<any | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  // Cost tracking state
  const [costSummary, setCostSummary] = useState<CostSummary>({
    total_cost: 0,
    total_tokens: 0,
    input_tokens: 0,
    output_tokens: 0,
    model_breakdown: [],
    agent_breakdown: [],
    step_breakdown: [],
  });
  const [costTimeSeries, setCostTimeSeries] = useState<CostTimeSeries[]>([]);

  // Files update counter - incremented when files_updated event is received
  const [filesUpdatedCounter, setFilesUpdatedCounter] = useState(0);

  // Agent messages for copilot chat
  const [agentMessages, setAgentMessages] = useState<AgentMessageData[]>([]);

  const clearAgentMessages = useCallback(() => {
    setAgentMessages([]);
  }, []);

  // WebSocket refs
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const heartbeatIntervalRef = useRef<NodeJS.Timeout>();
  const shouldReconnect = useRef<boolean>(false);
  const lastMessageTimestamp = useRef<number>(Date.now());  
  // Store task and config for reconnection
  const taskDataRef = useRef<{ task: string; config: any } | null>(null);
  // Console helpers
  const addConsoleOutput = useCallback((output: string) => {
    setConsoleOutput(prev => [...prev, output]);
  }, []);

  const clearConsole = useCallback(() => {
    setConsoleOutput([]);
    setCostSummary({
      total_cost: 0,
      total_tokens: 0,
      input_tokens: 0,
      output_tokens: 0,
      model_breakdown: [],
      agent_breakdown: [],
      step_breakdown: [],
    });
    setCostTimeSeries([]);
  }, []);

  // DAG helpers
  const updateDAGNode = useCallback((nodeId: string, status: string) => {
    setDAGData(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        nodes: prev.nodes.map(node =>
          node.id === nodeId ? { ...node, status } : node
        ),
      };
    });
  }, []);

  // Approval helpers
  const clearApproval = useCallback(() => {
    setPendingApproval(null);
  }, []);

  // Session-aware console output: show all output in main console
  // Session-scoping was intended for multi-session UIs, but currently we show everything
  const sessionFilteredAddConsole = useCallback((output: string) => {
    // Always add to console - session_id is for tracking, not filtering display
    addConsoleOutput(output);
  }, [addConsoleOutput]);

  // Ref to track whether current event being processed is session-scoped
  const sessionScopedEventRef = useRef(false);

  // Event handler
  const { handleEvent } = useEventHandler({
    onWorkflowStarted: (data) => {
      setWorkflowStatus('executing');
      sessionFilteredAddConsole(`🚀 Workflow started: ${data.task_description}`);
      // Reset cost tracking for new workflow
      setCostSummary({
        total_cost: 0,
        total_tokens: 0,
        input_tokens: 0,
        output_tokens: 0,
        model_breakdown: [],
        agent_breakdown: [],
        step_breakdown: [],
      });
      setCostTimeSeries([]);
    },
    onWorkflowStateChanged: (data) => {
      setWorkflowStatus(data.status);
    },
    onWorkflowPaused: () => {
      setWorkflowStatus('paused');
      sessionFilteredAddConsole('⏸️ Workflow paused');
    },
    onWorkflowResumed: () => {
      setWorkflowStatus('executing');
      sessionFilteredAddConsole('▶️ Workflow resumed');
    },
    onWorkflowCompleted: () => {
      setWorkflowStatus('completed');
      setIsRunning(false);
      shouldReconnect.current = false; // Stop reconnection on completion
      sessionFilteredAddConsole('✅ Workflow completed');
    },
    onWorkflowFailed: (error) => {
      setWorkflowStatus('failed');
      setIsRunning(false);
      shouldReconnect.current = false; // Stop reconnection on failure
      sessionFilteredAddConsole(`❌ Workflow failed: ${error}`);
    },
    onDAGCreated: (data: DAGCreatedData) => {
      setDAGData({ run_id: data.run_id, nodes: data.nodes, edges: data.edges });
      sessionFilteredAddConsole(`📊 DAG created with ${data.nodes.length} nodes`);
    },
    onDAGUpdated: (data: DAGCreatedData) => {
      setDAGData({ run_id: data.run_id, nodes: data.nodes, edges: data.edges });
      sessionFilteredAddConsole(`📊 DAG updated: ${data.nodes.length} nodes`);
    },
    onDAGNodeStatusChanged: (data: DAGNodeStatusChangedData) => {
      updateDAGNode(data.node_id, data.new_status);
    },
    onApprovalRequested: (data: ApprovalRequestedData) => {
      console.log('[WebSocket] Approval requested event received:', data);
      setPendingApproval(data);
      sessionFilteredAddConsole(`⏸️ Approval requested: ${data.description || data.message}`);
    },
    onApprovalReceived: () => {
      clearApproval();
    },
    onOutput: sessionFilteredAddConsole,
    onResult: (result: any) => {
      setResults(result);
      // Store session_id for continuation (works for ALL modes)
      if (result?.session_id) {
        setCopilotSessionId(result.session_id);
      }
    },
    onComplete: () => {
      setWorkflowStatus('completed');
      setIsRunning(false);
      shouldReconnect.current = false; // Stop reconnection on completion
      sessionFilteredAddConsole('✅ Task execution completed');
    },
    onError: (data) => {
      sessionFilteredAddConsole(`❌ ${data.error_type}: ${data.message}`);
    },
    onStatus: (status: any) => {
      const message = typeof status === 'string' ? status : status?.message || String(status);
      sessionFilteredAddConsole(`📊 ${message}`);
      // Capture session_id from initial status event (Stages 10-11)
      if (typeof status === 'object' && status?.session_id) {
        setCopilotSessionId(status.session_id);
      }
    },
    onFilesUpdated: (data: FilesUpdatedData) => {
      // Increment counter to trigger file refresh in DAGFilesView
      setFilesUpdatedCounter(prev => prev + 1);
      sessionFilteredAddConsole(`📁 ${data.files_tracked} file(s) tracked for node ${data.node_id || 'unknown'}`);
    },
    onAgentMessage: (data: AgentMessageData) => {
      // Store agent messages for copilot chat view
      setAgentMessages(prev => [...prev, data]);
    },
    onCostUpdate: (data: CostUpdateData) => {
      // Debug: Log all incoming cost updates to investigate "unknown" model
      console.log('🔍 Cost Update Received:', {
        model: data.model,
        step_id: data.step_id,
        cost_usd: data.cost_usd,
        total_cost_usd: data.total_cost_usd,
        tokens: data.tokens,
        input_tokens: data.input_tokens,
        output_tokens: data.output_tokens
      });

      // Update cost summary
      setCostSummary(prev => {
        // CostCollector always provides actual token counts from JSON
        const inputTokens = data.input_tokens || 0;
        const outputTokens = data.output_tokens || 0;

        // Update model breakdown
        const newModelBreakdown = [...prev.model_breakdown];
        const modelIndex = newModelBreakdown.findIndex(m => m.model === data.model);
        
        if (modelIndex >= 0) {
          // Update existing model entry
          newModelBreakdown[modelIndex] = {
            ...newModelBreakdown[modelIndex],
            cost: newModelBreakdown[modelIndex].cost + data.cost_usd,
            tokens: newModelBreakdown[modelIndex].tokens + data.tokens,
            input_tokens: newModelBreakdown[modelIndex].input_tokens + inputTokens,
            output_tokens: newModelBreakdown[modelIndex].output_tokens + outputTokens,
            call_count: newModelBreakdown[modelIndex].call_count + 1,
          };
        } else {
          // Add new model entry
          newModelBreakdown.push({
            model: data.model,
            cost: data.cost_usd,
            tokens: data.tokens,
            input_tokens: inputTokens,
            output_tokens: outputTokens,
            call_count: 1,
          });
        }

        // Update agent breakdown using agent name from CostCollector
        const newAgentBreakdown = [...prev.agent_breakdown];
        const agentName = data.agent || data.step_id?.replace(/_step$/, '') || 'unknown';

        const agentIndex = newAgentBreakdown.findIndex(a => a.agent === agentName);

        if (agentIndex >= 0) {
          newAgentBreakdown[agentIndex] = {
            ...newAgentBreakdown[agentIndex],
            cost: newAgentBreakdown[agentIndex].cost + data.cost_usd,
            tokens: newAgentBreakdown[agentIndex].tokens + data.tokens,
            input_tokens: newAgentBreakdown[agentIndex].input_tokens + inputTokens,
            output_tokens: newAgentBreakdown[agentIndex].output_tokens + outputTokens,
            call_count: newAgentBreakdown[agentIndex].call_count + 1,
          };
        } else {
          newAgentBreakdown.push({
            agent: agentName,
            model: data.model,
            cost: data.cost_usd,
            tokens: data.tokens,
            input_tokens: inputTokens,
            output_tokens: outputTokens,
            call_count: 1,
          });
        }

        // Update step breakdown
        const newStepBreakdown = [...prev.step_breakdown];
        if (data.step_id) {
          const stepIndex = newStepBreakdown.findIndex(s => s.step_id === data.step_id);
          
          if (stepIndex >= 0) {
            newStepBreakdown[stepIndex] = {
              ...newStepBreakdown[stepIndex],
              cost: newStepBreakdown[stepIndex].cost + data.cost_usd,
              tokens: newStepBreakdown[stepIndex].tokens + data.tokens,
            };
          } else {
            // Extract agent name for better description
            const stepNumber = newStepBreakdown.length + 1;
            newStepBreakdown.push({
              step_id: data.step_id,
              step_number: stepNumber,
              description: `${agentName} (Step ${stepNumber})`,
              cost: data.cost_usd,
              tokens: data.tokens,
            });
          }
        }

        console.log('📊 Updated Cost Summary:', {
          model_breakdown_count: newModelBreakdown.length,
          agent_breakdown_count: newAgentBreakdown.length,
          models: newModelBreakdown.map(m => m.model)
        });

        // Derive totals from model breakdown so they always match the displayed data
        const newTotalCost = newModelBreakdown.reduce((sum, m) => sum + m.cost, 0);
        const newTotalTokens = newModelBreakdown.reduce((sum, m) => sum + m.tokens, 0);
        const newInputTokens = newModelBreakdown.reduce((sum, m) => sum + m.input_tokens, 0);
        const newOutputTokens = newModelBreakdown.reduce((sum, m) => sum + m.output_tokens, 0);

        return {
          total_cost: newTotalCost,
          total_tokens: newTotalTokens,
          input_tokens: newInputTokens,
          output_tokens: newOutputTokens,
          model_breakdown: newModelBreakdown,
          agent_breakdown: newAgentBreakdown,
          step_breakdown: newStepBreakdown,
        };
      });

      // Add to time series
      setCostTimeSeries(prev => [
        ...prev,
        {
          timestamp: new Date().toISOString(),
          cumulative_cost: data.total_cost_usd,
          step_cost: data.cost_usd,
          step_number: data.step_id ? parseInt(data.step_id.replace(/\D/g, '')) : undefined,
        },
      ]);
    },
  });

  // Heartbeat management
  const startHeartbeat = useCallback((ws: WebSocket) => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    heartbeatIntervalRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: 'ping' }));
        } catch (error) {
          console.error('Error sending ping:', error);
        }
      }
    }, 30000);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = undefined;
    }
  }, []);

  // Connect function
  const connect = useCallback(async (taskId: string, task: string, config: any) => {
    // Close existing connection
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    setIsConnecting(true);
    setCurrentRunId(taskId);
    shouldReconnect.current = true;

    const wsUrl = getWsUrl(`/ws/${taskId}`);
    console.log(`[WebSocket] Connecting to ${wsUrl}...`);

    return new Promise<void>((resolve, reject) => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('[WebSocket] Connected');
          setConnected(true);
          setIsConnecting(false);
          setReconnectAttempt(0);
          setLastError(null);
          addConsoleOutput('🔌 WebSocket connected');

          // Send task data
          const taskData = { task, config };
          taskDataRef.current = taskData; // Store for reconnection
          ws.send(JSON.stringify(taskData));

          // Start heartbeat
          startHeartbeat(ws);

          resolve();
        };

        ws.onmessage = (event) => {
          try {
            const rawMessage = JSON.parse(event.data);
            lastMessageTimestamp.current = Date.now();

            // Normalize message format: backend uses 'type', new protocol uses 'event_type'
            const message: WebSocketEvent = {
              event_type: rawMessage.event_type || rawMessage.type || 'unknown',
              timestamp: rawMessage.timestamp || new Date().toISOString(),
              run_id: rawMessage.run_id,
              session_id: rawMessage.session_id,
              // Backend puts data directly in message, new protocol nests under 'data'
              data: rawMessage.data !== undefined ? rawMessage.data : rawMessage,
            };

            // Handle pong messages (don't pass to handler)
            if (message.event_type === 'pong') {
              return;
            }

            // If the event is session-scoped, inject session_id into data
            // so downstream handlers can detect it, and skip main console output
            if (message.session_id) {
              message.data = { ...message.data, _session_id: message.session_id };
              sessionScopedEventRef.current = true;
            } else {
              sessionScopedEventRef.current = false;
            }

            handleEvent(message);
            sessionScopedEventRef.current = false;
          } catch (error) {
            console.error('[WebSocket] Error parsing message:', error);
            setLastError('Error parsing message from server');
          }
        };

        ws.onerror = (error) => {
          console.error('[WebSocket] Error:', error);
          setLastError('WebSocket connection error');
          setIsConnecting(false);
          reject(new Error('WebSocket connection error'));
        };

        ws.onclose = (event) => {
          console.log(`[WebSocket] Closed (code: ${event.code}, reason: ${event.reason || 'none'})`);
          setConnected(false);
          setIsConnecting(false);
          stopHeartbeat();
          addConsoleOutput('🔌 WebSocket disconnected');

          // Handle reconnection with exponential backoff
          if (shouldReconnect.current && reconnectAttempt < 10) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), 30000);
            console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttempt + 1})`);

            reconnectTimeoutRef.current = setTimeout(() => {
              setReconnectAttempt(prev => prev + 1);
              // Re-establish connection
              if (wsRef.current === null || wsRef.current.readyState === WebSocket.CLOSED) {
                const newWs = new WebSocket(wsUrl);
                wsRef.current = newWs;

                newWs.onopen = () => {
                  setConnected(true);
                  setReconnectAttempt(0);
                  setLastError(null);
                  addConsoleOutput('🔌 WebSocket reconnected');

                  // Resend task data on reconnection
                  if (taskDataRef.current) {
                    console.log('[WebSocket] Resending task data on reconnection');
                    newWs.send(JSON.stringify(taskDataRef.current));
                  }

                  startHeartbeat(newWs);
                };

                newWs.onmessage = ws.onmessage;
                newWs.onerror = ws.onerror;
                newWs.onclose = ws.onclose;
              }
            }, delay);
          } else if (reconnectAttempt >= 10) {
            setLastError('Max reconnection attempts reached');
          }
        };

      } catch (error) {
        console.error('[WebSocket] Error creating connection:', error);
        setConnected(false);
        setIsConnecting(false);
        setLastError('Failed to create WebSocket connection');
        reject(error);
      }
    });
  }, [addConsoleOutput, handleEvent, reconnectAttempt, startHeartbeat, stopHeartbeat]);

  // Send message
  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(message));
      } catch (error) {
        console.error('[WebSocket] Error sending message:', error);
        setLastError('Error sending message');
      }
    } else {
      console.warn('[WebSocket] Cannot send message, not connected');
    }
  }, []);

  // Disconnect
  const disconnect = useCallback(() => {
    console.log('[WebSocket] Manual disconnect');
    shouldReconnect.current = false;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = undefined;
    }

    stopHeartbeat();

    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }

    setConnected(false);
    setIsConnecting(false);
    setReconnectAttempt(0);
    setLastError(null);
  }, [stopHeartbeat]);

  // Reconnect
  const reconnect = useCallback(() => {
    console.log('[WebSocket] Manual reconnect');
    if (currentRunId) {
      disconnect();
      shouldReconnect.current = true;
      setReconnectAttempt(0);
      // Note: Reconnection requires the original task/config which we don't have
      // This is mainly for UI purposes to show reconnection intent
    }
  }, [currentRunId, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      shouldReconnect.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      stopHeartbeat();
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
        wsRef.current = null;
      }
    };
  }, [stopHeartbeat]);

  // Session management (Stage 11)
  const resumeSession = useCallback(async (sessionId: string, additionalContext?: string) => {
    try {
      // Load session info to get config
      const response = await fetch(getApiUrl(`/api/sessions/${sessionId}`));
      if (!response.ok) throw new Error("Failed to load session");

      const session = await response.json();

      // Resume the session via API
      await fetch(getApiUrl(`/api/sessions/${sessionId}/resume`), { method: "POST" });

      // Generate a task ID and connect with session context
      const taskId = `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      await connect(taskId, additionalContext || "Continue the previous session.", {
        ...session.config,
        copilotSessionId: sessionId,
        additionalContext: additionalContext || "",
        mode: session.mode,
      });

      setCopilotSessionId(sessionId);
    } catch (error) {
      console.error("Failed to resume session:", error);
      throw error;
    }
  }, [connect, setCopilotSessionId]);

  const loadSessionHistory = useCallback(async (sessionId: string) => {
    const response = await fetch(getApiUrl(`/api/sessions/${sessionId}/history`));
    if (!response.ok) throw new Error("Failed to load history");
    return response.json();
  }, []);

  // State restoration setters (for tab switching)
  const setConsoleOutputDirect = useCallback((output: string[]) => {
    setConsoleOutput(output);
  }, []);

  const setDagDataDirect = useCallback((data: { run_id?: string; nodes: DAGNodeData[]; edges: DAGEdgeData[] } | null) => {
    setDAGData(data);
  }, []);

  const setCostSummaryDirect = useCallback((summary: CostSummary) => {
    setCostSummary(summary);
  }, []);

  const setCostTimeSeriesDirect = useCallback((series: CostTimeSeries[]) => {
    setCostTimeSeries(series);
  }, []);

  const value: WebSocketContextValue = useMemo(() => ({
    connected,
    reconnectAttempt,
    lastError,
    isConnecting,
    connect,
    sendMessage,
    disconnect,
    reconnect,
    currentRunId,
    setCurrentRunId,
    copilotSessionId,
    setCopilotSessionId,
    workflowStatus,
    setWorkflowStatus,
    dagData,
    updateDAGNode,
    pendingApproval,
    clearApproval,
    consoleOutput,
    addConsoleOutput,
    clearConsole,
    results,
    setResults,
    isRunning,
    setIsRunning,
    costSummary,
    costTimeSeries,
    filesUpdatedCounter,
    agentMessages,
    clearAgentMessages,
    resumeSession,
    loadSessionHistory,
    setConsoleOutputDirect,
    setDagDataDirect,
    setCostSummaryDirect,
    setCostTimeSeriesDirect,
  }), [
    connected, reconnectAttempt, lastError, isConnecting,
    connect, sendMessage, disconnect, reconnect,
    currentRunId, copilotSessionId, workflowStatus,
    dagData, updateDAGNode, pendingApproval, clearApproval,
    consoleOutput, addConsoleOutput, clearConsole,
    results, isRunning, costSummary, costTimeSeries,
    filesUpdatedCounter, agentMessages, clearAgentMessages,
    resumeSession, loadSessionHistory,
    setConsoleOutputDirect, setDagDataDirect,
    setCostSummaryDirect, setCostTimeSeriesDirect,
  ]);

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (context === undefined) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
}
