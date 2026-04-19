import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check } from "lucide-react";
import { fmtCoord } from "../lib/format";

interface ApiRow {
  id: string;
  source: string;
  caption: string;
  status: "pending" | "loading" | "done";
}

const ROWS: ApiRow[] = [
  { id: "census",      source: "U.S. Census ACS 5-Year",    caption: "Asking the census what your customers earn…",         status: "pending" },
  { id: "competitors", source: "Geoapify Places",            caption: "Interrogating nearby competitors…",                  status: "pending" },
  { id: "parcels",     source: "Minneapolis Open Data",      caption: "Triangulating the perfect corner lot…",              status: "pending" },
  { id: "schools",     source: "Geoapify Education",         caption: "Counting schools, sniffing out daytime footfall…",   status: "pending" },
  { id: "traffic",     source: "MnDOT AADT 2023",            caption: "Reverse-engineering foot traffic patterns…",         status: "pending" },
  { id: "neighborhoods", source: "City of Minneapolis GIS",  caption: "Convincing the city to share its block list…",       status: "pending" },
];

interface Props {
  lat: number;
  lon: number;
  radius_km: number;
  onComplete: () => void;
  fetchPromise: Promise<unknown>;
}

export function LoadingScreen({ lat, lon, radius_km, onComplete, fetchPromise }: Props) {
  const [rows, setRows] = useState<ApiRow[]>(ROWS);
  const [done, setDone] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Simulate per-row progression while real fetch runs in background.
  // Each row "finishes" after a staggered delay; final row waits for the actual
  // fetch promise to resolve before flipping to done.
  useEffect(() => {
    const start = performance.now();
    const tick = setInterval(() => setElapsed(performance.now() - start), 80);

    const startTimers = ROWS.map((row, i) =>
      setTimeout(() => {
        setRows((rs) =>
          rs.map((r) => (r.id === row.id ? { ...r, status: "loading" } : r))
        );
      }, 250 + i * 350)
    );

    const finishTimers = ROWS.slice(0, -1).map((row, i) =>
      setTimeout(() => {
        setRows((rs) =>
          rs.map((r) => (r.id === row.id ? { ...r, status: "done" } : r))
        );
      }, 1500 + i * 800)
    );

    fetchPromise
      .then(() => {
        setRows((rs) => rs.map((r) => ({ ...r, status: "done" as const })));
        setTimeout(() => setDone(true), 700);
      })
      .catch((e: Error) => {
        setError(e.message || "Fetch failed");
      });

    return () => {
      clearInterval(tick);
      startTimers.forEach(clearTimeout);
      finishTimers.forEach(clearTimeout);
    };
  }, [fetchPromise]);

  useEffect(() => {
    if (done) {
      const t = setTimeout(onComplete, 900);
      return () => clearTimeout(t);
    }
  }, [done, onComplete]);

  const progress = rows.filter((r) => r.status === "done").length / rows.length;

  return (
    <div className="relative h-[calc(100vh-4rem)] w-full bg-paper overflow-hidden">
      {/* Faint grid background */}
      <div
        className="absolute inset-0 opacity-[0.035]"
        style={{
          backgroundImage:
            "linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      <div className="relative h-full max-w-6xl mx-auto px-8 lg:px-12 grid grid-cols-12 gap-10 items-center">
        {/* LEFT — hero copy */}
        <div className="col-span-12 lg:col-span-5">
          <div className="label-xs mb-6">CHAPTER TWO — INGESTION</div>
          <h1 className="display-lg mb-6">
            We're <em className="italic">canvassing</em> your <br/> radius now.
          </h1>
          <p className="text-graphite text-base leading-relaxed mb-8 max-w-md">
            Six independent data systems. One million data points. Fetched in
            parallel, normalized in real time, persisted for the agents.
          </p>

          {/* Coords block */}
          <div className="hairline-t pt-6 grid grid-cols-3 gap-6 max-w-md">
            <div>
              <div className="label-xs mb-2">LAT</div>
              <div className="font-mono text-sm tabular">{fmtCoord(lat)}</div>
            </div>
            <div>
              <div className="label-xs mb-2">LON</div>
              <div className="font-mono text-sm tabular">{fmtCoord(lon)}</div>
            </div>
            <div>
              <div className="label-xs mb-2">RADIUS</div>
              <div className="font-mono text-sm tabular">{radius_km.toFixed(1)} km</div>
            </div>
          </div>
        </div>

        {/* RIGHT — API rows + giant timer */}
        <div className="col-span-12 lg:col-span-7">
          {/* Timer hero */}
          <div className="flex items-end justify-between mb-8 hairline-b pb-6">
            <div>
              <div className="label-xs mb-2">ELAPSED</div>
              <div className="font-display text-6xl tabular leading-none">
                {(elapsed / 1000).toFixed(2)}
                <span className="text-2xl text-mist ml-1">s</span>
              </div>
            </div>
            <div className="text-right">
              <div className="label-xs mb-2">PROGRESS</div>
              <div className="font-display text-6xl tabular leading-none text-emerald">
                {Math.round(progress * 100)}
                <span className="text-2xl text-mist ml-0.5">%</span>
              </div>
            </div>
          </div>

          {/* API rows */}
          <div className="space-y-0">
            {rows.map((r, i) => (
              <ApiRowDisplay key={r.id} row={r} index={i + 1} />
            ))}
          </div>

          {/* Done banner */}
          <AnimatePresence>
            {done && !error && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-8 hairline border-emerald p-5 flex items-center justify-between bg-emerald/[0.04]"
              >
                <div>
                  <div className="label-xs text-emerald mb-1">COMPLETE</div>
                  <div className="font-display text-2xl">All systems reported in.</div>
                </div>
                <Check className="w-6 h-6 text-emerald" strokeWidth={1.5} />
              </motion.div>
            )}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-8 hairline border-crimson p-5 bg-crimson/[0.04]"
              >
                <div className="label-xs text-crimson mb-1">PIPELINE ERROR</div>
                <div className="font-display text-xl text-ink mb-2">{error}</div>
                <div className="text-xs text-graphite">
                  Check the FastAPI server logs and try a different location.
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

function ApiRowDisplay({ row, index }: { row: ApiRow; index: number }) {
  const isLoading = row.status === "loading";
  const isDone    = row.status === "done";

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06, duration: 0.4 }}
      className={`hairline-b py-4 grid grid-cols-12 gap-4 items-center transition-colors
                  ${isLoading ? "bg-bone/40" : ""}`}
    >
      <div className="col-span-1 font-mono text-[10px] tabular text-mist">
        {String(index).padStart(2, "0")}
      </div>
      <div className="col-span-3">
        <div className="text-sm text-ink font-medium">{row.source}</div>
      </div>
      <div className="col-span-7">
        <AnimatePresence mode="wait">
          <motion.div
            key={row.status}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.25 }}
            className={`text-sm italic font-display ${isDone ? "text-mist line-through" : "text-graphite"}`}
          >
            {row.caption}
          </motion.div>
        </AnimatePresence>
      </div>
      <div className="col-span-1 flex justify-end">
        <StatusDot status={row.status} />
      </div>
    </motion.div>
  );
}

function StatusDot({ status }: { status: ApiRow["status"] }) {
  if (status === "done") {
    return (
      <div className="w-4 h-4 rounded-full border border-emerald bg-emerald flex items-center justify-center">
        <Check className="w-2.5 h-2.5 text-white" strokeWidth={3} />
      </div>
    );
  }
  if (status === "loading") {
    return (
      <div className="relative w-4 h-4 rounded-full border border-ink">
        <div className="absolute inset-0.5 rounded-full bg-ink animate-pulse" />
      </div>
    );
  }
  return <div className="w-4 h-4 rounded-full border border-hairline" />;
}
