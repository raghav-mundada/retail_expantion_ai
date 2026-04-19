// Top-left brand mark — used across all phases
export function Brand({ inverted = false }: { inverted?: boolean }) {
  const text = inverted ? "text-snow" : "text-ink";
  const slate = inverted ? "text-mist" : "text-slate";
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-7 w-7">
        {/* Compass / atlas mark — 4 quadrants */}
        <svg viewBox="0 0 28 28" className={text}>
          <rect x="0.5" y="0.5" width="27" height="27" fill="none" stroke="currentColor" strokeWidth="1" />
          <line x1="14" y1="0" x2="14" y2="28" stroke="currentColor" strokeWidth="0.8" />
          <line x1="0" y1="14" x2="28" y2="14" stroke="currentColor" strokeWidth="0.8" />
          <circle cx="14" cy="14" r="3" fill="#047857" />
        </svg>
      </div>
      <div className="flex items-baseline gap-2">
        <span className={`font-display text-2xl tracking-tightest leading-none ${text}`}>
          Atlas
        </span>
        <span className={`label-xs ${slate} hidden sm:inline`}>
          Retail Site Intelligence
        </span>
      </div>
    </div>
  );
}
