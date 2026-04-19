import { motion } from "framer-motion";
import {
  ResponsiveContainer, XAxis, YAxis, Tooltip,
  AreaChart, Area, CartesianGrid,
} from "recharts";
import {
  ArrowUpRight, Sparkles, MapPin, Building2, Users, TrendingUp,
  Flame, AlertTriangle, CheckCircle, Play, Cpu,
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Circle, CircleMarker, Tooltip as LeafletTooltip } from "react-leaflet";
import L from "leaflet";

import type { AnalysisResultV2 } from "../lib/api";
import { fmtNum, fmtUSD, fmtCoord } from "../lib/format";

interface Props {
  result: AnalysisResultV2;
  lat: number;
  lon: number;
  radius_km: number;
  onAskOracle: () => void;
  onRunSimulation: () => void;
}

function scoreColor(score: number): string {
  if (score >= 75) return "#2D6A4F";
  if (score >= 55) return "#5C8A5A";
  if (score >= 40) return "#B45309";
  return "#B91C1C";
}

function scoreBg(score: number): string {
  if (score >= 75) return "#EBF5EE";
  if (score >= 55) return "#EFF5EE";
  if (score >= 40) return "#FBF3E6";
  return "#FBE9E9";
}

function buildRevenueForecast(annualRevenue: number) {
  const ramp = [0.55, 0.62, 0.70, 0.75, 0.80, 0.84, 0.88, 0.91, 0.94, 0.97, 1.0, 1.02,
                1.04, 1.06, 1.07, 1.08, 1.09, 1.10, 1.11, 1.12, 1.13, 1.14, 1.15, 1.15];
  const monthly = annualRevenue / 12;
  return ramp.map((factor, i) => ({
    month: `Mo ${i + 1}`,
    revenue: Math.round(monthly * factor),
  }));
}

export function Dashboard({ result, lat, lon, radius_km, onAskOracle, onRunSimulation }: Props) {
  const { demographics, competitors, neighborhood, hotspot, amenity, simulation, brand_fit, score } = result;
  const forecastData = buildRevenueForecast(simulation.predicted_annual_revenue_usd);

  const scoreDimensions = [
    { label: "Demand",        score: score.demand_score,        weight: "20%" },
    { label: "Competition",   score: score.competition_score,   weight: "18%" },
    { label: "Accessibility", score: score.accessibility_score, weight: "12%" },
    { label: "Neighborhood",  score: score.neighborhood_score,  weight: "12%" },
    { label: "Brand Fit",     score: score.brand_fit_score,     weight: "12%" },
    { label: "Hotspot",       score: score.hotspot_score,       weight: "15%" },
    { label: "Risk",          score: score.risk_score,          weight: "8%"  },
    { label: "Amenity",       score: score.amenity_score,       weight: "3%"  },
  ];

  return (
    <div className="bg-paper min-h-[calc(100vh-4rem)]">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="hairline-b bg-snow"
      >
        <div className="px-6 lg:px-10 py-10 max-w-[1500px] mx-auto grid grid-cols-12 gap-6 items-end">
          <div className="col-span-12 lg:col-span-7">
            <div className="label-xs mb-4">CHAPTER FOUR — EVALUATE</div>
            <h1 className="display-lg mb-3">
              <em className="italic">{result.brand}</em> at {fmtCoord(lat)}, {fmtCoord(lon)}
            </h1>
            <p className="text-graphite max-w-2xl text-sm leading-relaxed">
              {result.address_label || `${radius_km} km radius`} ·{" "}
              {fmtNum(demographics.population, true)} residents ·{" "}
              Scored <strong>{score.total_score.toFixed(0)}/100</strong> — {score.rank_label}
            </p>
          </div>
          <div className="col-span-12 lg:col-span-5 flex lg:justify-end gap-3 flex-wrap">
            {/* Run AI Simulation CTA */}
            <button
              onClick={onRunSimulation}
              className="group relative flex items-center gap-3 px-7 py-5 select-none"
              style={{
                background:    'linear-gradient(135deg, #5C3D1E 0%, #A07850 50%, #C8A882 100%)',
                backgroundSize:'200% auto',
                border:        '1px solid rgba(200,168,130,0.35)',
                color:         '#FBF7F2',
                transition:    'all 180ms cubic-bezier(0.25,0.46,0.45,0.94)',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.backgroundPosition = 'right center';
                (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)';
                (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 8px 28px rgba(160,120,80,0.3)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.backgroundPosition = 'left center';
                (e.currentTarget as HTMLButtonElement).style.transform = 'none';
                (e.currentTarget as HTMLButtonElement).style.boxShadow = 'none';
              }}
              onMouseDown={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'scale(0.97)'; }}
              onMouseUp={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)'; }}
            >
              <Cpu className="w-4 h-4" strokeWidth={1.5} />
              <div className="text-left">
                <div className="text-sm font-medium">Run AI Simulation</div>
                <div className="text-[10px] uppercase tracking-widest opacity-70 mt-0.5 font-mono">220 AGENTS · 5 PHASES</div>
              </div>
              <Play className="w-3.5 h-3.5 opacity-70 group-hover:opacity-100 transition-opacity" strokeWidth={2} />
            </button>

            {/* Oracle debate */}
            <button
              onClick={onAskOracle}
              className="group relative btn-primary px-7 py-5 flex items-center gap-3"
            >
              <Sparkles className="w-4 h-4" strokeWidth={1.5} />
              <div className="text-left">
                <div className="text-sm font-medium">Get AI Debate</div>
                <div className="label-xs text-mist mt-0.5">BULL · BEAR · ORCHESTRATOR</div>
              </div>
              <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" strokeWidth={1.5} />
            </button>
          </div>
        </div>
      </motion.div>

      <div className="px-6 lg:px-10 py-10 max-w-[1500px] mx-auto space-y-6">

        {/* ══ ROW 1 — KPI Strip ══ */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.05 }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-0 hairline"
        >
          <Kpi
            icon={<Users className="w-3.5 h-3.5" strokeWidth={1.5} />}
            label="TRADE AREA POPULATION"
            value={fmtNum(demographics.population, true)}
            sub={`${fmtNum(demographics.household_count, true)} households`}
          />
          <Kpi
            icon={<Building2 className="w-3.5 h-3.5" strokeWidth={1.5} />}
            label="MEDIAN HH INCOME"
            value={fmtUSD(demographics.median_income)}
            sub={`${demographics.family_households_pct.toFixed(0)}% family households`}
            border
          />
          <Kpi
            icon={<TrendingUp className="w-3.5 h-3.5" strokeWidth={1.5} />}
            label="YEAR-1 REVENUE EST."
            value={fmtUSD(simulation.predicted_annual_revenue_usd)}
            sub={`${fmtUSD(simulation.confidence_interval_low)}–${fmtUSD(simulation.confidence_interval_high)} CI`}
            border
            accent
            onSimulate={onRunSimulation}
          />
          <Kpi
            icon={<MapPin className="w-3.5 h-3.5" strokeWidth={1.5} />}
            label="MONTHLY VISITS"
            value={fmtNum(simulation.predicted_monthly_visits, true)}
            sub={`${(simulation.pct_will_visit * 100).toFixed(1)}% of trade area`}
            border
          />
        </motion.div>

        {/* ══ ROW 2 — Score Badge + Dimension Bars ══ */}
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-4 card p-8 flex flex-col items-center justify-center text-center">
            <div className="label-xs mb-6">COMPOSITE LOCATION SCORE</div>
            <div
              className="w-36 h-36 rounded-full flex items-center justify-center mb-6 border-4"
              style={{ borderColor: scoreColor(score.total_score), background: scoreBg(score.total_score) }}
            >
              <div>
                <div className="font-display text-5xl leading-none tabular"
                     style={{ color: scoreColor(score.total_score) }}>
                  {score.total_score.toFixed(0)}
                </div>
                <div className="label-xs mt-1 text-graphite">/ 100</div>
              </div>
            </div>
            <div className="font-display text-xl mb-2">{score.rank_label}</div>
            <div className="label-xs text-slate mb-6">{brand_fit.recommended_format}</div>
            <div className="grid grid-cols-2 gap-3 w-full">
              <div className="bg-paper p-3">
                <div className="label-xs mb-1">MARKET SHARE 6MO</div>
                <div className="font-display text-2xl tabular" style={{ color: scoreColor(70) }}>
                  {(simulation.market_share_6mo * 100).toFixed(1)}%
                </div>
              </div>
              <div className="bg-paper p-3">
                <div className="label-xs mb-1">MARKET SHARE 24MO</div>
                <div className="font-display text-2xl tabular" style={{ color: scoreColor(80) }}>
                  {(simulation.market_share_24mo * 100).toFixed(1)}%
                </div>
              </div>
            </div>
          </div>

          <div className="col-span-12 lg:col-span-8 card p-6">
            <SectionHead
              eyebrow="8-DIMENSION EVALUATION"
              title="Score breakdown"
              caption="Demand 20% · Competition 18% · Access 12% · Neighborhood 12% · Brand Fit 12% · Hotspot 15% · Risk 8% · Amenity 3%"
            />
            <div className="space-y-3">
              {scoreDimensions.map((d) => (
                <div key={d.label} className="flex items-center gap-4">
                  <div className="w-28 label-xs text-right flex-shrink-0">{d.label}</div>
                  <div className="flex-1 bg-paper h-5 relative overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${d.score}%` }}
                      transition={{ duration: 0.9, delay: 0.1, ease: "easeOut" }}
                      className="h-full absolute left-0 top-0"
                      style={{ background: scoreColor(d.score) }}
                    />
                  </div>
                  <div className="w-10 font-mono text-sm tabular text-right"
                       style={{ color: scoreColor(d.score) }}>
                    {d.score.toFixed(0)}
                  </div>
                  <div className="w-8 label-xs text-mist">{d.weight}</div>
                </div>
              ))}
            </div>

            {score.why_this_wins.length > 0 && (
              <div className="mt-6 pt-6 hairline-t">
                <div className="label-xs mb-3" style={{ color: "#047857" }}>WHY THIS SITE WINS</div>
                <ul className="space-y-1.5">
                  {score.why_this_wins.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-graphite">
                      <CheckCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" style={{ color: "#047857" }} strokeWidth={1.5} />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {score.top_risks.length > 0 && (
              <div className="mt-4">
                <div className="label-xs mb-3 text-amber-600">KEY RISKS</div>
                <ul className="space-y-1.5">
                  {score.top_risks.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-graphite">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" strokeWidth={1.5} />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* ══ ROW 3 — Revenue Forecast + Simulation KPIs ══ */}
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8 card p-6">
            {/* Simulation CTA banner */}
            <div
              className="flex items-center justify-between mb-6 p-4 cursor-pointer group"
              style={{
                background:    'linear-gradient(135deg, rgba(92,61,30,0.08), rgba(200,168,130,0.12))',
                border:        '1px solid rgba(200,168,130,0.25)',
                transition:    'all 200ms ease',
              }}
              onClick={onRunSimulation}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.background = 'linear-gradient(135deg, rgba(92,61,30,0.14), rgba(200,168,130,0.20))';
                (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(200,168,130,0.5)';
                (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-1px)';
                (e.currentTarget as HTMLDivElement).style.boxShadow = '0 6px 20px rgba(160,120,80,0.15)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.background = 'linear-gradient(135deg, rgba(92,61,30,0.08), rgba(200,168,130,0.12))';
                (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(200,168,130,0.25)';
                (e.currentTarget as HTMLDivElement).style.transform = 'none';
                (e.currentTarget as HTMLDivElement).style.boxShadow = 'none';
              }}
            >
              <div className="flex items-center gap-3">
                <div style={{ width: 36, height: 36, borderRadius: 4, background: 'rgba(200,168,130,0.15)', border: '1px solid rgba(200,168,130,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Cpu size={16} style={{ color: '#C8A882' }} strokeWidth={1.5} />
                </div>
                <div>
                  <div className="text-sm font-medium text-ink">Run AI Simulation</div>
                  <div className="text-xs text-slate">220 household agents · 5 phases · live Monte Carlo</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  {['INIT','RAND','SCORE','CLUST','OUT'].map((l, i) => (
                    <span key={i} className="text-[9px] px-1.5 py-0.5 font-mono uppercase" style={{ background: 'rgba(200,168,130,0.12)', border: '1px solid rgba(200,168,130,0.2)', color: 'rgba(200,168,130,0.7)' }}>
                      {l}
                    </span>
                  ))}
                </div>
                <Play size={14} style={{ color: '#C8A882', marginLeft: 6 }} strokeWidth={2} className="group-hover:scale-110 transition-transform" />
              </div>
            </div>

            <SectionHead
              eyebrow="REVENUE SIMULATION"
              title="24-month ramp forecast"
              caption={`${fmtNum(simulation.simulated_households, true)} simulated households · ${(simulation.pct_will_visit * 100).toFixed(1)}% visit propensity`}
            />
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={forecastData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                  <defs>
                    <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#047857" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#047857" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" />
                  <XAxis dataKey="month" axisLine={false} tickLine={false}
                    tick={{ fontSize: 10, fill: "#A1A1AA", fontFamily: "Geist Mono" }} interval={5} />
                  <YAxis axisLine={false} tickLine={false}
                    tick={{ fontSize: 10, fill: "#A1A1AA", fontFamily: "Geist Mono" }}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} width={52} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="bg-snow border border-hairline shadow-lg p-3">
                          <div className="label-xs mb-1">{d.month}</div>
                          <div className="font-display text-xl tabular" style={{ color: "#047857" }}>{fmtUSD(d.revenue)}</div>
                          <div className="label-xs text-mist">monthly revenue</div>
                        </div>
                      );
                    }}
                  />
                  <Area type="monotone" dataKey="revenue" stroke="#047857" strokeWidth={2}
                    fill="url(#revenueGrad)" animationDuration={1400} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="col-span-12 lg:col-span-4 card p-6">
            <SectionHead
              eyebrow="SIMULATION OUTPUTS"
              title="Key metrics"
              caption="Household agent model · word-of-mouth spread"
            />
            <div>
              {[
                { label: "Annual Revenue",     value: fmtUSD(simulation.predicted_annual_revenue_usd), highlight: true },
                { label: "Confidence Low",     value: fmtUSD(simulation.confidence_interval_low) },
                { label: "Confidence High",    value: fmtUSD(simulation.confidence_interval_high) },
                { label: "Monthly Visits",     value: fmtNum(simulation.predicted_monthly_visits, true), highlight: true },
                { label: "Visit Propensity",   value: `${(simulation.pct_will_visit * 100).toFixed(1)}%` },
                { label: "Word-of-Mouth",      value: `${simulation.word_of_mouth_score.toFixed(1)}/100` },
                { label: "Market Share 6mo",   value: `${(simulation.market_share_6mo * 100).toFixed(1)}%` },
                { label: "Market Share 24mo",  value: `${(simulation.market_share_24mo * 100).toFixed(1)}%` },
                { label: "Cannibalization",    value: `${simulation.cannibalization_risk.toFixed(1)}%`,
                  warn: simulation.cannibalization_risk > 50 },
              ].map((item: any) => (
                <div key={item.label} className="data-row flex items-baseline justify-between hairline-b py-2 px-1 last:border-0">
                  <span className="label-xs">{item.label}</span>
                  <span className={`font-mono text-sm tabular ${
                    item.highlight ? "text-ink font-medium" :
                    item.warn ? "text-crimson" : "text-graphite"
                  }`}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ══ ROW 4 — TinyFish Hotspot + Amenity ══ */}
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-7 card p-6">
            <div className="flex items-start justify-between mb-6">
              <div>
                <div className="label-xs mb-2">TINYFISH HOTSPOT INTEL</div>
                <h3 className="font-display text-2xl tracking-tightest leading-none mb-2">Live retail momentum</h3>
                <div className="text-xs text-slate">Yelp openings · permit activity · Loopnet supply · store opening intel</div>
              </div>
              {hotspot && (
                <div className="flex flex-col items-end gap-1 flex-shrink-0 ml-4">
                  <div className="font-display text-4xl tabular leading-none"
                       style={{ color: scoreColor(hotspot.hotspot_score) }}>
                    {hotspot.hotspot_score.toFixed(0)}
                  </div>
                  <div className="label-xs">/100 HOTSPOT</div>
                  <div className={`label-xs px-2 py-0.5 ${hotspot.tinyfish_powered ? "bg-emerald text-snow" : "bg-bone text-graphite"}`}>
                    {hotspot.tinyfish_powered ? "LIVE" : "PROXY"}
                  </div>
                </div>
              )}
            </div>

            {hotspot ? (
              <>
                <p className="text-sm text-graphite leading-relaxed mb-5 italic">"{hotspot.narrative}"</p>
                <div className="grid grid-cols-3 gap-3 mb-5">
                  <div className="bg-paper p-4">
                    <div className="label-xs mb-1 text-mist">NEW OPENINGS</div>
                    <div className="font-display text-2xl tabular">{hotspot.new_openings_count}</div>
                  </div>
                  <div className="bg-paper p-4">
                    <div className="label-xs mb-1 text-mist">AVAIL. SPACES</div>
                    <div className="font-display text-2xl tabular">{hotspot.loopnet_active_listings}</div>
                  </div>
                  <div className="bg-paper p-4">
                    <div className="label-xs mb-1 text-mist">PERMIT SCORE</div>
                    <div className="font-display text-2xl tabular">{hotspot.permit_activity_score.toFixed(0)}</div>
                  </div>
                </div>

                {hotspot.trending_categories.length > 0 && (
                  <div className="mb-5">
                    <div className="label-xs mb-2">TRENDING CATEGORIES</div>
                    <div className="flex flex-wrap gap-2">
                      {hotspot.trending_categories.slice(0, 5).map((cat) => (
                        <span key={cat} className="px-3 py-1 bg-paper border border-hairline label-xs text-graphite">
                          {cat.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {hotspot.signals.length > 0 && (
                  <div>
                    <div className="label-xs mb-2">TOP SIGNALS</div>
                    <div className="space-y-2">
                      {hotspot.signals.slice(0, 5).map((s, i) => (
                        <div key={i} className="flex items-center gap-3 py-2 hairline-b last:border-0">
                          <Flame className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" strokeWidth={1.5} />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-ink truncate">{s.title}</div>
                            <div className="label-xs text-mist">{s.source} · {s.recency_days}d ago</div>
                          </div>
                          <div className="font-mono text-sm tabular flex-shrink-0"
                               style={{ color: scoreColor(s.signal_strength * 100) }}>
                            {(s.signal_strength * 100).toFixed(0)}%
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="py-12 text-center text-mist italic font-display text-lg">
                Hotspot data unavailable — TinyFish offline
              </div>
            )}
          </div>

          <div className="col-span-12 lg:col-span-5 card p-6">
            <SectionHead
              eyebrow="INFRASTRUCTURE AMENITY"
              title="Site suitability"
              caption="Power · water · broadband · zoning · development activity"
            />
            {amenity ? (
              <>
                <div className="mb-5">
                  <div className="flex items-baseline justify-between mb-2">
                    <span className="label-xs">OVERALL AMENITY SCORE</span>
                    <span className="font-display text-3xl tabular"
                          style={{ color: scoreColor(amenity.overall_amenity_score) }}>
                      {amenity.overall_amenity_score.toFixed(0)}/100
                    </span>
                  </div>
                  <div className="h-1.5 bg-paper overflow-hidden">
                    <motion.div className="h-full"
                      style={{ background: scoreColor(amenity.overall_amenity_score) }}
                      initial={{ width: 0 }}
                      animate={{ width: `${amenity.overall_amenity_score}%` }}
                      transition={{ duration: 0.8 }}
                    />
                  </div>
                </div>

                <div className="space-y-3 mb-5">
                  {[
                    { label: "⚡ Power Infrastructure", score: amenity.power_infrastructure_score },
                    { label: "💧 Water / Sewer",        score: amenity.water_sewer_score },
                    { label: "🌐 Broadband Reliability", score: amenity.internet_reliability_score },
                    { label: "📋 Zoning Compatibility", score: amenity.zoning_compatibility_score },
                    { label: "🚧 Development Activity", score: amenity.development_activity_score },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center gap-3">
                      <div className="w-44 text-xs text-graphite flex-shrink-0">{item.label}</div>
                      <div className="flex-1 bg-paper h-3 overflow-hidden">
                        <motion.div className="h-full"
                          style={{ background: scoreColor(item.score) }}
                          initial={{ width: 0 }}
                          animate={{ width: `${item.score}%` }}
                          transition={{ duration: 0.7 }}
                        />
                      </div>
                      <div className="font-mono text-xs tabular w-8 text-right"
                           style={{ color: scoreColor(item.score) }}>
                        {item.score.toFixed(0)}
                      </div>
                    </div>
                  ))}
                </div>

                {amenity.available_commercial_spaces > 0 && (
                  <div className="pt-4 hairline-t">
                    <div className="label-xs mb-2">AVAILABLE COMMERCIAL SPACES</div>
                    <div className="font-display text-3xl tabular mb-2">{amenity.available_commercial_spaces}</div>
                    <div className="flex flex-wrap gap-2">
                      {amenity.available_space_types.map((t) => (
                        <span key={t} className="px-2 py-0.5 bg-paper border border-hairline label-xs">
                          {t.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="py-8 text-center text-mist italic font-display text-lg">
                Amenity data unavailable
              </div>
            )}
          </div>
        </div>

        {/* ══ ROW 5 — Demographics + Brand Fit ══ */}
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-7 card p-6">
            <SectionHead
              eyebrow="DEMOGRAPHIC PROFILE"
              title="Trade area composition"
              caption={`${fmtNum(demographics.population, true)} residents · ${fmtNum(demographics.household_count, true)} households`}
            />
            <div className="grid grid-cols-3 gap-4 mb-6">
              {[
                { label: "Population",       value: fmtNum(demographics.population, true) },
                { label: "Median Income",    value: fmtUSD(demographics.median_income) },
                { label: "Median Age",       value: demographics.median_age.toFixed(1) },
                { label: "HH Size",          value: demographics.avg_household_size.toFixed(1) },
                { label: "Pop Growth/yr",    value: `+${demographics.population_growth_est.toFixed(1)}%` },
                { label: "Demand Score",     value: `${demographics.demand_score.toFixed(0)}/100` },
              ].map((d) => (
                <div key={d.label}>
                  <div className="label-xs mb-1">{d.label}</div>
                  <div className="font-display text-xl tabular">{d.value}</div>
                </div>
              ))}
            </div>
            <div className="space-y-2">
              {[
                { label: "Demand Score",   value: demographics.demand_score },
                { label: "Family HH %",   value: demographics.family_households_pct },
                { label: "College Edu %", value: demographics.college_educated_pct },
              ].map((d) => (
                <div key={d.label} className="flex items-center gap-3">
                  <div className="w-28 label-xs text-right flex-shrink-0">{d.label}</div>
                  <div className="flex-1 bg-paper h-4 overflow-hidden">
                    <motion.div className="h-full" style={{ background: "#047857" }}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(d.value, 100)}%` }}
                      transition={{ duration: 0.8 }}
                    />
                  </div>
                  <div className="font-mono text-xs tabular w-10 text-right text-emerald">
                    {d.value.toFixed(1)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="col-span-12 lg:col-span-5 card p-6">
            <SectionHead
              eyebrow="BRAND FIT + NEIGHBORHOOD"
              title={brand_fit.brand}
              caption={brand_fit.recommended_format}
            />
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="bg-paper p-3">
                <div className="label-xs mb-1">FIT SCORE</div>
                <div className="font-display text-2xl tabular"
                     style={{ color: scoreColor(brand_fit.fit_score) }}>
                  {brand_fit.fit_score.toFixed(0)}/100
                </div>
              </div>
              <div className="bg-paper p-3">
                <div className="label-xs mb-1">INCOME ALIGNMENT</div>
                <div className="font-display text-2xl tabular"
                     style={{ color: scoreColor(brand_fit.income_alignment) }}>
                  {brand_fit.income_alignment.toFixed(0)}/100
                </div>
              </div>
            </div>
            <p className="text-sm text-graphite leading-relaxed mb-5">{brand_fit.reasoning}</p>
            <div className="hairline-t pt-4">
              <div className="label-xs mb-3">NEIGHBORHOOD SIGNALS</div>
              <div className="space-y-2">
                {[
                  { label: "School Quality",    score: neighborhood.school_quality_index },
                  { label: "Family Density",    score: neighborhood.family_density_score },
                  { label: "Stability",         score: neighborhood.neighborhood_stability },
                  { label: "Housing Growth",    score: neighborhood.housing_growth_signal },
                  { label: "Overall",           score: neighborhood.overall_score },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-3">
                    <div className="w-28 label-xs text-right flex-shrink-0">{item.label}</div>
                    <div className="flex-1 bg-paper h-3 overflow-hidden">
                      <motion.div className="h-full"
                        style={{ background: scoreColor(item.score) }}
                        initial={{ width: 0 }}
                        animate={{ width: `${item.score}%` }}
                        transition={{ duration: 0.7 }}
                      />
                    </div>
                    <div className="font-mono text-xs tabular w-8 text-right"
                         style={{ color: scoreColor(item.score) }}>
                      {item.score.toFixed(0)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ══ ROW 6 — Competitors + Spatial Map ══ */}
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-4 card p-6">
            <SectionHead
              eyebrow="COMPETITIVE LANDSCAPE"
              title="Competitor summary"
              caption={`${competitors.total_count} stores · ${competitors.big_box_count} big-box`}
            />
            <div className="grid grid-cols-2 gap-3 mb-5">
              {[
                { label: "TOTAL",          value: competitors.total_count,         warn: competitors.total_count > 8 },
                { label: "BIG-BOX",        value: competitors.big_box_count,       warn: competitors.big_box_count > 3 },
                { label: "SAME-CATEGORY",  value: competitors.same_category_count, warn: competitors.same_category_count > 3 },
                { label: "UNDERSERVED?",   value: competitors.underserved ? "Yes" : "No", good: competitors.underserved },
              ].map((d: any) => (
                <div key={d.label} className="bg-paper p-3">
                  <div className="label-xs mb-1">{d.label}</div>
                  <div className="font-display text-2xl tabular"
                       style={{ color: d.good ? "#047857" : d.warn ? "#be123c" : "#0A0A0A" }}>
                    {d.value}
                  </div>
                </div>
              ))}
            </div>
            {[
              { label: "Saturation",        score: 100 - competitors.saturation_score, raw: competitors.saturation_score, invert: true },
              { label: "Demand Signal",     score: competitors.demand_signal_score },
              { label: "Competition Score", score: competitors.competition_score },
            ].map((item) => (
              <div key={item.label} className="mb-3">
                <div className="flex items-baseline justify-between label-xs mb-1">
                  <span>{item.label}</span>
                  <span style={{ color: scoreColor(item.score) }}>{item.score.toFixed(0)}/100</span>
                </div>
                <div className="h-2 bg-paper overflow-hidden">
                  <motion.div className="h-full"
                    style={{ background: scoreColor(item.score) }}
                    initial={{ width: 0 }}
                    animate={{ width: `${item.score}%` }}
                    transition={{ duration: 0.7 }}
                  />
                </div>
              </div>
            ))}

            {competitors.stores.length > 0 && (
              <div className="hairline-t pt-4">
                <div className="label-xs mb-2">NEAREST COMPETITORS</div>
                <div className="divide-y divide-hairline">
                  {competitors.stores.slice(0, 6).map((s: any, i: number) => (
                    <div key={i} className="py-2 flex items-baseline gap-2">
                      <span className="font-mono text-[10px] text-mist w-4">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-ink truncate">{s.brand_name}</div>
                        <div className="label-xs text-mist">{s.store_type}</div>
                      </div>
                      <div className="font-mono text-xs tabular text-graphite">
                        {s.distance_miles.toFixed(1)} mi
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="col-span-12 lg:col-span-8 card overflow-hidden">
            <div className="p-5 hairline-b">
              <SectionHead
                eyebrow="SPATIAL OVERVIEW"
                title="Competitor map"
                caption={`${competitors.total_count} competitors plotted within ${radius_km} km`}
                noMargin
              />
            </div>
            <SpatialMap lat={lat} lon={lon} radius_km={radius_km} competitors={competitors.stores} />
          </div>
        </div>

      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────
function SectionHead({ eyebrow, title, caption, noMargin }: any) {
  return (
    <div className={noMargin ? "" : "mb-6"}>
      <div className="label-xs mb-2">{eyebrow}</div>
      <h3 className="font-display text-2xl tracking-tightest leading-none mb-2">{title}</h3>
      {caption && <div className="text-xs text-slate">{caption}</div>}
    </div>
  );
}

function Kpi({ icon, label, value, sub, border, accent, onSimulate }: any) {
  return (
    <div
      className={`p-6 bg-snow transition-all duration-200 ${border ? "border-l border-hairline" : ""} ${accent ? "cursor-pointer group" : ""}`}
      style={accent ? { position: 'relative' } : undefined}
      onClick={accent && onSimulate ? onSimulate : undefined}
      onMouseEnter={accent ? (e) => {
        (e.currentTarget as HTMLDivElement).style.background = 'rgba(200,168,130,0.06)';
        (e.currentTarget as HTMLDivElement).style.boxShadow = '0 4px 16px rgba(160,120,80,0.12)';
      } : undefined}
      onMouseLeave={accent ? (e) => {
        (e.currentTarget as HTMLDivElement).style.background = '';
        (e.currentTarget as HTMLDivElement).style.boxShadow = '';
      } : undefined}
    >
      <div className="flex items-center gap-2 mb-4 text-graphite">
        {icon}
        <span className="label-xs">{label}</span>
        {accent && (
          <span className="ml-auto label-xs text-mocha opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
            <Play size={8} strokeWidth={2} />simulate
          </span>
        )}
      </div>
      <div className="font-display text-4xl tabular leading-none mb-2">{value}</div>
      <div className="text-xs text-slate">{sub}</div>
    </div>
  );
}

function SpatialMap({ lat, lon, radius_km, competitors }: any) {
  const pinIcon = L.divIcon({
    className: "",
    html: `<div style="width:18px;height:18px;background:#2D6A4F;border:3px solid #FBF7F2;border-radius:9999px;box-shadow:0 0 0 1.5px #2D6A4F,0 8px 18px rgba(0,0,0,0.22)"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });

  return (
    <div className="relative h-[380px] w-full">
      <div className="absolute top-4 right-4 z-[500] bg-snow border border-hairline px-4 py-3 shadow-md">
        <div className="label-xs mb-2">LEGEND</div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-xs text-graphite">
            <div className="w-3 h-3 rounded-full bg-emerald flex-shrink-0" />
            Your pin
          </div>
          <div className="flex items-center gap-2 text-xs text-graphite">
            <div className="w-2 h-2 rounded-full bg-ink flex-shrink-0" />
            Competitors ({competitors?.length || 0})
          </div>
        </div>
      </div>

      <MapContainer center={[lat, lon]} zoom={11} scrollWheelZoom={true} className="h-full w-full">
        <TileLayer attribution="" url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
        <Circle
          center={[lat, lon]}
          radius={radius_km * 1000}
          pathOptions={{ color: "#2D6A4F", weight: 1.5, fillColor: "#2D6A4F", fillOpacity: 0.05 }}
        />
        <Marker position={[lat, lon]} icon={pinIcon}>
          <LeafletTooltip direction="top" offset={[0, -10]} opacity={1} className="atlas-tooltip">
            <div className="label-xs mb-1">YOUR PIN</div>
            <div className="font-display text-base">{fmtCoord(lat)}, {fmtCoord(lon)}</div>
          </LeafletTooltip>
        </Marker>
        {competitors?.slice(0, 200).map((c: any, i: number) => (
          <CircleMarker
            key={`c-${i}`}
            center={[c.lat, c.lng]}
            radius={5}
            pathOptions={{ color: "#2C1810", weight: 1.5, fillColor: "#5C3D1E", fillOpacity: 0.8 }}
            eventHandlers={{
              mouseover: (e) => e.target.setStyle({ radius: 8, fillOpacity: 1, color: "#A07850" }),
              mouseout:  (e) => e.target.setStyle({ radius: 5, fillOpacity: 0.8, color: "#2C1810" }),
            }}
          >
            <LeafletTooltip direction="top" offset={[0, -6]} className="atlas-tooltip">
              <div className="label-xs mb-1">COMPETITOR</div>
              <div className="font-display text-base leading-tight">{c.brand_name || "Unnamed"}</div>
              <div className="text-xs text-graphite">{c.store_type} · {Number(c.distance_miles || 0).toFixed(1)} mi</div>
            </LeafletTooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
