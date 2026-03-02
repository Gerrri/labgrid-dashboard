import { useState, useEffect, useCallback, useRef } from 'react';
import type { WSMessage, Target, CommandOutput } from '../types';
import { buildWsUrl } from '../utils/urlBuilder';

const RECONNECT_INTERVAL = 5000;
const MAX_RECONNECT_ATTEMPTS = 10;

interface UseWebSocketOptions {
  onTargetUpdate?: (target: Target) => void;
  onCommandOutput?: (targetName: string, output: CommandOutput) => void;
  onScheduledOutput?: (targetName: string, commandName: string, output: CommandOutput) => void;
  onTargetsList?: (targets: Target[]) => void;
  onConnectionChange?: (connected: boolean) => void;
}

interface UseWebSocketResult {
  connected: boolean;
  send: (message: WSMessage) => void;
  subscribe: (targetName?: string) => void;
}

/**
 * Custom hook for WebSocket connection with reconnect logic.
 * Handles React Strict Mode double-mount gracefully.
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketResult {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const callbacksRef = useRef<UseWebSocketOptions>(options);
  // Flag to track intentional closes (cleanup, unmount) vs unexpected disconnects
  const intentionalCloseRef = useRef(false);

  const {
    onTargetUpdate,
    onCommandOutput,
    onScheduledOutput,
    onTargetsList,
    onConnectionChange,
  } = options;

  useEffect(() => {
    callbacksRef.current = options;
  }, [options]);

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

    // Reset intentional close flag when starting a new connection
    intentionalCloseRef.current = false;

    try {
      const wsUrl = buildWsUrl('/api/ws');
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        callbacksRef.current.onConnectionChange?.(true);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data);

          switch (message.type) {
            case 'target_update':
              callbacksRef.current.onTargetUpdate?.(message.data as Target);
              break;
            case 'command_output': {
              const data = message.data as {
                target_name?: string;
                target?: string;
                output: CommandOutput;
              };
              const targetName = data.target_name ?? data.target;
              if (targetName) {
                callbacksRef.current.onCommandOutput?.(targetName, data.output);
              }
              break;
            }
            case 'scheduled_output': {
              const data = message.data as {
                target: string;
                command_name: string;
                output: CommandOutput;
              };
              callbacksRef.current.onScheduledOutput?.(
                data.target,
                data.command_name,
                data.output
              );
              break;
            }
            case 'targets_list':
              callbacksRef.current.onTargetsList?.(message.data as Target[]);
              break;
            default:
              console.log('Unknown message type:', message.type);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = () => {
        // Only log errors if this wasn't an intentional close (e.g., React Strict Mode cleanup)
        // The error event doesn't contain useful information anyway (browser security)
        if (!intentionalCloseRef.current) {
          console.warn('WebSocket connection error, will attempt to reconnect...');
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;

        // Skip logging and reconnection if this was an intentional close (cleanup/unmount)
        if (intentionalCloseRef.current) {
          return;
        }

        console.log('WebSocket disconnected');
        callbacksRef.current.onConnectionChange?.(false);

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
          console.warn('WebSocket: Max reconnect attempts reached, giving up');
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
    }
  }, []);

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
      // Mark as intentional close to prevent error logging and reconnection attempts
      intentionalCloseRef.current = true;
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
