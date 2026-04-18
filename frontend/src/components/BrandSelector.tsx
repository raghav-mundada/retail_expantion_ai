"use client";
import { useState } from "react";
import type { RetailerProfile, StoreSizeEnum, PricePositioning } from "@/lib/api";

interface BrandSelectorProps {
  value: RetailerProfile;
  onChange: (profile: RetailerProfile) => void;
}

const KNOWN_BRANDS = [
  "Walmart", "Target", "Costco", "Aldi", "Trader Joe's", "Whole Foods",
  "Sprouts", "Kroger", "H-Mart", "Nordstrom Rack", "Dollar General",
  "Home Depot", "Lowe's", "TJ Maxx", "Burlington", "Five Below",
  "BJ's Wholesale", "Sam's Club", "Lidl", "Fresh Thyme",
];

const STORE_SIZES = [
  { value: "small", label: "Small", sub: "< 5,000 sq ft", icon: "🏪" },
  { value: "medium", label: "Medium", sub: "5K – 25K sq ft", icon: "🏬" },
  { value: "large", label: "Large", sub: "25K – 80K sq ft", icon: "🏢" },
  { value: "big_box", label: "Big-Box", sub: "80K+ sq ft", icon: "🏭" },
];

const CATEGORIES = [
  { value: "grocery", label: "Grocery", icon: "🛒" },
  { value: "liquor", label: "Liquor", icon: "🍾" },
  { value: "apparel", label: "Apparel", icon: "👗" },
  { value: "electronics", label: "Electronics", icon: "📱" },
  { value: "general_merchandise", label: "Gen. Merchandise", icon: "🏷️" },
  { value: "hardware", label: "Hardware", icon: "🔧" },
  { value: "pharmacy", label: "Pharmacy", icon: "💊" },
  { value: "specialty", label: "Specialty", icon: "🌟" },
  { value: "restaurant", label: "Restaurant", icon: "🍽️" },
  { value: "home_goods", label: "Home Goods", icon: "🛋️" },
];

const POSITIONING = [
  { value: "budget", label: "Budget", sub: "< $60K household", color: "#f59e0b" },
  { value: "mid_range", label: "Mid-Range", sub: "$55K – $120K", color: "#3b82f6" },
  { value: "premium", label: "Premium", sub: "$90K+ household", color: "#8b5cf6" },
];

export default function BrandSelector({ value, onChange }: BrandSelectorProps) {
  const [mode, setMode] = useState<"known" | "custom">(
    value.brand_name ? "known" : "custom"
  );
  const [brandInput, setBrandInput] = useState(value.brand_name || "");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>(
    (value.categories as string[] | undefined) || []
  );
  const [selectedSize, setSelectedSize] = useState<StoreSizeEnum>(value.store_size || "big_box");
  const [selectedPositioning, setSelectedPositioning] = useState<PricePositioning>(
    value.price_positioning || "mid_range"
  );

  // ── Known brand path ───────────────────────────────────────────────────────
  const handleBrandInput = (input: string) => {
    setBrandInput(input);
    if (input.length >= 2) {
      setSuggestions(
        KNOWN_BRANDS.filter((b) => b.toLowerCase().includes(input.toLowerCase())).slice(0, 6)
      );
    } else {
      setSuggestions([]);
    }
    // Update parent immediately with raw input
    onChange({ brand_name: input || undefined });
  };

  const handleBrandSelect = (brand: string) => {
    setBrandInput(brand);
    setSuggestions([]);
    onChange({ brand_name: brand });
  };

  // ── Custom store path ──────────────────────────────────────────────────────
  const toggleCategory = (cat: string) => {
    const next = selectedCategories.includes(cat)
      ? selectedCategories.filter((c) => c !== cat)
      : [...selectedCategories, cat];
    setSelectedCategories(next);
    onChange({
      store_size: selectedSize as RetailerProfile["store_size"],
      categories: next as RetailerProfile["categories"],
      price_positioning: selectedPositioning as RetailerProfile["price_positioning"],
    });
  };

  const handleSizeChange = (size: StoreSizeEnum) => {
    setSelectedSize(size);
    onChange({
      store_size: size,
      categories: selectedCategories as RetailerProfile["categories"],
      price_positioning: selectedPositioning,
    });
  };

  const handlePositioningChange = (pos: PricePositioning) => {
    setSelectedPositioning(pos);
    onChange({
      store_size: selectedSize,
      categories: selectedCategories as RetailerProfile["categories"],
      price_positioning: pos,
    });
  };

  const switchMode = (newMode: "known" | "custom") => {
    setMode(newMode);
    if (newMode === "known") {
      onChange({ brand_name: brandInput || undefined });
    } else {
      onChange({
        store_size: selectedSize,
        categories: selectedCategories as RetailerProfile["categories"],
        price_positioning: selectedPositioning,
      });
    }
  };

  return (
    <div className="brand-selector">
      {/* Mode Toggle */}
      <div className="brand-mode-toggle">
        <button
          id="brand-mode-known"
          className={`mode-tab ${mode === "known" ? "active" : ""}`}
          onClick={() => switchMode("known")}
        >
          🏪 Known Brand
        </button>
        <button
          id="brand-mode-custom"
          className={`mode-tab ${mode === "custom" ? "active" : ""}`}
          onClick={() => switchMode("custom")}
        >
          ⚙️ Custom Store
        </button>
      </div>

      {/* ── Known Brand Panel ── */}
      {mode === "known" && (
        <div className="brand-known-panel">
          <div className="brand-search-wrap">
            <input
              id="brand-name-input"
              type="text"
              className="brand-input"
              placeholder="Type brand name (e.g. Costco, H-Mart...)"
              value={brandInput}
              onChange={(e) => handleBrandInput(e.target.value)}
              autoComplete="off"
            />
            {suggestions.length > 0 && (
              <div className="brand-suggestions">
                {suggestions.map((s) => (
                  <div
                    key={s}
                    className="brand-suggestion-item"
                    onClick={() => handleBrandSelect(s)}
                  >
                    {s}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick-pick chips */}
          <div className="brand-quickpick">
            {["Walmart", "Target", "Costco", "Aldi", "Whole Foods", "Home Depot"].map((b) => (
              <button
                key={b}
                id={`quick-brand-${b.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
                className={`brand-chip ${brandInput === b ? "active" : ""}`}
                onClick={() => handleBrandSelect(b)}
              >
                {b}
              </button>
            ))}
          </div>

          {brandInput && (
            <div className="brand-hint">
              🔍 Gemini will resolve brand DNA for <strong>{brandInput}</strong>
            </div>
          )}
        </div>
      )}

      {/* ── Custom Store Panel ── */}
      {mode === "custom" && (
        <div className="brand-custom-panel">
          {/* Store Size */}
          <div className="custom-section-label">Store Size</div>
          <div className="custom-size-grid">
            {STORE_SIZES.map((s) => (
              <button
                key={s.value}
                id={`size-${s.value}`}
                className={`size-card ${selectedSize === s.value ? "active" : ""}`}
                onClick={() => handleSizeChange(s.value as StoreSizeEnum)}
              >
                <span className="size-icon">{s.icon}</span>
                <span className="size-label">{s.label}</span>
                <span className="size-sub">{s.sub}</span>
              </button>
            ))}
          </div>

          {/* Product Categories */}
          <div className="custom-section-label" style={{ marginTop: 12 }}>
            Product Categories <span style={{ opacity: 0.5, fontSize: 10 }}>(multi-select)</span>
          </div>
          <div className="custom-cat-grid">
            {CATEGORIES.map((c) => (
              <button
                key={c.value}
                id={`cat-${c.value}`}
                className={`cat-chip ${selectedCategories.includes(c.value) ? "active" : ""}`}
                onClick={() => toggleCategory(c.value)}
              >
                {c.icon} {c.label}
              </button>
            ))}
          </div>

          {/* Price Positioning */}
          <div className="custom-section-label" style={{ marginTop: 12 }}>
            Price Positioning
          </div>
          <div className="custom-pos-grid">
            {POSITIONING.map((p) => (
              <button
                key={p.value}
                id={`pos-${p.value}`}
                className={`pos-card ${selectedPositioning === p.value ? "active" : ""}`}
                style={
                  selectedPositioning === p.value
                    ? { borderColor: p.color, color: p.color }
                    : {}
                }
                onClick={() => handlePositioningChange(p.value as PricePositioning)}
              >
                <div className="pos-label">{p.label}</div>
                <div className="pos-sub">{p.sub}</div>
              </button>
            ))}
          </div>

          {selectedCategories.length === 0 && (
            <div className="brand-hint" style={{ marginTop: 8 }}>
              ⚠️ Select at least one product category to proceed
            </div>
          )}
        </div>
      )}
    </div>
  );
}
