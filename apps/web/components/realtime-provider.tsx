"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

type ConnectionState = "connecting" | "live" | "offline";
type RealtimeContextValue = {
  state: ConnectionState;
  lastEventAt: Date | null;
  refreshSubscriptions: () => void;
};

export function realtimeUrl(
  location: Pick<Location, "host" | "hostname" | "port" | "protocol">,
  configured?: string,
) {
  const explicit = configured?.trim();
  if (explicit) return explicit;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const host =
    location.port === "3000" ? `${location.hostname}:8000` : location.host;
  return `${protocol}://${host}/api/v1/realtime`;
}

const RealtimeContext = createContext<RealtimeContextValue>({
  state: "offline",
  lastEventAt: null,
  refreshSubscriptions: () => {},
});

const topicKeys: Record<string, string[]> = {
  members: ["members", "dashboard", "analytics"],
  organization: ["organization", "members"],
  content: ["content", "dashboard"],
  events: ["events", "dashboard"],
  documents: ["documents", "dashboard"],
  announcements: ["notifications", "dashboard"],
  media: ["media"],
  moderation: ["moderation"],
  adverts: ["adverts"],
  settings: ["settings", "public-home"],
  executives: ["executives", "public-home"],
  galleries: ["galleries", "public-home"],
  notifications: ["notifications", "dashboard"],
  polls: ["polls", "dashboard"],
};

export function realtimeInvalidationKeys(event: {
  type?: string;
  topic?: string;
}) {
  const topic = event.topic ?? "";
  const baseTopic = topic.startsWith("user:")
    ? "notifications"
    : topic.startsWith("conversation:")
      ? "chat"
      : topic.startsWith("poll:") || topic === "polls:management"
        ? "polls"
        : topic;
  const keys = topicKeys[baseTopic] ?? (baseTopic ? [baseTopic] : []);
  return event.type?.startsWith("poll.")
    ? Array.from(new Set([...keys, "polls", "dashboard"]))
    : keys;
}

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const pathname = usePathname();
  const [state, setState] = useState<ConnectionState>("offline");
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);
  const retryRef = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);
  const refreshSubscriptions = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: "subscriptions.refresh" }));
    }
  }, []);

  useEffect(() => {
    if (!pathname.startsWith("/dashboard")) return;
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;
    let invalidationTimer: ReturnType<typeof setTimeout> | null = null;
    const pendingKeys = new Set<string>();

    const connect = () => {
      setState("connecting");
      const url = realtimeUrl(window.location, process.env.NEXT_PUBLIC_WS_URL);
      socket = new WebSocket(url, "utag.v1");
      socketRef.current = socket;
      socket.onopen = () => {
        retryRef.current = 0;
        setState("live");
      };
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as {
          type?: string;
          topic?: string;
        };
        if (event.type === "heartbeat") {
          socket?.send(JSON.stringify({ type: "ping" }));
          return;
        }
        if (
          event.type === "connection.ready" ||
          event.type === "subscriptions.changed"
        ) {
          if (event.type === "connection.ready") {
            retryRef.current = 0;
            setState("live");
          }
          queryClient.invalidateQueries();
          if (event.type === "connection.ready") {
            socket?.send(JSON.stringify({ type: "resync.complete" }));
          }
          return;
        }
        setLastEventAt(new Date());
        const keys = realtimeInvalidationKeys(event);
        if (keys.includes("polls")) {
          // Batch bursts of votes without postponing updates indefinitely.
          keys.forEach((key) => pendingKeys.add(key));
          invalidationTimer ??= setTimeout(() => {
            pendingKeys.forEach((key) => {
              void queryClient.invalidateQueries({ queryKey: [key] });
            });
            pendingKeys.clear();
            invalidationTimer = null;
          }, 250);
        } else {
          keys.forEach((key) => {
            void queryClient.invalidateQueries({ queryKey: [key] });
          });
        }
      };
      socket.onclose = () => {
        setState("offline");
        if (closed) return;
        retryRef.current += 1;
        const delay =
          Math.min(30_000, 1_000 * 2 ** retryRef.current) + Math.random() * 750;
        retryTimer = setTimeout(connect, delay);
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (invalidationTimer) clearTimeout(invalidationTimer);
      socket?.close();
      socketRef.current = null;
    };
  }, [pathname, queryClient]);

  const value = useMemo(
    () => ({ state, lastEventAt, refreshSubscriptions }),
    [state, lastEventAt, refreshSubscriptions],
  );
  return (
    <RealtimeContext.Provider value={value}>
      {children}
    </RealtimeContext.Provider>
  );
}

export function useRealtime() {
  return useContext(RealtimeContext);
}
