import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export type StoreFormat =
  | "Target"
  | "Walmart"
  | "Costco"
  | "Home Depot"
  | "Best Buy"
  | "Walgreens"
  | "CVS"
  | "Whole Foods"
  | "Trader Joe's"
  | "Aldi"
  | "Starbucks"
  | "Local Grocery"
  | "Convenience Store"
  | "Coffee Shop";

interface FormatOption {
  key: StoreFormat;
  label: string;
  blurb: string;
  tier:
    | "BIG BOX"
    | "WAREHOUSE"
    | "HOME IMPROVEMENT"
    | "ELECTRONICS"
    | "GROCERY"
    | "PHARMACY"
    | "INDEPENDENT"
    | "QUICK STOP"
    | "F&B";
}

// 14 store formats — keep in sync with backend STORE_FORMATS in metrics.py
const FORMATS: FormatOption[] = [
  { key: "Best Buy",          label: "Best Buy",          blurb: "Consumer electronics",              tier: "ELECTRONICS" },
  { key: "Target",            label: "Target",            blurb: "Big-box general merchandise",       tier: "BIG BOX" },
  { key: "Walmart",           label: "Walmart",           blurb: "Supercenter · GM + grocery",        tier: "BIG BOX" },
  { key: "Costco",            label: "Costco",            blurb: "Members-only bulk warehouse",       tier: "WAREHOUSE" },
  { key: "Home Depot",        label: "Home Depot",        blurb: "DIY / home improvement",            tier: "HOME IMPROVEMENT" },
  { key: "Whole Foods",       label: "Whole Foods",       blurb: "Premium grocery, $85K+ income",     tier: "GROCERY" },
  { key: "Trader Joe's",      label: "Trader Joe's",      blurb: "Mid-size specialty grocery",        tier: "GROCERY" },
  { key: "Aldi",              label: "Aldi",              blurb: "Discount grocery, value shoppers",  tier: "GROCERY" },
  { key: "Walgreens",         label: "Walgreens",         blurb: "Pharmacy + convenience",            tier: "PHARMACY" },
  { key: "CVS",               label: "CVS",               blurb: "Pharmacy + health services",        tier: "PHARMACY" },
  { key: "Starbucks",         label: "Starbucks",         blurb: "Premium coffee chain",              tier: "F&B" },
  { key: "Coffee Shop",       label: "Coffee Shop",       blurb: "Cafe / espresso bar",               tier: "F&B" },
  { key: "Local Grocery",     label: "Local Grocery",     blurb: "Independent neighborhood market",   tier: "INDEPENDENT" },
  { key: "Convenience Store", label: "Convenience Store", blurb: "Corner store / gas station",        tier: "QUICK STOP" },
];

interface Props {
  value: StoreFormat;
  onChange: (v: StoreFormat) => void;
}

export function StoreFormatPicker({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const selected = FORMATS.find((f) => f.key === value) ?? FORMATS[0];

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-snow border border-hairline
                   hover:border-ink transition group"
      >
        <div className="text-left">
          <div className="label-xs mb-1">{selected.tier}</div>
          <div className="text-sm font-medium text-ink">{selected.label}</div>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-graphite transition-transform ${open ? "rotate-180" : ""}`}
          strokeWidth={1.5}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute z-[1100] mt-1 w-full bg-snow border border-hairline
                       shadow-[0_24px_60px_-30px_rgba(0,0,0,0.25)]
                       max-h-[min(640px,calc(100vh-14rem))] overflow-y-auto"
          >
            {FORMATS.map((f) => {
              const active = f.key === value;
              return (
                <button
                  key={f.key}
                  onClick={() => { onChange(f.key); setOpen(false); }}
                  className={`w-full text-left px-4 py-3.5 hairline-b last:border-b-0
                              hover:bg-bone transition flex items-start justify-between gap-3
                              ${active ? "bg-bone" : ""}`}
                >
                  <div className="flex-1">
                    <div className="label-xs mb-1">{f.tier}</div>
                    <div className="text-sm font-medium text-ink leading-tight">{f.label}</div>
                    <div className="text-xs text-graphite mt-0.5">{f.blurb}</div>
                  </div>
                  {active && (
                    <Check className="w-4 h-4 text-emerald shrink-0 mt-1" strokeWidth={1.5} />
                  )}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
