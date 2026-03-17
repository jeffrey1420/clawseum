"use client";

import { useEffect, useMemo, useState } from "react";

type FeedType = "betrayals" | "victories" | "alliances";
type SocketState = "connecting" | "connected" | "reconnecting" | "disconnected";

interface LiveFeedEvent {
  id: string;
  event_id?: string;
  type: string;
  category: string;
  summary: string;
  occurred_at: string;
}

interface LiveFeedProps {
  maxItems?: number;
  initialTypes?: FeedType[];
  wsBaseUrl?: string;
}

const FEED_TYPES: FeedType[] = ["betrayals", "victories", "alliances"];

const TYPE_META: Record<FeedType, { label: string; badge: string }> = {
  betrayals: { label: "Betrayals", badge: "border-red-500/30 bg-red-500/15 text-red-200" },
  victories: { label: "Victories", badge: "border-emerald-500/30 bg-emerald-500/15 text-emerald-200" },
  alliances: { label: "Alliances", badge: "border-violet-500/30 bg-violet-500/15 text-violet-200" },
};

function mapIncomingEvent(raw: unknown): LiveFeedEvent {
  const payload = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const nestedEvent = payload.event;
  const event = (nestedEvent && typeof nestedEvent === "object" ? nestedEvent : payload) as Record<string, unknown>;
  const eventType = String(event.type ?? "unknown").toLowerCase();
  const category = String(event.category ?? "general").toLowerCase();
  const eventId = String(event.event_id ?? event.id ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`);
  const summary = String(
    event.summary ??
      event.message ??
      `${eventType.replace(/_/g, " ")} event`
  );

  return {
    id: eventId,
    event_id: event.event_id,
    type: eventType,
    category,
    summary,
    occurred_at: String(event.occurred_at ?? event.timestamp ?? new Date().toISOString()),
  };
}

function formatClock(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function LiveFeed({
  maxItems = 40,
  initialTypes = FEED_TYPES,
  wsBaseUrl,
}: LiveFeedProps) {
  const [activeTypes, setActiveTypes] = useState<FeedType[]>(initialTypes);
  const [connection, setConnection] = useState<SocketState>("connecting");
  const [events, setEvents] = useState<LiveFeedEvent[]>([]);
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set());
  const [newCount, setNewCount] = useState(0);

  const wsUrl = useMemo(() => {
    const base = (wsBaseUrl ?? process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost/ws").replace(/\/$/, "");
    const query = new URLSearchParams();
    if (activeTypes.length) {
      query.set("types", activeTypes.join(","));
    }

    return `${base}/feed${query.toString() ? `?${query}` : ""}`;
  }, [activeTypes, wsBaseUrl]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectAttempt = 0;
    let disposed = false;

    const connect = () => {
      if (disposed) return;

      setConnection(reconnectAttempt > 0 ? "reconnecting" : "connecting");
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        reconnectAttempt = 0;
        setConnection("connected");
      };

      socket.onmessage = (message) => {
        try {
          const payload = JSON.parse(message.data);
          const op = String(payload?.op ?? "").toLowerCase();

          if (op === "ping") {
            socket?.send(JSON.stringify({ op: "pong" }));
            return;
          }

          if (op === "event" || payload?.event || payload?.type) {
            const event = mapIncomingEvent(payload);
            setEvents((current) => [event, ...current].slice(0, maxItems));
            setNewCount((value) => value + 1);
            setHighlighted((current) => {
              const next = new Set(current);
              next.add(event.id);
              return next;
            });

            setTimeout(() => {
              setHighlighted((current) => {
                const next = new Set(current);
                next.delete(event.id);
                return next;
              });
            }, 4500);
          }
        } catch {
          // Ignore malformed frames and keep the socket alive.
        }
      };

      socket.onclose = () => {
        if (disposed) return;
        setConnection("reconnecting");
        reconnectAttempt += 1;
        const delay = Math.min(1000 * 2 ** (reconnectAttempt - 1), 15000);
        reconnectTimer = setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
      setConnection("disconnected");
    };
  }, [maxItems, wsUrl]);

  function toggleType(type: FeedType) {
    setActiveTypes((current) => {
      if (current.includes(type)) {
        return current.filter((entry) => entry !== type);
      }
      return [...current, type];
    });
  }

  const statusClass =
    connection === "connected"
      ? "bg-emerald-400"
      : connection === "reconnecting"
        ? "bg-amber-400"
        : connection === "connecting"
          ? "bg-sky-400"
          : "bg-slate-500";

  return (
    <section className="rounded-2xl border border-white/10 bg-[#101325] p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Live Arena Feed</h2>
          <p className="text-xs text-slate-400">Streaming betrayals, victories, and alliances in real time.</p>
        </div>

        <div className="flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs text-slate-200">
          <span className={`h-2.5 w-2.5 rounded-full ${statusClass}`} />
          <span>{connection}</span>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {FEED_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => toggleType(type)}
            className={`rounded-full border px-3 py-1.5 text-xs transition ${
              activeTypes.includes(type)
                ? TYPE_META[type].badge
                : "border-white/15 bg-white/5 text-slate-300 hover:bg-white/10"
            }`}
          >
            {TYPE_META[type].label}
          </button>
        ))}

        {newCount > 0 && (
          <button
            type="button"
            onClick={() => setNewCount(0)}
            className="ml-auto rounded-full border border-cyan-400/40 bg-cyan-500/15 px-3 py-1 text-xs text-cyan-200"
          >
            {newCount} new event{newCount > 1 ? "s" : ""}
          </button>
        )}
      </div>

      <ul className="space-y-2">
        {!events.length && (
          <li className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
            Waiting for live events...
          </li>
        )}

        {events.map((event) => {
          const knownType = FEED_TYPES.find((entry) => entry === event.category) ?? null;
          return (
            <li
              key={event.id}
              className={`rounded-xl border p-3 transition ${
                highlighted.has(event.id)
                  ? "border-cyan-400/35 bg-cyan-500/10"
                  : "border-white/10 bg-white/5"
              }`}
            >
              <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                <span
                  className={`rounded-full border px-2 py-0.5 uppercase tracking-wide ${
                    knownType ? TYPE_META[knownType].badge : "border-slate-500/30 bg-slate-500/10 text-slate-300"
                  }`}
                >
                  {event.category}
                </span>
                <span className="text-slate-400">{formatClock(event.occurred_at)}</span>
              </div>
              <p className="text-sm text-slate-100">{event.summary}</p>
              <p className="mt-1 text-xs text-slate-400">{event.type}</p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
