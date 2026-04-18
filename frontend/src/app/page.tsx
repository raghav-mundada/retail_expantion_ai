"use client";
import { useCallback, useEffect, useState, useRef } from "react";
import dynamic from "next/dynamic";
import AgentTrace from "@/components/AgentTrace";
import ScoreCard from "@/components/ScoreCard";
import {
  getCandidates,
  getCompetitors,
  streamAnalysis,
  type AnalysisResult,
  type CandidateSite,
  type CompetitorStore,
  type TraceEvent,
} from "@/lib/api";

// SSR-safe Leaflet map
const Map = dynamic(() => import("@/components/Map"), { ssr: false });

export default function Home() {
  const [candidates, setCandidates] = useState<CandidateSite[]>([]);
  const [competitors, setCompetitors] = useState<CompetitorStore[]>([]);
  const [selectedSite, setSelectedSite] = useState<CandidateSite | null>(null);
  const [droppedPin, setDroppedPin] = useState<{ lat: number; lng: number } | null>(null);
  const [brand, setBrand] = useState<"walmart" | "target">("walmart");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stopRef = useRef<(() => void) | null>(null);

  // Load initial data
  useEffect(() => {
    getCandidates().then(setCandidates).catch(console.error);
    getCompetitors(33.4484, -112.074, 25)
      .then(setCompetitors)
      .catch(console.error);
  }, []);

  const handleSiteSelect = useCallback((site: CandidateSite) => {
    setSelectedSite(site);
    setDroppedPin({ lat: site.lat, lng: site.lng });
    setResult(null);
    setTraceEvents([]);
    setError(null);
  }, []);

  const handlePinDrop = useCallback((lat: number, lng: number) => {
    setDroppedPin({ lat, lng });
    setSelectedSite(null);
    setResult(null);
    setTraceEvents([]);
    setError(null);
  }, []);

  const handleAnalyze = useCallback(() => {
    const target = droppedPin;
    if (!target) {
      setError("Select a candidate site or click the map to place a pin first.");
      return;
    }

    if (stopRef.current) stopRef.current();
    setIsAnalyzing(true);
    setResult(null);
    setTraceEvents([]);
    setError(null);

    const stop = streamAnalysis(
      { lat: target.lat, lng: target.lng, brand, radius_miles: 10 },
      (event) => setTraceEvents((prev) => [...prev, event]),
      (res) => setResult(res),
      (err) => {
        setError(err);
        setIsAnalyzing(false);
      },
      () => setIsAnalyzing(false)
    );
    stopRef.current = stop;
  }, [droppedPin, brand]);

  const activeTarget = droppedPin;
  const canAnalyze = !!activeTarget && !isAnalyzing;

  return (
    <div className="app-layout">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-logo">
          <div className="logo-badge">
            <span>📍</span> RetailIQ
          </div>
          <span className="logo-subtitle">
            AI-Powered Superstore Site Intelligence · Phoenix Metro Demo
          </span>
        </div>
        <div className="header-meta">
          <div className="meta-badge">
            <div className="dot" />
            Agents Online
          </div>
          <div className="meta-badge">🏪 Phoenix, AZ Metro</div>
          <div className="meta-badge">📊 Census ACS + OSM Live</div>
        </div>
      </header>

      {/* ── Left Panel ── */}
      <aside className="left-panel">
        {/* Brand selector */}
        <div className="panel-section">
          <div className="panel-section-title">Select Retailer Brand</div>
          <div className="brand-selector">
            <button
              className={`brand-btn walmart ${brand === "walmart" ? "active" : ""}`}
              onClick={() => { setBrand("walmart"); setResult(null); setTraceEvents([]); }}
            >
              <span className="brand-icon">🔵</span>
              <span>Walmart</span>
            </button>
            <button
              className={`brand-btn target ${brand === "target" ? "active" : ""}`}
              onClick={() => { setBrand("target"); setResult(null); setTraceEvents([]); }}
            >
              <span className="brand-icon">🔴</span>
              <span>Target</span>
            </button>
          </div>
        </div>

        {/* Candidate sites */}
        <div className="panel-section" style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <div className="panel-section-title">Phoenix Candidate Sites</div>
          <div className="candidate-list" style={{ overflow: "auto", flex: 1 }}>
            {candidates.map((site) => (
              <button
                key={site.id}
                className={`candidate-item ${selectedSite?.id === site.id ? "active" : ""}`}
                onClick={() => handleSiteSelect(site)}
              >
                <div className="candidate-name">{site.name}</div>
                <div className="candidate-meta">
                  {site.acreage} ac · {site.zoning_type}
                </div>
                <div className="candidate-meta" style={{ marginTop: 2, fontStyle: "italic" }}>
                  {site.description}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Selected location info */}
        {activeTarget && (
          <div className="panel-section">
            <div className="panel-section-title">Analysis Target</div>
            <div style={{ fontSize: 12, color: "#7a9ab8", marginBottom: 8 }}>
              {selectedSite ? (
                <>
                  <strong style={{ color: "#e8f4f8" }}>{selectedSite.name}</strong>
                  <br />
                  {selectedSite.description}
                </>
              ) : (
                <>
                  <strong style={{ color: "#e8f4f8" }}>Custom Pin</strong>
                  <br />
                  {droppedPin?.lat.toFixed(5)}°N, {Math.abs(droppedPin?.lng ?? 0).toFixed(5)}°W
                </>
              )}
            </div>
            <div style={{ fontSize: 11, color: "#3d5a73" }}>
              Brand:{" "}
              <span style={{ color: brand === "walmart" ? "#5aa3e8" : "#f87171", fontWeight: 700 }}>
                {brand.charAt(0).toUpperCase() + brand.slice(1)}
              </span>
            </div>
          </div>
        )}

        {error && (
          <div
            style={{
              padding: "10px 12px",
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 8,
              fontSize: 12,
              color: "#f87171",
            }}
          >
            {error}
          </div>
        )}

        {/* Analyze button */}
        <button
          className={`analyze-btn ${isAnalyzing ? "running" : ""}`}
          onClick={handleAnalyze}
          disabled={!canAnalyze}
        >
          {isAnalyzing ? (
            <>
              <div className="spinner" />
              Running Analysis...
            </>
          ) : (
            <>
              ⚡ Run AI Analysis
            </>
          )}
        </button>

        {/* Data source credits */}
        <div
          style={{
            fontSize: 10,
            color: "#3d5a73",
            textAlign: "center",
            lineHeight: 1.8,
          }}
        >
          Data: Census ACS · OSM/Overpass · NCES
          <br />
          AI: Gemini 2.0 Flash · 5-Agent Pipeline
          <br />
          <span style={{ color: "#4f378b" }}>Foot Traffic: Placer.ai Proxy Model</span>
        </div>
      </aside>

      {/* ── Center Map ── */}
      <main className="map-container">
        <Map
          candidates={candidates}
          competitors={competitors}
          selectedSite={selectedSite}
          droppedPin={droppedPin}
          onSiteSelect={handleSiteSelect}
          onPinDrop={handlePinDrop}
          brand={brand}
          isAnalyzing={isAnalyzing}
        />
      </main>

      {/* ── Right Panel ── */}
      <aside className="right-panel">
        {result ? (
          <ScoreCard result={result} brand={brand} />
        ) : (
          <>
            {/* Agent Trace always shows when running */}
            {(isAnalyzing || traceEvents.length > 0) ? (
              <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                <div
                  style={{
                    padding: "10px 14px",
                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    color: "#3d5a73",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  {isAnalyzing && <div className="spinner" style={{ width: 10, height: 10 }} />}
                  Agent Trace Log
                </div>
                <AgentTrace events={traceEvents} isRunning={isAnalyzing} />
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">🗺️</div>
                <div className="empty-title">Select a Location</div>
                <div className="empty-desc">
                  Choose a candidate site from the list or click the map to drop a pin,
                  then run the AI analysis to see a full market simulation.
                </div>
                <div
                  style={{
                    marginTop: 16,
                    fontSize: 11,
                    color: "#3d5a73",
                    lineHeight: 1.8,
                    textAlign: "left",
                    borderLeft: "2px solid rgba(0,212,255,0.2)",
                    paddingLeft: 10,
                  }}
                >
                  5 AI agents will analyze:
                  <br />📊 Demographics (Census ACS)
                  <br />🏪 Competitors (OpenStreetMap)
                  <br />🎓 Schools (NCES)
                  <br />🧠 Market Simulation (Gemini)
                  <br />🎯 Brand Fit Scoring
                </div>
              </div>
            )}
          </>
        )}

        {/* Show trace below results too */}
        {result && traceEvents.length > 0 && (
          <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <div
              style={{
                padding: "8px 14px",
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "#3d5a73",
              }}
            >
              Agent Trace Log
            </div>
            <AgentTrace events={traceEvents} isRunning={isAnalyzing} />
          </div>
        )}
      </aside>
    </div>
  );
}
