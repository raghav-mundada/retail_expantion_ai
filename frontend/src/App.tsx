import { useState, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { PhaseHeader } from "./components/PhaseHeader";
import { MapPicker, type PickedLocation } from "./components/MapPicker";
import { LoadingScreen } from "./components/LoadingScreen";
import { Dashboard } from "./components/Dashboard";
import { AIRecommendation } from "./components/AIRecommendation";

import { analyze, type AnalyzeResponse } from "./lib/api";

type Phase = "pick" | "loading" | "dashboard";

export default function App() {
  const [phase, setPhase] = useState<Phase>("pick");
  const [location, setLocation] = useState<PickedLocation | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [showOracle, setShowOracle] = useState(false);

  // We hold onto the in-flight fetch promise so the LoadingScreen can await it
  const fetchPromiseRef = useRef<Promise<AnalyzeResponse> | null>(null);

  const phaseNumber =
    phase === "pick"      ? 1 :
    phase === "loading"   ? 2 :
    showOracle            ? 4 :
                            3;

  function handlePick(loc: PickedLocation) {
    setLocation(loc);
    fetchPromiseRef.current = analyze(loc.lat, loc.lon, loc.radius_km).then((res) => {
      setRunId(res.run_id);
      return res;
    });
    setPhase("loading");
  }

  function handleReset() {
    setPhase("pick");
    setLocation(null);
    setRunId(null);
    setShowOracle(false);
    fetchPromiseRef.current = null;
  }

  return (
    <div className="min-h-screen bg-paper">
      <PhaseHeader current={phaseNumber} onReset={handleReset} />

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

        {phase === "loading" && location && fetchPromiseRef.current && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <LoadingScreen
              lat={location.lat}
              lon={location.lon}
              radius_km={location.radius_km}
              fetchPromise={fetchPromiseRef.current}
              onComplete={() => setPhase("dashboard")}
            />
          </motion.div>
        )}

        {phase === "dashboard" && location && runId && (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <Dashboard
              runId={runId}
              lat={location.lat}
              lon={location.lon}
              radius_km={location.radius_km}
              onAskOracle={() => setShowOracle(true)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showOracle && runId && (
          <AIRecommendation
            runId={runId}
            storeFormat="Target"
            onClose={() => setShowOracle(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
