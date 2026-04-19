import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MapContainer, TileLayer, Marker, Tooltip, Circle } from "react-leaflet";
import L from "leaflet";
import { ArrowRight, X, Trophy, TrendingUp, Users, DollarSign, Crosshair } from "lucide-react";

import type { ScoutResponse, ScoutCandidate } from "../lib/api";
import { fmtUSD, fmtNum } from "../lib/format";

const MPLS_BOUNDS: L.LatLngBoundsLiteral = [[44.85, -93.40], [45.10, -93.10]];

// Anchor pin (search center) — outlined diamond
const anchorIcon = L.divIcon({
  className: "",
  html: `<div style="
    width: 14px; height: 14px;
    background: white;
    border: 2px solid #0A0A0A;
    transform: rotate(45deg);
    box-shadow: 0 6px 14px rgba(0,0,0,0.18);
  "></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

// Candidate pin — numbered emerald medallion
function candidateIcon(rank: number, active: boolean) {
  const size = active ? 36 : 30;
  const bg   = active ? "#047857" : "#FFFFFF";
  const fg   = active ? "#FFFFFF" : "#047857";
  const border = "#047857";
  return L.divIcon({
    className: "",
    html: `<div style="
      width:${size}px; height:${size}px;
      background:${bg};
      color:${fg};
      border: 2px solid ${border};
      border-radius: 9999px;
      display:flex; align-items:center; justify-content:center;
      font-family: 'Geist', system-ui, sans-serif;
      font-weight: 600;
      font-size: ${active ? 14 : 12}px;
      box-shadow: 0 8px 20px rgba(0,0,0,0.18);
      transition: all 0.18s ease;
    ">${rank}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

interface Props {
  data: ScoutResponse;
  onDeepDive: (candidate: ScoutCandidate) => void;
  onReset: () => void;
}

export function ScoutResults({ data, onDeepDive, onReset }: Props) {
  const [activeRank, setActiveRank] = useState<number>(1);
  const active = data.candidates.find((c) => c.rank === activeRank) ?? data.candidates[0];

  // map fits the search circle
  const center: [number, number] = [data.search.lat, data.search.lon];
  const radiusM = data.search.radius_km * 1000;

  if (data.candidates.length === 0) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center px-6">
        <div className="max-w-md text-center bg-snow border border-hairline p-10">
          <div className="label-xs mb-4">SCOUT RESULT</div>
          <h2 className="display-md mb-3">No retail-compatible parcels.</h2>
          <p className="text-sm text-graphite leading-relaxed mb-6">
            We found {data.summary.parcels_in_box} parcels inside this area, but
            none meet the minimum {data.summary.min_acres_filter} acre footprint
            for a {data.store_format}.
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
        zoom={13}
        minZoom={11}
        maxZoom={16}
        maxBounds={MPLS_BOUNDS}
        maxBoundsViscosity={1}
        zoomControl={true}
        scrollWheelZoom={true}
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />

        {/* Search area */}
        <Circle
          center={center}
          radius={radiusM}
          pathOptions={{
            color: "#0A0A0A",
            weight: 1.2,
            dashArray: "4 4",
            fillColor: "#0A0A0A",
            fillOpacity: 0.025,
          }}
        />
        <Marker position={center} icon={anchorIcon}>
          <Tooltip className="atlas-tooltip" direction="top" offset={[0, -8]}>
            <strong>Search Anchor</strong>
            <br />
            {data.search.radius_km.toFixed(1)} km radius
          </Tooltip>
        </Marker>

        {/* Candidate pins */}
        {data.candidates.map((c) => (
          <Marker
            key={c.rank}
            position={[c.lat, c.lon]}
            icon={candidateIcon(c.rank, c.rank === activeRank)}
            eventHandlers={{ click: () => setActiveRank(c.rank) }}
          >
            <Tooltip className="atlas-tooltip" direction="top" offset={[0, -16]} permanent={c.rank === activeRank}>
              <strong>#{c.rank} · Score {c.final_score}</strong>
              {c.address && (<><br /><span style={{ color: "#52525B" }}>{c.address}</span></>)}
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
            <div className="label-xs">SCOUT RESULTS</div>
            <div className="text-sm font-medium text-ink">
              Top {data.candidates.length} parcels for <em className="font-display italic">{data.store_format}</em>
              <span className="text-graphite font-normal"> · scored {fmtNum(data.summary.parcels_considered)} of {fmtNum(data.summary.parcels_in_box)} parcels</span>
            </div>
          </div>
        </div>
      </motion.div>

      <button
        onClick={onReset}
        className="absolute top-6 right-6 z-[1000] bg-snow border border-hairline px-3 py-2 hover:bg-bone transition flex items-center gap-2"
        title="Restart"
      >
        <X className="w-3.5 h-3.5 text-graphite" strokeWidth={1.5} />
        <span className="label-xs">RESET</span>
      </button>

      {/* ── Right panel — ranked list ─────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="absolute top-6 right-6 mt-14 w-[420px] z-[999] max-h-[calc(100vh-7rem)] overflow-hidden flex flex-col bg-snow border border-hairline shadow-[0_24px_60px_-30px_rgba(0,0,0,0.22)]"
      >
        {/* Active candidate header */}
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
                  Score <span className="text-emerald">{active.final_score}</span>
                </div>
                {active.address && (
                  <div className="text-sm text-ink font-medium leading-tight">{active.address}</div>
                )}
                {active.commercial_type && (
                  <div className="text-xs text-graphite mt-1">{active.commercial_type}</div>
                )}
              </div>
              <div className="bg-emerald/10 px-2 py-1 border border-emerald/30">
                <div className="label-xs text-emerald">{active.parcel_acres?.toFixed(1) ?? "—"} AC</div>
              </div>
            </div>

            {/* Key stats row */}
            <div className="grid grid-cols-3 gap-3 mt-4">
              <Stat
                icon={<Users className="w-3 h-3" strokeWidth={1.5} />}
                label="POP 1KM"
                value={fmtNum(active.features.pop_1km, true)}
              />
              <Stat
                icon={<DollarSign className="w-3 h-3" strokeWidth={1.5} />}
                label="MEDIAN HHI"
                value={fmtUSD(active.features.median_income_1km)}
              />
              <Stat
                icon={<TrendingUp className="w-3 h-3" strokeWidth={1.5} />}
                label="HUFF CAP"
                value={`${active.features.huff_capture_pct.toFixed(1)}%`}
              />
            </div>

            {/* Score breakdown bars */}
            <div className="mt-5">
              <div className="label-xs mb-2">SCORE BREAKDOWN</div>
              <div className="space-y-1.5">
                {Object.entries(active.breakdown).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2 text-[11px]">
                    <span className="w-24 font-mono uppercase text-slate tracking-wide">{k}</span>
                    <div className="flex-1 h-1.5 bg-bone relative overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${v}%` }}
                        transition={{ duration: 0.5, ease: "easeOut" }}
                        className="absolute inset-y-0 left-0 bg-emerald"
                      />
                    </div>
                    <span className="w-8 text-right font-mono tabular text-ink">{Math.round(v)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Competitor / traffic context */}
            <div className="mt-5 grid grid-cols-2 gap-3 text-[11px]">
              <div>
                <div className="label-xs mb-0.5">NEAREST RIVAL</div>
                <div className="text-ink leading-tight">
                  {active.features.nearest_rival_name ?? "—"}
                </div>
                <div className="text-graphite">
                  {active.features.nearest_rival_km !== null
                    ? `${active.features.nearest_rival_km} km away`
                    : "no direct rivals nearby"}
                </div>
              </div>
              <div>
                <div className="label-xs mb-0.5">AADT 1KM AVG</div>
                <div className="text-ink leading-tight">{fmtNum(active.features.avg_aadt_1km)}</div>
                <div className="text-graphite">{active.features.schools_2km} schools 2km</div>
              </div>
            </div>

            {/* Deep dive CTA */}
            <button
              onClick={() => onDeepDive(active)}
              className="mt-6 w-full bg-ink text-snow py-4 px-5 flex items-center justify-between
                         transition-all duration-300 hover:bg-graphite group"
            >
              <span className="text-sm font-medium tracking-snug">Run Deep Dive on This Site</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" strokeWidth={1.5} />
            </button>
          </motion.div>
        </AnimatePresence>

        {/* Other candidates list */}
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
                <div className="text-sm text-ink font-medium truncate">
                  {c.address ?? `(${c.lat.toFixed(3)}, ${c.lon.toFixed(3)})`}
                </div>
                <div className="text-[11px] text-graphite">
                  {c.parcel_acres?.toFixed(1) ?? "—"} ac · Huff {c.features.huff_capture_pct.toFixed(1)}%
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-display text-xl tabular text-ink leading-none">{c.final_score}</div>
                <div className="label-xs">SCORE</div>
              </div>
            </button>
          ))}
        </div>
      </motion.div>

      {/* ── Bottom-left — search context ──────────────────────────── */}
      <div className="absolute bottom-6 left-6 z-[1000] bg-paper/85 backdrop-blur-sm px-3 py-2 flex items-center gap-3 text-graphite">
        <Crosshair className="w-3.5 h-3.5" strokeWidth={1.5} />
        <span className="label-xs">
          ANCHOR {data.search.lat.toFixed(3)}, {data.search.lon.toFixed(3)}
          {" · "} {data.search.radius_km.toFixed(1)} KM
          {data.summary.min_spacing_km && ` · MIN SPACING ${data.summary.min_spacing_km.toFixed(1)} KM`}
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
