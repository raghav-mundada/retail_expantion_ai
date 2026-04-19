import { useState, useRef, useCallback, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';

import { PhaseHeader }  from './components/PhaseHeader';
import { BrandSelector } from './components/BrandSelector';
import { MapPicker, type PickedLocation } from './components/MapPicker';
import { LoadingScreen }  from './components/LoadingScreen';
import { Dashboard }      from './components/Dashboard';
import { AIRecommendation } from './components/AIRecommendation';
import { SplashScreen }   from './components/SplashScreen';
import { CursorGlow }     from './components/CursorGlow';
import { SimulationCanvas } from './components/SimulationCanvas';
import { ScoutResults } from './components/ScoutResults';
import { AuthModal }   from './components/AuthModal';
import { PricingPage } from './pages/PricingPage';
import { BillingPage }    from './pages/BillingPage';

import {
  analyzeV2, simulateV2, scoutTop3,
  type RetailerProfile, type AnalysisResultV2, type SimulationResult,
  type ScoutResponse, type ScoutCandidate,
} from './lib/api';
import { useAuth } from './context/AuthContext';

type AppPhase = 'brand' | 'pick' | 'loading' | 'dashboard' | 'scouting' | 'scout-results';

const SPLASH_KEY = 'retailiq_splash_seen';
function shouldShowSplash(): boolean {
  try { return !sessionStorage.getItem(SPLASH_KEY); } catch { return false; }
}

// ── Main app (all state-machine routes live under "/") ─────────────────────
function MainApp() {
  const { user, isPro, analysesLeft, incrementUsage, loading: authLoading } = useAuth();

  const [showSplash,      setShowSplash]      = useState(shouldShowSplash);
  const [appPhase,        setAppPhase]        = useState<AppPhase>('brand');
  const [retailer,        setRetailer]        = useState<RetailerProfile | null>(null);
  const [retailerName,    setRetailerName]    = useState('');
  const [location,        setLocation]        = useState<PickedLocation | null>(null);
  const [result,          setResult]          = useState<AnalysisResultV2 | null>(null);
  const [showOracle,      setShowOracle]      = useState(false);
  const [showSimulation,  setShowSimulation]  = useState(false);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationError,   setSimulationError]   = useState<string | null>(null);
  const [showAuthModal,   setShowAuthModal]   = useState(false);
  const [authPrompt,      setAuthPrompt]      = useState('');
  const [scoutResult,     setScoutResult]     = useState<ScoutResponse | null>(null);
  const [scoutError,      setScoutError]      = useState<string | null>(null);

  const fetchRef = useRef<Promise<AnalysisResultV2> | null>(null);

  const phaseNumber =
    appPhase === 'brand'          ? 1 :
    appPhase === 'pick'           ? 2 :
    appPhase === 'loading'        ? 3 :
    appPhase === 'scouting'       ? 3 :
    appPhase === 'scout-results'  ? 4 :
    showOracle                    ? 5 : 4;

  const handleSplashComplete = useCallback(() => {
    try { sessionStorage.setItem(SPLASH_KEY, '1'); } catch { /* ignore */ }
    setShowSplash(false);
  }, []);

  function handleBrandSelect(r: RetailerProfile, name: string) {
    if (!user && !authLoading) {
      setAuthPrompt('Sign in to run an analysis');
      setShowAuthModal(true);
      return;
    }
    if (analysesLeft !== null && analysesLeft <= 0) {
      // Free plan exhausted — go to pricing
      window.location.href = '/pricing';
      return;
    }
    setRetailer(r);
    setRetailerName(name);
    setAppPhase('pick');
  }

  function handlePick(loc: PickedLocation) {
    if (!retailer) return;
    setLocation(loc);
    fetchRef.current = analyzeV2({
      lat:          loc.lat,
      lng:          loc.lon,
      retailer,
      radius_miles: Math.round(loc.radius_km * 0.621371 * 10) / 10,
      region_city:  'Minneapolis, MN',
    }).then((res) => {
      setResult(res);
      incrementUsage();
      return res;
    });
    setAppPhase('loading');
  }

  function handleReset() {
    setAppPhase('brand');
    setRetailer(null);
    setRetailerName('');
    setLocation(null);
    setResult(null);
    setScoutResult(null);
    setScoutError(null);
    setShowOracle(false);
    setShowSimulation(false);
    fetchRef.current = null;
  }

  async function handleScout(loc: PickedLocation) {
    if (!retailer) return;
    if (!user && !authLoading) {
      setAuthPrompt('Sign in to run the top-3 scout');
      setShowAuthModal(true);
      return;
    }
    setLocation(loc);
    setScoutError(null);
    setScoutResult(null);
    setAppPhase('scouting');
    try {
      const res = await scoutTop3({
        lat:          loc.lat,
        lon:          loc.lon,
        radius_km:    loc.radius_km,
        retailer,
        n_candidates: 3,
      });
      setScoutResult(res);
      setAppPhase('scout-results');
    } catch (e: any) {
      setScoutError(e?.message ?? 'Scout failed');
      setAppPhase('pick');
    }
  }

  function handleScoutDeepDive(c: ScoutCandidate) {
    if (!retailer || !location) return;
    // Use the candidate's coordinates as the new pin; kick off the full analysis.
    const loc: PickedLocation = {
      lat:       c.lat,
      lon:       c.lng,
      radius_km: location.radius_km,
    };
    setLocation(loc);
    fetchRef.current = analyzeV2({
      lat:          loc.lat,
      lng:          loc.lon,
      retailer,
      radius_miles: Math.round(loc.radius_km * 0.621371 * 10) / 10,
      region_city:  'Minneapolis, MN',
    }).then((res) => {
      setResult(res);
      incrementUsage();
      return res;
    });
    setAppPhase('loading');
  }

  async function handleRunSimulation() {
    if (!isPro) {
      window.location.href = '/pricing';
      return;
    }
    if (!result || !retailer) return;

    // If we already have sim results (user reopening the canvas), just show it.
    if (result.simulation) {
      setShowSimulation(true);
      return;
    }

    setSimulationError(null);
    setSimulationLoading(true);
    setShowSimulation(true);
    try {
      const sim: SimulationResult = await simulateV2({
        lat:          result.lat,
        lng:          result.lng,
        retailer,
        demographics: result.demographics,
        competitors:  result.competitors,
      });
      setResult({ ...result, simulation: sim });
    } catch (e: any) {
      setSimulationError(e?.message ?? 'Simulation failed');
    } finally {
      setSimulationLoading(false);
    }
  }

  function handleAskOracle() {
    if (!isPro) {
      window.location.href = '/pricing';
      return;
    }
    setShowOracle(true);
  }

  return (
    <>
      <AnimatePresence>
        {showSplash && <SplashScreen onComplete={handleSplashComplete} />}
      </AnimatePresence>

      <CursorGlow />

      <div className="min-h-screen bg-paper">
        <PhaseHeader
          current={phaseNumber}
          onReset={handleReset}
          onOpenAuth={() => { setAuthPrompt(''); setShowAuthModal(true); }}
        />

        {/* Free plan exhausted banner */}
        {user && analysesLeft === 0 && appPhase === 'brand' && (
          <div className="bg-[rgba(200,168,130,0.12)] border-b border-hairline px-6 py-3 flex items-center justify-between">
            <span className="text-xs text-graphite">
              You've used all 3 free analyses this month.
            </span>
            <a href="/pricing" className="text-xs text-mocha underline underline-offset-2 hover:text-graphite transition-colors">
              Upgrade to Pro for unlimited access →
            </a>
          </div>
        )}

        <AnimatePresence mode="wait">
          {appPhase === 'brand' && (
            <motion.div key="brand"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <BrandSelector
                onSelect={handleBrandSelect}
                onSignIn={() => { setAuthPrompt(''); setShowAuthModal(true); }}
              />
            </motion.div>
          )}

          {appPhase === 'pick' && (
            <motion.div key="pick"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              {scoutError && (
                <div className="bg-red-50 border-b border-red-200 px-6 py-3 text-sm text-red-700 text-center">
                  Scout failed: {scoutError}
                </div>
              )}
              <MapPicker onAnalyze={handlePick} onScout={handleScout} retailerName={retailerName} />
            </motion.div>
          )}

          {appPhase === 'scouting' && location && (
            <motion.div key="scouting"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <ScoutingLoader lat={location.lat} lon={location.lon} radius_km={location.radius_km} />
            </motion.div>
          )}

          {appPhase === 'scout-results' && scoutResult && (
            <motion.div key="scout-results"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <ScoutResults
                data={scoutResult}
                onDeepDive={handleScoutDeepDive}
                onReset={() => { setAppPhase('pick'); setScoutResult(null); }}
              />
            </motion.div>
          )}

          {appPhase === 'loading' && location && fetchRef.current && (
            <motion.div key="loading"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <LoadingScreen
                lat={location.lat}
                lon={location.lon}
                radius_km={location.radius_km}
                fetchPromise={fetchRef.current as any}
                onComplete={() => setAppPhase('dashboard')}
              />
            </motion.div>
          )}

          {appPhase === 'dashboard' && location && result && (
            <motion.div key="dashboard"
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <Dashboard
                result={result}
                lat={location.lat}
                lon={location.lon}
                radius_km={location.radius_km}
                onAskOracle={handleAskOracle}
                onRunSimulation={handleRunSimulation}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Oracle debate overlay */}
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

      {/* Simulation canvas overlay */}
      <AnimatePresence>
        {showSimulation && result && (
          <motion.div key="sim"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.35 }}
            style={{ position: 'fixed', inset: 0, zIndex: 9998 }}
          >
            {result.simulation ? (
              <SimulationCanvas
                simulation={result.simulation}
                score={result.score}
                demographics={result.demographics}
                brand={result.brand}
                onClose={() => setShowSimulation(false)}
              />
            ) : (
              <SimulationLoadingPane
                loading={simulationLoading}
                error={simulationError}
                onClose={() => setShowSimulation(false)}
                onRetry={handleRunSimulation}
              />
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Auth modal */}
      <AuthModal
        open={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        intent={authPrompt === 'Sign in to run an analysis' ? 'save' : 'default'}
      />
    </>
  );
}

// ── Simulation loading pane (shown while /api/simulate is in-flight) ───────
function SimulationLoadingPane({
  loading, error, onClose, onRetry,
}: {
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onRetry: () => void;
}) {
  const stages = [
    'Spawning 500 household agents across the trade area…',
    'Modeling shopping frequency, price sensitivity, brand loyalty…',
    'Running Monte Carlo visit decisions vs nearby competitors…',
    'Aggregating word-of-mouth spread + market share by quarter…',
    'Computing revenue confidence intervals…',
  ];
  const [stageIx, setStageIx] = useState(0);
  useEffect(() => {
    if (!loading) return;
    const id = setInterval(() => setStageIx(i => Math.min(i + 1, stages.length - 1)), 1800);
    return () => clearInterval(id);
  }, [loading]);

  return (
    <div className="h-screen w-screen bg-paper flex items-center justify-center px-6">
      <div className="max-w-xl w-full bg-snow border border-hairline p-10 shadow-xl">
        <div className="flex items-start justify-between mb-6">
          <div>
            <div className="label-xs mb-3">RUNNING MARKET SIMULATION</div>
            <h2 className="display-md leading-[1.05]">
              Spinning up <em className="italic font-display">500 household agents</em>.
            </h2>
          </div>
          <button onClick={onClose} className="label-xs hover:text-ink transition">Close</button>
        </div>
        {error ? (
          <div className="bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 mb-4">
            {error}
          </div>
        ) : null}
        <div className="space-y-3">
          {stages.map((s, i) => {
            const done    = i < stageIx;
            const active  = i === stageIx && loading;
            const pending = i > stageIx;
            return (
              <div key={i} className="flex items-center gap-3 text-sm">
                <div className="w-4 h-4 flex items-center justify-center">
                  {done    && <div className="w-1.5 h-1.5 bg-emerald rounded-full" />}
                  {active  && <div className="w-2 h-2 border border-ink border-t-transparent rounded-full animate-spin" />}
                  {pending && <div className="w-1.5 h-1.5 bg-mist rounded-full" />}
                </div>
                <span className={done ? 'text-graphite line-through' : active ? 'text-ink' : 'text-mist'}>
                  {s}
                </span>
              </div>
            );
          })}
        </div>
        {error && (
          <button onClick={onRetry} className="mt-6 btn-primary px-6 py-3 text-sm">Retry</button>
        )}
      </div>
    </div>
  );
}

// ── Scouting loader (shown while /api/scout is running K-Means) ───────────
function ScoutingLoader({ lat, lon, radius_km }: { lat: number; lon: number; radius_km: number }) {
  const stages = [
    `Resolving census tracts within ${radius_km} km of your anchor…`,
    'Pulling ACS 2023 demographics (population, income, poverty)…',
    'Fetching OSM competitors + schools in the search circle…',
    'Scoring every tract on 6 weighted factors…',
    'Clustering with weighted K-Means → locking in your top 3…',
  ];
  const [ix, setIx] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setIx(i => Math.min(i + 1, stages.length - 1)), 1600);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="h-[calc(100vh-4rem)] bg-paper flex items-center justify-center px-6">
      <div className="max-w-xl w-full bg-snow border border-hairline p-10 shadow-xl">
        <div className="label-xs mb-3">RUNNING TOP-3 SCOUT</div>
        <h2 className="display-md leading-[1.05] mb-6">
          K-Means clustering the best <em className="italic font-display">3 tracts</em>.
        </h2>
        <div className="space-y-3 mb-6">
          {stages.map((s, i) => {
            const done   = i < ix;
            const active = i === ix;
            return (
              <div key={i} className="flex items-center gap-3 text-sm">
                <div className="w-4 h-4 flex items-center justify-center">
                  {done   && <div className="w-1.5 h-1.5 bg-emerald rounded-full" />}
                  {active && <div className="w-2 h-2 border border-ink border-t-transparent rounded-full animate-spin" />}
                  {!done && !active && <div className="w-1.5 h-1.5 bg-mist rounded-full" />}
                </div>
                <span className={done ? 'text-graphite line-through' : active ? 'text-ink' : 'text-mist'}>{s}</span>
              </div>
            );
          })}
        </div>
        <div className="label-xs text-mist">
          ANCHOR {lat.toFixed(3)}, {lon.toFixed(3)} · {radius_km.toFixed(1)} KM
        </div>
      </div>
    </div>
  );
}

// ── Root with router ───────────────────────────────────────────────────────
export default function App() {
  return (
    <Routes>
      <Route path="/pricing" element={<PricingPage />} />
      <Route path="/billing" element={<BillingPage />} />
      <Route path="/*"       element={<MainApp />}     />
    </Routes>
  );
}
