// hooks/useEventHandler.ts

import { useCallback } from 'react';
import {
  WebSocketEvent,
  WebSocketEventType,
  WorkflowStartedData,
  WorkflowStateChangedData,
  DAGCreatedData,
  DAGNodeStatusChangedData,
  ApprovalRequestedData,
  StepRetryStartedData,
  CostUpdateData,
  AgentMessageData,
  ErrorOccurredData,
  CodeExecutionData,
  ToolCallData,
  FilesUpdatedData,
} from '@/types/websocket-events';

interface EventHandlers {
  // Workflow handlers
  onWorkflowStarted?: (data: WorkflowStartedData) => void;
  onWorkflowStateChanged?: (data: WorkflowStateChangedData) => void;
  onWorkflowPaused?: () => void;
  onWorkflowResumed?: () => void;
  onWorkflowCompleted?: () => void;
  onWorkflowFailed?: (error: string) => void;

  // Step handlers
  onStepStarted?: (data: any) => void;
  onStepProgress?: (data: any) => void;
  onStepCompleted?: (data: any) => void;
  onStepFailed?: (data: any) => void;

  // Retry handlers
  onRetryStarted?: (data: StepRetryStartedData) => void;
  onRetryBackoff?: (data: any) => void;
  onRetrySucceeded?: (data: any) => void;
  onRetryExhausted?: (data: any) => void;

  // DAG handlers
  onDAGCreated?: (data: DAGCreatedData) => void;
  onDAGUpdated?: (data: any) => void;
  onDAGNodeStatusChanged?: (data: DAGNodeStatusChangedData) => void;

  // Agent handlers
  onAgentMessage?: (data: AgentMessageData) => void;
  onAgentThinking?: (data: any) => void;
  onAgentToolCall?: (data: any) => void;
  onCodeExecution?: (data: CodeExecutionData) => void;
  onToolCall?: (data: ToolCallData) => void;

  // Approval handlers
  onApprovalRequested?: (data: ApprovalRequestedData) => void;
  onApprovalReceived?: (data: any) => void;

  // Metrics handlers
  onCostUpdate?: (data: CostUpdateData) => void;
  onMetricUpdate?: (data: any) => void;

  // File handlers
  onFileCreated?: (data: any) => void;
  onFileUpdated?: (data: any) => void;
  onFilesUpdated?: (data: FilesUpdatedData) => void;

  // Error handlers
  onError?: (data: ErrorOccurredData) => void;

  // Legacy handlers (backward compatibility)
  onOutput?: (output: string) => void;
  onStatus?: (status: string) => void;
  onResult?: (result: any) => void;
  onComplete?: () => void;
}

export function useEventHandler(handlers: EventHandlers) {
  const handleEvent = useCallback((event: WebSocketEvent) => {
    const { event_type, data } = event;

    switch (event_type) {
      // Workflow events
      case WebSocketEventType.WORKFLOW_STARTED:
        handlers.onWorkflowStarted?.(data as WorkflowStartedData);
        break;
      case WebSocketEventType.WORKFLOW_STATE_CHANGED:
        handlers.onWorkflowStateChanged?.(data as WorkflowStateChangedData);
        break;
      case WebSocketEventType.WORKFLOW_PAUSED:
        handlers.onWorkflowPaused?.();
        break;
      case WebSocketEventType.WORKFLOW_RESUMED:
        handlers.onWorkflowResumed?.();
        break;
      case WebSocketEventType.WORKFLOW_COMPLETED:
        handlers.onWorkflowCompleted?.();
        break;
      case WebSocketEventType.WORKFLOW_FAILED:
      case 'workflow_cancelled':  // Backend sends this on cancel
        handlers.onWorkflowFailed?.(data.error || data.message || 'Unknown error');
        break;

      // Step events
      case WebSocketEventType.STEP_STARTED:
        handlers.onStepStarted?.(data);
        break;
      case WebSocketEventType.STEP_PROGRESS:
        handlers.onStepProgress?.(data);
        break;
      case WebSocketEventType.STEP_COMPLETED:
        handlers.onStepCompleted?.(data);
        break;
      case WebSocketEventType.STEP_FAILED:
        handlers.onStepFailed?.(data);
        break;

      // Retry events
      case WebSocketEventType.STEP_RETRY_STARTED:
        handlers.onRetryStarted?.(data as StepRetryStartedData);
        break;
      case WebSocketEventType.STEP_RETRY_BACKOFF:
        handlers.onRetryBackoff?.(data);
        break;
      case WebSocketEventType.STEP_RETRY_SUCCEEDED:
        handlers.onRetrySucceeded?.(data);
        break;
      case WebSocketEventType.STEP_RETRY_EXHAUSTED:
        handlers.onRetryExhausted?.(data);
        break;

      // DAG events
      case WebSocketEventType.DAG_CREATED:
        handlers.onDAGCreated?.(data as DAGCreatedData);
        break;
      case WebSocketEventType.DAG_UPDATED:
        handlers.onDAGUpdated?.(data);
        break;
      case WebSocketEventType.DAG_NODE_STATUS_CHANGED:
        handlers.onDAGNodeStatusChanged?.(data as DAGNodeStatusChangedData);
        break;

      // Agent events
      case WebSocketEventType.AGENT_MESSAGE:
        handlers.onAgentMessage?.(data as AgentMessageData);
        // Also send to legacy output handler with formatted message
        if (data.role === 'transition' || data.role === 'llm_call') {
          handlers.onOutput?.(`🔄 [${data.agent}] ${data.message}`);
        } else {
          handlers.onOutput?.(`💬 [${data.agent}] ${data.message}`);
        }
        break;
      case WebSocketEventType.AGENT_THINKING:
        handlers.onAgentThinking?.(data);
        handlers.onOutput?.(`🤔 [${data.agent || 'Agent'}] Thinking...`);
        break;
      case WebSocketEventType.AGENT_TOOL_CALL:
        handlers.onAgentToolCall?.(data);
        handlers.onOutput?.(`🔧 [${data.agent || 'Agent'}] Calling tool: ${data.tool_name || 'unknown'}`);
        break;
      case WebSocketEventType.CODE_EXECUTION:
        handlers.onCodeExecution?.(data as CodeExecutionData);
        // Show code execution in console with truncated code preview
        const codePreview = data.code?.substring(0, 100) || '';
        const codeSuffix = (data.code?.length > 100) ? '...' : '';
        handlers.onOutput?.(`📝 [${data.agent}] Code (${data.language}): ${codePreview}${codeSuffix}`);
        if (data.result) {
          handlers.onOutput?.(`📤 [${data.agent}] Result: ${data.result.substring(0, 200)}`);
        }
        break;
      case WebSocketEventType.TOOL_CALL:
        handlers.onToolCall?.(data as ToolCallData);
        handlers.onOutput?.(`🔧 [${data.agent}] Tool: ${data.tool_name}(${JSON.stringify(data.arguments).substring(0, 100)})`);
        if (data.result) {
          handlers.onOutput?.(`📤 [${data.agent}] Result: ${data.result.substring(0, 200)}`);
        }
        break;

      // Approval events
      case WebSocketEventType.APPROVAL_REQUESTED:
        handlers.onApprovalRequested?.(data as ApprovalRequestedData);
        break;
      case WebSocketEventType.APPROVAL_RECEIVED:
        handlers.onApprovalReceived?.(data);
        break;

      // Metrics events
      case WebSocketEventType.COST_UPDATE:
        handlers.onCostUpdate?.(data as CostUpdateData);
        break;
      case WebSocketEventType.METRIC_UPDATE:
        handlers.onMetricUpdate?.(data);
        break;

      // File events
      case WebSocketEventType.FILE_CREATED:
        handlers.onFileCreated?.(data);
        break;
      case WebSocketEventType.FILE_UPDATED:
        handlers.onFileUpdated?.(data);
        break;
      case WebSocketEventType.FILES_UPDATED:
        handlers.onFilesUpdated?.(data as FilesUpdatedData);
        break;

      // Error events
      case WebSocketEventType.ERROR_OCCURRED:
      case 'error':  // Backend sends 'error' not 'error_occurred'
        handlers.onError?.({
          error_type: data.error_type || 'ExecutionError',
          message: data.message || 'Unknown error',
          traceback: data.traceback,
        });
        handlers.onOutput?.(`❌ Error: ${data.message}`);
        break;

      // Heartbeat (ignore, just for connection keepalive)
      case WebSocketEventType.HEARTBEAT:
      case WebSocketEventType.PONG:
        break;

      // Legacy event types (backward compatibility)
      case WebSocketEventType.OUTPUT:
      case 'output':
        handlers.onOutput?.(data.data || data.message || String(data));
        break;
      case WebSocketEventType.STATUS:
      case 'status':
        handlers.onStatus?.(data.message || String(data));
        handlers.onOutput?.(`📊 ${data.message}`);
        break;
      case WebSocketEventType.RESULT:
      case 'result':
        handlers.onResult?.(data.data || data);
        break;
      case WebSocketEventType.COMPLETE:
      case 'complete':
        handlers.onComplete?.();
        break;

      default:
        console.log('Unhandled WebSocket event:', event_type, data);
    }
  }, [handlers]);

  return { handleEvent };
}
