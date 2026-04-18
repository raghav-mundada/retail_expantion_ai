"use client";
import { useEffect, useRef } from "react";
import type { TraceEvent } from "@/lib/api";

interface AgentTraceProps {
  events: TraceEvent[];
  isRunning: boolean;
}

const AGENT_COLORS: Record<string, string> = {
  orchestrator: "#00d4ff",
  demographics: "#60a5fa",
  competitor: "#f87171",
  schools: "#34d399",
  simulation: "#a78bfa",
  brand_fit: "#fcd34d",
};

function formatTime(): string {
  return new Date().toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function AgentTrace({ events, isRunning }: AgentTraceProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [events]);

  if (events.length === 0 && !isRunning) {
    return (
      <div
        className="trace-container"
        style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
      >
        <span style={{ color: "#3d5a73", fontSize: 11 }}>
          Awaiting analysis...{" "}
          <span className="trace-cursor" />
        </span>
      </div>
    );
  }

  return (
    <div className="trace-container" ref={containerRef}>
      <div style={{ color: "#3d5a73", marginBottom: 8, fontSize: 10, letterSpacing: "0.05em" }}>
        ── RETAILIQ AGENT TRACE ──────────────────────────────────
      </div>
      {events.map((event, i) => (
        <div key={i} className="trace-event">
          <span className="trace-timestamp">{formatTime()}</span>
          <span
            className={`trace-agent ${event.agent}`}
            style={{ color: AGENT_COLORS[event.agent] || "#7a9ab8" }}
          >
            [{event.agent.toUpperCase()}]
          </span>
          <span
            className={`trace-msg trace-status-${event.status}`}
            style={{
              color:
                event.status === "done" || event.status === "complete"
                  ? "#10b981"
                  : event.status === "error"
                  ? "#ef4444"
                  : "#7a9ab8",
            }}
          >
            {event.message}
          </span>
        </div>
      ))}
      {isRunning && (
        <div className="trace-event">
          <span className="trace-timestamp">{formatTime()}</span>
          <span className="trace-agent orchestrator" style={{ color: "#00d4ff" }}>
            [SYSTEM]
          </span>
          <span className="trace-msg" style={{ color: "#3d5a73" }}>
            Processing<span className="trace-cursor" />
          </span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
