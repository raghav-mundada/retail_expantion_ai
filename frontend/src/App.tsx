import { useState, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { PhaseHeader } from "./components/PhaseHeader";
import { BrandSelector } from "./components/BrandSelector";
import { MapPicker, type PickedLocation } from "./components/MapPicker";
import { LoadingScreen } from "./components/LoadingScreen";
import { Dashboard } from "./components/Dashboard";
import { AIRecommendation } from "./components/AIRecommendation";

import { analyzeV2, type RetailerProfile, type AnalysisResultV2 } from "./lib/api";

type Phase = "brand" | "pick" | "loading" | "dashboard";

export default function App() {
  const [phase, setPhase]           = useState<Phase>("brand");
  const [retailer, setRetailer]     = useState<RetailerProfile | null>(null);
  const [retailerName, setRetailerName] = useState<string>("");
  const [location, setLocation]     = useState<PickedLocation | null>(null);
  const [result, setResult]         = useState<AnalysisResultV2 | null>(null);
  const [showOracle, setShowOracle] = useState(false);

  const fetchPromiseRef = useRef<Promise<AnalysisResultV2> | null>(null);

  const phaseNumber =
    phase === "brand"   ? 1 :
    phase === "pick"    ? 2 :
    phase === "loading" ? 3 :
    showOracle          ? 5 :
                          4;

  function handleBrandSelect(r: RetailerProfile, name: string) {
    setRetailer(r);
    setRetailerName(name);
    setPhase("pick");
  }

  function handlePick(loc: PickedLocation) {
    if (!retailer) return;
    setLocation(loc);
    fetchPromiseRef.current = analyzeV2({
      lat: loc.lat,
      lng: loc.lon,
      retailer,
      radius_miles: Math.round(loc.radius_km * 0.621371 * 10) / 10,
      region_city: "Phoenix, AZ",
    }).then((res) => {
      setResult(res);
      return res;
    });
    setPhase("loading");
  }

  function handleReset() {
    setPhase("brand");
    setRetailer(null);
    setRetailerName("");
    setLocation(null);
    setResult(null);
    setShowOracle(false);
    fetchPromiseRef.current = null;
  }

  return (
    <div className="min-h-screen bg-paper">
      <PhaseHeader current={phaseNumber} onReset={handleReset} />

      <AnimatePresence mode="wait">
        {phase === "brand" && (
          <motion.div
            key="brand"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <BrandSelector onSelect={handleBrandSelect} />
          </motion.div>
        )}

        {phase === "pick" && (
          <motion.div
            key="pick"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <MapPicker onAnalyze={handlePick} retailerName={retailerName} />
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
              fetchPromise={fetchPromiseRef.current as any}
              onComplete={() => setPhase("dashboard")}
            />
          </motion.div>
        )}

        {phase === "dashboard" && location && result && (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <Dashboard
              result={result}
              lat={location.lat}
              lon={location.lon}
              radius_km={location.radius_km}
              onAskOracle={() => setShowOracle(true)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showOracle && result && (
          <AIRecommendation
            runId={`${result.lat.toFixed(4)}_${result.lng.toFixed(4)}`}
            storeFormat={result.brand}
            onClose={() => setShowOracle(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
