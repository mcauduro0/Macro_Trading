/**
 * hooks.jsx - Reusable data-fetching hooks for the Macro Trading Dashboard.
 *
 * useFetch:     Polls a REST endpoint at a configurable interval (default 30s).
 * useWebSocket: Connects to a WebSocket URL with exponential backoff reconnection.
 */

const { useState, useEffect, useRef, useCallback } = React;

// ---------------------------------------------------------------------------
// useFetch — periodic REST polling
// ---------------------------------------------------------------------------
function useFetch(url, intervalMs = 30000) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    // Fetch immediately on mount
    setLoading(true);
    fetchData();

    // Set up polling interval
    const interval = setInterval(fetchData, intervalMs);

    return () => clearInterval(interval);
  }, [fetchData, intervalMs]);

  return { data, loading, error, refetch: fetchData };
}

// ---------------------------------------------------------------------------
// useWebSocket — auto-reconnect with exponential backoff
// ---------------------------------------------------------------------------
function useWebSocket(path) {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const wsRef = useRef(null);
  const retriesRef = useRef(0);
  const timerRef = useRef(null);
  const unmountedRef = useRef(false);

  const BACKOFF_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000];

  const getBackoffDelay = useCallback(() => {
    const idx = Math.min(retriesRef.current, BACKOFF_DELAYS.length - 1);
    return BACKOFF_DELAYS[idx];
  }, []);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    // Build full ws:// URL from current location
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = protocol + "//" + window.location.host + path;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (unmountedRef.current) { ws.close(); return; }
        setConnected(true);
        retriesRef.current = 0;
      };

      ws.onmessage = (event) => {
        if (unmountedRef.current) return;
        try {
          setLastMessage(JSON.parse(event.data));
        } catch (_) {
          setLastMessage(event.data);
        }
      };

      ws.onclose = () => {
        if (unmountedRef.current) return;
        setConnected(false);
        // Schedule reconnect with exponential backoff
        const delay = getBackoffDelay();
        retriesRef.current += 1;
        timerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        // onclose will fire after onerror, so reconnection is handled there
        ws.close();
      };

      wsRef.current = ws;
    } catch (_) {
      // Connection creation failed, schedule retry
      const delay = getBackoffDelay();
      retriesRef.current += 1;
      timerRef.current = setTimeout(connect, delay);
    }
  }, [path, getBackoffDelay]);

  const send = useCallback((msg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  }, []);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { connected, lastMessage, send };
}

// Expose on window for CDN/Babel compatibility
window.useFetch = useFetch;
window.useWebSocket = useWebSocket;
