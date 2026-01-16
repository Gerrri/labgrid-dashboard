import { useState, useEffect, useCallback, useRef } from 'react';
import type { WSMessage, Target, CommandOutput } from '../types';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api/ws';
const RECONNECT_INTERVAL = 5000;
const MAX_RECONNECT_ATTEMPTS = 10;

interface UseWebSocketOptions {
  onTargetUpdate?: (target: Target) => void;
  onCommandOutput?: (targetName: string, output: CommandOutput) => void;
  onTargetsList?: (targets: Target[]) => void;
  onConnectionChange?: (connected: boolean) => void;
}

interface UseWebSocketResult {
  connected: boolean;
  send: (message: WSMessage) => void;
  subscribe: (targetName?: string) => void;
}

/**
 * Custom hook for WebSocket connection with reconnect logic
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketResult {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const {
    onTargetUpdate,
    onCommandOutput,
    onTargetsList,
    onConnectionChange,
  } = options;

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        onConnectionChange?.(true);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data);

          switch (message.type) {
            case 'target_update':
              onTargetUpdate?.(message.data as Target);
              break;
            case 'command_output': {
              const data = message.data as {
                target_name: string;
                output: CommandOutput;
              };
              onCommandOutput?.(data.target_name, data.output);
              break;
            }
            case 'targets_list':
              onTargetsList?.(message.data as Target[]);
              break;
            default:
              console.log('Unknown message type:', message.type);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        onConnectionChange?.(false);
        wsRef.current = null;

        // Attempt reconnection
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1;
          console.log(
            `Reconnecting in ${RECONNECT_INTERVAL / 1000}s... ` +
              `(attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`
          );
          reconnectTimeoutRef.current = window.setTimeout(
            connect,
            RECONNECT_INTERVAL
          );
        } else {
          console.error('Max reconnect attempts reached');
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
    }
  }, [onTargetUpdate, onCommandOutput, onTargetsList, onConnectionChange]);

  const send = useCallback((message: WSMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, message not sent');
    }
  }, []);

  const subscribe = useCallback(
    (targetName?: string) => {
      send({
        type: 'subscribe',
        data: targetName ? { target_name: targetName } : undefined,
      });
    },
    [send]
  );

  useEffect(() => {
    connect();

    return () => {
      clearReconnectTimeout();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, clearReconnectTimeout]);

  return {
    connected,
    send,
    subscribe,
  };
}

export default useWebSocket;
