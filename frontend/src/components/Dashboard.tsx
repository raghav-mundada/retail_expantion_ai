import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip,
  RadialBarChart, RadialBar, PolarAngleAxis, Cell,
} from "recharts";
import { ArrowUpRight, Sparkles, MapPin, Building2, Users, TrendingUp } from "lucide-react";
import { MapContainer, TileLayer, Marker, Circle, CircleMarker, Tooltip as LeafletTooltip } from "react-leaflet";
import L from "leaflet";

import {
  getRun, getDemographics, getCompetitors, getTraffic, getSchools, getNeighborhoods,
} from "../lib/api";
import { fmtNum, fmtUSD, fmtPctRaw, fmtCoord } from "../lib/format";

interface Props {
  runId: string;
  lat: number;
  lon: number;
  radius_km: number;
  onAskOracle: () => void;
}

export function Dashboard({ runId, lat, lon, radius_km, onAskOracle }: Props) {
  const [run, setRun]                   = useState<any>(null);
  const [demographics, setDemographics] = useState<any>(null);
  const [competitors, setCompetitors]   = useState<any[]>([]);
  const [traffic, setTraffic]           = useState<any>(null);
  const [schools, setSchools]           = useState<any[]>([]);
  const [neighborhoods, setNeighborhoods] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      getRun(runId).then(setRun),
      getDemographics(runId).then(setDemographics),
      getCompetitors(runId).then(setCompetitors),
      getTraffic(runId).then(setTraffic),
      getSchools(runId).then(setSchools),
      getNeighborhoods(runId).then(setNeighborhoods),
    ]).catch(console.error);
  }, [runId]);

  if (!run || !demographics) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center">
        <div className="font-display text-2xl italic text-mist animate-pulse">Loading dashboard…</div>
      </div>
    );
  }

  const summary = demographics.summary?.[0] || {};
  const tracts  = demographics.tracts || [];
  const trafSum = traffic?.summary?.[0] || {};
  const trafPts = traffic?.points || [];

  return (
    <div className="bg-paper min-h-[calc(100vh-4rem)]">
      <PageHero
        lat={lat} lon={lon} radius_km={radius_km}
        population={summary.total_population || 0}
        households={summary.total_households || 0}
        onAskOracle={onAskOracle}
      />

      <div className="px-6 lg:px-10 py-10 max-w-[1500px] mx-auto space-y-6">

        {/* ═════════ ROW 1 — KPI Strip ═════════ */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-0 hairline">
          <Kpi
            icon={<Users className="w-3.5 h-3.5" strokeWidth={1.5} />}
            label="POPULATION"
            value={fmtNum(summary.total_population || 0, true)}
            sub={`${summary.tract_count} census tracts`}
          />
          <Kpi
            icon={<Building2 className="w-3.5 h-3.5" strokeWidth={1.5} />}
            label="HOUSEHOLDS"
            value={fmtNum(summary.total_households || 0, true)}
            sub={`${fmtPctRaw((summary.avg_owner_share || 0) * 100, 0)} owner-occupied`}
            border
          />
          <Kpi
            icon={<TrendingUp className="w-3.5 h-3.5" strokeWidth={1.5} />}
            label="MEDIAN HH INCOME"
            value={fmtUSD(summary.median_hh_income_avg || 0)}
            sub={`${fmtPctRaw((summary.avg_poverty_rate || 0) * 100, 1)} poverty rate`}
            border
          />
          <Kpi
            icon={<MapPin className="w-3.5 h-3.5" strokeWidth={1.5} />}
            label="AVG DAILY TRAFFIC"
            value={fmtNum(trafSum.avg_aadt || 0, true)}
            sub={`Peak ${fmtNum(trafSum.max_aadt || 0, true)} AADT`}
            border
          />
        </div>

        {/* ═════════ ROW 2 — Income distribution + Top competitors ═════════ */}
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8 card p-6">
            <SectionHead
              eyebrow="DEMOGRAPHIC SIGNAL"
              title="Income distribution by tract"
              caption={`${tracts.length} census tracts plotted by median household income`}
            />
            <IncomeChart tracts={tracts} />
          </div>

          <div className="col-span-12 lg:col-span-4 card p-6">
            <SectionHead
              eyebrow="COMPETITIVE LANDSCAPE"
              title="Nearest rivals"
              caption={`${competitors.length} stores within ${radius_km} km`}
            />
            <CompetitorList competitors={competitors.slice(0, 7)} />
          </div>
        </div>

        {/* ═════════ ROW 3 — Traffic + Format mix ═════════ */}
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-7 card p-6">
            <SectionHead
              eyebrow="MOBILITY"
              title="Top 10 traffic arteries"
              caption="Annual Average Daily Traffic — MnDOT 2023"
            />
            <TrafficChart points={trafPts.slice(0, 10)} />
          </div>

          <div className="col-span-12 lg:col-span-5 card p-6">
            <SectionHead
              eyebrow="MARKET COMPOSITION"
              title="Competitor format mix"
              caption="Where the dollars currently go"
            />
            <FormatMix competitors={competitors} />
          </div>
        </div>

        {/* ═════════ ROW 4 — Spatial overview map ═════════ */}
        <div className="card overflow-hidden">
          <div className="p-6 hairline-b">
            <SectionHead
              eyebrow="SPATIAL OVERVIEW"
              title="Everything inside the radius"
              caption={`${competitors.length} competitors · ${schools.length} schools · ${neighborhoods.length} neighborhoods`}
              noMargin
            />
          </div>
          <SpatialMap
            lat={lat} lon={lon} radius_km={radius_km}
            competitors={competitors}
            schools={schools}
            neighborhoods={neighborhoods}
          />
        </div>

        {/* ═════════ ROW 5 — Neighborhood strip ═════════ */}
        <div className="card p-6">
          <SectionHead
            eyebrow="LOCAL CONTEXT"
            title={`Neighborhoods inside the ${radius_km} km radius`}
            caption={`${neighborhoods.length} hoods sorted by distance from your pin`}
          />
          <NeighborhoodStrip neighborhoods={neighborhoods.slice(0, 24)} />
        </div>

      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// HERO BAR
// ─────────────────────────────────────────────────────────────────────────────
function PageHero({ lat, lon, radius_km, population, households, onAskOracle }: any) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="hairline-b bg-snow"
    >
      <div className="px-6 lg:px-10 py-10 max-w-[1500px] mx-auto grid grid-cols-12 gap-6 items-end">
        <div className="col-span-12 lg:col-span-7">
          <div className="label-xs mb-4">CHAPTER THREE — INSPECT</div>
          <h1 className="display-lg mb-3">
            A <em className="italic">{fmtNum(population, true)}</em>-person market <br/>
            within {radius_km} km.
          </h1>
          <p className="text-graphite max-w-2xl text-sm leading-relaxed">
            Pin · {fmtCoord(lat)}, {fmtCoord(lon)} · {fmtNum(households, true)} households ·
            data refreshed live from six independent systems.
          </p>
        </div>

        <div className="col-span-12 lg:col-span-5 flex lg:justify-end">
          <button
            onClick={onAskOracle}
            className="group relative bg-ink text-snow px-7 py-5 flex items-center gap-3
                       hover:bg-graphite transition-colors"
          >
            <Sparkles className="w-4 h-4" strokeWidth={1.5} />
            <div className="text-left">
              <div className="text-sm font-medium">Get AI Recommendation</div>
              <div className="label-xs text-mist mt-0.5">BULL · BEAR · ORCHESTRATOR</div>
            </div>
            <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" strokeWidth={1.5} />
          </button>
        </div>
      </div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// COMPONENTS — Section heads, KPI cards
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

function Kpi({ icon, label, value, sub, border }: any) {
  return (
    <div className={`p-6 bg-snow ${border ? "border-l border-hairline" : ""}`}>
      <div className="flex items-center gap-2 mb-4 text-graphite">
        {icon}
        <span className="label-xs">{label}</span>
      </div>
      <div className="font-display text-4xl tabular leading-none mb-2">{value}</div>
      <div className="text-xs text-slate">{sub}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CHART: Income distribution
// ─────────────────────────────────────────────────────────────────────────────
function IncomeChart({ tracts }: { tracts: any[] }) {
  const buckets = [
    { range: "<$30K",     min: 0,      max: 30000  },
    { range: "$30–60K",   min: 30000,  max: 60000  },
    { range: "$60–90K",   min: 60000,  max: 90000  },
    { range: "$90–120K",  min: 90000,  max: 120000 },
    { range: "$120–150K", min: 120000, max: 150000 },
    { range: "$150K+",    min: 150000, max: 1e9    },
  ];
  const data = buckets.map((b) => {
    const matched = tracts.filter((t) => (t.median_hh_income || 0) >= b.min && (t.median_hh_income || 0) < b.max);
    return {
      range: b.range,
      tracts: matched.length,
      households: matched.reduce((s, t) => s + (t.total_households || 0), 0),
      population: matched.reduce((s, t) => s + (t.total_population || 0), 0),
    };
  });

  const maxIx = data.reduce((m, d, i) => (d.tracts > data[m].tracts ? i : m), 0);
  const colors = data.map((_, i) => i === maxIx ? "#047857" : "#0A0A0A");

  return (
    <div>
      <div className="flex items-center gap-4 mb-4 label-xs">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 bg-emerald" /> DOMINANT BAND</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 bg-ink" /> OTHER BANDS</span>
        <span className="text-mist ml-auto">Y-AXIS = NUMBER OF CENSUS TRACTS</span>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 16, right: 8, bottom: 8, left: 0 }}>
            <defs>
              <linearGradient id="emeraldGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#047857" stopOpacity={1} />
                <stop offset="100%" stopColor="#047857" stopOpacity={0.7} />
              </linearGradient>
              <linearGradient id="inkGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0A0A0A" stopOpacity={0.95} />
                <stop offset="100%" stopColor="#0A0A0A" stopOpacity={0.65} />
              </linearGradient>
            </defs>
            <XAxis dataKey="range" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#71717A", fontFamily: "Geist Mono" }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#A1A1AA", fontFamily: "Geist Mono" }} width={36} allowDecimals={false}
              label={{ value: "TRACTS", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#A1A1AA", fontFamily: "Geist Mono", letterSpacing: "0.16em" } }}
            />
            <Tooltip cursor={{ fill: "#F5F5F4" }} content={<IncomeTooltip />} />
            <Bar dataKey="tracts" radius={0} maxBarSize={80} animationDuration={1100} animationEasing="ease-out">
              {data.map((_, i) => (
                <Cell key={i} fill={colors[i] === "#047857" ? "url(#emeraldGrad)" : "url(#inkGrad)"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function IncomeTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-snow border border-hairline shadow-lg p-4 min-w-[200px]">
      <div className="label-xs mb-3">{label} INCOME BAND</div>
      <div className="space-y-2">
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-graphite">Census tracts</span>
          <span className="font-display text-2xl tabular leading-none text-emerald">{d.tracts}</span>
        </div>
        <div className="flex items-baseline justify-between hairline-t pt-2">
          <span className="text-xs text-graphite">Households</span>
          <span className="font-mono text-sm tabular">{d.households.toLocaleString()}</span>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-graphite">Population</span>
          <span className="font-mono text-sm tabular">{d.population.toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CHART: Traffic AADT bar
// ─────────────────────────────────────────────────────────────────────────────
function TrafficChart({ points }: { points: any[] }) {
  const data = points
    .filter((p) => p.street_name && p.street_name !== "nan" && (p.aadt || 0) > 0)
    .map((p) => ({ name: p.street_name.slice(0, 24), aadt: p.aadt }));
  const max = Math.max(...data.map((d) => d.aadt), 1);

  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <defs>
            <linearGradient id="trafficGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#047857" stopOpacity={0.85} />
              <stop offset="100%" stopColor="#0F766E" stopOpacity={1} />
            </linearGradient>
          </defs>
          <XAxis type="number" axisLine={false} tickLine={false}
            tick={{ fontSize: 10, fill: "#A1A1AA", fontFamily: "Geist Mono" }}
            tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}
          />
          <YAxis dataKey="name" type="category" axisLine={false} tickLine={false}
            tick={{ fontSize: 11, fill: "#3F3F46" }} width={150}
          />
          <Tooltip cursor={{ fill: "#F5F5F4" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div className="bg-snow border border-hairline shadow-lg p-3 min-w-[180px]">
                  <div className="label-xs mb-1.5">{d.name}</div>
                  <div className="font-display text-2xl tabular leading-none text-emerald">{d.aadt.toLocaleString()}</div>
                  <div className="text-[10px] text-graphite mt-0.5">vehicles per day</div>
                  <div className="text-[10px] text-mist mt-1.5">{((d.aadt / max) * 100).toFixed(0)}% of peak artery</div>
                </div>
              );
            }}
          />
          <Bar dataKey="aadt" fill="url(#trafficGrad)" radius={0} maxBarSize={20} animationDuration={1200} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// COMPETITOR LIST
// ─────────────────────────────────────────────────────────────────────────────
function CompetitorList({ competitors }: { competitors: any[] }) {
  return (
    <div className="divide-y divide-hairline">
      {competitors.map((c, i) => (
        <div key={i} className="py-3 flex items-baseline gap-3">
          <span className="font-mono text-[10px] tabular text-mist w-5">{String(i + 1).padStart(2, "0")}</span>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-ink truncate">{c.name || "—"}</div>
            <div className="label-xs mt-0.5">{c.shop_type || "store"}</div>
          </div>
          <div className="font-mono text-sm tabular text-emerald">{Number(c.dist_km || 0).toFixed(2)} km</div>
        </div>
      ))}
      {competitors.length === 0 && (
        <div className="py-8 text-center text-mist italic font-display text-lg">No competitors found in this radius.</div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FORMAT MIX — radial chart
// ─────────────────────────────────────────────────────────────────────────────
function FormatMix({ competitors }: { competitors: any[] }) {
  const counts: Record<string, number> = {};
  for (const c of competitors) {
    const k = c.shop_type || "other";
    counts[k] = (counts[k] || 0) + 1;
  }
  const top = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, count], i) => ({
      name, count,
      fill: ["#0A0A0A", "#047857", "#3F3F46", "#71717A", "#A1A1AA", "#D4D4D8"][i],
    }));
  const max = Math.max(...top.map((t) => t.count), 1);

  return (
    <div className="grid grid-cols-2 gap-6 items-center">
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart innerRadius="30%" outerRadius="100%" data={top} startAngle={90} endAngle={-270}>
            <PolarAngleAxis type="number" domain={[0, max]} tick={false} />
            <RadialBar background={{ fill: "#F5F5F4" }} dataKey="count" cornerRadius={0} />
          </RadialBarChart>
        </ResponsiveContainer>
      </div>
      <div className="space-y-2.5">
        {top.map((t) => (
          <div key={t.name} className="flex items-baseline gap-2 text-sm">
            <span className="w-2 h-2" style={{ background: t.fill }} />
            <span className="text-ink truncate flex-1">{t.name}</span>
            <span className="font-mono tabular text-graphite">{t.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SPATIAL MAP
// ─────────────────────────────────────────────────────────────────────────────
function SpatialMap({ lat, lon, radius_km, competitors, schools, neighborhoods }: any) {
  const pinIcon = L.divIcon({
    className: "",
    html: `<div style="width:18px;height:18px;background:#047857;border:3px solid white;border-radius:9999px;box-shadow:0 0 0 1.5px #047857, 0 8px 18px rgba(0,0,0,0.25)"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });

  return (
    <div className="relative h-[520px] w-full">
      {/* Dynamic legend — only shows categories with data */}
      <div className="absolute top-4 right-4 z-[500] bg-snow border border-hairline px-4 py-3 shadow-md">
        <div className="label-xs mb-2.5">LEGEND</div>
        <div className="space-y-1.5">
          <LegendItem color="#047857" label="Your pin" size={10} ring />
          {competitors.length > 0 && (
            <LegendItem color="#0A0A0A" label={`Competitors (${competitors.length})`} size={6} />
          )}
          {(schools?.length ?? 0) > 0 && (
            <LegendItem color="#B45309" label={`Schools (${schools.length})`} size={5} />
          )}
          {(neighborhoods?.length ?? 0) > 0 && (
            <LegendItem color="#1E40AF" label={`Neighborhoods (${neighborhoods.length})`} size={4} />
          )}
        </div>
      </div>

      <MapContainer center={[lat, lon]} zoom={13} scrollWheelZoom={true} className="h-full w-full">
        <TileLayer attribution="" url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
        <Circle center={[lat, lon]} radius={radius_km * 1000}
          pathOptions={{ color: "#047857", weight: 1.5, fillColor: "#047857", fillOpacity: 0.05 }}
        />
        <Marker position={[lat, lon]} icon={pinIcon}>
          <LeafletTooltip direction="top" offset={[0, -10]} opacity={1} className="atlas-tooltip">
            <div className="font-mono text-[10px] uppercase tracking-wider text-mist mb-1">YOUR PIN</div>
            <div className="font-display text-base">{fmtCoord(lat)}, {fmtCoord(lon)}</div>
            <div className="text-xs text-graphite">{radius_km} km radius</div>
          </LeafletTooltip>
        </Marker>

        {competitors.slice(0, 200).map((c: any, i: number) => (
          <CircleMarker key={`c-${i}`} center={[c.lat, c.lon]} radius={5}
            pathOptions={{ color: "#0A0A0A", weight: 1.5, fillColor: "#0A0A0A", fillOpacity: 0.85 }}
            eventHandlers={{
              mouseover: (e) => e.target.setStyle({ radius: 8, fillOpacity: 1, color: "#047857" }),
              mouseout:  (e) => e.target.setStyle({ radius: 5, fillOpacity: 0.85, color: "#0A0A0A" }),
            }}
          >
            <LeafletTooltip direction="top" offset={[0, -6]} className="atlas-tooltip">
              <div className="font-mono text-[10px] uppercase tracking-wider text-mist mb-1">COMPETITOR</div>
              <div className="font-display text-base leading-tight">{c.name || "Unnamed"}</div>
              <div className="text-xs text-graphite">{c.shop_type || "store"} · {Number(c.dist_km || 0).toFixed(2)} km</div>
              {c.address && <div className="text-[10px] text-mist mt-1 max-w-[200px]">{c.address}</div>}
            </LeafletTooltip>
          </CircleMarker>
        ))}

        {schools?.slice(0, 200).map((s: any, i: number) => (
          <CircleMarker key={`s-${i}`} center={[s.lat, s.lon]} radius={4}
            pathOptions={{ color: "#B45309", weight: 1, fillColor: "#B45309", fillOpacity: 0.7 }}
            eventHandlers={{
              mouseover: (e) => e.target.setStyle({ radius: 7, fillOpacity: 1 }),
              mouseout:  (e) => e.target.setStyle({ radius: 4, fillOpacity: 0.7 }),
            }}
          >
            <LeafletTooltip direction="top" offset={[0, -6]} className="atlas-tooltip">
              <div className="font-mono text-[10px] uppercase tracking-wider text-mist mb-1">SCHOOL</div>
              <div className="font-display text-base leading-tight">{s.name || "Unnamed"}</div>
              <div className="text-xs text-graphite">{s.amenity_type || "school"} · {Number(s.dist_km || 0).toFixed(2)} km</div>
            </LeafletTooltip>
          </CircleMarker>
        ))}

        {neighborhoods?.slice(0, 80).map((n: any, i: number) => (
          <CircleMarker key={`n-${i}`} center={[n.centroid_lat, n.centroid_lon]} radius={6}
            pathOptions={{ color: "#1E40AF", weight: 2, fillColor: "#1E40AF", fillOpacity: 0.15 }}
            eventHandlers={{
              mouseover: (e) => e.target.setStyle({ radius: 10, fillOpacity: 0.4 }),
              mouseout:  (e) => e.target.setStyle({ radius: 6, fillOpacity: 0.15 }),
            }}
          >
            <LeafletTooltip direction="top" offset={[0, -8]} className="atlas-tooltip" permanent={false}>
              <div className="font-mono text-[10px] uppercase tracking-wider text-mist mb-1">NEIGHBORHOOD</div>
              <div className="font-display text-base leading-tight">{n.neighborhood_name}</div>
              <div className="text-xs text-graphite">{Number(n.dist_km || 0).toFixed(2)} km from pin</div>
            </LeafletTooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}

function LegendItem({ color, label, size, ring }: any) {
  return (
    <div className="flex items-center gap-2.5 text-xs text-graphite">
      <div className="rounded-full flex-shrink-0" style={{
        width: size, height: size, background: color,
        boxShadow: ring ? `0 0 0 2px white, 0 0 0 3px ${color}` : "none",
      }} />
      {label}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// NEIGHBORHOOD STRIP
// ─────────────────────────────────────────────────────────────────────────────
function NeighborhoodStrip({ neighborhoods }: { neighborhoods: any[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-x-6 gap-y-3">
      {neighborhoods.map((n, i) => (
        <div key={i} className="flex items-baseline gap-2 text-sm">
          <span className="font-mono text-[10px] tabular text-mist">{String(i + 1).padStart(2, "0")}</span>
          <span className="text-ink truncate flex-1">{n.neighborhood_name}</span>
          <span className="font-mono text-xs tabular text-slate">{Number(n.dist_km || 0).toFixed(1)}km</span>
        </div>
      ))}
    </div>
  );
}