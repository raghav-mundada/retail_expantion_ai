import { useState, useRef, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Sparkles, Loader } from "lucide-react";

import { PhaseHeader } from "./components/PhaseHeader";
import { MapPicker, type PickedLocation } from "./components/MapPicker";
import { LoadingScreen } from "./components/LoadingScreen";
import { Dashboard } from "./components/Dashboard";
import { AIRecommendation } from "./components/AIRecommendation";
import { ScoutResults } from "./components/ScoutResults";
import { AuthModal } from "./components/AuthModal";
import { HistoryPanel } from "./components/HistoryPanel";
import type { StoreFormat } from "./components/StoreFormatPicker";

import { useAuth } from "./lib/auth";
import {
  analyze,
  scout,
  type AnalyzeResponse,
  type MyRun,
  type ScoutResponse,
  type ScoutCandidate,
} from "./lib/api";

type Phase =
  | "pick"          // Map landing — manual or scout mode
  | "loading"       // Loading screen for manual analyze
  | "scouting"      // Loading screen for auto-scout
  | "scout-results" // Top 3 candidates view
  | "dashboard";    // Deep-dive dashboard

interface DashboardLocation {
  lat: number;
  lon: number;
  radius_km: number;
}

export default function App() {
  const { user } = useAuth();
  const [phase, setPhase] = useState<Phase>("pick");
  const [storeFormat, setStoreFormat] = useState<StoreFormat>("Target");
  const [dashboardLoc, setDashboardLoc] = useState<DashboardLocation | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [scoutResult, setScoutResult] = useState<ScoutResponse | null>(null);
  const [showOracle, setShowOracle] = useState(false);

  // Auth + history overlays
  const [authOpen, setAuthOpen]       = useState(false);
  const [authIntent, setAuthIntent]   = useState<"default" | "history" | "save">("default");
  const [historyOpen, setHistoryOpen] = useState(false);

  // In-flight promises so loading screens can await them
  const fetchPromiseRef = useRef<Promise<AnalyzeResponse> | null>(null);
  const scoutPromiseRef = useRef<Promise<ScoutResponse> | null>(null);

  const phaseNumber =
    phase === "pick"           ? 1 :
    phase === "loading"        ? 2 :
    phase === "scouting"       ? 2 :
    phase === "scout-results"  ? 2 :
    showOracle                 ? 4 :
                                 3;

  function handlePick(loc: PickedLocation) {
    setStoreFormat(loc.store_format);

    if (loc.mode === "manual") {
      setDashboardLoc({ lat: loc.lat, lon: loc.lon, radius_km: loc.radius_km });
      fetchPromiseRef.current = analyze(loc.lat, loc.lon, loc.radius_km, loc.store_format).then((res) => {
        setRunId(res.run_id);
        return res;
      });
      setPhase("loading");
    } else {
      // Auto-scout — fire the scout call, show scouting loader
      scoutPromiseRef.current = scout(loc.lat, loc.lon, loc.radius_km, loc.store_format)
        .then((res) => {
          setScoutResult(res);
          setRunId(res.run_id);
          return res;
        });
      setPhase("scouting");
    }
  }

  function handleOpenHistory() {
    if (!user) {
      setAuthIntent("history");
      setAuthOpen(true);
      return;
    }
    setHistoryOpen(true);
  }

  function handleOpenSignIn() {
    setAuthIntent("default");
    setAuthOpen(true);
  }

  function handleOpenRunFromHistory(run: MyRun) {
    // We already have the run_id and the data lives in Supabase — skip the
    // /analyze cache lookup AND the cinematic loader entirely. Straight to
    // the dashboard, which fetches its slices from /runs/{id}/...
    setHistoryOpen(false);
    setStoreFormat((run.store_format as StoreFormat) ?? "Target");
    setDashboardLoc({ lat: run.lat, lon: run.lon, radius_km: run.radius_km });
    setRunId(run.id);
    setShowOracle(false);
    setScoutResult(null);
    fetchPromiseRef.current = null;
    setPhase("dashboard");
  }

  // If the user just signed in and they were trying to view history, open it.
  useEffect(() => {
    if (user && authOpen && authIntent === "history") {
      setAuthOpen(false);
      setHistoryOpen(true);
    }
  }, [user, authOpen, authIntent]);

  function handleScoutComplete() {
    setPhase("scout-results");
  }

  function handleDeepDive(candidate: ScoutCandidate) {
    if (!scoutResult) return;
    // Re-analyze around the picked candidate at a tight 3km — gives the
    // dashboard an accurate, focused view of THIS specific spot. Cached
    // hits return instantly.
    const tightRadius = 3;
    setDashboardLoc({ lat: candidate.lat, lon: candidate.lon, radius_km: tightRadius });
    fetchPromiseRef.current = analyze(candidate.lat, candidate.lon, tightRadius).then((res) => {
      setRunId(res.run_id);
      return res;
    });
    setPhase("loading");
  }

  function handleReset() {
    setPhase("pick");
    setDashboardLoc(null);
    setRunId(null);
    setScoutResult(null);
    setShowOracle(false);
    fetchPromiseRef.current = null;
    scoutPromiseRef.current = null;
  }

  return (
    <div className="min-h-screen bg-paper">
      <PhaseHeader
        current={phaseNumber}
        onReset={handleReset}
        onSignInClick={handleOpenSignIn}
        onHistoryClick={handleOpenHistory}
      />

      <AnimatePresence mode="wait">
        {phase === "pick" && (
          <motion.div
            key="pick"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <MapPicker onAnalyze={handlePick} />
          </motion.div>
        )}

        {phase === "loading" && dashboardLoc && fetchPromiseRef.current && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <LoadingScreen
              lat={dashboardLoc.lat}
              lon={dashboardLoc.lon}
              radius_km={dashboardLoc.radius_km}
              fetchPromise={fetchPromiseRef.current}
              onComplete={() => setPhase("dashboard")}
            />
          </motion.div>
        )}

        {phase === "scouting" && scoutPromiseRef.current && (
          <motion.div
            key="scouting"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <ScoutingScreen
              storeFormat={storeFormat}
              promise={scoutPromiseRef.current}
              onComplete={handleScoutComplete}
            />
          </motion.div>
        )}

        {phase === "scout-results" && scoutResult && (
          <motion.div
            key="scout-results"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <ScoutResults
              data={scoutResult}
              onDeepDive={handleDeepDive}
              onReset={handleReset}
            />
          </motion.div>
        )}

        {phase === "dashboard" && dashboardLoc && runId && (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <Dashboard
              runId={runId}
              lat={dashboardLoc.lat}
              lon={dashboardLoc.lon}
              radius_km={dashboardLoc.radius_km}
              onAskOracle={() => setShowOracle(true)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showOracle && runId && (
          <AIRecommendation
            runId={runId}
            storeFormat={storeFormat}
            onClose={() => setShowOracle(false)}
          />
        )}
      </AnimatePresence>

      {/* Auth + history overlays — sit above everything */}
      <AuthModal
        open={authOpen}
        intent={authIntent}
        onClose={() => setAuthOpen(false)}
      />
      <HistoryPanel
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onOpenRun={handleOpenRunFromHistory}
      />
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Lightweight scouting loader — distinct copy from the manual flow
// ──────────────────────────────────────────────────────────────────

const SCOUT_STAGES = [
  "Sweeping every commercial parcel inside your area…",
  "Pulling census tracts, traffic counts, and rival stores…",
  "Scoring each parcel on demand, competition, and Huff capture…",
  "Spreading the winners across distinct neighborhoods…",
  "Selecting the top three candidates…",
];

function ScoutingScreen({
  storeFormat,
  promise,
  onComplete,
}: {
  storeFormat: string;
  promise: Promise<ScoutResponse>;
  onComplete: () => void;
}) {
  const [stageIx, setStageIx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    promise
      .then(() => onComplete())
      .catch((e) => setError(e.message ?? "Scout failed"));
    const id = setInterval(
      () => setStageIx((ix) => Math.min(ix + 1, SCOUT_STAGES.length - 1)),
      2400,
    );
    const stop = setTimeout(() => clearInterval(id), 18_000);
    return () => { clearInterval(id); clearTimeout(stop); };
  }, [promise, onComplete]);

  return (
    <div className="h-[calc(100vh-4rem)] flex items-center justify-center px-6">
      <div className="max-w-xl w-full">
        <div className="flex items-center gap-3 mb-6">
          <Sparkles className="w-4 h-4 text-emerald" strokeWidth={1.5} />
          <span className="label-xs">AUTO-SCOUT · {storeFormat.toUpperCase()}</span>
        </div>

        <h1 className="display-lg mb-8 leading-[0.95]">
          Finding the corners <em className="italic font-display">worth opening</em>.
        </h1>

        <div className="bg-snow border border-hairline p-6 space-y-3">
          {SCOUT_STAGES.map((s, i) => {
            const done    = i < stageIx;
            const active  = i === stageIx;
            const pending = i > stageIx;
            return (
              <div key={i} className="flex items-center gap-3 text-sm">
                <div className="w-4 h-4 flex items-center justify-center">
                  {done && <div className="w-1.5 h-1.5 bg-emerald rounded-full" />}
                  {active && <Loader className="w-3.5 h-3.5 text-ink animate-spin" strokeWidth={1.5} />}
                  {pending && <div className="w-1.5 h-1.5 bg-mist rounded-full" />}
                </div>
                <span className={done ? "text-graphite line-through" : active ? "text-ink" : "text-mist"}>
                  {s}
                </span>
              </div>
            );
          })}
        </div>

        {error && (
          <div className="mt-6 bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
