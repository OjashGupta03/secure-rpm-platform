import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "../api/client";

export interface RealtimeEvent {
  event: string;
  data: Record<string, unknown>;
  receivedAt: number;
}

/**
 * Server-Sent Events client for the Realtime Gateway (Section 14A, ADR-002).
 * One connection per authenticated session; the browser sends the session cookie
 * automatically since EventSource requests are same-origin/credentialed by default
 * when withCredentials is set.
 */
export function useRealtime(enabled: boolean) {
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const source = new EventSource(`${API_BASE_URL}/realtime/stream`, { withCredentials: true });
    sourceRef.current = source;

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    const handlers: Record<string, (ev: MessageEvent) => void> = {};
    for (const eventName of ["new_alert", "quantum_rescore_available", "scope_revoked"]) {
      const handler = (ev: MessageEvent) => {
        const data = JSON.parse(ev.data);
        setEvents((prev) => [{ event: eventName, data, receivedAt: Date.now() }, ...prev].slice(0, 50));
      };
      handlers[eventName] = handler;
      source.addEventListener(eventName, handler);
    }

    return () => {
      for (const [eventName, handler] of Object.entries(handlers)) {
        source.removeEventListener(eventName, handler);
      }
      source.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [enabled]);

  return { events, connected };
}
