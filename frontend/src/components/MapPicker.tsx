import { useState, useMemo, useEffect, type ChangeEvent } from "react";
import { MapContainer, TileLayer, Marker, Circle, useMapEvents, useMap } from "react-leaflet";
import L from "leaflet";
import { motion } from "framer-motion";
import { ArrowRight, MapPin, Navigation, Crosshair, Sparkles, AlertCircle, LocateFixed } from "lucide-react";
import { StoreFormatPicker, type StoreFormat } from "./StoreFormatPicker";

const MPLS_CENTER: [number, number] = [44.9778, -93.2650];
const MPLS_BOUNDS: L.LatLngBoundsLiteral = [
  [44.85, -93.40],
  [45.10, -93.10],
];

const LAT_MIN = 44.85, LAT_MAX = 45.10;
const LON_MIN = -93.40, LON_MAX = -93.10;

const pinIcon = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;background:#047857;border:2px solid white;border-radius:9999px;box-shadow:0 0 0 1px #047857,0 6px 14px rgba(0,0,0,0.18)"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const scoutAnchorIcon = L.divIcon({
  className: "",
  html: `<div style="width:14px;height:14px;background:white;border:2px solid #0A0A0A;transform:rotate(45deg);box-shadow:0 6px 14px rgba(0,0,0,0.18)"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

function ClickHandler({ onPick }: { onPick: (lat: number, lon: number) => void }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) });
  return null;
}

function MapPanner({ pin }: { pin: { lat: number; lon: number } | null }) {
  const map = useMap();
  useEffect(() => {
    if (pin) map.panTo([pin.lat, pin.lon]);
  }, [pin, map]);
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

// Browser Geolocation wrapper — returns an imperative locate() + ui state.
function useGeolocation() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const locate = (
    onFound: (lat: number, lon: number, accuracy: number) => void,
  ) => {
    if (!("geolocation" in navigator)) {
      setError("Geolocation is not supported in this browser");
      return;
    }
    setBusy(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setBusy(false);
        onFound(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
      },
      (err) => {
        setBusy(false);
        setError(
          err.code === err.PERMISSION_DENIED
            ? "Location access denied — enable it in your browser settings"
            : err.code === err.POSITION_UNAVAILABLE
            ? "Location unavailable — try again outdoors"
            : "Could not get your location",
        );
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 },
    );
  };

  return { locate, busy, error, clearError: () => setError(null) };
}

function isInsideMpls(lat: number, lon: number): boolean {
  const [[swLat, swLon], [neLat, neLon]] = MPLS_BOUNDS;
  return lat >= swLat && lat <= neLat && lon >= swLon && lon <= neLon;
}

export function MapPicker({ onAnalyze }: Props) {
  const [mode, setMode] = useState<PickMode>("manual");
  const [pin, setPin] = useState<{ lat: number; lon: number } | null>(null);
  const [radius, setRadius] = useState(5);
  const [format, setFormat] = useState<StoreFormat>("Target");
  const [latInput, setLatInput] = useState("");
  const [lonInput, setLonInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [heroOpen, setHeroOpen] = useState(true);
  const [panelOpen, setPanelOpen] = useState(true);
  const [geoNotice, setGeoNotice] = useState<string | null>(null);
  const { locate, busy: locating, error: geoError } = useGeolocation();

  const ready =
    pin !== null &&
    latInput.trim() !== "" &&
    lonInput.trim() !== "" &&
    inputError === null;

  const radiusMeters = useMemo(() => radius * 1000, [radius]);
  const isScout = mode === "scout";
  const accent = isScout ? "#0A0A0A" : "#047857";

  function handleMapClick(lat: number, lon: number) {
    setPin({ lat, lon });
    setLatInput(lat.toFixed(4));
    setLonInput(lon.toFixed(4));
    setInputError(null);
  }

  function handleReset() {
    setPin(null);
    setLatInput("");
    setLonInput("");
    setInputError(null);
    setGeoNotice(null);
  }

  function handleLatChange(e: ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value;
    setLatInput(raw);

    if (raw.trim() === "") {
      setPin(null);
      setInputError(null);
      return;
    }

    const val = parseFloat(raw);
    if (isNaN(val)) {
      setInputError("Invalid latitude");
      return;
    }
    if (val < LAT_MIN || val > LAT_MAX) {
      setInputError(`Latitude must be ${LAT_MIN} – ${LAT_MAX}`);
      return;
    }

    if (lonInput.trim() === "") {
      setPin(null);
      setInputError(null);
      return;
    }

    const lonVal = parseFloat(lonInput);
    if (isNaN(lonVal)) {
      setInputError("Invalid longitude");
      return;
    }
    if (lonVal < LON_MIN || lonVal > LON_MAX) {
      setInputError(`Longitude must be ${LON_MIN} – ${LON_MAX}`);
      return;
    }

    setInputError(null);
    setPin({ lat: val, lon: lonVal });
  }

  function handleLonChange(e: ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value;
    setLonInput(raw);

    if (raw.trim() === "") {
      setPin(null);
      setInputError(null);
      return;
    }

    const val = parseFloat(raw);
    if (isNaN(val)) {
      setInputError("Invalid longitude");
      return;
    }
    if (val < LON_MIN || val > LON_MAX) {
      setInputError(`Longitude must be ${LON_MIN} – ${LON_MAX}`);
      return;
    }

    if (latInput.trim() === "") {
      setPin(null);
      setInputError(null);
      return;
    }

    const latVal = parseFloat(latInput);
    if (isNaN(latVal)) {
      setInputError("Invalid latitude");
      return;
    }
    if (latVal < LAT_MIN || latVal > LAT_MAX) {
      setInputError(`Latitude must be ${LAT_MIN} – ${LAT_MAX}`);
      return;
    }

    setInputError(null);
    setPin({ lat: latVal, lon: val });
  }

  const handleUseMyLocation = () => {
    setGeoNotice(null);
    locate((lat, lon, accuracy) => {
      if (!isInsideMpls(lat, lon)) {
        setGeoNotice(
          "You're outside Minneapolis — Atlas only analyzes MN sites today.",
        );
        return;
      }
      handleMapClick(lat, lon);
      setGeoNotice(`Location locked · ±${Math.round(accuracy)} m accuracy`);
    });
  };

  return (
    <div className="relative h-[calc(100vh-4rem)] w-full overflow-hidden">
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
          attribution="&copy; OpenStreetMap"
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        <ClickHandler onPick={handleMapClick} />
        <MapPanner pin={pin} />
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

      <motion.div
        initial={{ opacity: 0, x: -16 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className="absolute top-8 left-8 max-w-xs z-[1000]"
      >
        <div className="bg-snow/95 border border-hairline shadow-[0_24px_60px_-30px_rgba(0,0,0,0.18)] backdrop-blur-sm">
          <button
            onClick={() => setHeroOpen((h) => !h)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-bone transition"
          >
            <span className="label-xs">CHAPTER ONE — LOCATE</span>
            <span className="font-mono text-mist text-sm leading-none">
              {heroOpen ? "−" : "+"}
            </span>
          </button>
          {heroOpen && (
            <div className="px-4 pb-4 border-t border-hairline">
              {isScout ? (
                <>
                  <h1 className="text-2xl font-display mb-2 mt-3">
                    Let the engine <em className="italic">find</em> the corners worth opening.
                  </h1>
                  <p className="text-xs text-graphite leading-relaxed">
                    Drop an anchor and a search radius. We'll score every commercial
                    parcel inside, spread the winners across distinct neighborhoods,
                    and surface the top three.
                  </p>
                </>
              ) : (
                <>
                  <h1 className="text-2xl font-display mb-2 mt-3">
                    Drop a pin <em className="italic">anywhere</em> in Minneapolis.
                  </h1>
                  <p className="text-xs text-graphite leading-relaxed">
                    We'll pull every household, competitor, parcel, school, and traffic
                    count within your radius — and tell you whether it's worth the lease.
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
        className="absolute bottom-8 right-8 z-[1000] w-[440px] max-h-[calc(100vh-4rem)]"
      >
        <div className="bg-snow border border-hairline shadow-[0_24px_60px_-30px_rgba(0,0,0,0.18)] overflow-hidden flex flex-col">
          {panelOpen && (
            <div className="overflow-y-auto max-h-[calc(100vh-14rem)] flex flex-col order-1">
              <div className="grid grid-cols-2 border-b border-hairline flex-shrink-0">
                <button
                  onClick={() => setMode("manual")}
                  className={`px-4 py-3 flex items-center justify-center gap-2 transition
                    ${mode === "manual" ? "bg-ink text-snow" : "bg-snow text-graphite hover:text-ink"}`}
                >
                  <Crosshair className="w-3.5 h-3.5" strokeWidth={1.5} />
                  <span className="label-xs" style={{ color: mode === "manual" ? "white" : undefined }}>
                    MANUAL
                  </span>
                </button>
                <button
                  onClick={() => setMode("scout")}
                  className={`px-4 py-3 flex items-center justify-center gap-2 transition border-l border-hairline
                    ${mode === "scout" ? "bg-ink text-snow" : "bg-snow text-graphite hover:text-ink"}`}
                >
                  <Sparkles className="w-3.5 h-3.5" strokeWidth={1.5} />
                  <span className="label-xs" style={{ color: mode === "scout" ? "white" : undefined }}>
                    AUTO-SCOUT
                  </span>
                </button>
              </div>

              <div className="p-5 border-b border-hairline flex-shrink-0">
                <div className="label-xs mb-2">STORE FORMAT</div>
                <StoreFormatPicker value={format} onChange={setFormat} />
              </div>

              <div className="grid grid-cols-2 border-b border-hairline flex-shrink-0">
                <div className="p-5 border-r border-hairline">
                  <div className="label-xs mb-2">LATITUDE</div>
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder="44.9778"
                    value={latInput}
                    onChange={handleLatChange}
                    onBlur={() => {
                      if (pin && !inputError) setLatInput(pin.lat.toFixed(4));
                    }}
                    className={`font-mono text-base tabular text-ink bg-transparent w-full outline-none
                      border-b pb-1 transition-colors placeholder:text-mist
                      ${inputError ? "border-red-400" : "border-hairline focus:border-ink"}`}
                  />
                </div>
                <div className="p-5">
                  <div className="label-xs mb-2">LONGITUDE</div>
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder="-93.2650"
                    value={lonInput}
                    onChange={handleLonChange}
                    onBlur={() => {
                      if (pin && !inputError) setLonInput(pin.lon.toFixed(4));
                    }}
                    className={`font-mono text-base tabular text-ink bg-transparent w-full outline-none
                      border-b pb-1 transition-colors placeholder:text-mist
                      ${inputError ? "border-red-400" : "border-hairline focus:border-ink"}`}
                  />
                </div>
              </div>

              {inputError && (
                <div className="px-5 py-3 bg-red-50 border-b border-red-100 flex items-center gap-2 flex-shrink-0">
                  <AlertCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" strokeWidth={1.5} />
                  <span className="text-xs text-red-600 font-mono">{inputError}</span>
                </div>
              )}

              <div className="p-6 border-b border-hairline flex-shrink-0">
                <div className="flex items-baseline justify-between mb-3">
                  <span className="label-xs">
                    {isScout ? "SEARCH AREA RADIUS" : "CATCHMENT RADIUS"}
                  </span>
                  <div className="flex items-baseline gap-1.5">
                    <span className="font-display text-3xl tabular text-ink leading-none">
                      {radius.toFixed(1)}
                    </span>
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
                  <span>1 KM</span><span>5 KM</span><span>10 KM</span>
                </div>
                {isScout && (
                  <div className="mt-3 text-[11px] text-graphite leading-relaxed">
                    We'll score every retail-compatible parcel inside this circle and
                    surface the top 3 — spaced at least{" "}
                    <span className="text-ink font-medium">{(radius / 4).toFixed(1)} km</span> apart.
                  </div>
                )}
              </div>

              <button
                onClick={() =>
                  pin &&
                  onAnalyze({
                    mode,
                    lat: pin.lat,
                    lon: pin.lon,
                    radius_km: radius,
                    store_format: format,
                  })
                }
                disabled={!ready}
                className="w-full bg-ink text-snow py-5 px-6 flex items-center justify-between
                           transition-all duration-300 hover:bg-graphite flex-shrink-0
                           disabled:bg-bone disabled:text-mist disabled:cursor-not-allowed group"
              >
                <span className="text-sm font-medium tracking-snug">
                  {isScout ? `Scout Top 3 ${format} Sites` : "Analyze Location"}
                </span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" strokeWidth={1.5} />
              </button>
            </div>
          )}

          <div className="px-6 py-4 flex items-center justify-between border-t border-hairline flex-shrink-0 order-2">
            <div className="flex items-center gap-2">
              <MapPin className={`w-3.5 h-3.5 ${ready ? "text-emerald" : "text-mist"}`} strokeWidth={1.5} />
              <span className="label-xs">
                {ready
                  ? isScout ? "ANCHOR PLACED" : "PIN PLACED"
                  : isScout ? "AWAITING ANCHOR" : "AWAITING PIN"}
              </span>
            </div>
            {(pin || latInput || lonInput) && (
              <button onClick={handleReset} className="label-xs hover:text-ink transition">
                Reset
              </button>
            )}
          </div>

          <button
            onClick={() => setPanelOpen((p) => !p)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-bone transition border-t border-hairline flex-shrink-0 order-3"
          >
            <div className="flex items-center gap-2">
              <span className="label-xs">SITE SELECTION</span>
              {ready && <span className="w-1.5 h-1.5 rounded-full bg-emerald" />}
            </div>
            <span className="font-mono text-mist text-sm leading-none">
              {panelOpen ? "−" : "+"}
            </span>
          </button>
        </div>
      </motion.div>

      {/* Bottom-left — GPS + context strip */}
      <div className="absolute bottom-8 left-8 z-[1000] flex flex-col gap-2 items-start">
        <button
          onClick={handleUseMyLocation}
          disabled={locating}
          title="Use my current GPS location"
          className="bg-snow border border-hairline px-3 py-2 flex items-center gap-2 text-graphite
                     hover:text-ink hover:border-ink transition shadow-[0_12px_30px_-18px_rgba(0,0,0,0.25)]
                     disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <LocateFixed
            className={`w-3.5 h-3.5 ${locating ? "animate-pulse text-emerald" : ""}`}
            strokeWidth={1.5}
          />
          <span className="label-xs">
            {locating ? "LOCATING…" : "USE MY LOCATION"}
          </span>
        </button>
        {(geoError || geoNotice) && (
          <div
            className={`bg-snow border border-hairline px-3 py-1.5 text-[11px] leading-snug max-w-[280px] ${
              geoError ? "text-rose-600" : "text-graphite"
            }`}
          >
            {geoError ?? geoNotice}
          </div>
        )}
        <div className="bg-paper/80 backdrop-blur-sm px-3 py-2">
          <div className="flex items-center gap-3 text-graphite">
            <Navigation className="w-3.5 h-3.5" strokeWidth={1.5} />
            <span className="label-xs">CITY OF MINNEAPOLIS · 87 NEIGHBORHOODS · 232 CENSUS TRACTS</span>
          </div>
        </div>
      </div>
    </div>
  );
}