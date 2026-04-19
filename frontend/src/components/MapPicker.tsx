import { useState, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Circle, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { motion } from "framer-motion";
import { ArrowRight, MapPin, Navigation, Crosshair, Sparkles } from "lucide-react";
import { fmtCoord } from "../lib/format";
import { StoreFormatPicker, type StoreFormat } from "./StoreFormatPicker";

// Minneapolis hard bounds
const MPLS_CENTER: [number, number] = [44.9778, -93.2650];
const MPLS_BOUNDS: L.LatLngBoundsLiteral = [
  [44.85, -93.40],  // SW
  [45.10, -93.10],  // NE
];

// Manual mode pin — emerald solid
const pinIcon = L.divIcon({
  className: "",
  html: `<div style="
    width: 16px; height: 16px;
    background: #047857;
    border: 2px solid white;
    border-radius: 9999px;
    box-shadow: 0 0 0 1px #047857, 0 6px 14px rgba(0,0,0,0.18);
  "></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

// Scout mode anchor — outlined diamond, signals "this is the search center"
const scoutAnchorIcon = L.divIcon({
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

function ClickHandler({ onPick }: { onPick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click: (e) => onPick(e.latlng.lat, e.latlng.lng),
  });
  return null;
}

export type PickMode = "manual" | "scout";

export interface PickedLocation {
  mode: PickMode;
  lat: number;
  lon: number;
  radius_km: number;
  store_format: StoreFormat;
}

interface Props {
  onAnalyze: (loc: PickedLocation) => void;
}

export function MapPicker({ onAnalyze }: Props) {
  const [mode, setMode] = useState<PickMode>("manual");
  const [pin, setPin] = useState<{ lat: number; lon: number } | null>(null);
  const [radius, setRadius] = useState(5);
  const [format, setFormat] = useState<StoreFormat>("Target");

  const ready = pin !== null;
  const radiusMeters = useMemo(() => radius * 1000, [radius]);

  const isScout = mode === "scout";
  const accent = isScout ? "#0A0A0A" : "#047857";

  return (
    <div className="relative h-[calc(100vh-4rem)] w-full overflow-hidden">
      {/* Map */}
      <MapContainer
        center={MPLS_CENTER}
        zoom={12}
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
        <ClickHandler onPick={(lat, lon) => setPin({ lat, lon })} />
        {pin && (
          <>
            <Circle
              center={[pin.lat, pin.lon]}
              radius={radiusMeters}
              pathOptions={{
                color: accent,
                weight: isScout ? 1.2 : 1.5,
                dashArray: isScout ? "4 4" : undefined,
                fillColor: accent,
                fillOpacity: 0.05,
              }}
            />
            <Marker position={[pin.lat, pin.lon]} icon={isScout ? scoutAnchorIcon : pinIcon} />
          </>
        )}
      </MapContainer>

      {/* Hero overlay — left */}
      <motion.div
        initial={{ opacity: 0, x: -16 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className="absolute top-8 left-8 max-w-md z-[1000] pointer-events-none"
      >
        <div className="bg-snow border border-hairline p-7 pointer-events-auto shadow-[0_24px_60px_-30px_rgba(0,0,0,0.18)]">
          <div className="label-xs mb-4">CHAPTER ONE — LOCATE</div>
          {isScout ? (
            <>
              <h1 className="display-md mb-3">
                Let the engine <em className="italic font-display">find</em> the corners worth opening.
              </h1>
              <p className="text-sm text-graphite leading-relaxed">
                Drop an anchor and a search radius. We'll score every commercial
                parcel inside, spread the winners across distinct neighborhoods,
                and surface the top three.
              </p>
            </>
          ) : (
            <>
              <h1 className="display-md mb-3">
                Drop a pin <em className="italic font-display">anywhere</em> in Minneapolis.
              </h1>
              <p className="text-sm text-graphite leading-relaxed">
                We'll pull every household, competitor, parcel, school, and traffic
                count within your radius — and tell you whether it's worth the lease.
              </p>
            </>
          )}
        </div>
      </motion.div>

      {/* Pick panel — right */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
        className="absolute bottom-8 right-8 z-[1000] w-[440px]"
      >
        <div className="bg-snow border border-hairline shadow-[0_24px_60px_-30px_rgba(0,0,0,0.18)]">
          {/* ── Mode toggle ─────────────────────────────────────────── */}
          <div className="grid grid-cols-2 hairline-b">
            <button
              onClick={() => setMode("manual")}
              className={`px-4 py-3 flex items-center justify-center gap-2 transition
                          ${mode === "manual"
                            ? "bg-ink text-snow"
                            : "bg-snow text-graphite hover:text-ink"}`}
            >
              <Crosshair className="w-3.5 h-3.5" strokeWidth={1.5} />
              <span className="label-xs" style={{ color: mode === "manual" ? "white" : undefined }}>
                MANUAL
              </span>
            </button>
            <button
              onClick={() => setMode("scout")}
              className={`px-4 py-3 flex items-center justify-center gap-2 transition border-l border-hairline
                          ${mode === "scout"
                            ? "bg-ink text-snow"
                            : "bg-snow text-graphite hover:text-ink"}`}
            >
              <Sparkles className="w-3.5 h-3.5" strokeWidth={1.5} />
              <span className="label-xs" style={{ color: mode === "scout" ? "white" : undefined }}>
                AUTO-SCOUT
              </span>
            </button>
          </div>

          {/* ── Status row ──────────────────────────────────────────── */}
          <div className="hairline-b px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MapPin className={`w-3.5 h-3.5 ${ready ? "text-emerald" : "text-mist"}`} strokeWidth={1.5} />
              <span className="label-xs">
                {ready
                  ? isScout ? "ANCHOR PLACED" : "PIN PLACED"
                  : isScout ? "AWAITING ANCHOR" : "AWAITING PIN"}
              </span>
            </div>
            {pin && (
              <button onClick={() => setPin(null)} className="label-xs hover:text-ink transition">
                Reset
              </button>
            )}
          </div>

          {/* ── Store format picker ─────────────────────────────────── */}
          <div className="p-5 hairline-b">
            <div className="label-xs mb-2">STORE FORMAT</div>
            <StoreFormatPicker value={format} onChange={setFormat} />
          </div>

          {/* ── Coords ──────────────────────────────────────────────── */}
          <div className="grid grid-cols-2 hairline-b">
            <div className="p-5 hairline-r border-r border-hairline">
              <div className="label-xs mb-2">LATITUDE</div>
              <div className="font-mono text-base tabular text-ink">
                {pin ? fmtCoord(pin.lat) : "— — — —"}
              </div>
            </div>
            <div className="p-5">
              <div className="label-xs mb-2">LONGITUDE</div>
              <div className="font-mono text-base tabular text-ink">
                {pin ? fmtCoord(pin.lon) : "— — — —"}
              </div>
            </div>
          </div>

          {/* ── Radius ──────────────────────────────────────────────── */}
          <div className="p-6 hairline-b">
            <div className="flex items-baseline justify-between mb-3">
              <span className="label-xs">{isScout ? "SEARCH AREA RADIUS" : "CATCHMENT RADIUS"}</span>
              <div className="flex items-baseline gap-1.5">
                <span className="font-display text-3xl tabular text-ink leading-none">{radius.toFixed(1)}</span>
                <span className="label-sm">KM</span>
              </div>
            </div>
            <input
              type="range"
              min={1}
              max={10}
              step={0.5}
              value={radius}
              onChange={(e) => setRadius(parseFloat(e.target.value))}
              className="w-full accent-emerald"
            />
            <div className="flex justify-between mt-2 label-xs">
              <span>1 KM</span>
              <span>5 KM</span>
              <span>10 KM</span>
            </div>
            {isScout && (
              <div className="mt-3 text-[11px] text-graphite leading-relaxed">
                We'll score every retail-compatible parcel inside this circle and
                surface the top 3 — spaced at least <span className="text-ink font-medium">{(radius / 4).toFixed(1)} km</span> apart.
              </div>
            )}
          </div>

          {/* ── CTA ─────────────────────────────────────────────────── */}
          <button
            onClick={() => pin && onAnalyze({
              mode,
              lat: pin.lat,
              lon: pin.lon,
              radius_km: radius,
              store_format: format,
            })}
            disabled={!ready}
            className="w-full bg-ink text-snow py-5 px-6 flex items-center justify-between
                       transition-all duration-300 hover:bg-graphite disabled:bg-bone disabled:text-mist
                       disabled:cursor-not-allowed group"
          >
            <span className="text-sm font-medium tracking-snug">
              {isScout ? `Scout Top 3 ${format} Sites` : "Analyze Location"}
            </span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" strokeWidth={1.5} />
          </button>
        </div>
      </motion.div>

      {/* Bottom-left — context strip */}
      <div className="absolute bottom-8 left-8 z-[1000] bg-paper/80 backdrop-blur-sm px-3 py-2">
        <div className="flex items-center gap-3 text-graphite">
          <Navigation className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span className="label-xs">CITY OF MINNEAPOLIS · 87 NEIGHBORHOODS · 232 CENSUS TRACTS</span>
        </div>
      </div>
    </div>
  );
}
