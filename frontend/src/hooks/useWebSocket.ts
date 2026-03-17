import { useEffect, useRef, useState, useCallback } from 'react';

// WebSocket Configuration
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/feed';

// Event types
export type FeedEventType = 
  | 'mission_started'
  | 'mission_ended'
  | 'mission_completed'
  | 'mission_failed'
  | 'alliance_formed'
  | 'alliance_dissolved'
  | 'alliance_broken'
  | 'treaty_broken'
  | 'betrayal_detected'
  | 'agent_rank_changed'
  | 'agent_promoted'
  | 'agent_demoted'
  | 'agent_victory'
  | 'victory'
  | 'agent_defeated'
  | 'system';

export interface FeedEvent {
  event_id: string;
  type: FeedEventType;
  category: 'mission' | 'alliance' | 'betrayal' | 'rank' | 'victory' | 'system';
  summary: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
}

export interface WebSocketMessage {
  op: string;
  [key: string]: unknown;
}

export interface UseWebSocketOptions {
  types?: FeedEventType[];
  categories?: string[];
  reconnect?: boolean;
  onEvent?: (event: FeedEvent) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
}

export interface UseWebSocketReturn {
  events: FeedEvent[];
  isConnected: boolean;
  isConnecting: boolean;
  error: Error | null;
  send: (message: WebSocketMessage) => void;
  subscribe: (types: FeedEventType[]) => void;
  unsubscribe: (types: FeedEventType[]) => void;
  clearEvents: () => void;
  reconnect: () => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    types = [],
    categories: _categories = [],
    reconnect: shouldReconnect = true,
    onEvent,
    onConnect,
    onDisconnect,
    onError,
  } = options;

  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const connectionIdRef = useRef<string | null>(null);

  const MAX_RECONNECT_ATTEMPTS = 10;
  const RECONNECT_DELAY_BASE = 1000;
  const MAX_RECONNECT_DELAY = 30000;

  // Calculate exponential backoff delay
  const getReconnectDelay = useCallback(() => {
    const delay = Math.min(
      RECONNECT_DELAY_BASE * Math.pow(2, reconnectAttemptsRef.current),
      MAX_RECONNECT_DELAY
    );
    return delay + Math.random() * 1000; // Add jitter
  }, []);

  // Clear heartbeat interval
  const clearHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  // Setup heartbeat
  const setupHeartbeat = useCallback((intervalSeconds: number = 25) => {
    clearHeartbeat();
    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ op: 'ping' }));
      }
    }, intervalSeconds * 1000);
  }, [clearHeartbeat]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      // Build connection URL with filters
      const url = new URL(WS_URL);
      if (types.length > 0) {
        url.searchParams.set('types', types.join(','));
      }
      if (reconnectAttemptsRef.current > 0) {
        url.searchParams.set('reconnect', 'true');
      }

      const ws = new WebSocket(url.toString());
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
        setError(null);
        reconnectAttemptsRef.current = 0;
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          switch (message.op) {
            case 'snapshot':
              // Initial connection snapshot
              connectionIdRef.current = message.connection_id as string;
              const heartbeat = message.heartbeat as { interval_seconds: number } | undefined;
              if (heartbeat) {
                setupHeartbeat(heartbeat.interval_seconds);
              }
              // Process any recent events from reconnection
              const recentEvents = message.recent_events as FeedEvent[] | undefined;
              if (recentEvents && recentEvents.length > 0) {
                setEvents((prev) => {
                  const newEvents = recentEvents.filter(
                    (e) => !prev.some((p) => p.event_id === e.event_id)
                  );
                  return [...newEvents, ...prev].slice(0, 100);
                });
              }
              break;

            case 'subscribed':
            case 'filtered':
              // Subscription confirmed
              break;

            case 'recent_events':
              // Received recent events on request
              const events = message.events as FeedEvent[] | undefined;
              if (events) {
                setEvents((prev) => {
                  const newEvents = events.filter(
                    (e) => !prev.some((p) => p.event_id === e.event_id)
                  );
                  return [...newEvents, ...prev].slice(0, 100);
                });
              }
              break;

            case 'event':
              // New feed event
              const feedEvent = message as unknown as FeedEvent;
              setEvents((prev) => {
                // Prevent duplicates
                if (prev.some((e) => e.event_id === feedEvent.event_id)) {
                  return prev;
                }
                const newEvents = [feedEvent, ...prev].slice(0, 100);
                return newEvents;
              });
              onEvent?.(feedEvent);
              break;

            case 'pong':
              // Heartbeat response
              break;

            case 'ping':
              // Server heartbeat, respond with pong
              ws.send(JSON.stringify({ op: 'pong' }));
              break;

            case 'error':
              // Server error
              const errorMessage = message.message as string;
              const errorCode = message.code as string;
              console.error('WebSocket server error:', errorCode, errorMessage);
              setError(new Error(`Server error: ${errorCode} - ${errorMessage}`));
              onError?.(new Error(`Server error: ${errorCode} - ${errorMessage}`));
              break;

            case 'stats':
              // Server stats
              break;

            default:
              console.warn('Unknown WebSocket message type:', message.op);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (_error) => {
        const err = new Error('WebSocket error occurred');
        setError(err);
        setIsConnecting(false);
        onError?.(err);
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        setIsConnecting(false);
        clearHeartbeat();
        onDisconnect?.();

        // Attempt reconnection if enabled and not a clean close
        if (shouldReconnect && !event.wasClean && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++;
          const delay = getReconnectDelay();
          console.log(`WebSocket reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current})`);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch (err) {
      setIsConnecting(false);
      const error = err instanceof Error ? err : new Error('Failed to connect');
      setError(error);
      onError?.(error);
    }
  }, [types, shouldReconnect, onEvent, onConnect, onDisconnect, onError, getReconnectDelay, setupHeartbeat, clearHeartbeat]);

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    clearHeartbeat();

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, [clearHeartbeat]);

  // Send message
  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }, []);

  // Subscribe to event types
  const subscribe = useCallback((eventTypes: FeedEventType[]) => {
    send({ op: 'subscribe', types: eventTypes });
  }, [send]);

  // Unsubscribe from event types
  const unsubscribe = useCallback((eventTypes: FeedEventType[]) => {
    send({ op: 'unsubscribe', types: eventTypes });
  }, [send]);

  // Clear all events
  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  // Manual reconnect
  const reconnect = useCallback(() => {
    disconnect();
    reconnectAttemptsRef.current = 0;
    connect();
  }, [disconnect, connect]);

  // Connect on mount
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, []);

  // Update filters when types change
  useEffect(() => {
    if (isConnected && types.length > 0) {
      send({ op: 'filter', types });
    }
  }, [types, isConnected, send]);

  return {
    events,
    isConnected,
    isConnecting,
    error,
    send,
    subscribe,
    unsubscribe,
    clearEvents,
    reconnect,
  };
}

export default useWebSocket;
