import { useState, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Circle, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { motion } from "framer-motion";
import { ArrowRight, MapPin, Navigation } from "lucide-react";
import { fmtCoord } from "../lib/format";

// Minneapolis Metro — bounds cover the full Twin Cities area
const MPLS_CENTER: [number, number] = [44.9778, -93.2650];
const MPLS_BOUNDS: L.LatLngBoundsLiteral = [
  [44.75, -93.55],  // SW — covers Eden Prairie, Bloomington
  [45.20, -92.85],  // NE — covers Maplewood, White Bear Lake
];

// Custom emerald pin
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

function ClickHandler({ onPick }: { onPick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click: (e) => onPick(e.latlng.lat, e.latlng.lng),
  });
  return null;
}

export interface PickedLocation {
  lat: number;
  lon: number;
  radius_km: number;
}

interface Props {
  onAnalyze: (loc: PickedLocation) => void;
  retailerName?: string;
}

export function MapPicker({ onAnalyze, retailerName }: Props) {
  const [pin, setPin] = useState<{ lat: number; lon: number } | null>(null);
  const [radius, setRadius] = useState(5);

  const ready = pin !== null;
  const radiusMeters = useMemo(() => radius * 1000, [radius]);

  return (
    <div className="relative h-[calc(100vh-4rem)] w-full overflow-hidden">
      {/* Map */}
      <MapContainer
        center={MPLS_CENTER}
        zoom={11}
        minZoom={10}
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
              pathOptions={{ color: "#047857", weight: 1.5, fillColor: "#047857", fillOpacity: 0.06 }}
            />
            <Marker position={[pin.lat, pin.lon]} icon={pinIcon} />
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
          <div className="label-xs mb-4">CHAPTER TWO — LOCATE</div>
          <h1 className="display-md mb-3">
            Drop a pin{retailerName ? <> for <em className="italic font-display">{retailerName}</em></> : ""}<br />
            anywhere in Minneapolis Metro.
          </h1>
          <p className="text-sm text-graphite leading-relaxed">
            We'll run 8 parallel agents — demographics, competitors, hotspot signals,
            amenity intel, and brand fit — then score this location in seconds.
          </p>
        </div>
      </motion.div>

      {/* Pick panel — right */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
        className="absolute bottom-8 right-8 z-[1000] w-[420px]"
      >
        <div className="bg-snow border border-hairline shadow-[0_24px_60px_-30px_rgba(0,0,0,0.18)]">
          {/* Status row */}
          <div className="hairline-b px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MapPin className={`w-3.5 h-3.5 ${ready ? "text-emerald" : "text-mist"}`} strokeWidth={1.5} />
              <span className="label-xs">{ready ? "PIN PLACED" : "AWAITING PIN"}</span>
            </div>
            {pin && (
              <button
                onClick={() => setPin(null)}
                className="label-xs hover:text-ink transition"
              >
                Reset
              </button>
            )}
          </div>

          {/* Coords */}
          <div className="grid grid-cols-2 hairline-b">
            <div className="p-5 hairline-r border-r border-hairline">
              <div className="label-xs mb-2">LATITUDE</div>
              <div className="font-mono text-lg tabular text-ink">
                {pin ? fmtCoord(pin.lat) : "— — — —"}
              </div>
            </div>
            <div className="p-5">
              <div className="label-xs mb-2">LONGITUDE</div>
              <div className="font-mono text-lg tabular text-ink">
                {pin ? fmtCoord(pin.lon) : "— — — —"}
              </div>
            </div>
          </div>

          {/* Radius */}
          <div className="p-6 hairline-b">
            <div className="flex items-baseline justify-between mb-3">
              <span className="label-xs">CATCHMENT RADIUS</span>
              <div className="flex items-baseline gap-1.5">
                <span className="font-display text-3xl tabular text-ink leading-none">{radius.toFixed(1)}</span>
                <span className="label-sm">KM</span>
              </div>
            </div>
            <input
              type="range"
              min={1}
              max={16}
              step={0.5}
              value={radius}
              onChange={(e) => setRadius(parseFloat(e.target.value))}
              className="w-full accent-emerald"
            />
            <div className="flex justify-between mt-2 label-xs">
              <span>1 KM</span>
              <span>8 KM</span>
              <span>16 KM</span>
            </div>
          </div>

          {/* CTA */}
          <button
            onClick={() => pin && onAnalyze({ lat: pin.lat, lon: pin.lon, radius_km: radius })}
            disabled={!ready}
            className="w-full bg-ink text-snow py-5 px-6 flex items-center justify-between
                       transition-all duration-300 hover:bg-graphite disabled:bg-bone disabled:text-mist
                       disabled:cursor-not-allowed group"
          >
            <span className="text-sm font-medium tracking-snug">
              {retailerName ? `Run ${retailerName} Analysis` : "Analyze Location"}
            </span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" strokeWidth={1.5} />
          </button>
        </div>
      </motion.div>

      {/* Bottom-left — context strip */}
      <div className="absolute bottom-8 left-8 z-[1000] bg-paper/80 backdrop-blur-sm px-3 py-2">
        <div className="flex items-center gap-3 text-graphite">
          <Navigation className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span className="label-xs">MINNEAPOLIS METRO · 10 CANDIDATE SITES · 8-AGENT AI PIPELINE</span>
        </div>
      </div>
    </div>
  );
}
