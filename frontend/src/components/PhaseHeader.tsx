import { Brand } from "./Brand";

const PHASES = [
  { id: 1, label: "Locate" },
  { id: 2, label: "Ingest" },
  { id: 3, label: "Inspect" },
  { id: 4, label: "Decide" },
];

export function PhaseHeader({ current, onReset }: { current: number; onReset?: () => void }) {
  return (
    <header className="hairline-b bg-paper/90 backdrop-blur-md sticky top-0 z-[1100]">
      <div className="px-6 lg:px-10 h-16 flex items-center justify-between">
        <button onClick={onReset} className="cursor-pointer">
          <Brand />
        </button>

        <nav className="hidden md:flex items-center gap-1">
          {PHASES.map((p, i) => {
            const active = current === p.id;
            const done   = current > p.id;
            return (
              <div key={p.id} className="flex items-center">
                <div className={`flex items-center gap-2 px-3 py-1 ${active ? "text-ink" : done ? "text-graphite" : "text-mist"}`}>
                  <span className={`font-mono text-[10px] tabular ${active ? "text-emerald" : ""}`}>
                    {String(p.id).padStart(2, "0")}
                  </span>
                  <span className="text-xs tracking-snug font-medium">{p.label}</span>
                </div>
                {i < PHASES.length - 1 && (
                  <span className="text-mist text-xs">·</span>
                )}
              </div>
            );
          })}
        </nav>

        <div className="flex items-center gap-4">
          <span className="label-xs hidden lg:inline">MINNEAPOLIS · MN</span>
          <span className="h-2 w-2 rounded-full bg-emerald animate-pulse" />
        </div>
      </div>
    </header>
  );
}
