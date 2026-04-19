"use client";
import { useEffect, useState } from "react";
import { fetchHistory, HistoryEntry } from "@/lib/api";

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 75 ? "#22c55e" : score >= 55 ? "#f59e0b" : "#ef4444";
  const label =
    score >= 75 ? "Strong" : score >= 55 ? "Good" : "Low";
  return (
    <span
      style={{
        background: `${color}22`,
        color,
        border: `1px solid ${color}44`,
        borderRadius: 6,
        padding: "2px 8px",
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: "0.02em",
        whiteSpace: "nowrap",
      }}
    >
      {score?.toFixed(0)}/100 · {label}
    </span>
  );
}

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function HistoryPanel({
  onReplay,
}: {
  onReplay?: (entry: HistoryEntry) => void;
}) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchHistory(20)
      .then((data) => {
        setEntries(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Could not load history");
        setLoading(false);
      });
  }, []);

  return (
    <div
      style={{
        background: "rgba(15,17,27,0.95)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 16,
        padding: "24px 20px",
        marginTop: 24,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <div
          style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 15,
          }}
        >
          🕘
        </div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#fff", letterSpacing: "0.01em" }}>
            Analysis History
          </div>
          <div style={{ fontSize: 11, color: "#6b7280" }}>
            {loading ? "Loading..." : `${entries.length} saved analyses`}
          </div>
        </div>
        <button
          onClick={() => {
            setLoading(true);
            fetchHistory(20).then((d) => { setEntries(d); setLoading(false); });
          }}
          style={{
            marginLeft: "auto",
            background: "rgba(99,102,241,0.12)",
            border: "1px solid rgba(99,102,241,0.25)",
            borderRadius: 8,
            color: "#818cf8",
            fontSize: 11,
            padding: "4px 12px",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          Refresh
        </button>
      </div>

      {/* States */}
      {loading && (
        <div style={{ textAlign: "center", color: "#4b5563", padding: "32px 0", fontSize: 13 }}>
          <div style={{ marginBottom: 8, fontSize: 22 }}>⏳</div>
          Loading history from Supabase...
        </div>
      )}

      {error && (
        <div
          style={{
            background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 10, padding: "12px 16px", color: "#f87171", fontSize: 13,
          }}
        >
          ⚠️ {error} — check Supabase connection.
        </div>
      )}

      {!loading && !error && entries.length === 0 && (
        <div style={{ textAlign: "center", color: "#4b5563", padding: "32px 0", fontSize: 13 }}>
          <div style={{ marginBottom: 8, fontSize: 28 }}>📭</div>
          No analyses saved yet.
          <br />
          <span style={{ fontSize: 11, color: "#374151", marginTop: 6, display: "block" }}>
            Run an analysis and it will appear here automatically.
          </span>
        </div>
      )}

      {/* List */}
      {!loading && entries.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {entries.map((e) => (
            <div
              key={e.id}
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.06)",
                borderRadius: 12,
                padding: "12px 14px",
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: "6px 12px",
                cursor: onReplay ? "pointer" : "default",
                transition: "background 0.15s",
              }}
              onMouseEnter={(ev) =>
                ((ev.currentTarget as HTMLDivElement).style.background =
                  "rgba(99,102,241,0.07)")
              }
              onMouseLeave={(ev) =>
                ((ev.currentTarget as HTMLDivElement).style.background =
                  "rgba(255,255,255,0.03)")
              }
              onClick={() => onReplay?.(e)}
            >
              {/* Left col */}
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: "#e5e7eb" }}>
                    {e.retailer_name || "Unknown"}
                  </span>
                  <ScoreBadge score={e.overall_score} />
                </div>
                <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 3 }}>
                  📍 {e.address || `${e.lat?.toFixed(3)}, ${e.lng?.toFixed(3)}`}
                  {e.region_city ? ` · ${e.region_city}` : ""}
                </div>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                  {e.population != null && (
                    <span style={{ fontSize: 10, color: "#4b5563" }}>
                      👥 {(e.population / 1000).toFixed(0)}k pop
                    </span>
                  )}
                  {e.median_income != null && (
                    <span style={{ fontSize: 10, color: "#4b5563" }}>
                      💰 ${(e.median_income / 1000).toFixed(0)}k income
                    </span>
                  )}
                  {e.competitor_count != null && (
                    <span style={{ fontSize: 10, color: "#4b5563" }}>
                      🏪 {e.competitor_count} competitors
                    </span>
                  )}
                  {e.hotspot_score != null && (
                    <span style={{ fontSize: 10, color: "#4b5563" }}>
                      🔥 hotspot {e.hotspot_score?.toFixed(0)}
                    </span>
                  )}
                </div>
              </div>

              {/* Right col */}
              <div style={{ textAlign: "right", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <div style={{ fontSize: 10, color: "#374151", marginBottom: 4 }}>
                  {timeAgo(e.created_at)}
                </div>
                {onReplay && (
                  <span
                    style={{
                      fontSize: 10, color: "#818cf8", fontWeight: 600,
                      background: "rgba(99,102,241,0.1)", borderRadius: 5,
                      padding: "2px 7px", border: "1px solid rgba(99,102,241,0.2)",
                    }}
                  >
                    Replay ↗
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
