/**
 * Resilient WebSocket Hook with Auto-Reconnection
 *
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Heartbeat to keep connection alive
 * - Requests missed events on reconnection
 * - Handles structured event protocol
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { getWsUrl } from '@/lib/config';

interface WebSocketMessage {
  event_type: string;
  timestamp: string;
  run_id?: string;
  session_id?: string;
  data: any;
}

interface UseResilientWebSocketOptions {
  runId: string;
  onMessage: (message: WebSocketMessage) => void;
  onConnectionChange?: (connected: boolean) => void;
  maxReconnectAttempts?: number;
  initialReconnectDelay?: number;
  maxReconnectDelay?: number;
  heartbeatInterval?: number;
}

interface WebSocketState {
  connected: boolean;
  reconnectAttempt: number;
  lastError: string | null;
}

/**
 * Custom hook for resilient WebSocket connections
 */
export function useResilientWebSocket({
  runId,
  onMessage,
  onConnectionChange,
  maxReconnectAttempts = 999,
  initialReconnectDelay = 1000,
  maxReconnectDelay = 30000,
  heartbeatInterval = 30000,
}: UseResilientWebSocketOptions) {
  const [state, setState] = useState<WebSocketState>({
    connected: false,
    reconnectAttempt: 0,
    lastError: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const heartbeatIntervalRef = useRef<NodeJS.Timeout>();
  const lastMessageTimestamp = useRef<number>(Date.now());
  const shouldReconnect = useRef<boolean>(true);

  /**
   * Calculate reconnection delay with exponential backoff
   */
  const getReconnectDelay = useCallback(() => {
    return Math.min(
      initialReconnectDelay * Math.pow(2, state.reconnectAttempt),
      maxReconnectDelay
    );
  }, [state.reconnectAttempt, initialReconnectDelay, maxReconnectDelay]);

  /**
   * Start heartbeat to keep connection alive
   */
  const startHeartbeat = useCallback((ws: WebSocket) => {
    // Clear any existing heartbeat
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
    }, heartbeatInterval);
  }, [heartbeatInterval]);

  /**
   * Stop heartbeat
   */
  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = undefined;
    }
  }, []);

  /**
   * Connect to WebSocket server
   */
  const connect = useCallback(() => {
    // Don't connect if we shouldn't reconnect
    if (!shouldReconnect.current) {
      return;
    }

    const wsUrl = getWsUrl(`/ws/${runId}`);
    console.log(`[WebSocket] Connecting to ${wsUrl}...`);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        setState(prev => ({
          ...prev,
          connected: true,
          reconnectAttempt: 0,
          lastError: null,
        }));
        onConnectionChange?.(true);

        // Request current state on reconnect (if this is a reconnection)
        if (state.reconnectAttempt > 0) {
          ws.send(JSON.stringify({
            type: 'request_state',
            since: lastMessageTimestamp.current
          }));
        }

        // Start heartbeat
        startHeartbeat(ws);
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          lastMessageTimestamp.current = Date.now();

          // Handle pong messages (don't pass to onMessage)
          if (message.event_type === 'pong') {
            return;
          }

          onMessage(message);
        } catch (error) {
          console.error('[WebSocket] Error parsing message:', error);
          setState(prev => ({
            ...prev,
            lastError: 'Error parsing message from server'
          }));
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setState(prev => ({
          ...prev,
          lastError: 'WebSocket connection error'
        }));
      };

      ws.onclose = (event) => {
        console.log(`[WebSocket] Closed (code: ${event.code}, reason: ${event.reason || 'none'})`);

        setState(prev => ({
          ...prev,
          connected: false
        }));
        onConnectionChange?.(false);
        stopHeartbeat();

        // Attempt reconnection if we should and haven't exceeded max attempts
        if (shouldReconnect.current && state.reconnectAttempt < maxReconnectAttempts) {
          const delay = getReconnectDelay();
          console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${state.reconnectAttempt + 1})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            setState(prev => ({
              ...prev,
              reconnectAttempt: prev.reconnectAttempt + 1
            }));
            connect();
          }, delay);
        } else if (state.reconnectAttempt >= maxReconnectAttempts) {
          console.error('[WebSocket] Max reconnection attempts reached');
          setState(prev => ({
            ...prev,
            lastError: 'Max reconnection attempts reached'
          }));
        }
      };

    } catch (error) {
      console.error('[WebSocket] Error creating connection:', error);
      setState(prev => ({
        ...prev,
        connected: false,
        lastError: 'Failed to create WebSocket connection'
      }));
    }
  }, [
    runId,
    state.reconnectAttempt,
    onMessage,
    onConnectionChange,
    maxReconnectAttempts,
    getReconnectDelay,
    startHeartbeat,
    stopHeartbeat
  ]);

  /**
   * Send a message to the server
   */
  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(message));
      } catch (error) {
        console.error('[WebSocket] Error sending message:', error);
        setState(prev => ({
          ...prev,
          lastError: 'Error sending message'
        }));
      }
    } else {
      console.warn('[WebSocket] Cannot send message, not connected');
    }
  }, []);

  /**
   * Manually disconnect
   */
  const disconnect = useCallback(() => {
    console.log('[WebSocket] Manual disconnect');
    shouldReconnect.current = false;

    // Clear reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = undefined;
    }

    // Stop heartbeat
    stopHeartbeat();

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }

    setState({
      connected: false,
      reconnectAttempt: 0,
      lastError: null,
    });
  }, [stopHeartbeat]);

  /**
   * Manually reconnect
   */
  const reconnect = useCallback(() => {
    console.log('[WebSocket] Manual reconnect');
    disconnect();
    shouldReconnect.current = true;
    setState(prev => ({ ...prev, reconnectAttempt: 0 }));
    connect();
  }, [disconnect, connect]);

  /**
   * Effect: Connect on mount, disconnect on unmount
   */
  useEffect(() => {
    shouldReconnect.current = true;
    connect();

    return () => {
      shouldReconnect.current = false;

      // Cleanup on unmount
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }

      stopHeartbeat();

      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
        wsRef.current = null;
      }
    };
  }, [connect, stopHeartbeat]);

  return {
    connected: state.connected,
    reconnectAttempt: state.reconnectAttempt,
    lastError: state.lastError,
    sendMessage,
    disconnect,
    reconnect,
  };
}
