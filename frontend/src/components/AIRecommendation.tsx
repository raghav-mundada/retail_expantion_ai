import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, TrendingUp, TrendingDown, Gavel, Loader, Calculator, BookOpen } from "lucide-react";

import { startDebate, type DebateResponse, type ScoreContribution, type FormulaDoc } from "../lib/api";
import { fmtUSD } from "../lib/format";

interface Props {
  runId: string;
  storeFormat: string;
  onClose: () => void;
}

const AGENT_STAGES = [
  { id: "bull",   label: "Bull Agent",   caption: "Building the case to OPEN…" },
  { id: "bear",   label: "Bear Agent",   caption: "Building the case AGAINST…" },
  { id: "orch",   label: "Orchestrator", caption: "Synthesizing verdict…" },
];

export function AIRecommendation({ runId, storeFormat, onClose }: Props) {
  const [stage, setStage]     = useState<"loading" | "done">("loading");
  const [agentIx, setAgentIx] = useState(0);
  const [result, setResult]   = useState<DebateResponse | null>(null);
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;   // guard against React StrictMode double-fire
    fired.current = true;

    startDebate(runId, storeFormat)
      .then((r) => {
        setResult(r);
        setStage("done");
      })
      .catch((e) => {
        console.error(e);
        alert("Debate failed: " + e.message);
        onClose();
      });

    const t1 = setTimeout(() => setAgentIx(1), 4000);
    const t2 = setTimeout(() => setAgentIx(2), 9000);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [runId, storeFormat, onClose]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-paper overflow-y-auto"
    >
      {/* Top bar */}
      <div className="hairline-b sticky top-0 bg-paper/95 backdrop-blur z-10">
        <div className="px-6 lg:px-10 h-16 flex items-center justify-between max-w-[1500px] mx-auto">
          <div className="flex items-center gap-4">
            <span className="label-xs">CHAPTER FOUR — DECIDE</span>
            <span className="text-mist">·</span>
            <span className="label-xs text-emerald">AGENTIC ANALYSIS</span>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-bone transition">
            <X className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>
      </div>

      <div className="px-6 lg:px-10 py-12 max-w-[1500px] mx-auto">
        <AnimatePresence mode="wait">
          {stage === "loading" ? (
            <LoadingState key="load" agentIx={agentIx} />
          ) : (
            <ResultsState key="result" result={result!} />
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// LOADING STATE — agents thinking
// ─────────────────────────────────────────────────────────────────────────────
function LoadingState({ agentIx }: { agentIx: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="max-w-3xl mx-auto py-16"
    >
      <h1 className="display-lg mb-4">
        Three agents <em className="italic">deliberating</em>.
      </h1>
      <p className="text-graphite text-lg leading-relaxed mb-12 max-w-xl">
        We're running a structured debate. Bull argues for. Bear argues against.
        The Orchestrator weighs both against the metrics and renders the verdict.
      </p>

      <div className="space-y-0">
        {AGENT_STAGES.map((a, i) => {
          const status = i < agentIx ? "done" : i === agentIx ? "thinking" : "queued";
          return (
            <div key={a.id} className="hairline-b py-6 grid grid-cols-12 gap-4 items-center">
              <div className="col-span-1 font-mono text-[10px] tabular text-mist">
                {String(i + 1).padStart(2, "0")}
              </div>
              <div className="col-span-3 font-display text-2xl">{a.label}</div>
              <div className="col-span-7 italic text-graphite">{a.caption}</div>
              <div className="col-span-1 flex justify-end">
                {status === "done" && <div className="w-3 h-3 bg-emerald rounded-full" />}
                {status === "thinking" && <Loader className="w-4 h-4 animate-spin text-ink" strokeWidth={1.5} />}
                {status === "queued" && <div className="w-3 h-3 border border-hairline rounded-full" />}
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// RESULTS STATE — verdict + Bull/Bear cards + factors
// ─────────────────────────────────────────────────────────────────────────────
function ResultsState({ result }: { result: DebateResponse }) {
  const v       = result.verdict;
  const m       = result.metrics;
  const score   = v.score ?? result.composite_score;
  const verdict = v.recommendation || "—";

  // Color the score: ≥70 emerald, 40–70 amber, <40 crimson
  const accent =
    score >= 70 ? "#047857" :
    score >= 40 ? "#B45309" :
                  "#B91C1C";
  const verdictTone =
    score >= 70 ? "text-emerald" :
    score >= 40 ? "text-amber" :
                  "text-crimson";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-10"
    >
      {/* ═══ VERDICT HERO ═══ */}
      <div className="grid grid-cols-12 gap-8 items-end pb-8 hairline-b">
        <div className="col-span-12 lg:col-span-7">
          <div className="label-xs mb-4">FINAL VERDICT — {result.store_format.toUpperCase()}</div>
          <h1 className={`display-xl ${verdictTone} mb-4 leading-[0.85]`}>
            {verdict}
          </h1>
          <div className="text-lg font-display italic text-graphite max-w-2xl leading-tight">
            {v.summary}
          </div>
        </div>

        <div className="col-span-12 lg:col-span-5">
          <ScoreGauge score={score} accent={accent} />
        </div>
      </div>

      {/* ═══ KEY METRICS STRIP ═══ */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-0 hairline">
        <Stat
          label="MARKET CAPTURE"
          value={`${m.huff?.capture_rate_pct?.toFixed(1) || "—"}%`}
          sub={`${m.huff?.captured_households?.toLocaleString() || "—"} households`}
        />
        <Stat
          label="ANNUAL REVENUE"
          value={fmtUSD(m.sales?.annual_revenue_usd || 0)}
          sub={`${m.sales?.annual_revenue_m || 0}M projected`}
          border
        />
        <Stat
          label="ROI"
          value={`${m.roi?.roi_pct?.toFixed(1) || "—"}%`}
          sub={`Payback ${m.roi?.payback_years || "—"} yrs`}
          border
        />
        <Stat
          label="CONFIDENCE"
          value={v.confidence || "—"}
          sub={`${v.deciding_factors?.length || 0} factors weighed`}
          border
        />
      </div>

      {/* ═══ COMPOSITE SCORE BREAKDOWN ═══ */}
      <div>
        <SectionHead
          eyebrow="SCORE COMPOSITION"
          title="How we got to the number"
          caption="Each of the five dimensions contributes a weighted slice of the final 100-point score."
        />
        <ScoreBreakdownChart breakdown={result.score_breakdown} total={result.composite_score} />
      </div>

      {/* ═══ DECIDING FACTORS ═══ */}
      <div>
        <SectionHead
          eyebrow="EXPLAINABILITY"
          title="What moved the needle"
          caption="Each factor cited by the Orchestrator with its evidence."
        />
        <div className="mt-6 hairline">
          {v.deciding_factors?.map((f, i) => (
            <FactorRow key={i} factor={f} />
          ))}
        </div>
      </div>

      {/* ═══ METHODOLOGY ═══ */}
      <div>
        <SectionHead
          eyebrow="METHODOLOGY"
          title="The math behind the verdict"
          caption="Every formula, every constant. No black boxes."
        />
        <MethodologyGrid formulas={result.formulas} />
      </div>

      {/* ═══ BULL vs BEAR ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-0 hairline">
        <ArgumentCard
          title="Bull Case"
          icon={<TrendingUp className="w-4 h-4" strokeWidth={1.5} />}
          tone="emerald"
          content={result.bull}
          strengths={v.key_strengths}
        />
        <ArgumentCard
          title="Bear Case"
          icon={<TrendingDown className="w-4 h-4" strokeWidth={1.5} />}
          tone="crimson"
          content={result.bear}
          risks={v.key_risks}
          border
        />
      </div>

      {/* ═══ ORCHESTRATOR FOOTER ═══ */}
      <div className="hairline p-8 bg-snow flex items-start gap-6">
        <Gavel className="w-6 h-6 text-ink flex-shrink-0 mt-1" strokeWidth={1.5} />
        <div className="flex-1">
          <div className="label-xs mb-2">ORCHESTRATOR · FINAL READOUT</div>
          <div className="font-display text-2xl mb-3 leading-snug">{v.summary}</div>
          <div className="flex items-center gap-6 text-xs text-graphite">
            <span>Session <span className="font-mono">{result.session_id.slice(0, 8)}</span></span>
            <span>·</span>
            <span>Composite <span className="font-mono tabular">{result.composite_score}</span>/100</span>
            <span>·</span>
            <span>Confidence <span className="font-mono">{v.confidence}</span></span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────
function ScoreGauge({ score, accent }: { score: number; accent: string }) {
  const radius = 90;
  const circ   = 2 * Math.PI * radius;
  const offset = circ - (score / 100) * circ;

  return (
    <div className="flex items-center justify-center lg:justify-end gap-6">
      <div className="relative w-56 h-56">
        <svg viewBox="0 0 200 200" className="w-full h-full -rotate-90">
          <circle cx="100" cy="100" r={radius} stroke="#E4E4E7" strokeWidth="6" fill="none" />
          <motion.circle
            cx="100" cy="100" r={radius}
            stroke={accent} strokeWidth="6" fill="none"
            strokeLinecap="butt"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="label-xs mb-1">FEASIBILITY</div>
          <div className="font-display text-7xl tabular leading-none" style={{ color: accent }}>
            {score}
          </div>
          <div className="font-mono text-xs text-mist mt-1">/ 100</div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, border }: any) {
  return (
    <div className={`p-6 bg-snow ${border ? "border-l border-hairline" : ""}`}>
      <div className="label-xs mb-3">{label}</div>
      <div className="font-display text-3xl tabular leading-none mb-2">{value}</div>
      <div className="text-xs text-slate">{sub}</div>
    </div>
  );
}

function SectionHead({ eyebrow, title, caption }: any) {
  return (
    <div>
      <div className="label-xs mb-2">{eyebrow}</div>
      <h3 className="font-display text-3xl tracking-tightest leading-none mb-2">{title}</h3>
      {caption && <div className="text-sm text-slate">{caption}</div>}
    </div>
  );
}

function FactorRow({ factor }: { factor: any }) {
  const positive = factor.direction === "positive";
  return (
    <div className="grid grid-cols-12 gap-4 items-center px-6 py-5 hairline-b last:border-b-0 bg-snow">
      <div className="col-span-1 flex justify-center">
        {positive
          ? <TrendingUp className="w-4 h-4 text-emerald" strokeWidth={1.5} />
          : <TrendingDown className="w-4 h-4 text-crimson" strokeWidth={1.5} />
        }
      </div>
      <div className="col-span-4 font-display text-lg leading-tight">{factor.factor}</div>
      <div className="col-span-5 text-sm text-graphite">
        {positive ? "Strengthens the case." : "Weakens the case."} Evidence: <span className="font-mono text-ink">{factor.evidence}</span>
      </div>
      <div className="col-span-2 text-right">
        <span className={`label-sm ${positive ? "text-emerald" : "text-crimson"}`}>
          {positive ? "+ POSITIVE" : "− NEGATIVE"}
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SCORE BREAKDOWN — animated stacked bar showing how each dimension contributes
// ─────────────────────────────────────────────────────────────────────────────
function ScoreBreakdownChart({ breakdown, total }: { breakdown: ScoreContribution[]; total: number }) {
  const colors: Record<string, string> = {
    "Demand"      : "#0F766E",
    "Competition" : "#7C2D12",
    "Huff Capture": "#1E40AF",
    "Traffic"     : "#B45309",
    "Income Fit"  : "#86198F",
  };

  return (
    <div className="mt-6 space-y-6">
      {/* Stacked bar — full 100-pt scale */}
      <div className="card p-6">
        <div className="flex items-baseline justify-between mb-4">
          <span className="label-xs">FINAL SCORE — STACKED CONTRIBUTION</span>
          <div className="flex items-baseline gap-1.5">
            <span className="font-display text-4xl tabular leading-none text-ink">{total}</span>
            <span className="label-sm text-mist">/ 100</span>
          </div>
        </div>

        {/* The bar */}
        <div className="relative h-12 bg-bone hairline mb-3 overflow-hidden">
          {(() => {
            let acc = 0;
            return breakdown.map((c, i) => {
              const startPct = acc;
              acc += c.contribution;
              return (
                <motion.div
                  key={c.dimension}
                  initial={{ width: 0, x: `${startPct}%` }}
                  animate={{ width: `${c.contribution}%`, x: `${startPct}%` }}
                  transition={{ duration: 0.9, delay: 0.2 + i * 0.12, ease: [0.16, 1, 0.3, 1] }}
                  className="absolute top-0 h-full flex items-center justify-center text-snow text-xs font-mono tabular"
                  style={{ background: colors[c.dimension] || "#0A0A0A", left: 0 }}
                  title={`${c.dimension}: ${c.contribution} pts`}
                >
                  {c.contribution >= 4 && <span>+{c.contribution}</span>}
                </motion.div>
              );
            });
          })()}
        </div>

        {/* Scale ticks */}
        <div className="flex justify-between label-xs">
          <span>0</span><span>25</span><span>50</span><span>75</span><span>100</span>
        </div>
      </div>

      {/* Per-dimension rows */}
      <div className="hairline">
        {breakdown.map((c, i) => (
          <motion.div
            key={c.dimension}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6 + i * 0.08, duration: 0.4 }}
            className="grid grid-cols-12 gap-4 items-center px-6 py-5 hairline-b last:border-b-0 bg-snow"
          >
            <div className="col-span-1 flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full"
                style={{ background: colors[c.dimension] || "#0A0A0A" }}
              />
            </div>
            <div className="col-span-3 font-display text-lg leading-none">
              {c.dimension}
            </div>
            <div className="col-span-1 text-right">
              <div className="label-xs">RAW</div>
              <div className="font-mono text-sm tabular">{c.raw_score.toFixed(0)}/100</div>
            </div>
            <div className="col-span-1 text-right">
              <div className="label-xs">WEIGHT</div>
              <div className="font-mono text-sm tabular">{(c.weight * 100).toFixed(0)}%</div>
            </div>
            <div className="col-span-2 text-right">
              <div className="label-xs">ADDS</div>
              <div className="font-display text-2xl tabular leading-none">+{c.contribution.toFixed(1)}</div>
            </div>
            <div className="col-span-4 text-xs text-graphite italic font-display text-base leading-tight">
              {c.rationale}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Formula reminder */}
      <div className="bg-bone hairline p-5 flex items-start gap-3">
        <Calculator className="w-4 h-4 mt-0.5 text-graphite flex-shrink-0" strokeWidth={1.5} />
        <div className="font-mono text-xs text-graphite leading-relaxed">
          Score = 0.30·Demand + 0.25·Competition + 0.20·Huff + 0.15·Traffic + 0.10·IncomeFit
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// METHODOLOGY GRID — shows every formula used in the system
// ─────────────────────────────────────────────────────────────────────────────
function MethodologyGrid({ formulas }: { formulas: FormulaDoc[] }) {
  return (
    <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-0 hairline">
      {formulas.map((f, i) => (
        <motion.div
          key={f.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05, duration: 0.4 }}
          className={`p-6 bg-snow ${i % 2 === 1 ? "md:border-l border-hairline" : ""} ${i >= 2 ? "border-t border-hairline" : ""}`}
        >
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-3.5 h-3.5 text-graphite" strokeWidth={1.5} />
            <span className="label-xs">{String(i + 1).padStart(2, "0")} · {f.name.toUpperCase()}</span>
          </div>
          <div className="font-mono text-xs bg-bone p-3 mb-3 leading-relaxed text-ink whitespace-pre-line">
            {f.formula}
          </div>
          <div className="text-xs text-graphite leading-relaxed italic font-display text-base">
            {f.purpose}
          </div>
        </motion.div>
      ))}
    </div>
  );
}


function ArgumentCard({ title, icon, tone, content, strengths, risks, border }: any) {
  const toneColor = tone === "emerald" ? "text-emerald" : "text-crimson";
  return (
    <div className={`p-8 bg-snow ${border ? "border-l border-hairline" : ""}`}>
      <div className={`flex items-center gap-2 mb-4 ${toneColor}`}>
        {icon}
        <span className="label-sm">{title.toUpperCase()}</span>
      </div>
      <div className="prose prose-sm max-w-none text-graphite leading-relaxed font-sans whitespace-pre-line">
        {content}
      </div>

      {(strengths || risks) && (
        <div className="mt-6 hairline-t pt-4">
          <div className="label-xs mb-3">{strengths ? "KEY STRENGTHS" : "KEY RISKS"}</div>
          <div className="flex flex-wrap gap-2">
            {(strengths || risks)?.map((item: string, i: number) => (
              <span
                key={i}
                className={`text-xs px-3 py-1 border ${tone === "emerald" ? "border-emerald text-emerald" : "border-crimson text-crimson"}`}
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
