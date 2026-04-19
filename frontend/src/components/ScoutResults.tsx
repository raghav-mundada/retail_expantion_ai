import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MapContainer, TileLayer, Marker, Tooltip, Circle } from "react-leaflet";
import L from "leaflet";
import {
  ArrowRight, X, Trophy, Users, DollarSign, School, Target as TargetIcon, Crosshair,
} from "lucide-react";

import type { ScoutResponse, ScoutCandidate } from "../lib/api";
import { fmtUSD, fmtNum } from "../lib/format";

interface Props {
  data: ScoutResponse;
  onDeepDive: (candidate: ScoutCandidate) => void;
  onReset: () => void;
}

// ── Map icons ────────────────────────────────────────────────────────────────
const anchorIcon = L.divIcon({
  className: "",
  html: `<div style="width:14px;height:14px;background:white;border:2px solid #0A0A0A;transform:rotate(45deg);box-shadow:0 6px 14px rgba(0,0,0,0.18)"></div>`,
  iconSize:   [14, 14],
  iconAnchor: [7, 7],
});

function candidateIcon(rank: number, active: boolean) {
  const size   = active ? 36 : 30;
  const bg     = active ? "#047857" : "#FFFFFF";
  const fg     = active ? "#FFFFFF" : "#047857";
  return L.divIcon({
    className: "",
    html: `<div style="width:${size}px;height:${size}px;background:${bg};color:${fg};border:2px solid #047857;border-radius:9999px;display:flex;align-items:center;justify-content:center;font-family:'Geist',system-ui,sans-serif;font-weight:600;font-size:${active ? 14 : 12}px;box-shadow:0 8px 20px rgba(0,0,0,0.18);transition:all .18s ease">${rank}</div>`,
    iconSize:   [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// ── Component ────────────────────────────────────────────────────────────────
export function ScoutResults({ data, onDeepDive, onReset }: Props) {
  const [activeRank, setActiveRank] = useState<number>(1);
  const active = data.candidates.find((c) => c.rank === activeRank) ?? data.candidates[0];

  const center: [number, number] = [data.search.lat, data.search.lon];
  const radiusM = data.search.radius_km * 1000;

  // tight map bounds so panning doesn't drift past the search circle
  const bounds = useMemo<L.LatLngBoundsLiteral>(() => {
    const degPerKm = 1 / 111;
    const pad = data.search.radius_km * degPerKm * 1.5;
    return [
      [data.search.lat - pad, data.search.lon - pad],
      [data.search.lat + pad, data.search.lon + pad],
    ];
  }, [data.search.lat, data.search.lon, data.search.radius_km]);

  if (data.candidates.length === 0) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center px-6">
        <div className="max-w-md text-center bg-snow border border-hairline p-10">
          <div className="label-xs mb-4">SCOUT RESULT</div>
          <h2 className="display-md mb-3">No viable tracts found.</h2>
          <p className="text-sm text-graphite leading-relaxed mb-6">
            We scored {data.summary.tracts_considered} census tracts inside this area,
            but {data.summary.valid_tracts} had enough ACS data to evaluate — and none
            cleared the {data.store_format} viability bar. Try expanding the radius or
            picking a different anchor.
          </p>
          <button onClick={onReset} className="btn-secondary w-full">Pick a different area</button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-[calc(100vh-4rem)] w-full overflow-hidden bg-paper">
      {/* ── Map ─────────────────────────────────────────────────────── */}
      <MapContainer
        center={center}
        zoom={12}
        minZoom={10}
        maxZoom={16}
        maxBounds={bounds}
        maxBoundsViscosity={1}
        zoomControl={true}
        scrollWheelZoom={true}
        className="h-full w-full"
      >
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />

        <Circle
          center={center}
          radius={radiusM}
          pathOptions={{ color: "#0A0A0A", weight: 1.2, dashArray: "4 4", fillColor: "#0A0A0A", fillOpacity: 0.025 }}
        />
        <Marker position={center} icon={anchorIcon}>
          <Tooltip className="atlas-tooltip" direction="top" offset={[0, -8]}>
            <strong>Search anchor</strong><br />
            {data.search.radius_km.toFixed(1)} km radius
          </Tooltip>
        </Marker>

        {data.candidates.map((c) => (
          <Marker
            key={c.rank}
            position={[c.lat, c.lng]}
            icon={candidateIcon(c.rank, c.rank === activeRank)}
            eventHandlers={{ click: () => setActiveRank(c.rank) }}
          >
            <Tooltip
              className="atlas-tooltip"
              direction="top"
              offset={[0, -16]}
              permanent={c.rank === activeRank}
            >
              <strong>#{c.rank} · {c.nearest_tract}</strong>
              <br />
              <span style={{ color: "#52525B" }}>score {c.density_score.toFixed(3)}</span>
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>

      {/* ── Header strip ───────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="absolute top-6 left-6 z-[1000] bg-snow border border-hairline px-5 py-3 shadow-[0_24px_60px_-30px_rgba(0,0,0,0.18)]"
      >
        <div className="flex items-center gap-3">
          <Trophy className="w-4 h-4 text-emerald" strokeWidth={1.5} />
          <div>
            <div className="label-xs">TOP {data.candidates.length} TARGETS · K-MEANS</div>
            <div className="text-sm font-medium text-ink">
              Best sites for <em className="font-display italic">{data.store_format}</em>
              <span className="text-graphite font-normal">
                {" "}· {fmtNum(data.summary.valid_tracts)} of {fmtNum(data.summary.tracts_considered)} tracts scored
              </span>
            </div>
          </div>
        </div>
      </motion.div>

      <button
        onClick={onReset}
        className="absolute top-6 right-6 z-[1000] bg-snow border border-hairline px-3 py-2 hover:bg-bone transition flex items-center gap-2"
        title="Reset"
      >
        <X className="w-3.5 h-3.5 text-graphite" strokeWidth={1.5} />
        <span className="label-xs">RESET</span>
      </button>

      {/* ── Right panel — ranked list ─────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="absolute top-6 right-6 mt-14 w-[440px] z-[999] max-h-[calc(100vh-7rem)] overflow-hidden flex flex-col bg-snow border border-hairline shadow-[0_24px_60px_-30px_rgba(0,0,0,0.22)]"
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={active.rank}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="p-6 hairline-b"
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="label-xs mb-1">RANK #{active.rank} · {data.store_format.toUpperCase()}</div>
                <div className="display-md leading-none mb-2">
                  Density{" "}
                  <span className="text-emerald">{active.density_score.toFixed(3)}</span>
                </div>
                <div className="text-sm text-ink font-medium leading-tight">
                  {active.nearest_tract}
                </div>
                <div className="text-xs text-graphite mt-1">
                  {active.lat.toFixed(4)}°, {active.lng.toFixed(4)}°
                </div>
              </div>
              <div className="bg-emerald/10 px-2 py-1 border border-emerald/30">
                <div className="label-xs text-emerald">TOP {active.rank}</div>
              </div>
            </div>

            {/* Key stats row */}
            <div className="grid grid-cols-3 gap-3 mt-4">
              <Stat
                icon={<Users className="w-3 h-3" strokeWidth={1.5} />}
                label="POPULATION"
                value={fmtNum(active.population, true)}
              />
              <Stat
                icon={<DollarSign className="w-3 h-3" strokeWidth={1.5} />}
                label="MEDIAN HHI"
                value={fmtUSD(active.median_income)}
              />
              <Stat
                icon={<School className="w-3 h-3" strokeWidth={1.5} />}
                label="SCHOOLS 2KM"
                value={active.school_count_2km.toString()}
              />
            </div>

            {/* Competitor / traffic context */}
            <div className="mt-5 grid grid-cols-2 gap-3 text-[11px]">
              <div>
                <div className="label-xs mb-0.5">NEAREST DIRECT RIVAL</div>
                <div className="text-ink leading-tight">
                  {active.nearest_comp_km !== null
                    ? `${active.nearest_comp_km.toFixed(2)} km away`
                    : "no rivals nearby"}
                </div>
              </div>
              <div>
                <div className="label-xs mb-0.5">TRAFFIC PROXY</div>
                <div className="text-ink leading-tight">{fmtNum(active.avg_traffic_aadt)}</div>
                <div className="text-graphite">AADT estimate</div>
              </div>
            </div>

            {/* Why it wins */}
            {active.why_it_wins?.length > 0 && (
              <div className="mt-5">
                <div className="label-xs mb-2">WHY IT RANKS</div>
                <ul className="space-y-1.5">
                  {active.why_it_wins.map((r: string, i: number) => (
                    <li key={i} className="flex items-start gap-2 text-[12px] text-graphite leading-relaxed">
                      <TargetIcon className="w-3 h-3 mt-[3px] text-emerald shrink-0" strokeWidth={1.5} />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <button
              onClick={() => onDeepDive(active)}
              className="mt-6 w-full bg-ink text-snow py-4 px-5 flex items-center justify-between transition-all duration-300 hover:bg-graphite group"
            >
              <span className="text-sm font-medium tracking-snug">Run deep dive on this site</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" strokeWidth={1.5} />
            </button>
          </motion.div>
        </AnimatePresence>

        <div className="flex-1 overflow-y-auto">
          <div className="px-6 pt-5 pb-2">
            <div className="label-xs">ALL CANDIDATES</div>
          </div>
          {data.candidates.map((c) => (
            <button
              key={c.rank}
              onClick={() => setActiveRank(c.rank)}
              className={`w-full text-left px-6 py-3 hairline-b last:border-b-0 transition flex items-center gap-3
                          ${c.rank === activeRank ? "bg-bone" : "hover:bg-bone/50"}`}
            >
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium border-2 shrink-0
                               ${c.rank === activeRank
                                 ? "bg-emerald text-snow border-emerald"
                                 : "bg-snow text-emerald border-emerald"}`}>
                {c.rank}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-ink font-medium truncate">{c.nearest_tract}</div>
                <div className="text-[11px] text-graphite">
                  {fmtNum(c.population, true)} pop · {fmtUSD(c.median_income)}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-display text-xl tabular text-ink leading-none">
                  {c.density_score.toFixed(2)}
                </div>
                <div className="label-xs">DENSITY</div>
              </div>
            </button>
          ))}
        </div>
      </motion.div>

      <div className="absolute bottom-6 left-6 z-[1000] bg-paper/85 backdrop-blur-sm px-3 py-2 flex items-center gap-3 text-graphite">
        <Crosshair className="w-3.5 h-3.5" strokeWidth={1.5} />
        <span className="label-xs">
          ANCHOR {data.search.lat.toFixed(3)}, {data.search.lon.toFixed(3)} · {data.search.radius_km.toFixed(1)} KM
          · {data.summary.rivals_considered ?? 0} RIVALS · {data.summary.schools ?? 0} SCHOOLS
        </span>
      </div>
    </div>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-bone/50 px-3 py-2.5 border border-hairline">
      <div className="flex items-center gap-1 text-graphite mb-1">
        {icon}
        <span className="label-xs">{label}</span>
      </div>
      <div className="font-mono text-sm text-ink tabular">{value}</div>
    </div>
  );
}
