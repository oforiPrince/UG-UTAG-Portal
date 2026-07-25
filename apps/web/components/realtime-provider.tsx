"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";

type ConnectionState = "connecting" | "live" | "offline";
type RealtimeContextValue = { state: ConnectionState; lastEventAt: Date | null };

export function realtimeUrl(
  location: Pick<Location, "host" | "hostname" | "port" | "protocol">,
  configured?: string,
) {
  const explicit = configured?.trim();
  if (explicit) return explicit;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const host = location.port === "3000" ? `${location.hostname}:8000` : location.host;
  return `${protocol}://${host}/api/v1/realtime`;
}

const RealtimeContext = createContext<RealtimeContextValue>({
  state: "offline",
  lastEventAt: null,
});

const topicKeys: Record<string, string[]> = {
  members: ["members", "dashboard", "analytics"],
  organization: ["organization", "members"],
  content: ["content", "dashboard"],
  events: ["events", "dashboard"],
  documents: ["documents", "dashboard"],
  announcements: ["notifications", "dashboard"],
  media: ["media"],
  adverts: ["adverts"],
  settings: ["settings", "public-home"],
  executives: ["executives", "public-home"],
  galleries: ["galleries", "public-home"],
};

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const pathname = usePathname();
  const [state, setState] = useState<ConnectionState>("offline");
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!pathname.startsWith("/dashboard")) return;
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      setState("connecting");
      const url = realtimeUrl(window.location, process.env.NEXT_PUBLIC_WS_URL);
      socket = new WebSocket(url, "utag.v1");
      socket.onopen = () => {
        retryRef.current = 0;
        setState("live");
      };
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as { type?: string; topic?: string };
        if (event.type === "heartbeat") {
          socket?.send(JSON.stringify({ type: "ping" }));
          return;
        }
        if (event.type === "connection.ready") {
          queryClient.invalidateQueries();
          socket?.send(JSON.stringify({ type: "resync.complete" }));
          return;
        }
        setLastEventAt(new Date());
        const topic = event.topic ?? "";
        const baseTopic = topic.startsWith("user:")
          ? "notifications"
          : topic.startsWith("conversation:")
            ? "chat"
            : topic;
        for (const key of topicKeys[baseTopic] ?? [baseTopic]) {
          queryClient.invalidateQueries({ queryKey: [key] });
        }
      };
      socket.onclose = () => {
        setState("offline");
        if (closed) return;
        retryRef.current += 1;
        const delay = Math.min(30_000, 1_000 * 2 ** retryRef.current) + Math.random() * 750;
        retryTimer = setTimeout(connect, delay);
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close();
    };
  }, [pathname, queryClient]);

  const value = useMemo(() => ({ state, lastEventAt }), [state, lastEventAt]);
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export function useRealtime() {
  return useContext(RealtimeContext);
}
