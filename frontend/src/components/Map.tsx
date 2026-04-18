"use client";
import { useEffect, useRef, useState } from "react";
import type { CandidateSite, CompetitorStore } from "@/lib/api";

interface MapProps {
  candidates: CandidateSite[];
  competitors: CompetitorStore[];
  selectedSite: CandidateSite | null;
  droppedPin: { lat: number; lng: number } | null;
  onSiteSelect: (site: CandidateSite) => void;
  onPinDrop: (lat: number, lng: number) => void;
  brand: "walmart" | "target";
  isAnalyzing: boolean;
}

const BRAND_COLORS: Record<string, string> = {
  walmart: "#004c91",
  target: "#cc0000",
  costco: "#006fba",
  sams_club: "#005eb8",
  kroger: "#4f2683",
  aldi: "#00579c",
  meijer: "#c8102e",
  whole_foods: "#00674b",
  trader_joes: "#c8151b",
  safeway: "#e31837",
  sprouts: "#5a8d2b",
  other: "#6b7280",
};

const BRAND_EMOJI: Record<string, string> = {
  walmart: "W",
  target: "T",
  costco: "C",
  sams_club: "S",
  kroger: "K",
  aldi: "A",
  meijer: "M",
  whole_foods: "WF",
  trader_joes: "TJ",
  safeway: "SF",
  sprouts: "SP",
  other: "R",
};

export default function MapComponent({
  candidates,
  competitors,
  selectedSite,
  droppedPin,
  onSiteSelect,
  onPinDrop,
  brand,
  isAnalyzing,
}: MapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMapRef = useRef<unknown>(null);
  const markersRef = useRef<unknown[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !mapRef.current || leafletMapRef.current) return;

    // Dynamic import of Leaflet (SSR-safe)
    import("leaflet").then((L) => {
      // Fix default icon issue
      // @ts-ignore
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl:
          "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl:
          "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl:
          "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      // Init map centered on Phoenix
      const map = L.map(mapRef.current!, {
        center: [33.4484, -112.074],
        zoom: 11,
        zoomControl: false,
      });

      // Dark OSM tiles
      L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          attribution: "© OpenStreetMap contributors",
          maxZoom: 19,
        }
      ).addTo(map);

      // Custom zoom control bottom-right
      L.control.zoom({ position: "bottomright" }).addTo(map);

      // Click handler for pin drop
      map.on("click", (e: unknown) => {
        const { lat, lng } = (e as { latlng: { lat: number; lng: number } }).latlng;
        onPinDrop(lat, lng);
      });

      leafletMapRef.current = map;
    });

    // Load leaflet CSS
    if (!document.getElementById("leaflet-css")) {
      const link = document.createElement("link");
      link.id = "leaflet-css";
      link.rel = "stylesheet";
      link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
      document.head.appendChild(link);
    }
  }, [mounted]);

  // Update markers when data changes
  useEffect(() => {
    if (!leafletMapRef.current || !mounted) return;

    import("leaflet").then((L) => {
      const map = leafletMapRef.current as ReturnType<typeof L.map>;

      // Clear existing markers
      markersRef.current.forEach((m) => map.removeLayer(m as ReturnType<typeof L.marker>));
      markersRef.current = [];

      // Competitor markers
      competitors.forEach((store) => {
        const brandKey = store.brand_name.toLowerCase().replace(/\s+/g, "_");
        const color =
          BRAND_COLORS[
            Object.keys(BRAND_COLORS).find((k) =>
              store.brand_name.toLowerCase().includes(k)
            ) || "other"
          ] || "#6b7280";
        const letter =
          BRAND_EMOJI[
            Object.keys(BRAND_EMOJI).find((k) =>
              store.brand_name.toLowerCase().includes(k)
            ) || "other"
          ] || "R";

        const icon = L.divIcon({
          html: `<div style="
            width:24px;height:24px;border-radius:50%;
            background:${color};border:2px solid rgba(255,255,255,0.4);
            display:flex;align-items:center;justify-content:center;
            font-size:8px;font-weight:700;color:white;
            box-shadow:0 2px 8px rgba(0,0,0,0.6);
          ">${letter}</div>`,
          className: "",
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        });

        const marker = L.marker([store.lat, store.lng], { icon })
          .addTo(map)
          .bindPopup(
            `<div style="font-family:sans-serif;font-size:12px;">
              <strong>${store.brand_name}</strong><br/>
              ${store.distance_miles?.toFixed(1) ?? "?"} miles away
            </div>`
          );
        markersRef.current.push(marker);
      });

      // Candidate site markers
      candidates.forEach((site) => {
        const isSelected = selectedSite?.id === site.id;
        const icon = L.divIcon({
          html: `<div style="
            width:${isSelected ? 32 : 22}px;
            height:${isSelected ? 32 : 22}px;
            border-radius:50%;
            background:${isSelected ? "#00d4ff" : "rgba(0,212,255,0.3)"};
            border:2px solid ${isSelected ? "#00d4ff" : "rgba(0,212,255,0.6)"};
            display:flex;align-items:center;justify-content:center;
            font-size:9px;font-weight:700;color:${isSelected ? "#000" : "#00d4ff"};
            box-shadow:${isSelected ? "0 0 20px rgba(0,212,255,0.6)" : "none"};
            transition:all 0.2s;
          ">📍</div>`,
          className: "",
          iconSize: [isSelected ? 32 : 22, isSelected ? 32 : 22],
          iconAnchor: [isSelected ? 16 : 11, isSelected ? 16 : 11],
        });

        const marker = L.marker([site.lat, site.lng], { icon })
          .addTo(map)
          .bindPopup(
            `<div style="font-family:sans-serif;font-size:12px;max-width:180px;">
              <strong>${site.name}</strong><br/>
              <span style="color:#6b7280">${site.description}</span><br/>
              <span style="color:#6b7280">${site.acreage} acres · ${site.zoning_type}</span>
            </div>`
          )
          .on("click", () => onSiteSelect(site));
        markersRef.current.push(marker);
      });

      // Dropped pin
      if (droppedPin) {
        const pulseIcon = L.divIcon({
          html: `<div style="position:relative;width:40px;height:40px;display:flex;align-items:center;justify-content:center;">
            <div style="position:absolute;width:40px;height:40px;border-radius:50%;background:rgba(0,212,255,0.2);animation:pulse 1.5s infinite;"></div>
            <div style="position:absolute;width:20px;height:20px;border-radius:50%;background:#00d4ff;border:3px solid white;box-shadow:0 0 20px rgba(0,212,255,0.8);"></div>
          </div>
          <style>@keyframes pulse{0%,100%{transform:scale(1);opacity:0.6}50%{transform:scale(1.8);opacity:0.1}}</style>`,
          className: "",
          iconSize: [40, 40],
          iconAnchor: [20, 20],
        });
        const marker = L.marker([droppedPin.lat, droppedPin.lng], {
          icon: pulseIcon,
        })
          .addTo(map)
          .bindPopup("📍 Analysis target");
        markersRef.current.push(marker);
      }
    });
  }, [candidates, competitors, selectedSite, droppedPin, mounted]);

  if (!mounted) {
    return (
      <div
        style={{
          height: "100%",
          background: "#0a1628",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#3d5a73",
          fontSize: 13,
        }}
      >
        Loading map...
      </div>
    );
  }

  return (
    <div style={{ position: "relative", height: "100%" }}>
      <div ref={mapRef} style={{ height: "100%", width: "100%" }} />

      {/* Map overlay legend */}
      <div
        style={{
          position: "absolute",
          bottom: 40,
          left: 12,
          background: "rgba(5,10,20,0.85)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 8,
          padding: "10px 12px",
          backdropFilter: "blur(10px)",
          zIndex: 1000,
          fontSize: 11,
          color: "#7a9ab8",
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 6, color: "#e8f4f8", fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Legend
        </div>
        {[
          { color: "#004c91", label: "Walmart" },
          { color: "#cc0000", label: "Target" },
          { color: "#006fba", label: "Costco" },
          { color: "#5a8d2b", label: "Other Retail" },
          { color: "#00d4ff", label: "Candidate Sites" },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: color }} />
            <span>{label}</span>
          </div>
        ))}
      </div>

      {/* Analyzing overlay */}
      {isAnalyzing && (
        <div
          style={{
            position: "absolute",
            top: 12,
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(124,58,237,0.9)",
            border: "1px solid rgba(124,58,237,0.5)",
            borderRadius: 20,
            padding: "6px 16px",
            color: "white",
            fontSize: 12,
            fontWeight: 600,
            backdropFilter: "blur(10px)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div className="spinner" />
          AI agents analyzing market...
        </div>
      )}

      {/* Click instruction */}
      {!droppedPin && !isAnalyzing && (
        <div
          style={{
            position: "absolute",
            bottom: 40,
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(5,10,20,0.85)",
            border: "1px solid rgba(0,212,255,0.3)",
            borderRadius: 20,
            padding: "6px 14px",
            color: "#7a9ab8",
            fontSize: 11,
            backdropFilter: "blur(10px)",
            zIndex: 1000,
            whiteSpace: "nowrap",
          }}
        >
          🖱️ Click map to drop a custom pin · or select a candidate site →
        </div>
      )}
    </div>
  );
}
