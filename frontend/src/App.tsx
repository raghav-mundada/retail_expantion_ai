import { useState, useRef, useCallback } from 'react';
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
import { AuthModal }   from './components/AuthModal';
import { PricingPage } from './pages/PricingPage';
import { BillingPage }    from './pages/BillingPage';

import { analyzeV2, type RetailerProfile, type AnalysisResultV2 } from './lib/api';
import { useAuth } from './context/AuthContext';

type AppPhase = 'brand' | 'pick' | 'loading' | 'dashboard';

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
  const [showAuthModal,   setShowAuthModal]   = useState(false);
  const [authPrompt,      setAuthPrompt]      = useState('');

  const fetchRef = useRef<Promise<AnalysisResultV2> | null>(null);

  const phaseNumber =
    appPhase === 'brand'   ? 1 :
    appPhase === 'pick'    ? 2 :
    appPhase === 'loading' ? 3 :
    showOracle             ? 5 : 4;

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
    setShowOracle(false);
    setShowSimulation(false);
    fetchRef.current = null;
  }

  function handleRunSimulation() {
    if (!isPro) {
      window.location.href = '/pricing';
      return;
    }
    setShowSimulation(true);
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
              <MapPicker onAnalyze={handlePick} retailerName={retailerName} />
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
            <SimulationCanvas
              simulation={result.simulation}
              score={result.score}
              demographics={result.demographics}
              brand={result.brand}
              onClose={() => setShowSimulation(false)}
            />
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
