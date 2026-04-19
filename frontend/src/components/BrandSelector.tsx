import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Search, Store } from "lucide-react";
import { getKnownBrands, type RetailerProfile, type StoreSizeEnum, type PricePositioning } from "../lib/api";

interface Props {
  onSelect: (retailer: RetailerProfile, displayName: string) => void;
}

const SIZE_LABELS: Record<string, string> = {
  small: "Small (<5k sq ft)",
  medium: "Medium (5–25k sq ft)",
  large: "Large (25–80k sq ft)",
  big_box: "Big-Box (80k+ sq ft)",
};

const POS_LABELS: Record<string, string> = {
  budget: "Budget",
  mid_range: "Mid-Range",
  premium: "Premium",
};

const POPULAR_BRANDS = [
  "Walmart", "Target", "Costco", "Aldi", "Trader Joe's",
  "Whole Foods", "Home Depot", "TJ Maxx", "Dollar General", "Sprouts",
];

export function BrandSelector({ onSelect }: Props) {
  const [mode, setMode] = useState<"brand" | "custom">("brand");
  const [query, setQuery] = useState("");
  const [brands, setBrands] = useState<any[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [sizes, setSizes] = useState<string[]>([]);

  // Custom path
  const [customSize, setCustomSize] = useState<StoreSizeEnum>("large");
  const [customCats, setCustomCats] = useState<string[]>([]);
  const [customPos, setCustomPos] = useState<PricePositioning>("mid_range");

  useEffect(() => {
    getKnownBrands().then((d) => {
      setBrands(d.brands);
      setCategories(d.categories);
      setSizes(d.sizes);
    }).catch(() => {});
  }, []);

  const filtered = query.trim()
    ? brands.filter((b) => b.name.toLowerCase().includes(query.toLowerCase()))
    : brands.filter((b) => POPULAR_BRANDS.includes(b.name));

  function handleBrandPick(brand: any) {
    onSelect({ brand_name: brand.name }, brand.name);
  }

  function handleCustomSubmit() {
    if (customCats.length === 0) return;
    const displayName = `Custom ${SIZE_LABELS[customSize]?.split(" ")[0]} ${POS_LABELS[customPos]} Store`;
    onSelect({
      store_size: customSize,
      categories: customCats,
      price_positioning: customPos,
    }, displayName);
  }

  function toggleCat(cat: string) {
    setCustomCats((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-paper flex flex-col">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="hairline-b bg-snow"
      >
        <div className="px-6 lg:px-10 py-12 max-w-[1200px] mx-auto">
          <div className="label-xs mb-4">CHAPTER ONE — IDENTIFY</div>
          <h1 className="display-lg mb-3">
            Which <em className="italic">retailer</em> are you<br />siting today?
          </h1>
          <p className="text-sm text-graphite max-w-xl leading-relaxed">
            Select a known brand or define your own store spec.
            We'll align demographic, competitive, and hotspot data to its DNA.
          </p>
        </div>
      </motion.div>

      {/* Mode Toggle */}
      <div className="px-6 lg:px-10 py-8 max-w-[1200px] mx-auto w-full">
        <div className="flex items-center gap-0 hairline w-fit mb-8">
          <button
            onClick={() => setMode("brand")}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              mode === "brand" ? "bg-ink text-snow" : "bg-snow text-graphite hover:text-ink"
            }`}
          >
            Known Brand
          </button>
          <button
            onClick={() => setMode("custom")}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              mode === "custom" ? "bg-ink text-snow" : "bg-snow text-graphite hover:text-ink"
            }`}
          >
            Custom Store Spec
          </button>
        </div>

        {mode === "brand" && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {/* Search */}
            <div className="relative mb-6 max-w-lg">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-mist" strokeWidth={1.5} />
              <input
                type="text"
                placeholder="Search brand — Walmart, Aldi, Sprouts…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-snow border border-hairline text-sm text-ink
                           placeholder:text-mist outline-none focus:border-ink transition-colors"
              />
            </div>

            {!query && (
              <div className="label-xs mb-4 text-slate">POPULAR BRANDS</div>
            )}

            {/* Brand grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {filtered.map((brand) => (
                <button
                  key={brand.name}
                  onClick={() => handleBrandPick(brand)}
                  className="card p-5 text-left group hover:border-ink transition-colors"
                >
                  <div className="flex items-start justify-between mb-3">
                    <Store className="w-4 h-4 text-mist group-hover:text-ink transition-colors" strokeWidth={1.5} />
                    <ArrowRight className="w-3.5 h-3.5 text-mist group-hover:text-emerald opacity-0 group-hover:opacity-100 transition-all" strokeWidth={1.5} />
                  </div>
                  <div className="font-display text-lg leading-none mb-2">{brand.name}</div>
                  <div className="label-xs text-slate">
                    {brand.size?.replace("_", "-")} · {brand.positioning?.replace("_", "-")}
                  </div>
                  <div className="label-xs text-mist mt-1">{brand.category?.replace("_", " ")}</div>
                </button>
              ))}
            </div>

            {filtered.length === 0 && query && (
              <div className="py-12 text-center">
                <div className="font-display text-2xl mb-2 text-graphite italic">No match for "{query}"</div>
                <button
                  onClick={() => setMode("custom")}
                  className="label-xs text-emerald hover:underline"
                >
                  Switch to custom store spec →
                </button>
              </div>
            )}
          </motion.div>
        )}

        {mode === "custom" && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="max-w-2xl"
          >
            {/* Store Size */}
            <div className="mb-8">
              <div className="label-xs mb-4">STORE SIZE</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {(sizes.length ? sizes : ["small", "medium", "large", "big_box"]).map((s) => (
                  <button
                    key={s}
                    onClick={() => setCustomSize(s as StoreSizeEnum)}
                    className={`p-4 text-left hairline transition-colors ${
                      customSize === s ? "bg-ink text-snow border-ink" : "bg-snow hover:border-ink"
                    }`}
                  >
                    <div className="text-sm font-medium">{s.replace("_", "-")}</div>
                    <div className="label-xs mt-1 opacity-70">{SIZE_LABELS[s]?.split("(")[1]?.replace(")", "")}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Price Positioning */}
            <div className="mb-8">
              <div className="label-xs mb-4">PRICE POSITIONING</div>
              <div className="flex gap-2">
                {(["budget", "mid_range", "premium"] as PricePositioning[]).map((p) => (
                  <button
                    key={p}
                    onClick={() => setCustomPos(p)}
                    className={`px-6 py-3 text-sm font-medium hairline transition-colors ${
                      customPos === p ? "bg-ink text-snow border-ink" : "bg-snow hover:border-ink"
                    }`}
                  >
                    {POS_LABELS[p]}
                  </button>
                ))}
              </div>
            </div>

            {/* Categories */}
            <div className="mb-8">
              <div className="label-xs mb-4">PRODUCT CATEGORIES <span className="text-mist">(select at least one)</span></div>
              <div className="flex flex-wrap gap-2">
                {(categories.length ? categories : [
                  "grocery", "general_merchandise", "apparel", "electronics",
                  "hardware", "pharmacy", "specialty", "home_goods", "sporting_goods",
                ]).map((cat) => (
                  <button
                    key={cat}
                    onClick={() => toggleCat(cat)}
                    className={`px-4 py-2 text-xs font-mono uppercase tracking-wider hairline transition-colors ${
                      customCats.includes(cat)
                        ? "bg-emerald text-snow border-emerald"
                        : "bg-snow hover:border-ink text-graphite"
                    }`}
                  >
                    {cat.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={handleCustomSubmit}
              disabled={customCats.length === 0}
              className="btn-primary"
            >
              <span>Continue to Map</span>
              <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </motion.div>
        )}
      </div>
    </div>
  );
}
