import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * useWebSocket — Custom hook for WebSocket connection management.
 *
 * Features:
 *  - Auto-reconnect with exponential backoff
 *  - Parsed JSON data state
 *  - Command sending
 *  - Connection status tracking
 */
export default function useWebSocket(url) {
    const [data, setData] = useState(null);
    const [connected, setConnected] = useState(false);
    const wsRef = useRef(null);
    const reconnectTimer = useRef(null);
    const reconnectAttempts = useRef(0);
    const maxReconnectDelay = 10000;

    const connect = useCallback(() => {
        try {
            const ws = new WebSocket(url);

            ws.onopen = () => {
                setConnected(true);
                reconnectAttempts.current = 0;
            };

            ws.onmessage = (event) => {
                try {
                    const parsed = JSON.parse(event.data);
                    setData(parsed);
                } catch {
                    // Ignore non-JSON messages
                }
            };

            ws.onclose = () => {
                setConnected(false);
                scheduleReconnect();
            };

            ws.onerror = () => {
                ws.close();
            };

            wsRef.current = ws;
        } catch {
            scheduleReconnect();
        }
    }, [url]);

    const scheduleReconnect = useCallback(() => {
        if (reconnectTimer.current) return;
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), maxReconnectDelay);
        reconnectAttempts.current += 1;
        reconnectTimer.current = setTimeout(() => {
            reconnectTimer.current = null;
            connect();
        }, delay);
    }, [connect]);

    const sendCommand = useCallback((cmd) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(cmd));
        }
    }, []);

    useEffect(() => {
        connect();
        return () => {
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            if (wsRef.current) wsRef.current.close();
        };
    }, [connect]);

    return { data, connected, sendCommand };
}
