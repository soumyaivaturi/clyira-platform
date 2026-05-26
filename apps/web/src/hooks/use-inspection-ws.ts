"use client";

import { useEffect, useRef, useCallback } from "react";

export type WsEvent =
  | { type: "presence"; inspection_id: string; connected: number }
  | { type: "request_update"; inspection_id: string; request_id: string; status: string; fulfillment_progress: number }
  | { type: "scribe_note"; inspection_id: string; content: string; entry_type: string; author: string; timestamp: string }
  | { type: "sla_alert"; inspection_id: string; request_id: string; request_text: string; criticality: string }
  | { type: "chat_message"; id: string; inspection_id: string; sender_id: string; sender_name: string; content: string; room: string; message_type: string; linked_request_id: string | null; linked_commitment_id: string | null; converted_to_request_id: string | null; created_at: string }
  | { type: "request_created"; inspection_id: string; request_id: string; from_chat: boolean }
  | { type: "potential_finding_added"; id: string; inspection_id: string; [key: string]: unknown }
  | { type: "potential_finding_updated"; id: string; inspection_id: string; [key: string]: unknown }
  | { type: "ai_scan_complete"; inspection_id: string; count: number }
  | { type: "sme_update"; sme_id: string; name: string; availability?: string; qa_cleared?: boolean }
  | { type: "package_qa_pending"; package_id: string; title: string }
  | { type: "package_status_update"; package_id: string; status: string; title: string }
  | { type: "pong" };

type Handler = (event: WsEvent) => void;

export function useInspectionWs(inspectionId: string, onEvent: Handler) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  const connect = useCallback(() => {
    if (!mounted.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";
    const wsUrl = apiBase
      ? `${apiBase.replace(/^https?/, proto)}/api/v1/inspections/${inspectionId}/ws`
      : `${proto}://${window.location.host}/api/v1/inspections/${inspectionId}/ws`;

    const token = localStorage.getItem("clyira_token");

    try {
      const ws = new WebSocket(`${wsUrl}${token ? `?token=${token}` : ""}`);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as WsEvent;
          onEvent(data);
        } catch { /* ignore malformed */ }
      };

      ws.onclose = () => {
        if (!mounted.current) return;
        // Exponential-ish backoff: reconnect after 3s
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch { /* WebSocket not available in SSR */ }
  }, [inspectionId, onEvent]);

  useEffect(() => {
    mounted.current = true;
    connect();
    // Heartbeat ping every 25s to keep connection alive through proxies
    const heartbeat = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 25000);

    return () => {
      mounted.current = false;
      clearInterval(heartbeat);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { send };
}
