import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, MapPin, Loader2, ArrowRight, Search } from "lucide-react";

import { getMyRuns, type MyRun } from "../lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  onOpenRun: (run: MyRun) => void;
}

const fmtMoney = (n: number | null) =>
  n == null ? "—" : `$${Math.round(n).toLocaleString()}`;

const fmtNum = (n: number | null) =>
  n == null ? "—" : n.toLocaleString();

const fmtRelative = (iso: string) => {
  const ms  = Date.now() - new Date(iso).getTime();
  const s   = Math.floor(ms / 1000);
  const m   = Math.floor(s / 60);
  const h   = Math.floor(m / 60);
  const d   = Math.floor(h / 24);
  if (s < 60)  return `${s}s ago`;
  if (m < 60)  return `${m}m ago`;
  if (h < 24)  return `${h}h ago`;
  if (d < 30)  return `${d}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
};

export function HistoryPanel({ open, onClose, onOpenRun }: Props) {
  const [runs, setRuns]       = useState<MyRun[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [query, setQuery]     = useState("");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMyRuns()
      .then((rows) => { if (!cancelled) setRuns(rows); })
      .catch((e)   => { if (!cancelled) setError(e?.message ?? "Failed to load"); })
      .finally(()  => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const filtered = (runs ?? []).filter((r) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return (
      (r.label ?? "").toLowerCase().includes(q) ||
      (r.store_format ?? "").toLowerCase().includes(q) ||
      `${r.lat.toFixed(3)}, ${r.lon.toFixed(3)}`.includes(q)
    );
  });

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="history-overlay"
          className="fixed inset-0 z-[1800] flex justify-end"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <motion.div
            className="absolute inset-0 bg-ink/30 backdrop-blur-[2px]"
            onClick={onClose}
          />

          <motion.aside
            className="relative w-full max-w-[480px] h-full bg-snow border-l border-hairline
                       shadow-[-30px_0_60px_-20px_rgba(10,10,10,0.2)] flex flex-col"
            initial={{ x: 40 }}
            animate={{ x: 0 }}
            exit={{ x: 40 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Header */}
            <header className="px-6 py-5 border-b border-hairline flex items-start justify-between gap-4">
              <div>
                <div className="label-xs text-emerald mb-1.5">YOUR HISTORY</div>
                <h2 className="font-display text-3xl tracking-tightest leading-none">
                  Past <em className="italic">searches</em>
                </h2>
                <p className="text-xs text-slate mt-2">
                  Every location you've analyzed, ready to re-open.
                </p>
              </div>
              <button
                onClick={onClose}
                className="h-8 w-8 flex items-center justify-center text-slate hover:text-ink"
                aria-label="Close"
              >
                <X className="w-4 h-4" strokeWidth={1.5} />
              </button>
            </header>

            {/* Search bar */}
            <div className="px-6 py-3 border-b border-hairline flex items-center gap-2">
              <Search className="w-3.5 h-3.5 text-slate" strokeWidth={1.5} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter by format, label, or coords"
                className="flex-1 bg-transparent outline-none text-sm placeholder:text-mist"
              />
              {runs && (
                <span className="font-mono text-[10px] text-slate tabular">
                  {filtered.length} / {runs.length}
                </span>
              )}
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto">
              {loading && (
                <div className="px-6 py-10 flex items-center gap-3 text-sm text-slate">
                  <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />
                  Loading your runs…
                </div>
              )}

              {error && !loading && (
                <div className="px-6 py-10 text-sm text-crimson">{error}</div>
              )}

              {!loading && !error && runs && runs.length === 0 && (
                <EmptyState />
              )}

              {!loading && !error && filtered.length === 0 && runs && runs.length > 0 && (
                <div className="px-6 py-10 text-center text-sm text-slate">
                  Nothing matches “{query}”.
                </div>
              )}

              {!loading && !error && filtered.length > 0 && (
                <ul className="divide-y divide-hairline">
                  {filtered.map((r) => (
                    <li key={r.id}>
                      <button
                        onClick={() => onOpenRun(r)}
                        className="group w-full text-left px-6 py-4 hover:bg-bone transition-colors"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <MapPin className="w-3 h-3 text-emerald" strokeWidth={1.8} />
                              <span className="font-mono text-[11px] tabular text-ink">
                                {r.lat.toFixed(4)}, {r.lon.toFixed(4)}
                              </span>
                              <span className="text-mist">·</span>
                              <span className="font-mono text-[11px] tabular text-graphite">
                                {r.radius_km} km
                              </span>
                            </div>

                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-sm font-medium text-ink">
                                {r.label ?? r.store_format ?? "Untitled run"}
                              </span>
                              {r.store_format && r.label && (
                                <span className="label-xs text-slate">{r.store_format}</span>
                              )}
                            </div>

                            <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate tabular">
                              <span>{fmtNum(r.summary.total_population)} pop</span>
                              <span>·</span>
                              <span>{fmtNum(r.summary.total_households)} HH</span>
                              <span>·</span>
                              <span>{fmtMoney(r.summary.median_hh_income)} median</span>
                              <span>·</span>
                              <span>{r.summary.competitors_count} rivals</span>
                            </div>
                          </div>

                          <div className="flex flex-col items-end gap-2">
                            <span className="font-mono text-[10px] text-slate">
                              {fmtRelative(r.created_at)}
                            </span>
                            <ArrowRight
                              className="w-3.5 h-3.5 text-mist group-hover:text-ink group-hover:translate-x-0.5 transition-all"
                              strokeWidth={1.5}
                            />
                          </div>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function EmptyState() {
  return (
    <div className="px-6 py-12 text-center">
      <div className="mx-auto h-12 w-12 mb-4 border border-hairline flex items-center justify-center">
        <MapPin className="w-5 h-5 text-mist" strokeWidth={1.5} />
      </div>
      <h3 className="font-display text-2xl tracking-tightest mb-2">
        No <em className="italic">searches yet</em>
      </h3>
      <p className="text-xs text-slate max-w-[280px] mx-auto leading-relaxed">
        Drop a pin or run an Auto-Scout from the home screen — it'll show up here automatically.
      </p>
    </div>
  );
}
